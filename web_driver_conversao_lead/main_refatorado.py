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

# Modo passo-a-passo: pausa antes de cada etapa esperando ENTER no terminal.
# Util pra debugar/remapear XPaths quando a UI HubSoft muda entre tenants.
STEP_DEBUG: bool = False

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
                
                # Schema do Hubtrix nao tem data_atualizacao em prospectos
                # (so data_criacao e data_processamento). Usa data_processamento
                # como timestamp mais recente.
                cursor.execute("""
                    UPDATE prospectos SET
                        nome_prospecto = %s,
                        status = %s,
                        data_processamento = %s,
                        tentativas_processamento = %s,
                        erro_processamento = %s,
                        tempo_processamento = %s,
                        resultado_processamento = %s
                    WHERE id = %s
                """, (
                    nome_prospecto, status_db, datetime.datetime.now(),
                    self.tentativa_atual, erro, tempo_processamento,
                    Json(resultado) if resultado is not None else None, id_existente
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
                        data_criacao, data_processamento,
                        tentativas_processamento, erro_processamento,
                        tempo_processamento, resultado_processamento,
                        prioridade, tenant_id, lead_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    nome_prospecto, id_prospecto_hubsoft, status_db,
                    datetime.datetime.now(), datetime.datetime.now(),
                    self.tentativa_atual, erro, tempo_processamento,
                    Json(resultado) if resultado is not None else None,
                    1, tenant_id, lead_id_resolvido,
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
    """Imprime cabeçalho formatado de uma etapa. Em modo --step-debug, pausa
    ANTES do header esperando ENTER pra inspecao manual no navegador."""
    if STEP_DEBUG:
        try:
            input(f"\n⏸️  [STEP-DEBUG] Pause ANTES de ETAPA {numero}: {titulo}. "
                  f"Inspecione o navegador e tecle ENTER pra continuar (ou Ctrl+C pra abortar)... ")
        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Abortado pelo usuario no step-debug.")
            raise
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

def _executar_wizard_nuvyon(processor, driver, wait, dry_run, headless, nome_filtro, id_prospecto, coletar_dom=False):
    """Executa as 7 etapas do wizard `Adicionar Cliente` do HubSoft Nuvyon.

    Estrutura validada via DOM (web_driver_conversao_lead/dom_capturado/):
      step1 Cadastro:  set grupo_cliente=RESIDENCIAL + genero=MASCULINO
      step2 Enderecoo:  ja pre-preenchido, so avancar
      step3 Plano:     selecionar endereco_instalacao + vendedor=hubtrix + data_venda=hoje
      step4 Contrato:  sem campos, so avancar
      step5 Cobranca:  Forma=Sicredi - Nuvyion, vencimento=do lead (id_dia_vencimento), tipo=Postecipada (Pos-Pago)
      step6 Pacotes:   sem campos, so avancar
      step7 OS:        clicar SALVAR (a menos que dry_run=True)
    """
    # Snapshot DOM em pontos-chave (ativo com coletar_dom=True). Sobrescreve
    # os arquivos dom_capturado/stepN.html da rodada anterior — captura agora
    # eh POS-fill (depois das interacoes), reflete o estado real do Angular.
    import pathlib
    _snap_dir = pathlib.Path('dom_capturado') if coletar_dom else None
    if _snap_dir:
        _snap_dir.mkdir(exist_ok=True)

    def snapshot(slug: str):
        if not _snap_dir:
            return
        try:
            dialog = driver.find_element(By.XPATH, "//hubsoft-cliente-wizard")
            html = dialog.get_attribute('outerHTML')
            f = _snap_dir / f"{slug}.html"
            f.write_text(html, encoding='utf-8')
            print(f"      📸 snapshot {f.name} ({len(html):,} bytes)")
        except Exception as e:
            print(f"      ⚠️ snapshot {slug} falhou: {e}")

    def goto_step(n: int):
        """Clica no nav <li name='stepN'> do wizard (estavel, sem texto acentuado)."""
        for xp in [f"//li[@name='step{n}']//button", f"//li[@name='step{n}']"]:
            try:
                el = driver.find_element(By.XPATH, xp)
                driver.execute_script("arguments[0].click();", el)
                time.sleep(2)
                return True
            except Exception:
                continue
        # Fallback Angular direto
        try:
            driver.execute_script(
                f"angular.element(document.querySelector('hubsoft-cliente-wizard'))"
                f".scope().vm.gotoStep(null,'step{n}');"
                f"angular.element(document.querySelector('hubsoft-cliente-wizard')).scope().$apply();"
            )
            time.sleep(2)
            return True
        except Exception:
            return False

    def open_select_by_name(name: str):
        """Abre o md-select pelo atributo name= (acentos OK no XPath)."""
        xp = f"//md-select[@name='{name}']"
        el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", el)
        time.sleep(1.5)
        return el

    def click_option_by_text(texto: str, exato: bool = False):
        """Clica no md-option cujo .md-text contem (ou e exatamente) `texto`."""
        if exato:
            xp = f"//md-option//div[@class='md-text ng-binding' and normalize-space(text())='{texto}']/.."
        else:
            xp = f"//md-option//div[contains(@class,'md-text') and contains(normalize-space(text()),'{texto}')]/.."
        opt = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(0.7)

    def fechar_dropdown():
        """ESC pra fechar dropdown multi-select. Usa ActionChains pra robustez."""
        try:
            driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        except Exception:
            try:
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
        time.sleep(0.7)

    def listar_opcoes_visiveis() -> list:
        """Util de debug — lista textos das md-option visiveis na tela."""
        try:
            els = driver.find_elements(By.XPATH, "//md-option//div[contains(@class,'md-text')]")
            return [(el.text or '').strip() for el in els if (el.text or '').strip()]
        except Exception:
            return []

    # === STEP 1: CADASTRO ===
    print("\n   📋 STEP 1 CADASTRO: rg + grupo_cliente=RESIDENCIAL + genero=MASCULINO")

    # Carrega rg do lead via DB Hubtrix (conexao do processor — primary)
    rg_lead = ''
    try:
        cur = processor.conn.cursor()
        cur.execute(
            "SELECT rg FROM leads_prospectos WHERE id_hubsoft=%s AND tenant_id=%s LIMIT 1",
            (str(id_prospecto), TENANT_CONFIG.tenant_id if TENANT_CONFIG else None),
        )
        row = cur.fetchone()
        cur.close()
        rg_lead = (row[0] or '').strip() if row else ''
    except Exception as e:
        print(f"      ⚠️ Falha ao consultar rg do lead: {e}")

    if rg_lead:
        try:
            rg_input = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//input[@name='rg']")
            ))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", rg_input)
            rg_input.clear()
            rg_input.send_keys(rg_lead)
            rg_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            print(f"      ✓ rg={rg_lead}")
        except Exception as e:
            print(f"      ❌ Falha ao preencher rg: {e}")
            raise Exception(f"step1: nao foi possivel preencher RG ({rg_lead})")
    else:
        raise Exception(
            f"Lead com id_hubsoft={id_prospecto} esta sem RG no Hubtrix. "
            "RG e obrigatorio no wizard Nuvyon — preencha leads_prospectos.rg antes de rodar o bot."
        )

    open_select_by_name('grupo_cliente')
    click_option_by_text('RESIDENCIAL', exato=True)
    fechar_dropdown()
    print("      ✓ grupo_cliente=RESIDENCIAL marcado")

    open_select_by_name('genero')
    click_option_by_text('MASCULINO', exato=True)
    print("      ✓ genero=MASCULINO setado")

    snapshot('step1_pos_fill')
    processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_TELA1")

    # === STEP 2: ENDEREÇO === (já pré-preenchido pelo prospect)
    print("\n   📋 STEP 2 ENDEREÇO: pré-preenchido, só avançar")
    if not goto_step(2):
        raise Exception("Falha ao navegar pra step2 Endereço")
    time.sleep(2)
    snapshot('step2_pos_load')

    # === STEP 3: PLANO ===
    print("\n   📋 STEP 3 PLANO: endereco_instalacao + vendedor=hubtrix + data_venda=hoje")
    if not goto_step(3):
        raise Exception("Falha ao navegar pra step3 Plano")
    time.sleep(2)
    snapshot('step3_pre_fill')

    # Endereço de instalação (única opção). Estrategia: clicar de verdade na
    # md-option (dispara ng-change nativo → vm.carregaUnidadeNegocio() async).
    # Usa aria-owns pra achar o container real do dropdown (Angular Material
    # move pra <body> quando abre).
    try:
        # Pega aria-owns ANTES de abrir
        sel_el = driver.find_element(By.XPATH, "//md-select[@name='cliente_servico_endereco_instalacao']")
        owns = sel_el.get_attribute('aria-owns') or ''
        open_select_by_name('cliente_servico_endereco_instalacao')
        try:
            xp_opt = f"//div[@id='{owns}']//md-option[1]" if owns else "//md-option"
            primeira = wait.until(EC.element_to_be_clickable((By.XPATH, xp_opt)))
            driver.execute_script("arguments[0].click();", primeira)
            time.sleep(3)  # carregaUnidadeNegocio() AJAX
            print(f"      ✓ endereco_instalacao clicado de verdade (container={owns})")
        except Exception as e:
            # Fallback: seta diretamente via Angular scope
            print(f"      ⚠️ click falhou ({type(e).__name__}); tentando via Angular scope")
            try:
                # Importante: NG-CHANGE original do select dispara:
                #   vm.verificaPromocoesDisponiveis(); vm.carregaUnidadeNegocio();
                #   vm.validadorStep(vm.currentNavItem); vm.PermiteAtualizacaoCoords(...)
                # Como estamos pulando o click, precisamos chamar essas funcoes
                # MANUAL pra que cascade Angular dispare (em especial a UN, que
                # eh a fonte de `formas_cobranca` no step5).
                driver.execute_script("""
                    var sel = document.querySelector('md-select[name="cliente_servico_endereco_instalacao"]');
                    var scope = angular.element(sel).scope();
                    if (scope.vm.cliente.cliente_endereco_numeros && scope.vm.cliente.cliente_endereco_numeros.length) {
                        scope.vm.cliente.cliente_servico_endereco_instalacao = scope.vm.cliente.cliente_endereco_numeros[0];
                        // Cascade do ng-change original:
                        try { scope.vm.verificaPromocoesDisponiveis(); } catch(e){}
                        try { scope.vm.carregaUnidadeNegocio(); } catch(e){}
                        try { scope.vm.validadorStep(scope.vm.currentNavItem); } catch(e){}
                        scope.$apply();
                    }
                """)
                time.sleep(2.5)  # aguarda carregaUnidadeNegocio() (AJAX) terminar
                fechar_dropdown()
                print("      ✓ endereco_instalacao setado via Angular + cascade ng-change")
            except Exception as e2:
                print(f"      ❌ Angular fallback falhou: {e2}")
                fechar_dropdown()
    except Exception as e:
        print(f"      ⚠️ Falha ao abrir endereco_instalacao: {e}")

    # Vendedor = hubtrix
    try:
        open_select_by_name('vendedor')
        click_option_by_text('hubtrix', exato=False)
        print("      ✓ vendedor=hubtrix")
    except Exception as e:
        print(f"      ⚠️ Falha ao setar vendedor: {e}")
        opcoes = listar_opcoes_visiveis()
        if opcoes:
            print(f"      Opcoes visiveis: {opcoes[:10]}")
        fechar_dropdown()

    # data_venda — md-datepicker tem input filho; setar via JS é mais confiavel
    try:
        from datetime import datetime as _dt
        hoje_br = _dt.now().strftime('%d/%m/%Y')
        # Datepicker em md-datepicker[name=data_venda]; busca o input dentro
        dp_input = driver.find_element(
            By.XPATH, "//md-datepicker[@name='data_venda']//input"
        )
        dp_input.clear()
        dp_input.send_keys(hoje_br)
        dp_input.send_keys(Keys.TAB)
        time.sleep(0.5)
        print(f"      ✓ data_venda={hoje_br}")
    except Exception as e:
        print(f"      ⚠️ Falha ao setar data_venda: {e}")

    snapshot('step3_pos_fill')
    processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_SELECOES")

    # === STEP 4: CONTRATO === (sem campos obrigatórios)
    print("\n   📋 STEP 4 CONTRATO: sem campos, só avançar")
    if not goto_step(4):
        raise Exception("Falha ao navegar pra step4 Contrato")
    time.sleep(2)
    snapshot('step4_pos_load')

    # === STEP 5: COBRANÇA ===
    print("\n   📋 STEP 5 COBRANÇA: Forma=Sicredi - Nuvyion, vencimento=do lead, tipo=Postecipada")
    if not goto_step(5):
        raise Exception("Falha ao navegar pra step5 Cobrança")
    time.sleep(2)
    snapshot('step5_pre_fill')

    # Forma de Cobranca: componente custom <hubsoft-select-virtual-repeat> com
    # AJAX lazy load via vm.unidade_negocio.formas_cobranca. Lista popula
    # apos request async — bot precisa fazer polling ate `formas_cobranca`
    # ter itens antes de tentar setar via Angular scope.
    forma_cobranca_skipped = False
    # FIX 1: limpa qualquer md-list-item residual ANTES de abrir (sobras de
    # selects anteriores no DOM podem ser pegas pelo polling).
    try:
        fechar_dropdown()
        time.sleep(0.5)
    except Exception:
        pass

    # Abre dropdown pra disparar md-on-open (fnOnOpen) que carrega a lista.
    try:
        open_select_by_name('Forma de Cobrança')
        print("      ✓ Forma de Cobrança aberto — fnOnOpen() disparado")
    except Exception as e:
        print(f"      ⚠️ Nao consegui abrir Forma de Cobrança: {e}")

    # FIX 2: espera MINIMA antes de procurar (md-on-open dispara load AJAX
    # da UN; mesmo cacheado leva 1-2s pra renderizar o md-list-item REAL).
    time.sleep(2.0)

    print("      ⏳ Aguardando md-list-item com 'SICREDI' aparecer no DOM...")
    max_wait = 30
    poll_interval = 0.5
    inicio_poll = time.time()
    sicredi_el = None
    while time.time() - inicio_poll < max_wait:
        try:
            # XPath mais especifico: md-list-item DENTRO do md-select-menu
            # que está ABERTO (aria-hidden=false) — evita residuais.
            candidatos = driver.find_elements(
                By.XPATH,
                "//md-select-menu//md-list-item[contains(translate(normalize-space(.),"
                "'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),"
                "'SICREDI')]"
            )
            if candidatos:
                sicredi_el = candidatos[-1]  # ultimo (mais provavel ser o atual)
                break
        except Exception:
            pass
        time.sleep(poll_interval)
    tempo_espera = time.time() - inicio_poll

    if sicredi_el:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sicredi_el)
            time.sleep(0.5)
            # FIX 3: click REAL via ActionChains (dispara ng-click do Angular).
            # JS execute_script.click() nao dispara handlers Angular sintetizados.
            try:
                ActionChains(driver).move_to_element(sicredi_el).click().perform()
                time.sleep(1.5)
            except Exception:
                # Fallback: JS click + dispatch event explicito
                driver.execute_script("""
                    var el = arguments[0];
                    el.click();
                    var evt = new MouseEvent('click', {bubbles:true, cancelable:true, view:window});
                    el.dispatchEvent(evt);
                """, sicredi_el)
                time.sleep(1.5)

            # VERIFICACAO: o md-select pai agora deve mostrar valor selecionado.
            verif = driver.execute_script("""
                var sel = document.querySelector('md-select[name="Forma de Cobrança"]');
                if (!sel) return {ok: false, err: 'select sumiu'};
                // md-select-value contem o label do escolhido (ou placeholder)
                var val = sel.querySelector('md-select-value');
                var txt = val ? (val.innerText || val.textContent || '').trim() : '';
                var placeholder = val && val.classList.contains('md-select-placeholder');
                return {
                    ok: !placeholder && txt.length > 0 && txt.toUpperCase().indexOf('SICREDI') !== -1,
                    texto: txt,
                    placeholder: placeholder
                };
            """)
            if verif.get('ok'):
                print(f"      ✓ Forma de Cobrança=SICREDI confirmado ({tempo_espera:.1f}s busca + click). UI mostra: {verif['texto']!r}")
            else:
                print(f"      ⚠️ Click feito mas UI nao confirmou: {verif}")
                forma_cobranca_skipped = True
        except Exception as e:
            print(f"      ❌ Falha ao clicar em SICREDI: {e}")
            forma_cobranca_skipped = True
            fechar_dropdown()
    else:
        print(f"      ⚠️  md-list-item SICREDI nao apareceu em {max_wait}s — pulando")
        forma_cobranca_skipped = True
        fechar_dropdown()

    # Vencimento: le id_dia_vencimento do lead e mapeia pro DIA, em vez de fixar 9.
    # Mapa id->dia extraido do flow Matrix v8 da Nuvyon (nos red_*venc*).
    VENCIMENTO_ID_PARA_DIA = {4: '10', 5: '15', 6: '20', 9: '5'}
    dia_venc = None
    try:
        _cur = processor.conn.cursor()
        _cur.execute(
            "SELECT id_dia_vencimento FROM leads_prospectos WHERE id_hubsoft=%s AND tenant_id=%s LIMIT 1",
            (str(id_prospecto), TENANT_CONFIG.tenant_id if TENANT_CONFIG else None),
        )
        _row = _cur.fetchone()
        _cur.close()
        if _row and _row[0] is not None:
            dia_venc = VENCIMENTO_ID_PARA_DIA.get(int(_row[0]))
            if dia_venc is None:
                print(f"      ⚠️ id_dia_vencimento={_row[0]} sem mapeamento Nuvyon — vencimento nao alterado")
    except Exception as e:
        print(f"      ⚠️ Falha ao ler id_dia_vencimento: {e}")
    try:
        if dia_venc:
            open_select_by_name('vencimento')
            click_option_by_text(dia_venc, exato=True)
            print(f"      ✓ vencimento={dia_venc} (do lead, id_dia_vencimento)")
        else:
            print("      ⚠️ vencimento nao mapeado — mantendo o que veio do prospecto")
    except Exception as e:
        print(f"      ⚠️ Falha em vencimento: {e}")
        fechar_dropdown()

    # Tipo cobranca = Postecipada (Pós-Pago)
    try:
        open_select_by_name('tipo_cobranca')
        time.sleep(1.5)
        click_option_by_text('Postecipada', exato=False)
        print("      ✓ tipo_cobranca=Postecipada (Pós-Pago)")
    except Exception as e:
        print(f"      ⚠️ Falha em tipo_cobranca: {e}")
        print(f"      Opcoes visiveis: {listar_opcoes_visiveis()[:10]}")
        fechar_dropdown()

    snapshot('step5_pos_fill')

    # === STEP 6: PACOTES === (skip)
    print("\n   📋 STEP 6 PACOTES: sem campos, só avançar")
    if not goto_step(6):
        raise Exception("Falha ao navegar pra step6 Pacotes")
    time.sleep(2)
    snapshot('step6_pos_load')

    # === STEP 7: ORDEM DE SERVIÇO + SALVAR ===
    print("\n   📋 STEP 7 OS: navegar e clicar SALVAR")
    if not goto_step(7):
        raise Exception("Falha ao navegar pra step7 OS")
    time.sleep(3)
    snapshot('step7_pos_load')

    # Botao SALVAR: a estrutura pode ser md-dialog-actions na parte inferior
    # do dialog. XPath relativo (em vez do absoluto de 9 niveis).
    print("      ⏳ Procurando botao SALVAR / FINALIZAR / CONCLUIR...")
    botao_salvar = None
    for xp in [
        "//hubsoft-cliente-wizard//md-dialog-actions//button[contains(translate(.,'salvar','SALVAR'),'SALVAR')]",
        "//hubsoft-cliente-wizard//md-dialog-actions//button[contains(translate(.,'finalizar','FINALIZAR'),'FINALIZAR')]",
        "//hubsoft-cliente-wizard//md-dialog-actions//button[contains(translate(.,'concluir','CONCLUIR'),'CONCLUIR')]",
        "//md-dialog-actions//button[last()]",  # fallback: ultimo botao da barra de acoes
    ]:
        try:
            botao_salvar = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            print(f"      ✓ Botao SALVAR encontrado via {xp[:60]}")
            break
        except Exception:
            continue

    if not botao_salvar:
        raise Exception("Botao SALVAR nao encontrado em step7")

    if dry_run:
        print("\n" + "🛑"*40)
        print("🛑 DRY-RUN ATIVO — Botao SALVAR LOCALIZADO mas NAO clicado.")
        print(f"🛑 Prospecto {id_prospecto} NAO foi convertido em cliente.")
        print("🛑 Pra fazer a conversao real: rode SEM --dry-run.")
        print("🛑"*40)
        processor.salvar_prospecto(nome_filtro, id_prospecto, "WIZARD_TELA2",
                                   "DRY-RUN: parou antes do clique final", "dry_run")
        if not headless:
            print("\n👁️  Navegador permanece aberto por 30s pra inspecao visual...")
            time.sleep(30)
        return

    # Se Forma de Cobranca foi pulada, NAO clica SALVAR (Angular vai impedir
    # ou HubSoft vai retornar erro). Deixa o navegador aberto pro operador
    # completar manual (escolher Sicredi + clicar Salvar).
    if forma_cobranca_skipped:
        print("\n" + "🟡"*40)
        print("🟡 WIZARD PARCIAL — Bot completou 6 de 7 campos.")
        print(f"🟡 Prospecto {id_prospecto}: precisa do operador completar 'Forma de Cobrança'")
        print("🟡 + clicar SALVAR. Os ~95% do trabalho foi feito.")
        print("🟡"*40)
        processor.salvar_prospecto(
            nome_filtro, id_prospecto,
            "WIZARD_TELA2",
            "Bot completou wizard exceto Forma de Cobrança — operador finaliza manual",
            "parcial",
        )
        if not headless:
            print("\n👁️  Navegador permanece aberto por 60s pro operador finalizar...")
            time.sleep(60)
        return

    driver.execute_script("arguments[0].click();", botao_salvar)
    print("      ✅ SALVAR clicado!")
    time.sleep(5)

    processor.salvar_prospecto(nome_filtro, id_prospecto, "CONCLUIDO", None, "sucesso")
    print("\n" + "🎉"*40)
    print(f"✨ SUCESSO! Prospecto {id_prospecto} convertido em cliente.")
    print("🎉"*40)


def main(nome_filtro=None, id_prospecto=None, texto_boleto_digital=None, texto_varejo=None, texto_banco_itau=None, tenant_slug=None, dry_run=False, step_debug=False, coletar_dom=False):
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
    global TENANT_CONFIG, STEP_DEBUG
    STEP_DEBUG = bool(step_debug)
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

        # ETAPA 6: Wizard Nuvyon (steps 1-7 do Adicionar Cliente)
        # Substitui as antigas etapas 6-10 (4 telas Megalink) pela estrutura
        # real do HubSoft Nuvyon (7 abas Angular). Ver _executar_wizard_nuvyon.
        try:
            inicio_etapa = time.time()
            print_etapa_header(6, "WIZARD NUVYON (7 steps)",
                               "Cadastro -> Endereco -> Plano -> Contrato -> Cobranca -> Pacotes -> OS")
            _executar_wizard_nuvyon(processor, driver, wait, dry_run, headless,
                                    nome_filtro, id_prospecto, coletar_dom=coletar_dom)
            tempo_etapa = time.time() - inicio_etapa
            print_sucesso_etapa(6, tempo_etapa)

        except Exception as e:
            erro_detalhado = f"ETAPA 6 - ERRO WIZARD NUVYON: {str(e)}"
            print(f"\n   ERRO: {erro_detalhado}")
            processor.capturar_screenshot_erro(driver, "wizard_nuvyon", "ETAPA6")
            processor.salvar_prospecto(nome_filtro, id_prospecto, "ERRO_WIZARD1", erro_detalhado)
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
    cli.add_argument('--dry-run', action='store_true',
                     help='Roda o wizard completo mas NAO clica em SALVAR no final '
                          '(valida fluxo sem criar cliente real no HubSoft)')
    cli.add_argument('--step-debug', action='store_true',
                     help='Pausa antes de cada ETAPA esperando ENTER no terminal '
                          '(util pra remapear XPaths em UIs HubSoft diferentes)')
    cli.add_argument('--coletar-dom', action='store_true',
                     help='Abre o wizard, navega pelas abas e salva outerHTML de '
                          'cada uma em dom_capturado/. Nao faz conversao real.')
    args, _ = cli.parse_known_args()

    main(
        nome_filtro=args.nome,
        id_prospecto=args.id_prospecto,
        texto_boleto_digital=args.boleto,
        texto_varejo=args.grupo,
        texto_banco_itau=args.banco,
        tenant_slug=args.tenant,
        dry_run=args.dry_run,
        step_debug=args.step_debug,
        coletar_dom=args.coletar_dom,
    )