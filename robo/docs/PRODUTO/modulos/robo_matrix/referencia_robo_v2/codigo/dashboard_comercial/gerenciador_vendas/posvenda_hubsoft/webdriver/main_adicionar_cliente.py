"""
Webdriver: ADICIONAR CLIENTE na instância HubSoft DELLINK.

URL: https://dellink.hubsoft.com.br/cliente/adicionar/

Modo de operação atual: EXPLORATÓRIO + DRY-RUN.
  - Captura screenshot ANTES e DEPOIS de preencher cada aba
    (pra documentar as abas que ainda não conhecemos: 04 Contrato,
    06 Pacotes, 07 Ordem de Serviço).
  - Preenche o cadastro completo com dados do cliente de teste
    (DARLAN — fixo no `DADOS_TESTE` abaixo).
  - Avança por todas as abas até a tela final do SALVAR.
  - **NÃO clica SALVAR** — pode ser ativado depois com --salvar.

Reaproveita helpers do `main_novo_servico.py` no diretório pai (driver
setup, clique via JS, _md_select_por_label, _filtrar_e_clicar_virtual_repeat).
"""

import argparse
import datetime as _dt
import logging
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Reaproveita helpers do módulo irmão (mesmo pacote webdriver/).
# Import duplo: relativo quando carregado como pacote (Django) e absoluto
# (sys.path) quando rodado como script solto (debug/CLI).
try:
    from .main_novo_servico import (  # noqa: E402
        configurar_driver,
        clicar,
        esperar_clicavel,
        esperar_visivel,
        _filtrar_e_clicar_virtual_repeat,
        _md_select_por_label,
        TIMEOUT_PADRAO, PAUSA_CURTA, PAUSA_MEDIA, PAUSA_LONGA,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from main_novo_servico import (  # noqa: E402
        configurar_driver,
        clicar,
        esperar_clicavel,
        esperar_visivel,
        _filtrar_e_clicar_virtual_repeat,
        _md_select_por_label,
        TIMEOUT_PADRAO, PAUSA_CURTA, PAUSA_MEDIA, PAUSA_LONGA,
    )

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger("adicionar_cliente")

MEGALINK_URL_BASE = os.environ.get(
    'MEGALINK_URL_BASE', 'https://megalinktelecom.hubsoft.com.br'
)


# ════════════════════════════════════════════════════════════════════
#  Dados do cliente de teste (DARLAN — conforme imagens enviadas)
# ════════════════════════════════════════════════════════════════════
@dataclass
class DadosCliente:
    # 01 - CADASTRO
    tipo_cliente: str = 'fisica'  # 'fisica' | 'juridica'
    nome: str = 'DARLAN DA SILVA COSTA VELOZO'
    cpf_cnpj: str = '621.382.013-25'
    nome_social: str = 'DARLAN DA SILVA COSTA VELOZO'
    data_nascimento: str = '14/11/2002'   # dd/mm/aaaa
    telefone_1: str = '(86) 99514-1449'
    telefone_2: str = '(86) 99960-3981'
    email_principal: str = 'darlanveloso14@gmail.com'
    email_secundario: str = 'josesoousalima@gmail.com'
    grupo_cliente: str = 'Boleto Digital'

    # 02 - ENDEREÇO
    cep: str = '64020-340'
    numero: str = '20'
    complemento: str = 'q51'
    referencia: str = 'CASA DA ESQUINA'
    usar_endereco_cobranca: bool = True
    # Fallback se o CEP não autopreencher os campos:
    estado_uf: str = ''        # ex: 'PI' ou 'PIAUÍ'
    cidade: str = ''           # ex: 'PICOS' ou 'TERESINA/PI'
    bairro: str = ''           # ex: 'RURAL'
    rua: str = ''              # ex: 'ANGICO TORTO'

    # 03 - PLANO
    plano_titulo: str = '(VAREJO) 620 MB TOP'    # match parcial no dropdown
    id_plano_megalink: str = ''  # id_servico no banco megalink (usado pra match exato)
    grupo_servico: str = 'Varejo'   # grupo correto (NÃO "Varejo - Regional 5")
    vendedor: str = 'DARLAN VELOZO'
    validade_contrato_meses: str = '12'

    # 05 - COBRANÇA
    forma_cobranca: str = 'BANCO ITAU'
    dia_vencimento: str = '1'
    tipo_cobranca: str = 'Postecipada (Pós-Pago)'
    carne: str = 'Sim'
    cobrar_taxa_instalacao: str = 'Não'
    gerar_carne: str = 'Não Gerar Carnê'

    # PÓS-SALVAR — autenticação PPPoE (vem do CSV: login, login_password)
    login_pppoe: str = ''
    senha_pppoe: str = ''


DADOS_TESTE = DadosCliente()


# ════════════════════════════════════════════════════════════════════
#  Login no DELLINK (mesmo pattern do megalink)
# ════════════════════════════════════════════════════════════════════
def fazer_login(driver, wait, usuario: str, senha: str):
    log.info("ETAPA 1: login no DELLINK")
    driver.get(f"{MEGALINK_URL_BASE}/login")
    email_in = WebDriverWait(driver, 45).until(
        EC.presence_of_element_located((By.NAME, "email"))
    )
    email_in.clear(); email_in.send_keys(usuario)
    time.sleep(PAUSA_CURTA)

    # Botão Validar (HubSoft confirma o email primeiro)
    try:
        btn_validar = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Validar')]")
            )
        )
        btn_validar.click()
        log.info("  Validar clicado")
    except TimeoutException:
        log.info("  Sem botão 'Validar' — talvez fluxo de 1 etapa")

    pwd = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
    )
    pwd.clear(); pwd.send_keys(senha)
    time.sleep(PAUSA_CURTA)
    esperar_clicavel(wait, "//button[contains(., 'Entrar')]").click()
    log.info("  Entrar clicado")
    time.sleep(PAUSA_LONGA)
    log.info("✓ Login enviado")


def esperar_dashboard(driver, timeout: int = 30) -> bool:
    """Espera o login completar — critério SIMPLES e CONFIÁVEL:
      - URL não contém '/login' (mudou para /dashboard, /home, etc)
      - Body tem conteúdo renderizado (não está em branco)
    Retorna True se chegou ao dashboard; False se ainda preso no login
    após `timeout`."""
    log.info("  aguardando dashboard (sair de /login)...")
    fim = time.time() + timeout
    while time.time() < fim:
        cur_url = (driver.current_url or '')
        if '/login' not in cur_url and cur_url and not cur_url.endswith('://'):
            # Aguarda body com algo renderizado
            try:
                body = driver.find_element(By.TAG_NAME, 'body')
                if body.is_displayed() and (body.text or '').strip():
                    # Dá uma folga adicional pro AngularJS bindar
                    time.sleep(1.5)
                    log.info(f"  ✓ dashboard pronto (url={cur_url})")
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    log.warning(f"  ⚠ login não concluiu em {timeout}s (url={driver.current_url!r})")
    return False


# ════════════════════════════════════════════════════════════════════
#  Helpers de wizard
# ════════════════════════════════════════════════════════════════════
WIZARD_ROOT = "//hubsoft-cliente-wizard | //*[contains(@class,'cliente-adicionar')]"

# Botão Avançar — wizard de adicionar cliente
BTN_AVANCAR_XPATH = (
    "//button["
    "contains(., 'Avançar') or contains(., 'AVANÇAR') or "
    "contains(., 'Próximo') or contains(., 'PRÓXIMO') or "
    "contains(., 'Continuar') or contains(., 'CONTINUAR')"
    "]"
)


def _input_por_label(driver, label_texto: str):
    """Acha input visível cujo label flutuante contém `label_texto`."""
    candidatos = [
        f"//md-input-container[.//label[contains(normalize-space(.), \"{label_texto}\")]]//input",
        f"//md-input-container[.//label[normalize-space(.)=\"{label_texto}\"]]//input",
        f"//*[contains(@class,'label') and contains(normalize-space(.), \"{label_texto}\")]/following::input[1]",
    ]
    for xp in candidatos:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for e in els:
                if e.is_displayed():
                    return e
        except Exception:
            continue
    raise NoSuchElementException(f"input com label {label_texto!r} não encontrado")


def _preencher_texto(driver, wait, label: str, valor: str, *, log_label=None):
    if not valor:
        return
    log.info(f"  {log_label or label}: {valor!r}")
    el = _input_por_label(driver, label)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].focus();", el)
    el.send_keys(Keys.CONTROL, 'a')
    el.send_keys(Keys.DELETE)
    el.send_keys(valor)
    time.sleep(0.3)


def _selecionar_radio_por_texto(driver, texto: str):
    """Seleciona um md-radio-button cujo label contém `texto`."""
    candidatos = [
        f"//md-radio-button[contains(normalize-space(.), \"{texto}\")]",
        f"//md-radio-group//*[contains(normalize-space(.), \"{texto}\")]/ancestor-or-self::md-radio-button",
    ]
    for xp in candidatos:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for e in els:
                if e.is_displayed():
                    clicar(driver, e)
                    return
        except Exception:
            continue
    raise NoSuchElementException(f"radio {texto!r} não encontrado")


def _ligar_switch_por_label(driver, label_texto: str):
    """Garante que um md-switch próximo a um label esteja LIGADO."""
    xp = (
        f"//*[contains(normalize-space(.), \"{label_texto}\")]"
        "/ancestor-or-self::*[descendant::md-switch][1]"
        "//md-switch"
    )
    try:
        sw = driver.find_element(By.XPATH, xp)
    except Exception:
        return
    if (sw.get_attribute("aria-checked") or "").lower() == "true":
        return
    clicar(driver, sw)
    time.sleep(0.3)


def _clicar_aba(driver, wait, nome_aba: str):
    """Clica numa aba do wizard pelo texto (ex: '02 - ENDEREÇO')."""
    xp = f"//*[self::md-tab or contains(@class,'tab')][contains(normalize-space(.), \"{nome_aba}\")]"
    el = esperar_clicavel(wait, xp)
    clicar(driver, el)
    time.sleep(PAUSA_MEDIA)


def avancar(driver, wait, contexto: str = ""):
    log.info(f"  AVANÇAR ({contexto})")
    btn = esperar_clicavel(wait, BTN_AVANCAR_XPATH)
    clicar(driver, btn)
    time.sleep(PAUSA_LONGA)


# ════════════════════════════════════════════════════════════════════
#  Preenchimento de cada aba
# ════════════════════════════════════════════════════════════════════
def preencher_aba_01_cadastro(driver, wait, d: DadosCliente):
    log.info("┌─ ABA 01 - CADASTRO ────────────────────")
    # Tipo cliente: Pessoa Física
    try:
        _selecionar_radio_por_texto(driver, 'Pessoa Física' if d.tipo_cliente == 'fisica' else 'Pessoa Jurídica')
        log.info(f"  Tipo: {d.tipo_cliente}")
    except Exception as e:
        log.warning(f"  Tipo cliente: {e}")

    _preencher_texto(driver, wait, 'Nome', d.nome)
    _preencher_texto(driver, wait, 'CPF', d.cpf_cnpj)
    _preencher_texto(driver, wait, 'Nome Social', d.nome_social)
    _preencher_texto(driver, wait, 'Nascimento', d.data_nascimento)
    _preencher_texto(driver, wait, 'Telefone 1', d.telefone_1)
    _preencher_texto(driver, wait, 'Telefone 2', d.telefone_2)
    _preencher_texto(driver, wait, 'Email Principal', d.email_principal)
    _preencher_texto(driver, wait, 'Email Secundário', d.email_secundario)

    # Grupo do Cliente (md-select)
    try:
        sel = _md_select_por_label_local(driver, wait, 'Grupo do Cliente')
        clicar(driver, sel)
        time.sleep(PAUSA_MEDIA)
        opt = esperar_clicavel(
            wait, f"//md-option[contains(normalize-space(.), \"{d.grupo_cliente}\")]"
        )
        clicar(driver, opt)
        log.info(f"  Grupo do Cliente: {d.grupo_cliente}")
    except Exception as e:
        log.warning(f"  Grupo do Cliente: {e}")
    time.sleep(PAUSA_MEDIA)


UF_NOME_COMPLETO = {
    'AC': 'ACRE', 'AL': 'ALAGOAS', 'AP': 'AMAPÁ', 'AM': 'AMAZONAS',
    'BA': 'BAHIA', 'CE': 'CEARÁ', 'DF': 'DISTRITO FEDERAL',
    'ES': 'ESPÍRITO SANTO', 'GO': 'GOIÁS', 'MA': 'MARANHÃO',
    'MT': 'MATO GROSSO', 'MS': 'MATO GROSSO DO SUL', 'MG': 'MINAS GERAIS',
    'PA': 'PARÁ', 'PB': 'PARAÍBA', 'PR': 'PARANÁ', 'PE': 'PERNAMBUCO',
    'PI': 'PIAUÍ', 'RJ': 'RIO DE JANEIRO', 'RN': 'RIO GRANDE DO NORTE',
    'RS': 'RIO GRANDE DO SUL', 'RO': 'RONDÔNIA', 'RR': 'RORAIMA',
    'SC': 'SANTA CATARINA', 'SP': 'SÃO PAULO', 'SE': 'SERGIPE',
    'TO': 'TOCANTINS',
}


def _normalizar_endereco(s: str) -> str:
    """Normaliza string para comparação fuzzy de endereços/bairros/etc."""
    import re as _re
    import unicodedata as _ud
    if not s: return ''
    s = str(s).upper().strip()
    s = ''.join(c for c in _ud.normalize('NFKD', s) if not _ud.combining(c))
    s = _re.sub(r'[^A-Z0-9 ]', ' ', s)
    return _re.sub(r'\s+', ' ', s).strip()


def _tokens_significativos(s: str) -> set:
    """Pega tokens >2 chars de um texto normalizado (ignora palavras curtas)."""
    return {t for t in _normalizar_endereco(s).split() if len(t) > 2}


def _autocomplete_fallback(driver, wait, label: str, valor: str,
                            permitir_livre: bool = True):
    """Para CEPs rurais que não autopreenchem: digita `valor` no
    md-autocomplete do `label`.

    Estratégia revisada (corrige bug histórico em endereços rurais):
    1. Digita o valor
    2. Lê as sugestões disponíveis
    3. Procura sugestão que tenha pelo menos 1 token significativo em comum
       com o valor digitado
    4. Se nenhuma bate, NÃO aceita 1ª sugestão cegamente — mantém texto
       livre (Hubsoft aceita texto livre em md-autocomplete para o salvar)
    5. Loga WARNING quando entrou em fallback livre, para revisão posterior

    Se o campo já tem valor, não toca.
    """
    if not valor:
        return
    try:
        input_el = driver.find_element(
            By.XPATH,
            f"//md-autocomplete[contains(@md-floating-label, \"{label}\")]//input | "
            f"//md-autocomplete//input[contains(@aria-label, \"{label}\")]"
        )
    except Exception:
        log.warning(f"  Endereço fallback: autocomplete {label!r} não encontrado")
        return
    val_atual = (input_el.get_attribute('value') or '').strip()
    if val_atual:
        log.info(f"  {label}: já preenchido com {val_atual!r}, mantendo")
        return
    try:
        input_el.click()
    except Exception:
        driver.execute_script("arguments[0].focus();", input_el)
    input_el.send_keys(valor)
    log.info(f"  {label}: digitando {valor!r}")
    # md-autocomplete tem md-delay="750" — espera o debounce + busca async
    # Aumentado pra autocomplete megalink que pode demorar mais
    time.sleep(PAUSA_LONGA + 3)

    # Lê sugestões disponíveis no dropdown — tenta múltiplas vezes pq pode
    # demorar pra renderizar
    sugestoes = []
    for tentativa in range(3):
        try:
            items = driver.find_elements(
                By.XPATH,
                "//ul[contains(@class,'md-autocomplete-suggestions')]/li | "
                "//md-virtual-repeat-container//li | "
                "//md-autocomplete-wrap//li"
            )
            for it in items[:30]:
                try:
                    txt = (it.text or '').strip()
                    if txt and (txt, it) not in sugestoes:
                        sugestoes.append((txt, it))
                except Exception:
                    pass
            if sugestoes:
                break
        except Exception:
            pass
        time.sleep(1.0)
    log.info(f"    {label}: {len(sugestoes)} sugestões — "
             f"{[s[0][:30] for s in sugestoes[:5]]}")

    # OPÇÃO A: critério SUBSTRING EXATA. Aceita sugestão só se o valor
    # digitado for substring exata da sugestão (normalizado, sem acentos)
    # ou vice-versa. Evita pegar ruas parecidas com nome diferente.
    valor_norm = _normalizar_endereco(valor)
    melhor_match = None
    for txt, it in sugestoes:
        sug_norm = _normalizar_endereco(txt)
        if not sug_norm:
            continue
        # Aceita se valor digitado está contido na sugestão, OU a sugestão
        # está totalmente contida no valor (cobre abreviações).
        if valor_norm in sug_norm or sug_norm in valor_norm:
            melhor_match = (txt, it, 'substring')
            break

    if melhor_match:
        txt, it, modo = melhor_match
        try:
            clicar(driver, it)
            time.sleep(PAUSA_MEDIA)
            val_final = (input_el.get_attribute('value') or '').strip()
            log.info(f"  {label}: selecionado {val_final!r} (match: {modo})")
        except Exception as e:
            log.warning(f"  {label}: falha ao clicar match — {e}")
    else:
        # Nenhuma sugestão bate com o que foi digitado — não aceita cegamente.
        if sugestoes and not permitir_livre:
            # Fallback histórico: pega 1ª opção (só se permitir_livre=False)
            try:
                input_el.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.5)
                input_el.send_keys(Keys.ENTER)
                time.sleep(PAUSA_MEDIA)
                val_final = (input_el.get_attribute('value') or '').strip()
                log.warning(f"  ⚠ {label}: sem match real, pegou 1ª sugestão "
                            f"{val_final!r} (valor original: {valor!r})")
            except Exception:
                pass
        else:
            # Permite texto livre: confirma com TAB (sem limpar) e fica fora do dropdown
            try:
                input_el.send_keys(Keys.TAB)
                time.sleep(0.3)
            except Exception:
                pass
            val_final = (input_el.get_attribute('value') or '').strip()
            if not val_final:
                # TAB pode ter limpado em algum md-autocomplete — re-digita
                try:
                    input_el.click()
                    input_el.send_keys(valor)
                    time.sleep(0.4)
                    # Confirma com blur via JS pra não limpar
                    driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('blur', {bubbles:true}));"
                        "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                        input_el)
                    time.sleep(0.3)
                    val_final = (input_el.get_attribute('value') or '').strip()
                except Exception:
                    pass
            log.warning(f"  ⚠ {label}: sem sugestão correspondente; mantendo "
                        f"texto livre {val_final!r} (esperado: {valor!r}) "
                        f"— REVISAR MANUALMENTE")


def preencher_aba_02_endereco(driver, wait, d: DadosCliente) -> list[str]:
    """Preenche aba endereço.
    Retorna lista de divergências detectadas (campo: csv vs hub).
    Lista vazia = endereço bate com CSV.
    """
    log.info("┌─ ABA 02 - ENDEREÇO ────────────────────")
    _preencher_texto(driver, wait, 'CEP', d.cep)
    log.info("  aguardando autopreenchimento do CEP...")
    time.sleep(PAUSA_LONGA + 1)

    uf = (d.estado_uf or '').strip().upper()
    estado_nome = UF_NOME_COMPLETO.get(uf, uf)
    _autocomplete_fallback(driver, wait, 'Estado', estado_nome)
    time.sleep(PAUSA_MEDIA)
    _autocomplete_fallback(driver, wait, 'Cidade', d.cidade)
    time.sleep(PAUSA_MEDIA)
    _autocomplete_fallback(driver, wait, 'Bairro', d.bairro)
    time.sleep(PAUSA_MEDIA)
    _autocomplete_fallback(driver, wait, 'Endereço', d.rua)
    time.sleep(PAUSA_MEDIA)

    _preencher_texto(driver, wait, 'Número', d.numero)
    _preencher_texto(driver, wait, 'Complemento', d.complemento)
    _preencher_texto(driver, wait, 'Referência', d.referencia)

    if d.usar_endereco_cobranca:
        _ligar_switch_por_label(driver, 'Usar o endereço Cadastral')

    time.sleep(PAUSA_MEDIA)

    # ===== VALIDAÇÃO: compara valor final dos campos com o esperado do CSV =====
    divergencias: list[str] = []

    def _ler_input_por_label(label: str) -> str:
        xps = [
            f"//md-input-container[.//label[normalize-space(.)={label!r}]]//input",
            f"//md-autocomplete[contains(@md-floating-label, {label!r})]//input",
            f"//md-autocomplete//input[contains(@aria-label, {label!r})]",
        ]
        for xp in xps:
            try:
                el = driver.find_element(By.XPATH, xp)
                v = (el.get_attribute('value') or '').strip()
                if v:
                    return v
            except Exception:
                continue
        return ''

    def _bate(csv_val: str, hub_val: str) -> bool:
        a = _normalizar_endereco(csv_val)
        b = _normalizar_endereco(hub_val)
        if not a:
            return True  # CSV vazio = OK
        if not b:
            return False
        return a in b or b in a

    checks = [
        ('Bairro', d.bairro, _ler_input_por_label('Bairro')),
        ('Endereço', d.rua, _ler_input_por_label('Endereço')),
        ('Número', d.numero, _ler_input_por_label('Número')),
    ]
    for campo, csv_val, hub_val in checks:
        if csv_val and not _bate(csv_val, hub_val):
            div = f"{campo}: csv={csv_val!r} hub={hub_val!r}"
            divergencias.append(div)
            log.warning(f"  ⚠ DIVERGE {div}")

    if divergencias:
        log.warning(f"  ⚠ Endereço com {len(divergencias)} divergência(s) — "
                    f"cliente será marcado para revisão manual")
    else:
        log.info("  ✓ Endereço idêntico ao CSV")

    return divergencias


def _selecionar_opcao_simples(driver, wait, md_select_el, texto_alvo: str,
                              match_first: bool = False):
    """Abre um md-select já localizado e clica em md-option pelo texto.
    Se `match_first=True`, clica na PRIMEIRA opção visível (útil quando há
    só uma opção, ex: Endereço de Instalação)."""
    clicar(driver, md_select_el)
    time.sleep(PAUSA_MEDIA)
    if match_first:
        opt = esperar_clicavel(wait, "//md-option[1]")
    else:
        opt = esperar_clicavel(
            wait, f"//md-option[contains(normalize-space(.), \"{texto_alvo}\")]"
        )
    clicar(driver, opt)
    time.sleep(PAUSA_MEDIA)


def _md_select_por_name(driver, wait, name: str, timeout: int = 10):
    """Localiza md-select pelo atributo `name` (mais estável que label).
    Usa presence_of_element_located (não exige clickable) — alguns
    md-select têm `ng-disabled` que se resolve só depois da animação
    do step anterior. Quem chama deve usar JS click pra contornar."""
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(
        (By.XPATH, f"//md-select[@name='{name}']")
    ))


def preencher_aba_03_plano(driver, wait, d: DadosCliente):
    log.info("┌─ ABA 03 - PLANO ────────────────────")

    # 1) ENDEREÇO DE INSTALAÇÃO — md-select name='cliente_servico_endereco_instalacao'
    # Esse campo é problemático: tem ng-disabled e o dropdown demora pra abrir.
    # Estratégia: scroll para o topo + Selenium native click + diagnóstico de DOM.
    sucesso_endereco = False
    try:
        sel = _md_select_por_name(
            driver, wait, 'cliente_servico_endereco_instalacao', timeout=15
        )
        # Scroll TOPO da página pra garantir viewport correto
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'start'});", sel
        )
        time.sleep(0.5)

        # Selenium native click (não JS) — funciona melhor em md-select
        try:
            sel.click()
            log.info("  Endereço Instalação: native click executado")
        except Exception as ne:
            log.warning(f"  native click falhou: {ne}, usando JS")
            driver.execute_script("arguments[0].click();", sel)

        # Espera o dropdown abrir
        time.sleep(PAUSA_LONGA)

        # Diagnóstico: lista quantos md-option apareceram
        opts = driver.find_elements(By.XPATH, "//md-option")
        visiveis = [o for o in opts if o.is_displayed()]
        log.info(f"  Endereço Instalação: {len(opts)} md-option no DOM, {len(visiveis)} visíveis")

        if visiveis:
            opt = visiveis[0]
            try:
                opt.click()
            except Exception:
                driver.execute_script("arguments[0].click();", opt)
            log.info(f"  Endereço de Instalação: clicado na 1ª opção visível")
            sucesso_endereco = True
        elif opts:
            # Forçar click no 1º via JS mesmo invisível
            opt = opts[0]
            driver.execute_script("arguments[0].click();", opt)
            log.info(f"  Endereço de Instalação: força-clicado na 1ª (forçado)")
            sucesso_endereco = True

    except Exception as e:
        log.warning(f"  Endereço Instalação: falha — {e}")

    if not sucesso_endereco:
        log.error("  ❌ Endereço de Instalação NÃO foi preenchido — aba 03 incompleta")
        # Diagnóstico extra: dumpa estado do select
        try:
            sel2 = driver.find_element(By.XPATH, "//md-select[@name='cliente_servico_endereco_instalacao']")
            log.error(f"     aria-disabled={sel2.get_attribute('aria-disabled')!r} "
                      f"aria-expanded={sel2.get_attribute('aria-expanded')!r} "
                      f"class={(sel2.get_attribute('class') or '')[:120]!r}")
        except Exception:
            pass
    time.sleep(PAUSA_MEDIA)

    # 2) PLANO / SERVIÇO — md-autocomplete[@md-floating-label='Plano / Serviço']
    try:
        # Acha o input dentro do autocomplete
        input_plano = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
            (By.XPATH,
             "//md-autocomplete[@md-floating-label='Plano / Serviço']//input | "
             "//md-autocomplete//input[@aria-label='Plano / Serviço']")
        ))
        try:
            input_plano.click()
        except Exception:
            driver.execute_script("arguments[0].focus();", input_plano)
        # Espera dropdown abrir e backend popular sugestões iniciais
        time.sleep(PAUSA_LONGA + 1)
        # Chave de busca: digita o NOME EXATO do plano (send_keys —
        # o autocomplete megalink só dispara filtro com eventos de teclado
        # reais; JS dispatch quebra o filtro).
        chave_busca = d.plano_titulo
        input_plano.send_keys(chave_busca)
        log.info(f"  Plano: digitando filtro {chave_busca!r} "
                 f"(id_plano_megalink={d.id_plano_megalink!r})")
        # Espera autocomplete buscar (md-delay="750" + AJAX)
        time.sleep(PAUSA_LONGA + 3)

        alvo_norm = _normalizar_endereco(d.plano_titulo)
        opt = None
        match_modo = ''
        sugestoes_plano = []

        # Container do dropdown (pode ser md-virtual-repeat-container ou
        # ul.md-autocomplete-suggestions)
        try:
            container = driver.find_element(
                By.XPATH,
                "//md-virtual-repeat-container | "
                "//ul[contains(@class,'md-autocomplete-suggestions')]"
            )
        except Exception:
            container = None

        # Loop com early-break: a cada lote de items renderizados, verifica
        # match exato OU 'contém' em ambas direções.
        for tent in range(30):
            try:
                items_plano = driver.find_elements(
                    By.XPATH,
                    "//ul[contains(@class,'md-autocomplete-suggestions')]/li | "
                    "//md-virtual-repeat-container//li"
                )
            except Exception:
                items_plano = []

            for it in items_plano:
                try:
                    t = (it.text or '').strip()
                    if not t or any(t == s[0] for s in sugestoes_plano):
                        continue
                    sugestoes_plano.append((t, it))
                    tn = _normalizar_endereco(t)
                    # Early-break com hierarquia de match dentro do loop
                    if tn == alvo_norm:
                        opt, match_modo = it, 'exato'; break
                    if alvo_norm and alvo_norm in tn:
                        opt, match_modo = it, 'contém'; break
                    if tn and tn in alvo_norm:
                        opt, match_modo = it, 'sub-versão'; break
                except Exception:
                    pass
            if opt is not None:
                break
            if container is None:
                break
            try:
                driver.execute_script(
                    "arguments[0].scrollTop += arguments[0].clientHeight;",
                    container,
                )
                time.sleep(0.3)
            except Exception:
                break

        log.info(f"    Plano: {len(sugestoes_plano)} sugestões inspecionadas "
                 f"em {tent + 1} iterações")
        if opt is None:
            if sugestoes_plano:
                # NÃO cai cegamente — aborta com erro pra revisão
                erros = [s[0] for s in sugestoes_plano[:5]]
                raise TimeoutException(
                    f"NENHUMA sugestão bate com {d.plano_titulo!r}. "
                    f"Disponíveis: {erros}"
                )
            else:
                raise TimeoutException("nenhuma sugestão de plano apareceu")
        clicar(driver, opt)
        log.info(f"  Plano selecionado: {d.plano_titulo} (match: {match_modo})")
    except Exception as e:
        log.warning(f"  Plano: falha — {e}")
    time.sleep(PAUSA_MEDIA)

    # 3) GRUPOS — md-select name='grupo' (multiple)
    try:
        sel = _md_select_por_name(driver, wait, 'grupo')
        clicar(driver, sel)
        time.sleep(PAUSA_MEDIA)
        opt = esperar_clicavel(
            wait, f"//md-option[contains(normalize-space(.), \"{d.grupo_servico}\")]"
        )
        clicar(driver, opt)
        # Multiple → precisa fechar com ESC
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass
        log.info(f"  Grupos: {d.grupo_servico}")
    except Exception as e:
        log.warning(f"  Grupos: {e}")
    time.sleep(PAUSA_MEDIA)

    # 4) DATA DA VENDA — preenche se vazio
    try:
        el = _input_por_label(driver, 'Data da Venda')
        val_atual = (el.get_attribute('value') or '').strip()
        if not val_atual:
            hoje = _dt.date.today().strftime('%d/%m/%Y')
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].focus();", el)
            el.send_keys(hoje)
            log.info(f"  Data da Venda: {hoje}")
        else:
            log.info(f"  Data da Venda: já {val_atual!r}")
    except Exception as e:
        log.warning(f"  Data da Venda: {e}")
    time.sleep(PAUSA_MEDIA)

    # 5) VENDEDOR — md-select name='vendedor'
    try:
        sel = _md_select_por_name(driver, wait, 'vendedor')
        clicar(driver, sel)
        time.sleep(PAUSA_MEDIA)
        opt = esperar_clicavel(
            wait, f"//md-option[contains(normalize-space(.), \"{d.vendedor}\")]"
        )
        clicar(driver, opt)
        log.info(f"  Vendedor: {d.vendedor}")
    except Exception as e:
        log.warning(f"  Vendedor: {e}")
    time.sleep(PAUSA_MEDIA)

    # 6) VALIDADE — pode já vir default 12; preenche se vazio
    try:
        el = _input_por_label(driver, 'Validade')
        val_atual = (el.get_attribute('value') or '').strip()
        if val_atual != d.validade_contrato_meses:
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].focus();", el)
            el.send_keys(Keys.CONTROL, 'a'); el.send_keys(Keys.DELETE)
            el.send_keys(d.validade_contrato_meses)
            log.info(f"  Validade: {d.validade_contrato_meses}")
        else:
            log.info(f"  Validade: já {val_atual!r}")
    except Exception as e:
        log.warning(f"  Validade: {e}")
    time.sleep(PAUSA_MEDIA)


def _select_por_hs_label(driver, wait, hs_label: str, valor: str,
                         *, timeout: int = 10, log_label: str = None):
    """Abre um <hubsoft-select-virtual-repeat hs-label='X'> e seleciona
    o item cujo texto contém `valor` (usa o filtro interno do dropdown).
    Funciona pra Forma de Cobrança, Carnê, etc.
    """
    rotulo = log_label or hs_label
    try:
        # Acha o md-select dentro do wrapper
        sel = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((
                By.XPATH,
                f"//hubsoft-select-virtual-repeat[@hs-label=\"{hs_label}\"]//md-select"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sel)
        time.sleep(0.3)
        try:
            sel.click()
        except Exception:
            driver.execute_script("arguments[0].click();", sel)
        time.sleep(PAUSA_MEDIA)
        # Usa helper de filtro (já testado no megalink)
        _filtrar_e_clicar_virtual_repeat(driver, wait, valor)
        log.info(f"  {rotulo}: {valor!r}")
        time.sleep(PAUSA_MEDIA)
        return True
    except Exception as e:
        log.warning(f"  {rotulo}: {e}")
        return False


def preencher_aba_05_cobranca(driver, wait, d: DadosCliente):
    log.info("┌─ ABA 05 - COBRANÇA ────────────────────")

    def _select_por_name(name: str, valor: str, *, timeout: int = 10,
                         log_label: str = None):
        rotulo = log_label or name
        try:
            sel = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, f"//md-select[@name=\"{name}\"]")
                )
            )
        except Exception as e:
            log.warning(f"  {rotulo}: {e}")
            return False

        # Tenta 3 estratégias de abertura (igual Endereço de Instalação)
        opts_visiveis = []
        for tentativa, descricao in enumerate([
            'scrollTop + native click',
            'click no md-select-value interno',
            'JS click direto',
        ], start=1):
            try:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.3)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sel)
                time.sleep(0.3)

                if tentativa == 1:
                    sel.click()
                elif tentativa == 2:
                    val_el = sel.find_element(
                        By.XPATH, ".//md-select-value | .//*[contains(@class,'md-select-value')]"
                    )
                    driver.execute_script("arguments[0].click();", val_el)
                else:
                    driver.execute_script("arguments[0].click();", sel)

                time.sleep(PAUSA_MEDIA)
                opts_visiveis = [
                    o for o in driver.find_elements(By.XPATH, "//md-option")
                    if o.is_displayed()
                ]
                if opts_visiveis:
                    break
            except Exception as e:
                log.warning(f"  {rotulo} tentativa {tentativa} ({descricao}): {e}")
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                except Exception:
                    pass

        if not opts_visiveis:
            log.warning(f"  {rotulo}: dropdown não abriu após 3 tentativas")
            return False

        # Escolhe opção com TEXT EXATAMENTE igual `valor` (case-insens) primeiro
        # Procura entre TODAS as md-option (mesmo as fora da viewport).
        valor_l = valor.strip().lower()

        def _achar_alvo_qualquer():
            """Acha por TEXTO (mesmo fora da viewport). Faz scrollIntoView
            antes de retornar pra ficar clicável."""
            # Match exato primeiro
            todos = driver.find_elements(By.XPATH, "//md-option")
            for o in todos:
                try:
                    txt = (o.text or '').strip().lower()
                    # AngularJS pode ter texto vazio se elemento fora da viewport;
                    # tenta também atributos
                    if not txt:
                        txt = (o.get_attribute('aria-label') or '').strip().lower()
                    if txt == valor_l:
                        return o, 'exato'
                except Exception:
                    continue
            # Sem exato, tenta "contém" (mas evita falso positivo: '5' não casa com '15'/'25')
            for o in todos:
                try:
                    txt = (o.text or '').strip().lower()
                    if not txt:
                        txt = (o.get_attribute('aria-label') or '').strip().lower()
                    # Só aceita "contém" se a string for parecida em tamanho (não substr)
                    if valor_l in txt and len(txt) <= len(valor_l) + 5:
                        return o, 'contém'
                except Exception:
                    continue
            return None, None

        alvo, modo = _achar_alvo_qualquer()
        if alvo is None:
            # Diagnóstico: lista md-option visíveis na primeira tentativa
            try:
                todos = driver.find_elements(By.XPATH, "//md-option")
                textos = [(o.text or '').strip() for o in todos[:30]]
                visiveis = [o.is_displayed() for o in todos[:30]]
                log.warning(f"  diag: {len(todos)} md-option no DOM; "
                            f"primeiros textos={textos[:10]} visíveis={sum(visiveis)}")
            except Exception:
                pass
            # Tenta scroll dentro do container (último recurso pra virtual scroll)
            for _ in range(20):
                try:
                    container = driver.find_element(
                        By.XPATH,
                        "//md-select-menu//md-content | //md-virtual-repeat-container"
                    )
                    driver.execute_script(
                        "arguments[0].scrollTop += arguments[0].clientHeight * 0.7;",
                        container,
                    )
                    time.sleep(0.3)
                    alvo, modo = _achar_alvo_qualquer()
                    if alvo is not None:
                        break
                except Exception:
                    break

        # Antes de clicar: scrollIntoView pra garantir que está clicável
        if alvo is not None:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", alvo)
                time.sleep(0.3)
            except Exception:
                pass

        if alvo is None:
            log.warning(f"  {rotulo}: '{valor}' não encontrado em nenhum scroll — fechando dropdown")
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
            return False

        try:
            alvo.click()
        except Exception:
            driver.execute_script("arguments[0].click();", alvo)
        log.info(f"  {rotulo}: {alvo.text.strip()!r} (match: {modo})")
        time.sleep(PAUSA_MEDIA)
        return True

    # 1) Forma de Cobrança — hubsoft-select-virtual-repeat (4 itens com filtro)
    _select_por_hs_label(driver, wait, 'Forma de Cobrança', d.forma_cobranca)

    # Após escolher forma, novos campos (Carnê, Taxa, etc.) aparecem
    time.sleep(PAUSA_LONGA)

    # 2) Dia de Vencimento — md-select simples (name='vencimento')
    # SICOOB filtra dias disponíveis (ex.: só ~15 dias). Se exato falhar,
    # cai para o próximo dia maior disponível (ou maior disponível, se nenhum >).
    if not _select_por_name('vencimento', d.dia_vencimento,
                            log_label='Dia de Vencimento'):
        log.warning(f"  Dia '{d.dia_vencimento}' não disponível — buscando fallback")
        try:
            sel = driver.find_element(By.XPATH, "//md-select[@name='vencimento']")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sel)
            sel.click()
            time.sleep(1.2)
            # scroll up até o topo do container pra reler
            for _ in range(8):
                try:
                    c = driver.find_element(By.XPATH,
                        "//md-select-menu//md-content | //md-virtual-repeat-container")
                    driver.execute_script("arguments[0].scrollTop = 0;", c)
                except Exception:
                    pass
                break
            disponiveis = []
            seen = set()
            for _ in range(20):
                opts = driver.find_elements(By.XPATH, "//md-option")
                for o in opts:
                    t = (o.text or '').strip()
                    if t.isdigit() and t not in seen:
                        seen.add(t)
                        disponiveis.append(int(t))
                try:
                    c = driver.find_element(By.XPATH,
                        "//md-select-menu//md-content | //md-virtual-repeat-container")
                    driver.execute_script(
                        "arguments[0].scrollTop += arguments[0].clientHeight * 0.7;", c)
                    time.sleep(0.25)
                except Exception:
                    break
            disponiveis = sorted(set(disponiveis))
            log.info(f"  dias disponíveis no SICOOB: {disponiveis}")
            pedido = int(d.dia_vencimento)
            maiores = [x for x in disponiveis if x > pedido]
            escolhido = str(maiores[0] if maiores else (disponiveis[-1] if disponiveis else pedido))
            log.info(f"  fallback dia_vencimento: {d.dia_vencimento} -> {escolhido}")
            # Fecha dropdown e seleciona o novo dia
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
            time.sleep(0.5)
            _select_por_name('vencimento', escolhido, log_label='Dia de Vencimento (fb)')
        except Exception as e:
            log.error(f"  fallback dia_vencimento falhou: {e}")

    # 3) Tipo de Cobrança — geralmente já vem preenchido (name='tipo_cobranca')
    _select_por_name('tipo_cobranca', d.tipo_cobranca,
                     log_label='Tipo de Cobrança', timeout=5)

    # 4) Carnê — hubsoft-select-virtual-repeat (provavelmente)
    if not _select_por_hs_label(driver, wait, 'Carnê', d.carne, timeout=5):
        _select_por_name('carne', d.carne, timeout=3, log_label='Carnê')

    # 5) Cobrar Taxa de Instalação
    if not _select_por_hs_label(driver, wait, 'Cobrar Taxa de Instalação',
                                d.cobrar_taxa_instalacao, timeout=5):
        for candidato in ['cobrar_taxa_instalacao', 'cobrar_taxa']:
            if _select_por_name(candidato, d.cobrar_taxa_instalacao,
                                timeout=3, log_label=f'Cobrar Taxa ({candidato})'):
                break

    # 6) Gerar Carnê
    if not _select_por_hs_label(driver, wait, 'Gerar Carnê',
                                d.gerar_carne, timeout=5):
        _select_por_name('gerar_carne', d.gerar_carne,
                         timeout=3, log_label='Gerar Carnê')


def _md_select_por_label_local(driver, wait, label_texto: str,
                               timeout: int = 8):
    """Versão local com fallbacks — tenta achar md-select por várias
    estruturas (label dentro de md-input-container, label como sibling,
    ng-model com nome similar etc.)."""
    candidatos = [
        # md-input-container com <label> contendo o texto
        f"//md-input-container[.//label[contains(normalize-space(.), \"{label_texto}\")]]//md-select",
        # texto em qualquer elemento, sobe pra md-input-container e acha md-select
        f"//*[contains(normalize-space(.), \"{label_texto}\")]/ancestor::md-input-container[1]//md-select",
        # texto e o md-select é o próximo no DOM
        f"//*[self::label or self::span or self::div][contains(normalize-space(.), \"{label_texto}\")]/following::md-select[1]",
    ]
    last_err = None
    for xp in candidatos:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            return el
        except TimeoutException as e:
            last_err = e
            continue
    raise (last_err or TimeoutException(
        f"md-select com label {label_texto!r} não encontrado"
    ))


# ════════════════════════════════════════════════════════════════════
#  PÓS-SALVAR — habilitar serviço e editar autenticação PPPoE
# ════════════════════════════════════════════════════════════════════
def _obter_id_cliente_pos_save(driver, cpf_cnpj: str):
    """Tenta obter id_cliente do URL (após save o dellink redireciona).
    Se não conseguir, busca no banco do dellink pelo CPF (mais recente)."""
    import re
    try:
        url = driver.current_url or ''
        m = re.search(r'/cliente/editar/(\d+)', url)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    # Fallback DB
    try:
        import psycopg2
        cpf = ''.join(c for c in (cpf_cnpj or '') if c.isdigit())
        if not cpf:
            return None
        conn = psycopg2.connect(
            host=os.environ['DELLINK_DB_HOST'],
            port=os.environ['DELLINK_DB_PORT'],
            dbname=os.environ['DELLINK_DB_NAME'],
            user=os.environ['DELLINK_DB_USER'],
            password=os.environ['DELLINK_DB_PASSWORD'],
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT id_cliente FROM cliente "
            "WHERE cpf_cnpj=%s ORDER BY data_cadastro DESC NULLS LAST LIMIT 1",
            (cpf,),
        )
        r = cur.fetchone()
        cur.close(); conn.close()
        return int(r[0]) if r else None
    except Exception as e:
        log.warning(f"  fallback DB falhou: {e}")
        return None


def _clicar_menu_card_servico(driver, wait):
    """Abre o menu '⋮' do card de serviço."""
    xp = (
        "//hubsoft-cliente-servico-card-b2c//md-menu/button | "
        "//hubsoft-cliente-servico-card-base//md-menu/button | "
        "//md-card-header//md-menu/button"
    )
    btn = esperar_clicavel(wait, xp)
    clicar(driver, btn)
    time.sleep(PAUSA_MEDIA)


def habilitar_e_editar_autenticacao(driver, wait, d: DadosCliente,
                                    shot=lambda t: None) -> bool:
    """Após salvar o cliente, navega pra /servico, habilita o serviço e
    edita login/senha PPPoE. Retorna True se completou.
    """
    log.info("┌─ PÓS-SALVAR: habilitar serviço + editar autenticação ──")
    if not d.login_pppoe or not d.senha_pppoe:
        log.warning("  sem login/senha PPPoE no CSV — pulando habilitação")
        return False

    # 1) Resolver id_cliente
    id_cliente = _obter_id_cliente_pos_save(driver, d.cpf_cnpj)
    if not id_cliente:
        log.error("  não consegui resolver id_cliente — abortando")
        return False
    log.info(f"  id_cliente={id_cliente}")

    # 2) Navegar pra /servico
    url = f"{MEGALINK_URL_BASE}/cliente/editar/{id_cliente}/servico"
    log.info(f"  → {url}")
    driver.get(url)
    time.sleep(PAUSA_LONGA + 1)
    shot("16_pos_save_servico")

    # 3) Abrir menu ⋮
    _clicar_menu_card_servico(driver, wait)

    # 4) Clicar "Ativar" (match por texto — mais robusto)
    log.info("  Ativar serviço...")
    xp_ativar = (
        "//md-menu-content//button[@aria-label='Ativar'] | "
        "//md-menu-content//md-menu-item//button"
        "[normalize-space(.)='Ativar']"
    )
    try:
        btn_ativar = esperar_clicavel(wait, xp_ativar)
        clicar(driver, btn_ativar)
        time.sleep(PAUSA_MEDIA)
        shot("17_ativar_clicado")
    except Exception as e:
        log.warning(f"  'Ativar' não encontrado (talvez já ativo): {e}")
        # Fecha menu com ESC
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass

    # 5) Confirmar diálogo de habilitação
    try:
        btn_confirmar = WebDriverWait(driver, 8).until(EC.element_to_be_clickable(
            (By.XPATH, "//md-dialog/md-dialog-actions/button[2] | "
                       "//md-dialog//button[contains(., 'Confirmar') or "
                       "contains(., 'Sim') or contains(., 'OK')]")
        ))
        clicar(driver, btn_confirmar)
        time.sleep(PAUSA_LONGA)
        shot("18_habilitacao_confirmada")
    except TimeoutException:
        log.info("  sem diálogo de confirmação — provavelmente já ativo")

    # 6) Abrir menu ⋮ novamente
    _clicar_menu_card_servico(driver, wait)

    # 7) Clicar "Editar" (match por texto)
    log.info("  Editar serviço...")
    xp_editar = (
        "//md-menu-content//button[@aria-label='Editar'] | "
        "//md-menu-content//md-menu-item//button"
        "[normalize-space(.)='Editar']"
    )
    btn_editar = esperar_clicavel(wait, xp_editar)
    clicar(driver, btn_editar)
    time.sleep(PAUSA_LONGA + 1)
    shot("19_editar_aberto")

    # 8) Clicar na aba "Autenticação"
    log.info("  Aba Autenticação...")
    xp_aba_auth = (
        "//hubsoft-cliente-servico//md-nav-bar//ul/li[4]/button | "
        "//md-nav-bar//button[contains(., 'Autenticação')]"
    )
    btn_aba = esperar_clicavel(wait, xp_aba_auth)
    clicar(driver, btn_aba)
    time.sleep(PAUSA_LONGA)
    shot("20_aba_autenticacao")

    def _preencher_angular_input(el, valor: str, rotulo: str):
        """Limpa, digita e força sincronização com ng-model do AngularJS."""
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        # Limpa via select-all + delete
        el.send_keys(Keys.CONTROL, 'a')
        el.send_keys(Keys.DELETE)
        time.sleep(0.2)
        # Digita char-a-char (eventos keypress/keyup disparam $watch do AngularJS)
        for ch in valor:
            el.send_keys(ch)
        time.sleep(0.3)
        # Força sync com ng-model: set value via JS + disparar 'input'/'change'/'blur'
        # E faz $apply no scope AngularJS pra commitar
        driver.execute_script(
            "var el = arguments[0]; var v = arguments[1];"
            "el.value = v;"
            "el.dispatchEvent(new Event('input', {bubbles:true}));"
            "el.dispatchEvent(new Event('change', {bubbles:true}));"
            "try { var ng = window.angular;"
            "  if (ng && ng.element) {"
            "    var s = ng.element(el).scope();"
            "    var ctrl = ng.element(el).controller('ngModel');"
            "    if (ctrl) { ctrl.$setViewValue(v); ctrl.$commitViewValue(); ctrl.$render(); }"
            "    if (s) { s.$apply(); }"
            "  }"
            "} catch(e) { console.log('ng apply err', e); }",
            el, valor)
        time.sleep(0.4)
        lido = driver.execute_script("return arguments[0].value;", el)
        if lido != valor:
            log.warning(f"  ⚠ {rotulo}: valor lido {lido!r} != enviado {valor!r}")
        else:
            log.info(f"  ✓ {rotulo} sincronizado (lido={lido!r})")

    # 9) Alterar login — match pelo label "Login"
    log.info(f"  Login PPPoE: {d.login_pppoe!r}")
    xp_login = (
        "//md-input-container[.//label["
        "normalize-space(.)='Login' or normalize-space(.)='Login *' "
        "or starts-with(normalize-space(.), 'Login')"
        "]]//input"
    )
    input_login = esperar_clicavel(wait, xp_login)
    _preencher_angular_input(input_login, d.login_pppoe, 'Login')

    # 10) Alterar senha — match pelo label "Senha"
    log.info(f"  Senha PPPoE: {'*' * len(d.senha_pppoe)}")
    xp_senha = (
        "//md-input-container[.//label["
        "normalize-space(.)='Senha' or normalize-space(.)='Senha *' "
        "or starts-with(normalize-space(.), 'Senha')"
        "]]//input"
    )
    input_senha = esperar_clicavel(wait, xp_senha)
    _preencher_angular_input(input_senha, d.senha_pppoe, 'Senha')
    shot("21_login_senha_preenchidos")

    # 11) Confirmar fluxo de salvamento — pode haver "Alterações Pendentes"
    #     que precisa ser confirmado antes do SALVAR. Tenta detectar.
    time.sleep(1.0)
    xp_pendentes = (
        "//md-dialog/md-dialog-actions/div/button[1] | "
        "//md-dialog//button[contains(translate(., 'PENDÊNCIAS', 'pendências'), 'pendente')]"
    )
    pendentes_visivel = False
    try:
        btn_pend = driver.find_element(By.XPATH, xp_pendentes)
        pendentes_visivel = btn_pend.is_displayed() and btn_pend.is_enabled()
    except Exception:
        pendentes_visivel = False

    if pendentes_visivel:
        log.info("  Abrindo Alterações Pendentes...")
        clicar(driver, btn_pend)
        time.sleep(PAUSA_LONGA)
        shot("22_alteracoes_pendentes")
        try:
            log.info("  Confirmar alterações...")
            xp_confirmar_alt = (
                "//md-sidenav//md-list-item/div/button[2] | "
                "//md-sidenav//button[contains(., 'Confirmar')]"
            )
            btn_conf = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, xp_confirmar_alt)))
            clicar(driver, btn_conf)
            time.sleep(PAUSA_LONGA + 1)
            shot("23_alteracoes_confirmadas")
        except TimeoutException:
            log.warning("  sidenav Alterações Pendentes não tinha 'Confirmar' — seguindo")
    else:
        log.info("  Sem 'Alterações Pendentes' visível — indo direto pro SALVAR")
        shot("22_sem_pendentes")

    # 12) SALVAR final — botão azul canto inferior direito do dialog
    log.info("  SALVAR edição...")
    xp_salvar_final = (
        "//md-dialog//button[contains(translate(., 'salvar', 'SALVAR'), 'SALVAR')] | "
        "//md-dialog/md-dialog-actions//button[last()]"
    )
    btn_salvar = esperar_clicavel(wait, xp_salvar_final)
    clicar(driver, btn_salvar)
    time.sleep(PAUSA_LONGA * 2)
    shot("24_salvar_edicao_clicado")

    # 13) Verificar toast de sucesso final
    try:
        toast = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.XPATH, "//md-toast | //*[contains(@class,'toast') or "
                       "contains(@class,'snackbar')]")))
        log.info(f"  toast pós-SALVAR: {(toast.text or '').strip()[:200]!r}")
    except TimeoutException:
        log.info("  sem toast pós-SALVAR detectado")

    log.info("✅ Pós-save: serviço habilitado + auth atualizada")
    return True


# ════════════════════════════════════════════════════════════════════
#  Orquestrador
# ════════════════════════════════════════════════════════════════════
def executar(headless: bool = False,
             dry_run: bool = True,
             manter_aberto_segundos: int = 0,
             salvar: bool = False,
             dados: 'DadosCliente | None' = None,
             driver_existente=None,
             wait_existente=None,
             ja_logado: bool = False) -> dict:
    """Executa o fluxo de adicionar cliente. dry_run=True para antes do SALVAR.

    Se `dados=None`, usa DADOS_TESTE (DARLAN) hardcoded.

    Se `driver_existente` e `wait_existente` forem passados, REUSA a
    sessão (não cria driver novo, não fecha no final). Se `ja_logado=True`
    pula o login. Útil pra lote (uma sessão pra N clientes).
    """
    usuario = os.environ.get('USUARIO', '')
    senha = os.environ.get('SENHA', '')
    if not usuario or not senha:
        raise SystemExit("USUARIO/SENHA não definidos no .env (megalink)")

    d = dados if dados is not None else DADOS_TESTE
    log.info(f"Cliente alvo: {d.nome!r} CPF {d.cpf_cnpj!r}")

    # Driver: reusa o existente ou cria um novo
    driver_proprio = driver_existente is None
    if driver_proprio:
        driver, tmp = configurar_driver(headless)
        wait = WebDriverWait(driver, TIMEOUT_PADRAO)
    else:
        driver = driver_existente
        wait = wait_existente if wait_existente is not None else WebDriverWait(driver, TIMEOUT_PADRAO)
        tmp = None

    shots_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'screenshots'
    )
    os.makedirs(shots_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')

    def shot(tag: str):
        try:
            p = os.path.join(shots_dir, f"{stamp}_{tag}.png")
            driver.save_screenshot(p)
            log.info(f"  📸 {p}")
        except Exception as e:
            log.warning(f"shot fail: {e}")

    etapa = 'init'
    try:
        # 1) Login (pula se a sessão já está aberta)
        if not ja_logado:
            etapa = 'login'
            login_ok = False
            for tentativa in range(1, 4):
                try:
                    fazer_login(driver, wait, usuario, senha)
                except Exception as e:
                    log.warning(f"  tentativa login {tentativa}: {e}")
                shot(f'01_login_t{tentativa}')
                if esperar_dashboard(driver, timeout=25):
                    login_ok = True
                    break
                log.warning(f"  tentativa login {tentativa} não chegou no dashboard, retentando...")
                time.sleep(3)
            if not login_ok:
                return {
                    'status': 'falha',
                    'erro': 'Não conseguiu chegar no dashboard após 3 tentativas de login (instabilidade dellink)',
                    'etapa': 'login_timeout',
                }
            shot('02_dashboard')
        else:
            log.info("  ↻ reusando sessão de login")

        # 2) Navegar pra /cliente/adicionar/
        etapa = 'abrir_adicionar_cliente'
        url = f"{MEGALINK_URL_BASE}/cliente/adicionar/"
        log.info(f"ETAPA 2: navegar para {url}")
        driver.get(url)
        # Espera o form da aba 01 renderizar (radio Pessoa Física é um marcador estável)
        try:
            WebDriverWait(driver, 30).until(EC.visibility_of_element_located(
                (By.XPATH, "//md-radio-button[contains(normalize-space(.), 'Pessoa Física')] | "
                           "//input[@name='cpf_cnpj'] | "
                           "//md-input-container[.//label[contains(.,'CPF')]]")
            ))
            log.info("  form de cadastro renderizado")
        except TimeoutException:
            log.warning("  form não confirmado, seguindo com timeout extra")
            time.sleep(PAUSA_LONGA)
        shot('03_pagina_adicionar_cliente')

        # 3) Aba 01 - CADASTRO
        etapa = 'aba01_cadastro'
        shot('04_aba01_antes')
        preencher_aba_01_cadastro(driver, wait, d)
        shot('05_aba01_depois')

        avancar(driver, wait, 'pós-Cadastro')

        # 4) Aba 02 - ENDEREÇO
        etapa = 'aba02_endereco'
        shot('06_aba02_antes')
        divergencias_endereco = preencher_aba_02_endereco(driver, wait, d)
        shot('07_aba02_depois')

        # Se endereço diverge do CSV E vamos salvar, ABORTA antes de seguir
        # pras outras abas pra cliente ser revisado manualmente.
        if divergencias_endereco and salvar and not dry_run:
            log.error(f"  ❌ ABORTANDO cadastro: endereço diverge do CSV em "
                      f"{len(divergencias_endereco)} campo(s) — cliente vai "
                      f"para revisão manual")
            return {
                'status': 'endereco_divergente',
                'erro': '; '.join(divergencias_endereco)[:400],
                'etapa': 'aba02_endereco_validacao',
                'divergencias': divergencias_endereco,
            }

        avancar(driver, wait, 'pós-Endereço')

        # 5) Aba 03 - PLANO
        etapa = 'aba03_plano'
        shot('08_aba03_antes')
        preencher_aba_03_plano(driver, wait, d)
        shot('09_aba03_depois')

        avancar(driver, wait, 'pós-Plano')

        # 6) Aba 04 - CONTRATO (não temos imagem — só capturamos e avançamos)
        etapa = 'aba04_contrato'
        shot('10_aba04_contrato_descoberta')
        log.info("┌─ ABA 04 - CONTRATO (descoberta) ──────")
        log.info("  conteúdo capturado no screenshot — sem preenchimento agora")
        time.sleep(PAUSA_MEDIA)
        avancar(driver, wait, 'pós-Contrato')

        # 7) Aba 05 - COBRANÇA
        etapa = 'aba05_cobranca'
        shot('11_aba05_antes')
        preencher_aba_05_cobranca(driver, wait, d)
        shot('12_aba05_depois')

        avancar(driver, wait, 'pós-Cobrança')

        # 8) Aba 06 - PACOTES (descoberta)
        etapa = 'aba06_pacotes'
        shot('13_aba06_pacotes_descoberta')
        log.info("┌─ ABA 06 - PACOTES (descoberta) ──────")
        time.sleep(PAUSA_MEDIA)
        avancar(driver, wait, 'pós-Pacotes')

        # 9) Aba 07 - ORDEM DE SERVIÇO (descoberta)
        etapa = 'aba07_os'
        shot('14_aba07_os_descoberta')
        log.info("┌─ ABA 07 - ORDEM DE SERVIÇO (descoberta) ──────")
        time.sleep(PAUSA_MEDIA)

        # 10) Tela do SALVAR
        if salvar and not dry_run:
            etapa = 'salvar'
            log.info("Clicando SALVAR final...")
            btn_salvar = esperar_clicavel(
                wait, "//button[contains(., 'Salvar') or contains(., 'SALVAR')]"
            )
            clicar(driver, btn_salvar); shot('15a_salvando')
            # Aguarda confirmação do salvamento (até 30s):
            #   - URL muda de /adicionar/ → sucesso
            #   - md-dialog de erro aparece → falha
            #   - botão volta de 'SALVANDO' pra 'SALVAR' sem redirect → falha
            log.info("  aguardando confirmação do salvamento (até 30s)...")
            fim = time.time() + 30
            salvou_ok = False
            erro_visivel = ''
            shot_n = 0
            while time.time() < fim:
                cur_url = (driver.current_url or '')
                if '/adicionar' not in cur_url:
                    log.info(f"  ✓ URL mudou ({cur_url}) — salvou")
                    salvou_ok = True
                    break
                # Captura toasts/snackbars (mensagens flutuantes que somem rápido)
                try:
                    toasts = driver.find_elements(
                        By.XPATH,
                        "//md-toast | //md-snackbar | "
                        "//*[contains(@class,'toast') or contains(@class,'snackbar') "
                        "or contains(@class,'alert')] | "
                        "//*[contains(@class,'md-warn') and not(self::md-icon)]"
                    )
                    for t in toasts:
                        if not t.is_displayed():
                            continue
                        txt = (t.text or '').strip()
                        if not txt:
                            continue
                        # Distingue toast de SUCESSO vs ERRO
                        txt_l = txt.lower()
                        if 'sucesso' in txt_l or 'adicionado com sucesso' in txt_l:
                            log.info(f"  ✓ toast sucesso: {txt!r}")
                            salvou_ok = True
                            break
                        # Toast de erro/aviso
                        erro_visivel = txt[:300]
                        log.warning(f"  ⚠ toast/snackbar: {txt!r}")
                        break
                    if salvou_ok or erro_visivel:
                        break
                except Exception:
                    pass
                # Shot a cada 3s pra capturar mensagens transitórias
                shot_n += 1
                if shot_n % 3 == 1:
                    shot(f'15_pol_t{shot_n}s')
                time.sleep(1)
            shot('15b_apos_salvar')
            if not salvou_ok:
                log.warning(
                    f"  ⚠ Salvamento não confirmado em 30s (url ainda /adicionar). "
                    f"Erro: {erro_visivel!r}"
                )
                return {
                    'status': 'falha',
                    'erro': f'SALVAR não confirmou em 30s. {erro_visivel or "sem mensagem visível"}'[:400],
                    'etapa': 'salvar_timeout',
                }

            # PÓS-SALVAR: habilitar serviço + editar autenticação PPPoE
            if d.login_pppoe and d.senha_pppoe:
                try:
                    etapa = 'pos_save_auth'
                    habilitar_e_editar_autenticacao(driver, wait, d, shot=shot)
                except Exception as e:
                    log.exception(f"  pós-save: {e}")
                    shot("ERRO_pos_save_auth")
                    # Não retorna falha — o cliente JÁ foi salvo. Só notifica.
                    return {
                        'status': 'sucesso',
                        'erro': f'pós-save auth falhou: {type(e).__name__}: {e}'[:300],
                        'etapa': 'pos_save_falha',
                    }
            else:
                log.info("  sem login_pppoe/senha_pppoe — pulando pós-save")

            return {'status': 'sucesso', 'erro': '', 'etapa': 'fim'}
        else:
            log.info("════════════════════════════════════════════════════")
            log.info("✅ DRY-RUN OK — parou na tela do SALVAR sem clicar")
            log.info("════════════════════════════════════════════════════")
            shot('15_tela_salvar_sem_clicar')

        if manter_aberto_segundos > 0:
            log.info(f"Mantendo navegador aberto por {manter_aberto_segundos}s...")
            time.sleep(manter_aberto_segundos)

        return {'status': 'dry_run', 'erro': '', 'etapa': 'fim'}

    except Exception as e:
        log.exception(f"❌ Falha na etapa {etapa!r}: {e}")
        shot(f"ERRO_{etapa}")
        return {
            'status': 'falha',
            'erro': f"{type(e).__name__}: {e}"[:500],
            'etapa': etapa,
        }
    finally:
        # Só fecha o driver/tmp se for nosso (não fecha o do caller)
        if driver_proprio:
            try:
                driver.quit()
            except Exception:
                pass
            try:
                if tmp:
                    shutil.rmtree(tmp)
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser(description="Webdriver Adicionar Cliente — DELLINK")
    p.add_argument("--headless", action="store_true",
                   help="Roda sem janela (default: com janela)")
    p.add_argument("--salvar", action="store_true",
                   help="Clica SALVAR no final (default: NÃO clica — dry-run)")
    p.add_argument("--manter-aberto", type=int, default=0,
                   help="Segundos pra manter o navegador aberto no final")
    args = p.parse_args()

    res = executar(
        headless=args.headless,
        dry_run=not args.salvar,
        salvar=args.salvar,
        manter_aberto_segundos=args.manter_aberto,
    )
    log.info(f"RESULTADO: {res}")
    sys.exit(0 if res['status'] in ('sucesso', 'dry_run') else 1)


if __name__ == "__main__":
    main()
