"""
Webdriver: contratar NOVO serviço pra cliente que já existe no HubSoft.

Fluxo: login → /cliente/editar/{id_cliente}/servico → botão "+" → wizard
(plano, vendedor, grupo, endereço, vencimento, forma cobrança, vários
avançar) → PARA antes do botão SALVAR final.

Origem dos dados: tabela `new_service` (DB robovendas) cruzada com
`prospecto`/`servico` no HubSoft pra resolver:
  - lead.id_hubsoft (= prospecto.id_prospecto) → prospecto.id_cliente
  - new_service.id_plano_rp → servico.descricao
"""

import argparse
import logging
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass

import psycopg2
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger("novo_servico")

HUBSOFT_URL_BASE = "https://megalinktelecom.hubsoft.com.br"

# Tempos longos: o HubSoft é AngularJS e tem dialogs que demoram pra abrir.
TIMEOUT_PADRAO = 20
PAUSA_CURTA = 1.0
PAUSA_MEDIA = 2.5
PAUSA_LONGA = 4.0


# ════════════════════════════════════════════════════════════════════
#  Modelo de dados que o wizard precisa
# ════════════════════════════════════════════════════════════════════
@dataclass
class DadosNovoServico:
    new_service_id: int
    id_cliente_hubsoft: int
    nome_cliente: str
    plano_titulo: str            # texto exato do dropdown HubSoft
    dia_vencimento: str          # como aparece no dropdown HubSoft: '5','10','15','20','25','1','ultimo_dia' etc.
    cep: str
    rua: str
    numero: str
    bairro: str
    cidade: str
    estado: str                  # UF, ex: "PI"
    complemento: str = ''
    referencia: str = ''


# ════════════════════════════════════════════════════════════════════
#  Banco de dados — busca cruzada robovendas + hubsoft
# ════════════════════════════════════════════════════════════════════
def _conn(prefix: str):
    return psycopg2.connect(
        host=os.environ[f'{prefix}_DB_HOST'],
        port=os.environ[f'{prefix}_DB_PORT'],
        dbname=os.environ[f'{prefix}_DB_NAME'],
        user=os.environ[f'{prefix}_DB_USER'],
        password=os.environ[f'{prefix}_DB_PASSWORD'],
    )


def _so_digitos(s: str) -> str:
    return ''.join(c for c in (s or '') if c.isdigit())


def _resolver_id_cliente(cur_hs, *, id_prospecto_hubsoft, cpf_cnpj, nome,
                         ns_id: int) -> int:
    """Tenta achar o id_cliente no HubSoft com várias estratégias:
      1) Via lead.id_hubsoft → prospecto.id_prospecto → prospecto.id_cliente
      2) Via cpf_cnpj (só dígitos) → cliente.cpf_cnpj
      3) Via cpf_cnpj → prospecto.cpf_cnpj → prospecto.id_cliente
    Devolve o id_cliente ou levanta SystemExit explicativo.
    """
    tentativas = []

    if id_prospecto_hubsoft:
        cur_hs.execute(
            "SELECT id_cliente FROM prospecto WHERE id_prospecto = %s",
            (int(id_prospecto_hubsoft),),
        )
        r = cur_hs.fetchone()
        tentativas.append(f"prospecto id_prospecto={id_prospecto_hubsoft} → {r}")
        if r and r[0]:
            log.info(f"  id_cliente {r[0]} resolvido via id_hubsoft={id_prospecto_hubsoft}")
            return int(r[0])

    cpf_norm = _so_digitos(cpf_cnpj)
    if cpf_norm and len(cpf_norm) in (11, 14):
        # 2) cliente direto por CPF/CNPJ
        cur_hs.execute(
            "SELECT id_cliente, nome_razaosocial FROM cliente WHERE cpf_cnpj = %s LIMIT 2",
            (cpf_norm,),
        )
        rows = cur_hs.fetchall()
        tentativas.append(f"cliente cpf_cnpj={cpf_norm} → {rows}")
        if len(rows) == 1:
            log.info(
                f"  id_cliente {rows[0][0]} resolvido via cpf_cnpj "
                f"(HubSoft: {rows[0][1]!r}, lead: {nome!r})"
            )
            return int(rows[0][0])
        elif len(rows) > 1:
            raise SystemExit(
                f"new_service {ns_id}: CPF {cpf_norm} retornou múltiplos "
                f"clientes no HubSoft: {rows}"
            )

        # 3) prospecto por CPF (caso o cliente foi convertido mas o link
        #    direto em cliente.cpf_cnpj não bate)
        cur_hs.execute(
            "SELECT id_prospecto, id_cliente, nome_razaosocial "
            "FROM prospecto WHERE cpf_cnpj = %s AND id_cliente IS NOT NULL LIMIT 2",
            (cpf_norm,),
        )
        rows = cur_hs.fetchall()
        tentativas.append(f"prospecto cpf_cnpj={cpf_norm} → {rows}")
        if len(rows) == 1:
            log.info(
                f"  id_cliente {rows[0][1]} resolvido via prospecto+cpf "
                f"(prospecto {rows[0][0]}, HubSoft: {rows[0][2]!r})"
            )
            return int(rows[0][1])
        elif len(rows) > 1:
            raise SystemExit(
                f"new_service {ns_id}: CPF {cpf_norm} retornou múltiplos "
                f"prospectos no HubSoft: {rows}"
            )

    raise SystemExit(
        f"new_service {ns_id}: não consegui resolver id_cliente no HubSoft "
        f"(id_hubsoft={id_prospecto_hubsoft!r}, cpf_cnpj={cpf_cnpj!r}, "
        f"nome={nome!r}). Tentativas: {tentativas}"
    )


def buscar_dados(new_service_id: int) -> DadosNovoServico:
    log.info(f"Buscando dados do new_service id={new_service_id}")
    conn_rv = _conn('ROBOVENDAS')
    try:
        cur = conn_rv.cursor()
        cur.execute(
            """
            SELECT ns.id, ns.id_plano_rp, ns.id_dia_vencimento,
                   ns.cep, ns.rua, ns.numero_residencia, ns.bairro,
                   ns.cidade, ns.estado, ns.ponto_referencia,
                   lp.id_hubsoft, lp.nome_razaosocial, lp.cpf_cnpj
              FROM new_service ns
              JOIN leads_prospectos lp ON lp.id = ns.lead_id
             WHERE ns.id = %s
            """,
            (new_service_id,),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn_rv.close()

    if not row:
        raise SystemExit(f"new_service id={new_service_id} não encontrado")

    (ns_id, id_plano_rp, dia_venc, cep, rua, numero, bairro, cidade,
     estado, referencia, id_prospecto_hubsoft, nome, cpf_cnpj) = row

    conn_hs = _conn('HUBSOFT')
    try:
        cur = conn_hs.cursor()

        id_cliente = _resolver_id_cliente(
            cur,
            id_prospecto_hubsoft=id_prospecto_hubsoft,
            cpf_cnpj=cpf_cnpj,
            nome=nome,
            ns_id=ns_id,
        )

        cur.execute(
            "SELECT descricao FROM servico WHERE id_servico = %s",
            (int(id_plano_rp),),
        )
        r = cur.fetchone()
        if not r:
            raise SystemExit(
                f"plano id_servico={id_plano_rp} não existe no HubSoft"
            )
        plano_titulo = r[0]

        # Resolver dia_vencimento: new_service.id_dia_vencimento é o
        # id_vencimento do HubSoft (NÃO o dia literal). Buscamos o
        # `dia_vencimento` real (string: '5','15','20','ultimo_dia', etc.)
        dia_vencimento_str = ''
        if dia_venc is not None:
            cur.execute(
                "SELECT dia_vencimento, ativo FROM vencimento WHERE id_vencimento = %s",
                (int(dia_venc),),
            )
            r = cur.fetchone()
            if not r:
                raise SystemExit(
                    f"id_dia_vencimento={dia_venc} não corresponde a nenhum "
                    f"id_vencimento no HubSoft"
                )
            dia_real, ativo = r
            if not ativo:
                raise SystemExit(
                    f"vencimento id={dia_venc} (dia '{dia_real}') está "
                    f"inativo no HubSoft"
                )
            dia_vencimento_str = str(dia_real)
            log.info(
                f"  vencimento id={dia_venc} → dia {dia_vencimento_str!r}"
            )
        cur.close()
    finally:
        conn_hs.close()

    dados = DadosNovoServico(
        new_service_id=ns_id,
        id_cliente_hubsoft=id_cliente,
        nome_cliente=nome or '',
        plano_titulo=plano_titulo,
        dia_vencimento=dia_vencimento_str,
        cep=(cep or '').strip(),
        rua=(rua or '').strip(),
        numero=str(numero or '').strip(),
        bairro=(bairro or '').strip(),
        cidade=(cidade or '').strip(),
        estado=(estado or '').strip(),
        complemento='',
        referencia=(referencia or '').strip(),
    )
    log.info(
        f"Cliente HubSoft #{dados.id_cliente_hubsoft} — {dados.nome_cliente!r} | "
        f"plano {dados.plano_titulo!r} | venc dia {dados.dia_vencimento} | "
        f"end {dados.rua}, {dados.numero} — {dados.bairro}, {dados.cidade}/{dados.estado}"
    )
    return dados


# ════════════════════════════════════════════════════════════════════
#  Selenium helpers
# ════════════════════════════════════════════════════════════════════
def configurar_driver(headless: bool):
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    opts.add_argument("--window-size=1920,1080")
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--force-device-scale-factor=1")

    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "temp_chrome_profiles")
    os.makedirs(base, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=base)
    opts.add_argument(f"--user-data-dir={tmp}")
    opts.add_argument("--no-first-run")
    opts.add_argument("--disable-default-apps")

    driver = webdriver.Chrome(options=opts)
    return driver, tmp


def clicar(driver, el):
    """Click via JS depois de centralizar — mais robusto contra overlay."""
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});", el
    )
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", el)


def esperar_visivel(wait, xpath: str):
    return wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))


def esperar_clicavel(wait, xpath: str):
    return wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))


def fechar_dialog_se_aberto(driver):
    """Best effort: fecha overlays/dialogs residuais com ESC."""
    try:
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
#  Login (reaproveitado do main_refatorado.py — ETAPA 1)
# ════════════════════════════════════════════════════════════════════
def fazer_login(driver, wait, usuario: str, senha: str):
    log.info("ETAPA 1: login")
    driver.get(f"{HUBSOFT_URL_BASE}/login")
    # Login carrega bundles AngularJS — aceita até 45s
    email_in = WebDriverWait(driver, 45).until(
        EC.presence_of_element_located((By.NAME, "email"))
    )
    email_in.clear()
    email_in.send_keys(usuario)
    time.sleep(PAUSA_CURTA)
    esperar_clicavel(wait, "//button[contains(., 'Validar')]").click()
    pwd = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[type='password']")))
    pwd.clear()
    pwd.send_keys(senha)
    time.sleep(PAUSA_CURTA)
    esperar_clicavel(wait, "//button[contains(., 'Entrar')]").click()
    time.sleep(PAUSA_LONGA)
    log.info("✓ Login OK")


# ════════════════════════════════════════════════════════════════════
#  Wizard — adicionar novo serviço
# ════════════════════════════════════════════════════════════════════
WIZARD_ROOT = "//hubsoft-cliente-servico-wizard"
BTN_AVANCAR_XPATH = (
    f"{WIZARD_ROOT}//md-dialog-actions//button["
    "contains(., 'Avançar') or contains(., 'Próximo') or contains(., 'Continuar')"
    "]"
)


def abrir_servico(driver, wait, id_cliente: int):
    url = f"{HUBSOFT_URL_BASE}/cliente/editar/{id_cliente}/servico"
    log.info(f"ETAPA 2: navegar para {url}")
    driver.get(url)
    time.sleep(PAUSA_LONGA)


def clicar_adicionar_servico(driver, wait):
    log.info("ETAPA 3: clicar botão '+ Adicionar Serviço'")
    btn = esperar_clicavel(
        wait, "//button[@aria-label='Adicionar Serviço']"
    )
    clicar(driver, btn)
    time.sleep(PAUSA_LONGA)


def selecionar_plano(driver, wait, titulo: str):
    log.info(f"ETAPA 4: selecionar plano {titulo!r}")
    md_select = esperar_clicavel(
        wait, f"{WIZARD_ROOT}//md-select[@name='servico']"
    )
    clicar(driver, md_select)
    time.sleep(PAUSA_MEDIA)

    # O dropdown tem um input de busca "Procurar Servico" no topo — usamos
    # ele pra filtrar (a lista é virtual-scroll, contém todos os planos).
    # Chave de busca: pegamos algo distinto do titulo. Usamos a parte sem o
    # prefixo "(GRUPO) " quando presente.
    chave = titulo
    if chave.startswith("(") and ")" in chave:
        chave = chave.split(")", 1)[1].strip()
    chave_busca = chave[:30]  # 30 chars geralmente bastam pra reduzir lista

    try:
        busca = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.XPATH, "//md-select-menu//input[@placeholder='Procurar Servico'] | "
                       "//input[@placeholder='Procurar Servico']")
        ))
        busca.clear()
        busca.send_keys(chave_busca)
        log.info(f"  Buscando por {chave_busca!r}")
        time.sleep(PAUSA_MEDIA)
    except TimeoutException:
        log.warning("  Sem input de busca, vou tentar clicar direto na opção")

    # Match flexível: a opção no dropdown costuma vir SEM o prefixo "(GRUPO) "
    # e às vezes com " (R$ X)" no final. Tentamos primeiro pela `chave` (sem
    # prefixo) e caímos para o `titulo` completo como fallback.
    opt = None
    for alvo in (chave, titulo):
        try:
            opt = esperar_clicavel(
                wait, f"//md-option[contains(normalize-space(.), \"{alvo}\")]")
            break
        except TimeoutException:
            continue
    if opt is None:
        raise TimeoutException(f"opção de plano não encontrada p/ {titulo!r}/{chave!r}")
    clicar(driver, opt)
    time.sleep(PAUSA_MEDIA)


def _filtrar_e_clicar_virtual_repeat(driver, wait, alvo: str):
    """Dentro de um dropdown <md-select-menu> que tem input de busca
    (placeholder começa com 'Filtrar em N itens'), digita parte do
    nome `alvo` pra reduzir a lista e clica no botão correspondente.

    O matching do botão é tolerante: busca por aria-label contendo TODAS
    as palavras significativas de `alvo` (em qualquer ordem, case-insens).
    """
    # O input fica visível mas pode estar em qualquer container; busca
    # entre TODOS os inputs visíveis com placeholder começando por 'Filtrar'.
    palavras = [p for p in alvo.replace('-', ' ').split() if len(p) >= 3]
    chave_filtro = palavras[0] if palavras else alvo[:10]

    candidatos_xp = [
        "//input[contains(@placeholder,'Filtrar em')]",
        "//input[contains(@placeholder,'Filtrar')]",
        "//md-select-menu//input",
        "//md-virtual-repeat-container/preceding-sibling::*//input",
    ]
    busca = None
    for xp in candidatos_xp:
        try:
            els = driver.find_elements(By.XPATH, xp)
            for e in els:
                if e.is_displayed():
                    busca = e
                    log.info(f"  filtro: input achado via {xp}")
                    break
            if busca is not None:
                break
        except Exception:
            continue

    if busca is not None:
        log.info(f"  Filtrando dropdown por {chave_filtro!r}")
        try:
            busca.click()
        except Exception:
            driver.execute_script("arguments[0].focus();", busca)
        # Limpa via JS + dispara input event (AngularJS escuta input event)
        driver.execute_script(
            "arguments[0].value=''; "
            "arguments[0].dispatchEvent(new Event('input'));", busca,
        )
        time.sleep(0.2)
        for ch in chave_filtro:
            busca.send_keys(ch)
            time.sleep(0.04)
        # Garantir que AngularJS escutou — dispara input event final
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input'));", busca,
        )
        time.sleep(PAUSA_MEDIA)
    else:
        log.warning("  filtro: nenhum input visível encontrado, seguindo sem filtrar")

    # Match tolerante: aria-label que contém TODAS as palavras (case-insens via translate)
    cond = " and ".join([
        f"contains(translate(@aria-label,"
        f"'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÂÊÔÃÕÇ',"
        f"'abcdefghijklmnopqrstuvwxyzáéíóúâêôãõç'), '{p.lower()}')"
        for p in palavras
    ]) or f"@aria-label=\"{alvo}\""
    xp_btn = f"//md-virtual-repeat-container//button[{cond}] | //md-select-menu//button[{cond}]"
    btn = esperar_clicavel(wait, xp_btn)
    clicar(driver, btn)
    time.sleep(PAUSA_MEDIA)


def _md_select_por_label(driver, wait, label_texto: str):
    """Encontra um md-select pelo label do md-input-container que o contém.
    Funciona pra inputs com label flutuante (que vem antes ou dentro do container).
    """
    xp = (
        f"{WIZARD_ROOT}//md-input-container["
        f".//label[contains(normalize-space(.), \"{label_texto}\")]"
        f"]//md-select"
    )
    return esperar_clicavel(wait, xp)


def selecionar_vendedor(driver, wait, vendedor: str):
    log.info(f"ETAPA 5: selecionar vendedor {vendedor!r}")
    md_select = _md_select_por_label(driver, wait, "Vendedor")
    clicar(driver, md_select)
    time.sleep(PAUSA_MEDIA)

    _filtrar_e_clicar_virtual_repeat(driver, wait, vendedor)


def selecionar_grupo(driver, wait, grupo: str):
    log.info(f"ETAPA 6: selecionar grupo {grupo!r}")
    # Label aparece como "Grupos" (com s) na tela.
    md_select = _md_select_por_label(driver, wait, "Grupos")
    clicar(driver, md_select)
    time.sleep(PAUSA_MEDIA)
    opt = esperar_clicavel(
        wait,
        f"//md-option[.//div[contains(@class,'md-text') and "
        f"normalize-space(text())=\"{grupo}\"]]"
    )
    clicar(driver, opt)
    time.sleep(PAUSA_MEDIA)


def preencher_endereco(driver, wait, d: DadosNovoServico):
    log.info("ETAPA 4: adicionar endereço (primeiro passo do wizard)")
    # Botão "+" azul ao lado do dropdown de endereço.
    # Procura por button com ícone plus dentro do form do wizard.
    candidatos_xp = [
        f"{WIZARD_ROOT}//form//button[.//md-icon[contains(@class,'icon-plus') or @md-font-icon='icon-plus']]",
        f"{WIZARD_ROOT}//form//button[contains(@class,'md-fab')]",
        f"{WIZARD_ROOT}//form//div[1]/div[2]/button",
    ]
    btn_add = None
    for xp in candidatos_xp:
        try:
            btn_add = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            log.info(f"  Botão '+' achado via: {xp}")
            break
        except TimeoutException:
            continue
    if btn_add is None:
        raise RuntimeError("Não achei o botão '+' de adicionar endereço")
    clicar(driver, btn_add)
    time.sleep(PAUSA_LONGA)

    # Agora estamos no dialog de endereço — preencher CEP primeiro
    log.info(f"  CEP: {d.cep}")
    cep_in = esperar_clicavel(wait, "//input[@name='cep']")
    cep_in.clear()
    cep_in.send_keys(d.cep.replace("-", ""))
    # CEP dispara busca via ng-change; espera autopreenchimento
    time.sleep(PAUSA_LONGA)
    # Tira foco pra firar onblur
    cep_in.send_keys(Keys.TAB)
    time.sleep(PAUSA_MEDIA)

    # Estado / Cidade / Bairro / Endereço podem ter sido preenchidos pelo CEP.
    # Se algum estiver vazio, fazemos fallback digitando.
    _autocomplete_fallback(driver, wait, "Estado", d.estado)
    _autocomplete_fallback(driver, wait, "Cidade", d.cidade)
    _autocomplete_fallback(driver, wait, "Bairro", d.bairro)
    _autocomplete_fallback(driver, wait, "Endereço", d.rua)

    # Número
    log.info(f"  Número: {d.numero}")
    num_in = esperar_clicavel(wait, "//input[@name='numero']")
    num_in.clear()
    num_in.send_keys(d.numero)
    time.sleep(PAUSA_CURTA)

    # Complemento
    if d.complemento:
        log.info(f"  Complemento: {d.complemento}")
        c_in = esperar_clicavel(wait, "//input[@name='complemento']")
        c_in.clear()
        c_in.send_keys(d.complemento)
        time.sleep(PAUSA_CURTA)

    # Referência
    if d.referencia:
        log.info(f"  Referência: {d.referencia}")
        r_in = esperar_clicavel(wait, "//input[@name='referencia']")
        r_in.clear()
        r_in.send_keys(d.referencia)
        time.sleep(PAUSA_CURTA)

    # Salvar endereço — o botão fica em md-dialog-actions do dialog (div[8])
    log.info("  Salvando endereço...")
    btn_salvar = esperar_clicavel(
        wait, "//md-dialog//md-dialog-actions//button[contains(., 'Salvar')]"
    )
    clicar(driver, btn_salvar)
    time.sleep(PAUSA_LONGA)


def _autocomplete_fallback(driver, wait, label: str, valor: str):
    """Se o md-autocomplete com esse label estiver vazio, digita o valor e
    seleciona a primeira sugestão. Senão ignora."""
    if not valor:
        return
    try:
        # md-autocomplete cujo md-input-container tem label com texto exato
        input_xpath = (
            f"//md-autocomplete[.//label[normalize-space(text())='{label}']]"
            "//input[@type='search']"
        )
        el = driver.find_element(By.XPATH, input_xpath)
    except Exception:
        log.warning(f"  Não achei autocomplete {label!r}")
        return

    val_atual = (el.get_attribute("value") or "").strip()
    if val_atual:
        log.info(f"  {label}: já preenchido com {val_atual!r}, mantendo")
        return

    log.info(f"  {label}: digitando {valor!r}")
    el.click()
    el.clear()
    el.send_keys(valor)
    time.sleep(PAUSA_MEDIA)
    # Primeira sugestão
    try:
        sug = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
            (By.XPATH, "//ul[contains(@class,'md-autocomplete-suggestions')]/li[1]")
        ))
        clicar(driver, sug)
    except TimeoutException:
        # Pode ser que o select-on-match já tenha selecionado
        log.warning(f"  {label}: sem sugestão visível, seguindo")
    time.sleep(PAUSA_CURTA)


def clicar_avancar(driver, wait, contexto: str = ""):
    log.info(f"AVANÇAR ({contexto})")
    btn = esperar_clicavel(wait, BTN_AVANCAR_XPATH)
    clicar(driver, btn)
    time.sleep(PAUSA_LONGA)


def clicar_salvar(driver, wait):
    """Clica o botão SALVAR final do wizard (concluir a contratação)."""
    log.info("SALVAR — finalizar contratação no HubSoft")
    xp = (
        f"{WIZARD_ROOT}//md-dialog-actions//button["
        "contains(translate(., 'SALVAR', 'salvar'), 'salvar')"
        "]"
    )
    btn = esperar_clicavel(wait, xp)
    clicar(driver, btn)
    # Após salvar, esperar feedback (toast/dialog fecha)
    time.sleep(PAUSA_LONGA * 2)


def selecionar_vencimento(driver, wait, dia: str):
    """Seleciona o dia de vencimento. `dia` é a string como aparece no
    HubSoft: '1', '5', '10', '15', '20', '25', 'ultimo_dia', etc."""
    log.info(f"ETAPA 9: selecionar vencimento dia {dia!r}")
    # Tela "02 - Cobrança": campo "Dia de Vencimento"
    md_select = _md_select_por_label(driver, wait, "Dia de Vencimento")
    clicar(driver, md_select)
    time.sleep(PAUSA_MEDIA)

    # 'ultimo_dia' aparece no dropdown como "Último dia" ou "Ultimo dia"
    if dia == 'ultimo_dia':
        candidatos = [
            "//md-option[contains(translate(., 'ÚU', 'úu'), 'último dia')]",
            "//md-option[contains(translate(., 'ÚU', 'úu'), 'ultimo dia')]",
            "//md-option[contains(., 'Último') or contains(., 'Ultimo')]",
        ]
    else:
        # Match EXATO pelo número (evita 5 casar com 15/25)
        candidatos = [
            f"//md-option[normalize-space(.)='{dia}']",
            f"//md-option[.//div[normalize-space(text())='{dia}']]",
            f"//md-option[contains(normalize-space(.), 'Dia {dia}') "
            f"and not(contains(normalize-space(.), 'Dia {dia}0')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}1')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}2')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}3')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}4')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}5')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}6')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}7')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}8')) "
            f"and not(contains(normalize-space(.), 'Dia {dia}9'))]",
        ]
    opt = None
    for xp in candidatos:
        try:
            opt = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            break
        except TimeoutException:
            continue
    if opt is None:
        # Diagnóstico — lista as opções visíveis
        try:
            opts = driver.find_elements(By.XPATH, "//md-option")
            visiveis = [o.text for o in opts if o.is_displayed()][:30]
            log.error(f"  opções visíveis: {visiveis}")
        except Exception:
            pass
        raise RuntimeError(f"Não achei opção de vencimento para dia {dia}")
    clicar(driver, opt)
    time.sleep(PAUSA_MEDIA)


def selecionar_forma_cobranca(driver, wait, banco: str):
    log.info(f"ETAPA 10: selecionar forma cobrança {banco!r}")
    # Procura o md-select pelo label "Forma de Cobrança" / "Conta"
    candidatos = ["Forma de Cobrança", "Cobrança", "Banco", "Conta"]
    md_select = None
    for lbl in candidatos:
        try:
            md_select = _md_select_por_label(driver, wait, lbl)
            log.info(f"  achei via label {lbl!r}")
            break
        except TimeoutException:
            continue
    if md_select is None:
        # Fallback posicional: hubsoft-select-virtual-repeat dentro do form
        md_select = esperar_clicavel(
            wait,
            f"{WIZARD_ROOT}//form//hubsoft-select-virtual-repeat//md-select",
        )
    clicar(driver, md_select)
    time.sleep(PAUSA_MEDIA)
    _filtrar_e_clicar_virtual_repeat(driver, wait, banco)


# ════════════════════════════════════════════════════════════════════
#  Orquestrador
# ════════════════════════════════════════════════════════════════════
def executar(new_service_id: int,
             vendedor: str = "Venda-Automática-Matrix",
             grupo: str = "Varejo",
             banco: str = "BANCO ITAU",
             headless: bool = False,
             avancos_pos_cobranca: int = 5,
             dry_run: bool = False,
             manter_aberto_segundos: int = 0) -> dict:
    """Executa o fluxo de contratação de novo serviço no HubSoft.

    Retorna um dict com `status` ∈ {'sucesso','falha','dry_run'},
    `erro` (str ou ''), `etapa` (nome da última etapa antes de falhar)
    e `nome_cliente`.
    """
    usuario = os.environ.get('USUARIO', '')
    senha = os.environ.get('SENHA', '')
    if not usuario or not senha:
        raise SystemExit("USUARIO/SENHA não definidos no .env")

    dados = buscar_dados(new_service_id)

    driver, tmp = configurar_driver(headless)
    wait = WebDriverWait(driver, TIMEOUT_PADRAO)

    shots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "screenshots_novo_servico")
    os.makedirs(shots_dir, exist_ok=True)
    import datetime as _dt
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    def shot(tag: str):
        try:
            p = os.path.join(shots_dir, f"{stamp}_{tag}.png")
            driver.save_screenshot(p)
            log.info(f"  📸 {p}")
        except Exception as e:
            log.warning(f"shot fail: {e}")

    etapa_atual = "init"
    try:
        etapa_atual = "login"
        fazer_login(driver, wait, usuario, senha); shot("01_login_ok")
        etapa_atual = "abrir_servico"
        abrir_servico(driver, wait, dados.id_cliente_hubsoft); shot("02_pagina_servico")
        etapa_atual = "btn_adicionar"
        clicar_adicionar_servico(driver, wait); shot("03_wizard_aberto")
        etapa_atual = "preencher_endereco"
        preencher_endereco(driver, wait, dados); shot("04_endereco_ok")
        etapa_atual = "selecionar_plano"
        selecionar_plano(driver, wait, dados.plano_titulo); shot("05_plano_ok")
        etapa_atual = "selecionar_vendedor"
        selecionar_vendedor(driver, wait, vendedor); shot("06_vendedor_ok")
        etapa_atual = "selecionar_grupo"
        selecionar_grupo(driver, wait, grupo); shot("07_grupo_ok")
        etapa_atual = "avancar_pos_grupo"
        clicar_avancar(driver, wait, "pós-grupo"); shot("08_avancou_1")
        etapa_atual = "selecionar_vencimento"
        selecionar_vencimento(driver, wait, dados.dia_vencimento); shot("09_venc_ok")
        etapa_atual = "selecionar_forma_cobranca"
        selecionar_forma_cobranca(driver, wait, banco); shot("10_banco_ok")
        for i in range(avancos_pos_cobranca):
            etapa_atual = f"avancar_{i+1}"
            clicar_avancar(driver, wait, f"pós-cobrança {i+1}/{avancos_pos_cobranca}")
            shot(f"11_avanco_{i+1}")

        if dry_run:
            log.info("════════════════════════════════════════════════════")
            log.info("✅ DRY-RUN OK — chegou no passo anterior ao SALVAR")
            log.info("   (o botão SALVAR final NÃO foi clicado)")
            log.info("════════════════════════════════════════════════════")
            resultado_status = 'dry_run'
        else:
            etapa_atual = "clicar_salvar"
            clicar_salvar(driver, wait); shot("12_salvar_clicado")
            log.info("════════════════════════════════════════════════════")
            log.info("✅ SALVO — contratação criada no HubSoft")
            log.info("════════════════════════════════════════════════════")
            resultado_status = 'sucesso'

        if manter_aberto_segundos > 0:
            log.info(f"Mantendo navegador aberto por {manter_aberto_segundos}s...")
            time.sleep(manter_aberto_segundos)
        return {
            'status': resultado_status,
            'erro': '',
            'etapa': 'fim',
            'nome_cliente': dados.nome_cliente,
            'id_cliente_hubsoft': dados.id_cliente_hubsoft,
        }
    except Exception as e:
        log.exception(f"❌ Falha na etapa {etapa_atual!r}: {e}")
        shot(f"ERRO_{etapa_atual}")
        return {
            'status': 'falha',
            'erro': f"{type(e).__name__}: {e}"[:500],
            'etapa': etapa_atual,
            'nome_cliente': dados.nome_cliente,
            'id_cliente_hubsoft': dados.id_cliente_hubsoft,
        }
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description="Webdriver novo serviço HubSoft")
    p.add_argument("--id", "--new-service-id", dest="new_service_id",
                   type=int, required=True,
                   help="ID da row em new_service")
    p.add_argument("--vendedor", default="Venda-Automática-Matrix")
    p.add_argument("--grupo", default="Varejo")
    p.add_argument("--banco", default="BANCO ITAU")
    p.add_argument("--headless", action="store_true",
                   help="Roda sem janela (default: com janela)")
    p.add_argument("--avancos", type=int, default=5,
                   help="Quantos Avançar após escolher forma de cobrança")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="Não clica o SALVAR final — só percorre até lá")
    p.add_argument("--manter-aberto", type=int, default=0,
                   help="Segundos pra manter o navegador aberto no final")
    args = p.parse_args()

    res = executar(
        new_service_id=args.new_service_id,
        vendedor=args.vendedor,
        grupo=args.grupo,
        banco=args.banco,
        headless=args.headless,
        avancos_pos_cobranca=args.avancos,
        dry_run=args.dry_run,
        manter_aberto_segundos=args.manter_aberto,
    )
    log.info(f"RESULTADO: {res}")
    sys.exit(0 if res['status'] in ('sucesso', 'dry_run') else 1)


if __name__ == "__main__":
    main()
