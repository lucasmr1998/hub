import time
import os
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
import datetime
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import logging
import psycopg2
from psycopg2.extras import Json
import tempfile
import shutil
import json

from credenciais import carregar_config, hubtrix_db_config, ConfigTenant

# Configurar logging apenas para erros
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carrega .env (USUARIO/SENHA legados Megalink, NAVEGADOR, etc) + .env.hubtrix
# (credenciais do DB Hubtrix + SECRET_KEY pra decryptar IntegracaoAPI).
load_dotenv()
load_dotenv('.env.hubtrix', override=False)

# DB_CONFIG agora aponta pro Hubtrix (aurora). Multi-tenant: o tenant_id do
# prospecto e injetado em runtime pela ConfigTenant carregada via --tenant.
# A tabela de destino e `prospectos` no proprio DB Hubtrix (schema identico
# ao DB legado robo_venda_automatica, ja existente com tenant_id+lead_id).
DB_CONFIG = hubtrix_db_config()

# Replicacao secundaria desligada — tudo grava no Hubtrix.
DB_CONFIG_DJANGO = None

# Slot global preenchido por main() a partir do --tenant. Acessivel ao
# salvar_prospecto pra incluir tenant_id no INSERT/UPDATE.
TENANT_CONFIG: ConfigTenant | None = None

class ProspectoProcessor:
    def __init__(self):
        # Conexões separadas para permitir replicação sem quebrar o fluxo atual
        self.conn_primary = None
        self.conn_secondary = None
        # Backward-compat: manter atributo "conn" apontando para o primário
        self.conn = None
        self.screenshots_dir = "screenshots"
        self.start_time = None
        self.current_prospecto_id = None
        self.tentativa_atual = None  # Controla a tentativa atual da execução
        self.primeira_chamada = True  # Flag para identificar primeira chamada da execução
        
        # Criar pasta para screenshots apenas para erros
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
    
    def conectar_banco(self):
        """Conecta ao DB Hubtrix. Replicacao no secundario foi desativada
        (todo o estado vive na tabela `prospectos` do proprio Hubtrix)."""
        try:
            self.conn_primary = psycopg2.connect(**DB_CONFIG)
            self.conn_secondary = None
            if DB_CONFIG_DJANGO:
                try:
                    self.conn_secondary = psycopg2.connect(**DB_CONFIG_DJANGO)
                except Exception as e_sec:
                    logger.error(f"Falha ao conectar no banco secundario: {e_sec}")
                    self.conn_secondary = None
            self.conn = self.conn_primary
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco Hubtrix: {e}")
            return False
    
    def desconectar_banco(self):
        """Desconecta dos bancos de dados."""
        try:
            if self.conn_primary:
                self.conn_primary.close()
        finally:
            self.conn_primary = None
            self.conn = None
        if self.conn_secondary:
            try:
                self.conn_secondary.close()
            finally:
                self.conn_secondary = None
    
    def salvar_prospecto(self, nome_prospecto, id_prospecto_hubsoft, status_atual, erro=None, resultado=None):
        """Salva ou atualiza dados do prospecto no banco primário e replica para o secundário."""
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor()
            tempo_processamento = int(time.time() - self.start_time) if self.start_time else 0
            
            # Mapear status interno para os valores permitidos pela tabela
            status_mapping = {
                "INICIANDO": "processando",
                "LOGIN_REALIZADO": "processando", 
                "NAVEGACAO_PROSPECTOS": "processando",
                "PROSPECTO_LOCALIZADO": "processando",
                "MENU_ACOES_ABERTO": "processando",
                "WIZARD_INICIADO": "processando",
                "WIZARD_TELA1": "processando",
                "WIZARD_SELECOES": "processando", 
                "WIZARD_TELA2": "processando",
                "CONCLUIDO": "finalizado",
                "ERRO_LOGIN": "erro",
                "ERRO_NAVEGACAO": "erro",
                "ERRO_LOCALIZACAO": "erro",
                "ERRO_ACOES": "erro",
                "ERRO_CONVERTER": "erro",
                "ERRO_WIZARD1": "erro",
                "ERRO_WIZARD_SELECOES": "erro",
                "ERRO_WIZARD2": "erro",
                "ERRO_FINALIZACAO": "erro",
                "ERRO_GERAL": "erro"
            }
            
            status_db = status_mapping.get(status_atual, "erro")
            # Para o banco Django, 'finalizado' deve virar 'aguardando_validacao'
            status_django = "aguardando_validacao" if status_db == "finalizado" else status_db
            
            # VERIFICAÇÃO CRÍTICA: Só permite "finalizado" se for realmente CONCLUIDO com sucesso
            if status_db == "finalizado" and resultado != "sucesso":
                print(f"⚠️ ATENÇÃO: Status '{status_atual}' mapeado para 'finalizado' mas resultado não é 'sucesso'")
                status_db = "erro"
                erro = f"Processo não finalizado corretamente. Status original: {status_atual}"
                resultado = "falha"
            
            # Multi-tenant: prospectos.id_prospecto_hubsoft NAO eh unico globalmente
            # (Megalink id 22651 e Nuvyon id 22651 sao prospects diferentes em
            # sistemas diferentes). Tem que filtrar por tenant_id.
            tenant_id = TENANT_CONFIG.tenant_id if TENANT_CONFIG else None
            if tenant_id:
                cursor.execute(
                    "SELECT id, tentativas_processamento FROM prospectos "
                    "WHERE id_prospecto_hubsoft = %s AND tenant_id = %s",
                    (id_prospecto_hubsoft, tenant_id),
                )
            else:
                cursor.execute(
                    "SELECT id, tentativas_processamento FROM prospectos "
                    "WHERE id_prospecto_hubsoft = %s",
                    (id_prospecto_hubsoft,),
                )
            resultado_busca = cursor.fetchone()
            
            if resultado_busca:
                # Atualizar registro existente
                id_existente, tentativas_atuais = resultado_busca
                self.current_prospecto_id = id_existente
                
                # CORREÇÃO: Incrementar tentativas apenas na primeira chamada da execução
                if self.primeira_chamada:
                    self.tentativa_atual = tentativas_atuais + 1
                    self.primeira_chamada = False
                    print(f"🔄 Nova execução iniciada - Tentativa {self.tentativa_atual}")
                else:
                    # Manter a mesma tentativa para atualizações de status da mesma execução
                    self.tentativa_atual = tentativas_atuais if self.tentativa_atual is None else self.tentativa_atual
                
                # VERIFICAÇÃO: Se atingiu 3 tentativas e está com erro, marcar como erro final
                if self.tentativa_atual >= 3 and status_db == "erro":
                    print(f"❌ Prospecto {nome_prospecto} atingiu o máximo de 3 tentativas - marcando como erro final")
                    erro = f"Máximo de 3 tentativas atingido. Última falha: {erro}" if erro else "Máximo de 3 tentativas atingido"
                    status_db = "erro"  # Força status como erro
                    resultado = "falha"  # Força resultado como falha
                
                cursor.execute("""
                    UPDATE prospectos SET
                        nome_prospecto = %s,
                        status = %s,
                        data_atualizacao = %s,
                        data_processamento = %s,
                        tentativas_processamento = %s,
                        erro_processamento = %s,
                        tempo_processamento = %s,
                        resultado_processamento = %s
                    WHERE id = %s
                """, (
                    nome_prospecto, status_db, datetime.datetime.now(), datetime.datetime.now(),
                    self.tentativa_atual, erro, tempo_processamento, resultado, id_existente
                ))
                
                print(f"🔄 Atualizando prospecto ID {id_existente}: {status_atual} -> {status_db} (Tentativa {self.tentativa_atual})")
            else:
                # Criar novo registro
                self.tentativa_atual = 1
                self.primeira_chamada = False
                
                # Resolve lead_id via leads_prospectos.id_hubsoft (snapshot
                # do prospect criado pela API antes da conversao via Selenium).
                lead_id_resolvido = None
                if tenant_id:
                    cursor.execute(
                        "SELECT id FROM leads_prospectos "
                        "WHERE id_hubsoft = %s AND tenant_id = %s LIMIT 1",
                        (id_prospecto_hubsoft, tenant_id),
                    )
                    r_lead = cursor.fetchone()
                    if r_lead:
                        lead_id_resolvido = r_lead[0]

                cursor.execute("""
                    INSERT INTO prospectos (
                        nome_prospecto, id_prospecto_hubsoft, status,
                        data_criacao, data_atualizacao, data_processamento,
                        tentativas_processamento, erro_processamento,
                        tempo_processamento, resultado_processamento,
                        tenant_id, lead_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    nome_prospecto, id_prospecto_hubsoft, status_db,
                    datetime.datetime.now(), datetime.datetime.now(), datetime.datetime.now(),
                    self.tentativa_atual, erro, tempo_processamento, resultado,
                    tenant_id, lead_id_resolvido,
                ))
                self.current_prospecto_id = cursor.fetchone()[0]
                
                print(f"✨ Criando novo prospecto ID {self.current_prospecto_id}: {status_atual} -> {status_db} (Tentativa {self.tentativa_atual})")
            
            self.conn.commit()
            cursor.close()

            # Replicar alterações no banco secundário (Django)
            try:
                if self.conn_secondary:
                    sec_cursor = self.conn_secondary.cursor()
                    # Converter resultado para JSONB quando aplicável
                    resultado_jsonb = Json(resultado) if resultado is not None else None

                    # Verificar existência no secundário
                    sec_cursor.execute(
                        "SELECT id FROM prospectos WHERE id_prospecto_hubsoft = %s",
                        (id_prospecto_hubsoft,)
                    )
                    sec_row = sec_cursor.fetchone()

                    if sec_row:
                        sec_id = sec_row[0]
                        sec_cursor.execute(
                            """
                            UPDATE prospectos SET
                                nome_prospecto = %s,
                                status = %s,
                                data_processamento = %s,
                                tentativas_processamento = %s,
                                erro_processamento = %s,
                                tempo_processamento = %s,
                                resultado_processamento = %s
                            WHERE id = %s
                            """,
                            (
                                nome_prospecto,
                                status_django,
                                datetime.datetime.now(),
                                self.tentativa_atual,
                                erro,
                                tempo_processamento,
                                resultado_jsonb,
                                sec_id,
                            ),
                        )
                    else:
                        # Inserir preenchendo campos obrigatórios do modelo Django
                        sec_cursor.execute(
                            """
                            INSERT INTO prospectos (
                                nome_prospecto,
                                id_prospecto_hubsoft,
                                status,
                                data_criacao,
                                data_processamento,
                                tentativas_processamento,
                                tempo_processamento,
                                erro_processamento,
                                prioridade,
                                dados_processamento,
                                resultado_processamento,
                                lead_id,
                                data_fim_processamento,
                                data_inicio_processamento,
                                score_conversao,
                                usuario_processamento
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            """,
                            (
                                nome_prospecto,
                                id_prospecto_hubsoft,
                                status_django,
                                datetime.datetime.now(),
                                datetime.datetime.now(),
                                self.tentativa_atual,
                                tempo_processamento,
                                erro,
                                1,  # prioridade default
                                None,  # dados_processamento
                                resultado_jsonb,
                                None,  # lead_id
                                None,  # data_fim_processamento
                                None,  # data_inicio_processamento
                                None,  # score_conversao
                                None,  # usuario_processamento
                            ),
                        )

                    self.conn_secondary.commit()
                    sec_cursor.close()
            except Exception as e_sec:
                # Não interromper processamento caso o secundário falhe
                logger.error(f"Falha ao replicar no banco secundário: {e_sec}")
                try:
                    if self.conn_secondary:
                        self.conn_secondary.rollback()
                except Exception:
                    pass

            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar prospecto: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def capturar_screenshot_erro(self, driver, nome, etapa):
        """Captura screenshot apenas em caso de erro"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.screenshots_dir}/ERRO_{timestamp}_{etapa}_{nome}.png"
            driver.save_screenshot(filename)
            logger.error(f"Screenshot de erro salvo: {filename}")
            print(f"📸 Screenshot de erro salvo: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return None

def print_etapa_header(numero, titulo, descricao=""):
    """Imprime cabeçalho formatado de uma etapa"""
    print("\n" + "="*80)
    print(f"🔹 ETAPA {numero}: {titulo}")
    if descricao:
        print(f"   {descricao}")
    print("="*80)

def print_elemento_buscado(tipo_elemento, localizador, metodo, acao):
    """Imprime informações sobre o elemento sendo buscado"""
    print(f"   🔍 Elemento: {tipo_elemento}")
    print(f"   📍 Localizador: {localizador}")
    print(f"   🔧 Método: {metodo}")
    print(f"   ⚡ Ação: {acao}")

def print_sucesso_etapa(numero, tempo_etapa=None):
    """Imprime mensagem de sucesso da etapa"""
    if tempo_etapa:
        print(f"   ✅ ETAPA {numero} concluída com sucesso em {tempo_etapa:.2f}s")
    else:
        print(f"   ✅ ETAPA {numero} concluída com sucesso")
    print("="*80)

def main(nome_filtro=None, id_prospecto=None, texto_boleto_digital=None, texto_varejo=None, texto_banco_itau=None, tenant_slug=None):
    """
    Função principal que automatiza a conversão de prospectos em clientes.

    Args:
        nome_filtro: Nome do prospecto para buscar
        id_prospecto: ID do prospecto no Hubsoft
        texto_boleto_digital: Texto da opção de boleto digital a selecionar (ETAPA 6)
        texto_varejo: Texto do grupo de cliente a selecionar, ex: "Varejo" (ETAPA 7)
        texto_banco_itau: Texto do banco para cobrança, ex: "BANCO ITAU" (ETAPA 7)
        tenant_slug: Slug do tenant Hubtrix (ex: 'nuvyon'). Carrega URL HubSoft +
            usuario + senha decryptados de IntegracaoAPI desse tenant. Default
            via env DEFAULT_TENANT_SLUG.
    """
    global TENANT_CONFIG
    tenant_slug = tenant_slug or os.environ.get('DEFAULT_TENANT_SLUG', 'nuvyon')
    try:
        TENANT_CONFIG = carregar_config(tenant_slug)
        print(f"\n🔑 Config carregada pra tenant={tenant_slug}:")
        print(f"   URL UI    : {TENANT_CONFIG.url_ui_login}")
        print(f"   Usuario   : {TENANT_CONFIG.username}")
        print(f"   Tenant ID : {TENANT_CONFIG.tenant_id}")
    except Exception as e:
        print(f"❌ Falha ao carregar config do tenant {tenant_slug!r}: {e}")
        return

    processor = ProspectoProcessor()
    processor.start_time = time.time()
    
    # Garantir que id_prospecto seja string
    id_prospecto = str(id_prospecto)
    
    print("\n" + "🚀"*40)
    print("🤖 ROBÔ DE CONVERSÃO AUTOMÁTICA DE PROSPECTOS")
    print("🚀"*40)
    print(f"\n📋 Informações do Processamento:")
    print(f"   👤 Nome: {nome_filtro}")
    print(f"   🆔 ID Prospecto: {id_prospecto}")
    print(f"   💳 Boleto: {texto_boleto_digital}")
    print(f"   👥 Grupo: {texto_varejo}")
    print(f"   🏦 Banco: {texto_banco_itau}")
    
    # Conectar ao banco
    print("\n📊 Conectando ao banco de dados...")
    if not processor.conectar_banco():
        print("❌ Falha ao conectar ao banco de dados")
        return
    print("   ✅ Conectado ao banco de dados PostgreSQL")
    
    # VERIFICAÇÃO: Não processar se já tem 3 ou mais tentativas
    print("\n🔍 Verificando histórico de tentativas...")
    try:
        cursor = processor.conn.cursor()
        cursor.execute(
            "SELECT tentativas_processamento, status FROM prospectos WHERE id_prospecto_hubsoft = %s",
            (id_prospecto,)
        )
        resultado = cursor.fetchone()
        cursor.close()
        
        if resultado:
            tentativas, status = resultado
            print(f"   📊 Tentativas anteriores: {tentativas}")
            print(f"   📊 Status atual: {status}")
            
            if tentativas >= 3:
                print(f"   ❌ Prospecto já atingiu o máximo de 3 tentativas")
                processor.desconectar_banco()
                return
            if status == 'erro' and tentativas >= 3:
                print(f"   ❌ Prospecto já marcado como erro final")
                processor.desconectar_banco()
                return
        else:
            print("   ✨ Prospecto novo - primeira tentativa")
    except Exception as e:
        print(f"   ⚠️ Erro ao verificar tentativas: {e}")
    
    # Configurar argumentos de linha de comando
    parser = argparse.ArgumentParser(description='Automatização de conversão de prospectos')
    parser.add_argument('--no-headless', action='store_true',
                        help='Executar o navegador em modo visível (desabilita headless)')
    parser.add_argument('--tenant', type=str, default=None,
                        help='Slug do tenant Hubtrix (ex: nuvyon). Ja foi resolvido pelo main; '
                             'esta flag e aceita pra rodar via CLI direta.')
    args, _ = parser.parse_known_args()
    
    # MUDANÇA: Agora headless é padrão, use --no-headless para desabilitar
    headless = not args.no_headless and os.environ.get('HEADLESS', 'true').lower() != 'false'
    
    # Credenciais vem da ConfigTenant (IntegracaoAPI do Hubtrix, decryptada).
    # Fallback pro .env legado se o tenant nao tiver config completa.
    usuario = (TENANT_CONFIG.username if TENANT_CONFIG else '') or os.environ.get('USUARIO', '')
    senha = (TENANT_CONFIG.password if TENANT_CONFIG else '') or os.environ.get('SENHA', '')

    if not usuario or not senha:
        print("❌ Credenciais HubSoft nao encontradas (tenant config nem .env)")
        processor.desconectar_banco()
        return
    
    print(f"\n⚙️ Configurando navegador Chrome...")
    print(f"   🕶️ Modo headless: {'Sim' if headless else 'Não'}")
    print(f"   📐 Resolução: 1920x1080")
    
    # Configurações do Chrome
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--v=1')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Habilitar logs de performance e DevTools Protocol
    chrome_options.set_capability("goog:loggingPrefs", {
        "browser": "ALL",
        "performance": "ALL",
        "network": "ALL"
    })
    
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--force-device-scale-factor=1')
    
    driver = None
    temp_dir = None
    try:
        # Inicializar status
        processor.salvar_prospecto(nome_filtro, id_prospecto, "INICIANDO")
        
        # Criar diretório temporário dentro do projeto
        projeto_dir = os.path.dirname(os.path.abspath(__file__))
        temp_base = os.path.join(projeto_dir, "temp_chrome_profiles")
        os.makedirs(temp_base, exist_ok=True)
        
        # Adicionar diretório único para evitar conflitos
        temp_dir = tempfile.mkdtemp(dir=temp_base)
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-default-apps")
        
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 15)
        
        print("   ✅ Navegador Chrome inicializado")
        
        # ====================================================================
        # ETAPA 1: AUTENTICAÇÃO NO SISTEMA
        # ====================================================================
        try:
            inicio_etapa = time.time()
            print_etapa_header(1, "AUTENTICAÇÃO NO SISTEMA", 
                             "Realizando login na plataforma HubSoft")
            
            # Navegar para página de login — URL dinamica pelo tenant.
            url_login = (TENANT_CONFIG.url_ui_login if TENANT_CONFIG else
                         "https://megalinktelecom.hubsoft.com.br/login")
            print(f"   🌐 Acessando URL de login: {url_login}")
            driver.get(url_login)
            print("   ✅ Página de login carregada")
            
            # Campo de email
            print_elemento_buscado(
                tipo_elemento="Input (Email)",
                localizador="name='email'",
                metodo="By.NAME",
                acao="Preencher com usuário"
            )
            email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            email_input.clear()
            email_input.send_keys(usuario)
            print("   ✅ Email preenchido")
            time.sleep(1)
            
            # Botão Validar
            print_elemento_buscado(
                tipo_elemento="Button (Validar)",
                localizador="//button[contains(., 'Validar')]",
                metodo="By.XPATH",
                acao="Click"
            )
            validar_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Validar')]")))
            validar_button.click()
            print("   ✅ Botão 'Validar' clicado")
            
            # Campo de senha
            print_elemento_buscado(
                tipo_elemento="Input (Password)",
                localizador="input[type='password']",
                metodo="By.CSS_SELECTOR",
                acao="Preencher com senha"
            )
            password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            password_input.clear()
            password_input.send_keys(senha)
            print("   ✅ Senha preenchida")
            time.sleep(1)
            
            # Botão Entrar
            print_elemento_buscado(
                tipo_elemento="Button (Entrar)",
                localizador="//button[contains(., 'Entrar')]",
                metodo="By.XPATH",
                acao="Click"
            )
            entrar_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Entrar')]")))
            entrar_button.click()
            print("   ✅ Botão 'Entrar' clicado")
            
            print("   ⏳ Aguardando dashboard carregar (5s)...")
            time.sleep(5)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "LOGIN_REALIZADO")
            tempo_etapa = time.time() - inicio_etapa
            print_sucesso_etapa(1, tempo_etapa)
            
        except Exception as e:
            erro_detalhado = f"ETAPA 1 - ERRO LOGIN: {str(e)}"
            print(f"\n   ❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "login", "ETAPA1")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_LOGIN", erro_detalhado)
            raise
        
        # ETAPA 2: Navegação para Prospectos
        try:
            print("🧭 ETAPA 2: Navegando para prospectos...")
            # Expandir menu Cliente
            cliente_arrow = wait.until(EC.element_to_be_clickable((By.XPATH, "//i[contains(@class, 'icon-chevron-right') and contains(@class, 'arrow')]")))
            cliente_arrow.click()
            time.sleep(1)
            
            # Clicar em Prospectos
            prospectos_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='title ng-scope ng-binding flex' and contains(text(), 'Prospectos')]//parent::a")))
            prospectos_link.click()
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "NAVEGACAO_PROSPECTOS")
            print("✅ ETAPA 2: Navegação concluída com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 2 - ERRO NAVEGAÇÃO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "navegacao", "ETAPA2")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_NAVEGACAO", erro_detalhado)
            raise
        
        # ETAPA 3: Filtrar e localizar prospecto
        try:
            print("🔍 ETAPA 3: Localizando prospecto...")
            # Localizar tabela
            tabela = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.dataTable.row-border.hover")))
            
            # Filtrar por nome
            campo_busca = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[ng-model='vm.filtros.busca']")))
            campo_busca.clear()
            campo_busca.send_keys(nome_filtro)
            campo_busca.send_keys(Keys.ENTER)
            time.sleep(2)
            
            # CRÍTICO: Maximizar janela ANTES de procurar o botão de Ações
            print("🔧 MAXIMIZANDO JANELA DO NAVEGADOR (essencial para visualizar botões na tabela)...")
            
            # Primeiro, definir um tamanho grande para garantir
            try:
                # Para headless, é importante definir um tamanho específico primeiro
                driver.set_window_size(1920, 1080)
                print("✅ Tamanho inicial definido: 1920x1080")
                time.sleep(1)
                
                # Tentar maximizar (funciona melhor após definir um tamanho)
                driver.maximize_window()
                print("✅ Janela maximizada com sucesso!")
                
                # Em modo headless, forçar tamanho máximo de tela
                if headless:
                    # Para headless, usar tamanho de tela full HD ou maior
                    driver.set_window_size(1920, 1080)
                    print("✅ Modo headless: viewport definido para 1920x1080")
                    
                    # Opção adicional: tentar definir um tamanho ainda maior para headless
                    try:
                        driver.execute_script("window.moveTo(0, 0);")
                        driver.execute_script("window.resizeTo(screen.width, screen.height);")
                        print("✅ JavaScript: janela redimensionada para tamanho máximo da tela")
                    except:
                        pass
                
                # Aguardar a janela se ajustar e a tabela re-renderizar
                time.sleep(3)
                print("✅ Aguardando re-renderização da tabela com janela maximizada...")
                
            except Exception as e:
                print(f"⚠️ Erro ao maximizar: {e}")
                # Fallback final: garantir pelo menos um tamanho grande
                try:
                    driver.set_window_size(1920, 1080)
                    print("✅ Fallback: tamanho 1920x1080 aplicado")
                    time.sleep(2)
                except:
                    print("❌ Não foi possível ajustar o tamanho da janela")
            
            # Forçar um refresh da página para garantir que a tabela seja re-renderizada
            try:
                driver.execute_script("window.dispatchEvent(new Event('resize'));")
                print("✅ Evento de redimensionamento disparado para atualizar layout")
            except:
                pass
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "PROSPECTO_LOCALIZADO")
            print("✅ ETAPA 3: Prospecto localizado com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 3 - ERRO LOCALIZAÇÃO PROSPECTO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "localizacao", "ETAPA3")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_LOCALIZACAO", erro_detalhado)
            raise
        
        # ETAPA 4: Clicar no botão de Ações
        try:
            print("⚙️ ETAPA 4: Abrindo menu de ações...")
            xpath_acoes = f"//tr[.//td[normalize-space(.)='{id_prospecto}']]/descendant::button[@aria-label='Open menu with custom trigger' and .//span[normalize-space(.)='Ações']]"
            acoes_button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_acoes)))
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", acoes_button)
            time.sleep(1)
            
            acoes_button.click()
            time.sleep(2)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "MENU_ACOES_ABERTO")
            print("✅ ETAPA 4: Menu de ações aberto com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 4 - ERRO MENU AÇÕES: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "acoes", "ETAPA4")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_ACOES", erro_detalhado)
            raise
        
        # ETAPA 5: Converter em Cliente
        try:
            print("🔄 ETAPA 5: Convertendo para cliente...")
            converter_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@style='color:green' and contains(text(), 'Converter em Cliente')]")))
            driver.execute_script("arguments[0].click();", converter_button)
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_INICIADO")
            print("✅ ETAPA 5: Wizard de conversão iniciado com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 5 - ERRO CONVERSÃO: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "converter", "ETAPA5")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_CONVERTER", erro_detalhado)
            raise
        
        # ETAPA 6: Wizard - Primeira tela
        try:
            print("📋 ETAPA 6: Preenchendo wizard (1/4)...")
            
            # Selecionar opção no campo md-select (Boleto Digital)
            print(f"🔽 Selecionando opção '{texto_boleto_digital}' no campo...")
            md_select_campo = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/hubsoft-accordion/div[2]/hubsoft-accordion-content/div/form/div/div[6]/md-input-container[1]/md-select")))
            driver.execute_script("arguments[0].click();", md_select_campo)
            time.sleep(1)
            
            # Buscar a opção que contém o texto especificado
            if texto_boleto_digital:
                xpath_boleto = f"//md-option[contains(., '{texto_boleto_digital}')]"
                opcao_campo = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_boleto)))
                print(f"✅ Opção '{texto_boleto_digital}' encontrada")
            else:
                # Fallback: primeira opção se não especificado
                opcao_campo = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option[1]")))
                print("⚠️ Usando primeira opção (padrão)")
            
            driver.execute_script("arguments[0].click();", opcao_campo)
            time.sleep(1)
            
            # Primeiro botão
            primeiro_botao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", primeiro_botao)
            time.sleep(2)
            
            # Segundo botão
            segundo_botao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", segundo_botao)
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_TELA1")
            print("✅ ETAPA 6: Primeira tela do wizard concluída com sucesso")
            
        except Exception as e:
            erro_detalhado = f"ETAPA 6 - ERRO WIZARD TELA 1: {str(e)}"
            print(f"❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "wizard1", "ETAPA6")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD1", erro_detalhado)
            raise
        
        # ETAPA 7: Wizard - Seleções
        try:
            inicio_etapa = time.time()
            print_etapa_header(7, "WIZARD - SELEÇÕES (ENDEREÇO E GRUPO)",
                             "Selecionando endereço e grupo de cliente")
            
            # Aguardar a página carregar completamente
            time.sleep(2)
            
            # Primeiro md-select (Endereço - geralmente só tem uma opção)
            print_elemento_buscado(
                tipo_elemento="md-select (Endereço)",
                localizador="/html/body/div[5]/.../md-select",
                metodo="By.XPATH",
                acao="Abrir dropdown de endereços"
            )
            md_select1 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/div/form/div/md-input-container/md-select")))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", md_select1)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", md_select1)
            print("   ✅ Dropdown de endereço aberto")
            time.sleep(2)
            
            # Aguardar menu abrir e selecionar a primeira (e geralmente única) opção
            # IMPORTANTE: O menu abre em div[7], não em md-select-menu
            print_elemento_buscado(
                tipo_elemento="md-option (Endereço)",
                localizador="/html/body/div[7]/md-select-menu/md-content/md-option",
                metodo="By.XPATH",
                acao="Selecionar endereço (única opção disponível)"
            )
            md_option1 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[7]/md-select-menu/md-content/md-option")))
            print("   ✅ Opção de endereço encontrada")
            
            driver.execute_script("arguments[0].click();", md_option1)
            print("   ✅ Endereço selecionado")
            time.sleep(2)
            
            # Segundo md-select (Grupo de Cliente - Varejo)
            print_elemento_buscado(
                tipo_elemento="md-select (Grupo Cliente)",
                localizador="/html/body/div[5]/.../md-select",
                metodo="By.XPATH",
                acao="Abrir dropdown de grupos de cliente"
            )
            md_select2 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/div/form/div/div[2]/md-input-container[2]/md-select")))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", md_select2)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", md_select2)
            print("   ✅ Dropdown de grupo aberto")
            time.sleep(2)
            
            if texto_varejo:
                # O menu abre em div[8] quando é o segundo dropdown
                # Buscar pela opção que contém exatamente o texto "Varejo"
                print_elemento_buscado(
                    tipo_elemento="md-option (Grupo)",
                    localizador=f"//div[8]//md-option[.//div[contains(@class, 'md-text') and normalize-space(text())='{texto_varejo}']]",
                    metodo="By.XPATH",
                    acao=f"Selecionar grupo '{texto_varejo}'"
                )
                # XPath testado e funcionando - busca md-option com div.md-text contendo texto exato
                xpath_varejo = f"//div[8]//md-option[.//div[contains(@class, 'md-text') and normalize-space(text())='{texto_varejo}']]"
                
                # Aguardar o elemento estar presente e clicável
                print(f"   ⏳ Aguardando opção '{texto_varejo}' ficar clicável...")
                opcao_varejo = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_varejo)))
                print(f"   ✅ Opção '{texto_varejo}' encontrada e clicável")
            else:
                # Fallback: primeira opção
                opcao_varejo = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[8]/md-select-menu/md-content/md-option[1]")))
                print("   ⚠️ Usando primeira opção (padrão)")
            
            # Usar JavaScript para garantir o clique
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", opcao_varejo)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", opcao_varejo)
            print("   ✅ Grupo selecionado")
            time.sleep(3)  # Aumentar tempo de espera após seleção
            
            # Primeiro clique no botão Avançar (após selecionar Grupo)
            print_elemento_buscado(
                tipo_elemento="Button (Avançar 1)",
                localizador="/html/body/div[5]/.../button",
                metodo="By.XPATH",
                acao="Avançar após seleção de grupo"
            )
            print("   ⏳ Aguardando botão aparecer...")
            time.sleep(2)  # Aguardar botão aparecer
            botao_avancar1 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", botao_avancar1)
            print("   ✅ Primeiro avançar clicado")
            time.sleep(3)
            
            # Segundo clique no botão Avançar
            print_elemento_buscado(
                tipo_elemento="Button (Avançar 2)",
                localizador="/html/body/div[5]/.../button",
                metodo="By.XPATH",
                acao="Avançar segunda vez"
            )
            print("   ⏳ Aguardando botão aparecer novamente...")
            time.sleep(2)  # Aguardar botão aparecer novamente
            botao_avancar2 = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", botao_avancar2)
            print("   ✅ Segundo avançar clicado")
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_SELECOES")
            tempo_etapa = time.time() - inicio_etapa
            print_sucesso_etapa(7, tempo_etapa)
            
        except Exception as e:
            erro_detalhado = f"ETAPA 7 - ERRO WIZARD SELEÇÕES: {str(e)}"
            print(f"\n   ❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "wizard_selecoes", "ETAPA7")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD_SELECOES", erro_detalhado)
            raise
        
        # ETAPA 8: Wizard - Seleção do Banco
        try:
            inicio_etapa = time.time()
            print_etapa_header(8, "WIZARD - SELEÇÃO DE BANCO",
                             "Selecionando banco para cobrança")
            
            # md-select (Banco para cobrança)
            print_elemento_buscado(
                tipo_elemento="hubsoft-select-virtual-repeat (Banco)",
                localizador="/html/body/div[5]/.../md-select",
                metodo="By.XPATH",
                acao="Abrir dropdown de bancos"
            )
            print("   ⏳ Aguardando campo de banco aparecer...")
            time.sleep(3)  # Aguardar tela carregar completamente
            
            md_select_banco = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[1]/div/form/div[1]/div/hubsoft-select-virtual-repeat/md-input-container/md-select")))
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", md_select_banco)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", md_select_banco)
            print("   ✅ Dropdown de banco aberto")
            time.sleep(3)  # Aguardar menu abrir e carregar opções
            
            if texto_banco_itau:
                # Tentar múltiplas estratégias para encontrar o botão
                print(f"   🔍 Buscando banco '{texto_banco_itau}'...")
                
                # Estratégia 1: Buscar em qualquer div com virtual-repeat
                xpaths_to_try = [
                    f"//button[@aria-label='{texto_banco_itau}']",  # Simples e direto
                    f"//div[8]//button[@aria-label='{texto_banco_itau}']",  # Com div[8]
                    f"//md-virtual-repeat-container//button[@aria-label='{texto_banco_itau}']",  # Dentro do container virtual
                    f"//md-select-menu//button[@aria-label='{texto_banco_itau}']",  # Dentro do menu
                ]
                
                opcao_banco = None
                for i, xpath in enumerate(xpaths_to_try, 1):
                    try:
                        print(f"   🧪 Tentativa {i}: {xpath[:60]}...")
                        opcao_banco = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                        print(f"   ✅ Encontrado com tentativa {i}!")
                        break
                    except Exception as e:
                        print(f"   ❌ Tentativa {i} falhou")
                        if i == len(xpaths_to_try):
                            # Última tentativa falhou, listar o que tem disponível
                            print("   📋 Listando botões disponíveis:")
                            try:
                                todos_botoes = driver.find_elements(By.XPATH, "//button[@aria-label]")
                                for btn in todos_botoes[:10]:  # Mostrar até 10
                                    label = btn.get_attribute("aria-label")
                                    print(f"      - {label}")
                            except:
                                pass
                            raise
                
                if opcao_banco:
                    print(f"   ✅ Banco '{texto_banco_itau}' encontrado e clicável")
                else:
                    raise Exception(f"Não foi possível encontrar o banco '{texto_banco_itau}'")
            else:
                # Fallback: primeiro banco disponível
                opcao_banco = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label]")))
                print("   ⚠️ Usando primeiro banco (padrão)")
            
            # Usar JavaScript para garantir o clique
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", opcao_banco)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", opcao_banco)
            print("   ✅ Banco selecionado")
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_TELA2")
            tempo_etapa = time.time() - inicio_etapa
            print_sucesso_etapa(8, tempo_etapa)
            
        except Exception as e:
            erro_detalhado = f"ETAPA 8 - ERRO SELEÇÃO BANCO: {str(e)}"
            print(f"\n   ❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "selecao_banco", "ETAPA8")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD2", erro_detalhado)
            raise
        
        # ETAPA 9: Wizard - Próxima tela
        try:
            inicio_etapa = time.time()
            print_etapa_header(9, "WIZARD - PENÚLTIMA TELA",
                             "Avançando para finalização")
            
            # Primeiro botão Avançar
            print_elemento_buscado(
                tipo_elemento="Button (Avançar)",
                localizador="/html/body/div[5]/.../button",
                metodo="By.XPATH",
                acao="Avançar para próxima tela"
            )
            print("   ⏳ Aguardando botão aparecer...")
            time.sleep(2)
            proximo_botao = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", proximo_botao)
            print("   ✅ Avançado")
            time.sleep(3)
            
            tempo_etapa = time.time() - inicio_etapa
            print_sucesso_etapa(9, tempo_etapa)
            
        except Exception as e:
            erro_detalhado = f"ETAPA 9 - ERRO PENÚLTIMA TELA: {str(e)}"
            print(f"\n   ❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "penultima_tela", "ETAPA9")
            raise
        
        # ETAPA 10: Finalização
        try:
            inicio_etapa = time.time()
            print_etapa_header(10, "FINALIZAÇÃO",
                             "Salvando e finalizando conversão do prospecto")
            
            # Botão Avançar final
            print_elemento_buscado(
                tipo_elemento="Button (Avançar)",
                localizador="/html/body/div[5]/.../button",
                metodo="By.XPATH",
                acao="Avançar para tela de salvar"
            )
            print("   ⏳ Aguardando botão aparecer...")
            time.sleep(2)
            botao_avancar_final = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/button")))
            driver.execute_script("arguments[0].click();", botao_avancar_final)
            print("   ✅ Avançado para tela de salvar")
            time.sleep(3)
            
            # Botão SALVAR
            print_elemento_buscado(
                tipo_elemento="Button (SALVAR)",
                localizador="/html/body/div[5]/.../div/button",
                metodo="By.XPATH",
                acao="Salvar conversão do prospecto"
            )
            print("   ⏳ Aguardando botão SALVAR aparecer...")
            time.sleep(2)
            botao_salvar = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard/div[2]/md-dialog-actions/div[2]/div/button")))
            driver.execute_script("arguments[0].click();", botao_salvar)
            print("   ✅ Conversão salva!")
            time.sleep(3)
            
            processor.salvar_prospecto(nome_filtro, id_prospecto, "CONCLUIDO", None, "sucesso")
            
            tempo_total = int(time.time() - processor.start_time)
            tempo_etapa = time.time() - inicio_etapa
            print_sucesso_etapa(10, tempo_etapa)
            
            print("\n" + "🎉"*40)
            print(f"✨ SUCESSO TOTAL! Prospecto convertido em {tempo_total}s ✨")
            print("🎉"*40)
            
        except Exception as e:
            erro_detalhado = f"ETAPA 10 - ERRO FINALIZAÇÃO: {str(e)}"
            print(f"\n   ❌ {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "finalizacao", "ETAPA10")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_FINALIZACAO", erro_detalhado)
            raise
        
    except Exception as e:
        erro_detalhado = f"ERRO GERAL DO PROCESSO: {str(e)}"
        logger.error(erro_detalhado)
        print(f"❌ {erro_detalhado}")
        if processor.current_prospecto_id:
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_GERAL", erro_detalhado, "falha")
        if driver:
            processor.capturar_screenshot_erro(driver, "erro_geral", "GERAL")
    finally:
        if driver:
            driver.quit()
        if temp_dir:
            shutil.rmtree(temp_dir)
        processor.desconectar_banco()
        print("🔌 Desconectado do banco")
if __name__ == "__main__":
    # CLI multi-tenant:
    #   python main_refatorado.py --tenant nuvyon --nome "LUCAS ..." --id-prospecto 22651
    #     [--boleto "Boleto Digital"] [--grupo "Varejo"] [--banco "BANCO ITAU"] [--no-headless]
    cli = argparse.ArgumentParser(description='Robo de conversao de prospectos HubSoft (Hubtrix)')
    cli.add_argument('--tenant', default=os.environ.get('DEFAULT_TENANT_SLUG', 'nuvyon'),
                     help='Slug do tenant Hubtrix (default: nuvyon)')
    cli.add_argument('--nome', required=True, help='Nome do prospecto (filtro UI)')
    cli.add_argument('--id-prospecto', required=True, help='id_prospecto no HubSoft (ex: 22651)')
    cli.add_argument('--boleto', default='Boleto Digital', help='Texto da opcao de boleto')
    cli.add_argument('--grupo', default='Varejo', help='Grupo de cliente (ex: Varejo)')
    cli.add_argument('--banco', default='BANCO ITAU', help='Banco de cobranca')
    cli.add_argument('--no-headless', action='store_true', help='Modo navegador visivel')
    args, _ = cli.parse_known_args()

    main(
        nome_filtro=args.nome,
        id_prospecto=args.id_prospecto,
        texto_boleto_digital=args.boleto,
        texto_varejo=args.grupo,
        texto_banco_itau=args.banco,
        tenant_slug=args.tenant,
    )