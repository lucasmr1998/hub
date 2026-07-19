"""
Webdriver: UPGRADE de plano de um cliente_servico existente no HubSoft.

Fluxo: login → /cliente/editar/{id_cliente}/servico → cola
`id_cliente_servico` no campo de busca → 3-dots menu do card → "Migrar
para Outro Serviço" → wizard (plano novo, vendedor, switch migração
imediata, 6× Avançar) → SALVAR (ou para antes, em dry-run).

Origem dos dados: tabela `upgrade_plano` (DB robovendas).

Reaproveita helpers de `main_novo_servico.py` (login, driver setup,
selecionar_plano, selecionar_vendedor, etc.) — não duplica código.
"""

import argparse
import datetime as _dt
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
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Reaproveitamos infra do novo_servico — main_novo_servico.py vive na raiz
import sys as _sys
import os as _os

_IMPORTS = (
    'HUBSOFT_URL_BASE', 'TIMEOUT_PADRAO', 'PAUSA_CURTA', 'PAUSA_MEDIA', 'PAUSA_LONGA',
    '_conn', 'configurar_driver', 'clicar', 'esperar_clicavel', 'fazer_login',
    'selecionar_plano', 'selecionar_vendedor', 'WIZARD_ROOT', 'BTN_AVANCAR_XPATH',
    'clicar_avancar', 'clicar_salvar',
)
try:  # pacote (Django)
    from . import main_novo_servico as _mns
except ImportError:  # script solto
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import main_novo_servico as _mns
globals().update({_n: getattr(_mns, _n) for _n in _IMPORTS})

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger("upgrade_plano")


# ════════════════════════════════════════════════════════════════════
#  Modelo de dados que o wizard de upgrade precisa
# ════════════════════════════════════════════════════════════════════
@dataclass
class DadosUpgrade:
    upgrade_id: int
    id_cliente_hubsoft: int
    id_cliente_servico: int
    nome_cliente: str
    plano_atual_titulo: str       # só pra log/auditoria
    plano_novo_titulo: str        # texto exato do dropdown HubSoft


def buscar_dados(upgrade_id: int) -> DadosUpgrade:
    """Pega a row de upgrade_plano e cruza com HubSoft pra resolver
    nome do cliente e título do plano novo."""
    log.info(f"Buscando dados do upgrade_plano id={upgrade_id}")
    conn_rv = _conn('ROBOVENDAS')
    try:
        cur = conn_rv.cursor()
        cur.execute(
            """
            SELECT id, id_cliente_servico, id_plano_novo, lead_id
              FROM upgrade_plano
             WHERE id = %s
            """,
            (upgrade_id,),
        )
        row = cur.fetchone()
        cur.close()
    finally:
        conn_rv.close()

    if not row:
        raise SystemExit(f"upgrade_plano id={upgrade_id} não encontrado")

    up_id, id_cs, id_plano_novo, lead_id = row

    conn_hs = _conn('HUBSOFT')
    try:
        cur = conn_hs.cursor()
        # 1) Resolver id_cliente, plano atual e status do cliente_servico
        cur.execute(
            """
            SELECT cs.id_cliente, cs.id_servico, s_atual.descricao,
                   c.nome_razaosocial,
                   cs.id_servico_status, ss.descricao,
                   cs.data_cancelamento
              FROM cliente_servico cs
              LEFT JOIN servico s_atual ON s_atual.id_servico = cs.id_servico
              LEFT JOIN cliente c ON c.id_cliente = cs.id_cliente
              LEFT JOIN servico_status ss ON ss.id_servico_status = cs.id_servico_status
             WHERE cs.id_cliente_servico = %s
            """,
            (int(id_cs),),
        )
        r = cur.fetchone()
        if not r:
            raise SystemExit(
                f"upgrade_plano {up_id}: id_cliente_servico={id_cs} não existe no HubSoft"
            )
        (id_cliente, id_servico_atual, plano_atual, nome_cliente,
         id_status, status_desc, data_canc) = r

        # Status 9=Cancelado, 10=Inativo → não dá upgrade
        if id_status in (9, 10) or data_canc is not None:
            raise SystemExit(
                f"upgrade_plano {up_id}: serviço {id_cs} está "
                f"{status_desc!r} (data_cancelamento={data_canc}). "
                f"Upgrade só é permitido em serviço ativo."
            )

        # 2) Resolver título do plano novo
        cur.execute(
            "SELECT descricao, ativo FROM servico WHERE id_servico = %s",
            (int(id_plano_novo),),
        )
        r = cur.fetchone()
        if not r:
            raise SystemExit(
                f"plano id_servico={id_plano_novo} não existe no HubSoft"
            )
        plano_novo_desc, ativo_plano = r
        if not ativo_plano:
            raise SystemExit(
                f"plano destino id_servico={id_plano_novo} ({plano_novo_desc!r}) "
                f"está INATIVO no HubSoft"
            )
        if int(id_servico_atual) == int(id_plano_novo):
            raise SystemExit(
                f"upgrade_plano {up_id}: plano atual já é {plano_novo_desc!r} "
                f"(id_servico={id_plano_novo}). Nada a migrar."
            )

        cur.close()
    finally:
        conn_hs.close()

    dados = DadosUpgrade(
        upgrade_id=up_id,
        id_cliente_hubsoft=int(id_cliente),
        id_cliente_servico=int(id_cs),
        nome_cliente=nome_cliente or '',
        plano_atual_titulo=plano_atual or '',
        plano_novo_titulo=plano_novo_desc,
    )
    log.info(
        f"Cliente HubSoft #{dados.id_cliente_hubsoft} — {dados.nome_cliente!r} | "
        f"cs={dados.id_cliente_servico} ({dados.plano_atual_titulo!r}) "
        f"→ novo plano: {dados.plano_novo_titulo!r}"
    )
    return dados


# ════════════════════════════════════════════════════════════════════
#  Etapas específicas do fluxo de upgrade
# ════════════════════════════════════════════════════════════════════
def esperar_dashboard(driver, timeout: int = 30):
    """Garante que login completou antes de navegar. Espera por elementos
    típicos da home/menu (link 'Cliente' ou ícone do user no topo)."""
    log.info("  aguardando dashboard ficar pronto...")
    candidatos = [
        "//*[@class='hs-logo' or contains(@class,'logo')]",
        "//md-icon[contains(@class,'icon-menu')]",
        "//*[contains(text(),'Cliente') or contains(text(),'Dashboard')]",
    ]
    fim = time.time() + timeout
    while time.time() < fim:
        for xp in candidatos:
            try:
                els = driver.find_elements(By.XPATH, xp)
                if any(e.is_displayed() for e in els):
                    log.info("  dashboard pronto")
                    return
            except Exception:
                pass
        # Detecta se voltamos pra tela de login
        try:
            if driver.find_elements(By.NAME, "email") and any(
                e.is_displayed() for e in driver.find_elements(By.NAME, "email")
            ):
                # ainda na tela de login — espera login completar
                pass
        except Exception:
            pass
        time.sleep(1)
    log.warning("  dashboard não confirmado — seguindo mesmo assim")


def abrir_servico(driver, wait, id_cliente: int):
    esperar_dashboard(driver)
    url = f"{HUBSOFT_URL_BASE}/cliente/editar/{id_cliente}/servico"
    log.info(f"ETAPA 2: navegar para {url}")
    driver.get(url)
    time.sleep(PAUSA_LONGA)
    # Se ainda assim caímos no login, tenta novamente após mais tempo
    try:
        if driver.find_elements(By.NAME, "email"):
            log.warning("  caiu na tela de login após navigate, aguardando...")
            time.sleep(PAUSA_LONGA * 2)
            driver.get(url)
            time.sleep(PAUSA_LONGA)
    except Exception:
        pass


def _aumentar_itens_por_pagina(driver, wait):
    """Sobe pra 50 itens/página pra reduzir necessidade de paginação."""
    try:
        sel = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.XPATH, "//md-select[contains(@ng-model,'itensPorPagina') "
                       "or contains(@aria-label,'Itens por')]")
        ))
        clicar(driver, sel)
        time.sleep(PAUSA_CURTA)
        opt = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.XPATH, "//md-option[contains(., '50')]")
        ))
        clicar(driver, opt)
        time.sleep(PAUSA_MEDIA)
        log.info("  itens por página → 50")
    except TimeoutException:
        log.info("  selector de itens/página não achado, seguindo com default")


def _localizar_card_xpath(id_cliente_servico: int) -> str:
    """XPath do CARD que contém 'ID Cliente Serviço: {N}'."""
    return (
        f"//*[contains(normalize-space(.), 'ID Cliente Serviço: {id_cliente_servico}')]"
        f"[not(.//*[contains(normalize-space(.), 'ID Cliente Serviço: {id_cliente_servico}')])]"
        "/ancestor::*[self::md-card or self::hs-card "
        "or contains(@class,'card') or contains(@class,'hs-card')][1]"
    )


def localizar_card_servico(driver, wait, id_cliente_servico: int):
    """Procura na página o card que contém 'ID Cliente Serviço: {id}'.

    Se não achar e houver paginação, tenta avançar páginas até encontrar.
    Retorna o WebElement do card.
    """
    log.info(f"ETAPA 3: localizar card do cs={id_cliente_servico} na lista")
    _aumentar_itens_por_pagina(driver, wait)

    texto_xp = (
        f"//*[contains(normalize-space(.), 'ID Cliente Serviço: "
        f"{id_cliente_servico}')]"
    )

    for tentativa in range(1, 11):  # até 10 páginas
        try:
            els = driver.find_elements(By.XPATH, texto_xp)
            for e in els:
                if e.is_displayed():
                    # Ancestor é o card real
                    log.info(f"  ✓ card achado na tentativa {tentativa}")
                    return e
        except Exception:
            pass
        # Tenta avançar página
        try:
            proxima = driver.find_element(
                By.XPATH,
                "//button[contains(@aria-label,'Próxima') or "
                "contains(@aria-label,'próxima') or "
                "contains(@aria-label,'Next')]"
            )
            if not proxima.is_enabled():
                break
            clicar(driver, proxima)
            time.sleep(PAUSA_MEDIA)
        except Exception:
            break

    raise RuntimeError(
        f"Card com 'ID Cliente Serviço: {id_cliente_servico}' não foi "
        f"encontrado em nenhuma página da lista"
    )


def abrir_menu_acoes_do_servico(driver, wait, id_cliente_servico: int):
    """Acha o card pelo texto 'ID Cliente Serviço: {N}' e clica no
    ícone '⋮' dele.
    """
    log.info(f"ETAPA 4: abrir menu '⋮' do card cs={id_cliente_servico}")
    # Sobe pelo DOM até o md-card ancestral, depois busca o ⋮ dentro dele
    card_xp = _localizar_card_xpath(id_cliente_servico)

    icone = None
    # 1ª tentativa: ícone dentro do card ancestral
    try:
        els = driver.find_elements(
            By.XPATH,
            f"{card_xp}//md-icon[contains(@class,'icon-dots-vertical') "
            f"or @md-font-icon='icon-dots-vertical']",
        )
        for e in els:
            if e.is_displayed():
                icone = e
                break
    except Exception:
        pass

    # 2ª tentativa: ícone como sibling do texto (sem precisar de md-card)
    if icone is None:
        try:
            els = driver.find_elements(
                By.XPATH,
                f"//*[contains(normalize-space(.), 'ID Cliente Serviço: "
                f"{id_cliente_servico}')]"
                "/ancestor::*[descendant::md-icon["
                "contains(@class,'icon-dots-vertical') "
                "or @md-font-icon='icon-dots-vertical'"
                "]][1]"
                "//md-icon[contains(@class,'icon-dots-vertical') "
                "or @md-font-icon='icon-dots-vertical']",
            )
            for e in els:
                if e.is_displayed():
                    icone = e
                    break
        except Exception:
            pass

    if icone is None:
        raise RuntimeError(
            f"Não achei o ícone '⋮' próximo ao card cs={id_cliente_servico}"
        )
    clicar(driver, icone)
    time.sleep(PAUSA_MEDIA)


def fechar_pesquisa_nps(driver):
    """Fecha o popup de pesquisa NPS do HubSoft (Em uma escala de 0 a 10...) que
    aparece intermitentemente e bloqueia os cliques. Idempotente."""
    for rotulo in ('NÃO QUERO RESPONDER', 'RESPONDER DEPOIS', 'Não quero responder'):
        try:
            els = driver.find_elements(
                By.XPATH,
                f'//*[self::button or @role="button" or self::a]'
                f'[contains(normalize-space(.), "{rotulo}")]')
            for e in els:
                if e.is_displayed():
                    driver.execute_script("arguments[0].click();", e)
                    time.sleep(0.6)
                    log.info(f"  popup NPS fechado ({rotulo!r})")
                    return True
        except Exception:
            pass
    return False


def clicar_migrar_para_outro_servico(driver, wait):
    log.info("ETAPA 5: clicar 'Migrar para Outro Serviço'")
    fechar_pesquisa_nps(driver)
    # O item costuma ser o último do menu (fora do viewport) → element_to_be_clickable
    # falha. Buscamos por PRESENÇA (is_displayed) e clicamos via JS (scrollIntoView).
    # 'Outro Serviço' distingue de 'Migrar para Outro Cliente'.
    xps = (
        "//button[@aria-label='Migrar para Outro Serviço']",
        "//*[self::button or self::md-menu-item or @role='menuitem']"
        "[contains(normalize-space(.), 'Migrar para Outro Serviço')]",
    )
    btn = None
    fim = time.time() + 15
    while btn is None and time.time() < fim:
        for xp in xps:
            for e in driver.find_elements(By.XPATH, xp):
                if e.is_displayed():
                    btn = e
                    break
            if btn:
                break
        if btn is None:
            time.sleep(0.5)
    if btn is None:
        raise TimeoutException("opção 'Migrar para Outro Serviço' não encontrada")
    clicar(driver, btn)   # scrollIntoView + JS click
    time.sleep(PAUSA_LONGA)


def ativar_switch_migracao_imediata(driver, wait):
    """Liga o md-switch de 'Executar Migração Imediata' (se já não estiver).
    O switch fica no form, em div[6]/div[1] segundo o roteiro. Buscamos
    pelo aria-label/atributo mais estável quando possível.
    """
    log.info("ETAPA 7: ativar switch 'Migração Imediata'")
    # Tentamos múltiplas formas de localizar o switch
    candidatos = [
        f"{WIZARD_ROOT}//md-switch["
        "contains(translate(@aria-label,'IM','im'), 'migra') and "
        "contains(translate(@aria-label,'IM','im'), 'imediata')]",
        f"{WIZARD_ROOT}//md-switch[contains(@aria-label,'Imediata') "
        "or contains(@aria-label,'imediata')]",
        # Switch dentro de um container cujo label menciona "Migração Imediata"
        f"{WIZARD_ROOT}//*[contains(translate(., 'IÇ', 'iç'), 'imediata')]"
        "/ancestor-or-self::*//md-switch[1]",
        # Posicional do roteiro (fallback)
        f"{WIZARD_ROOT}//form/div[6]/div[1]/md-switch",
    ]
    sw = None
    for xp in candidatos:
        try:
            sw = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            log.info(f"  switch achado via: {xp[:80]}...")
            break
        except TimeoutException:
            continue
    if sw is None:
        raise RuntimeError("Não achei o switch 'Migração Imediata'")

    # Já está ligado?
    aria_checked = (sw.get_attribute("aria-checked") or "").lower()
    if aria_checked == "true":
        log.info("  já está ligado, nada a fazer")
        return
    clicar(driver, sw)
    time.sleep(PAUSA_MEDIA)
    # Confirma que ligou
    aria_checked2 = (sw.get_attribute("aria-checked") or "").lower()
    if aria_checked2 != "true":
        log.warning(f"  aria-checked após clique: {aria_checked2!r} (esperava 'true')")


# ════════════════════════════════════════════════════════════════════
#  Orquestrador
# ════════════════════════════════════════════════════════════════════
def executar(upgrade_id: int,
             vendedor: str = "Venda-Automática-Matrix",
             headless: bool = False,
             avancos_pos_switch: int = 6,
             dry_run: bool = True,
             manter_aberto_segundos: int = 0) -> dict:
    """Executa o fluxo de upgrade de plano no HubSoft.

    Default `dry_run=True` por segurança — quem chama (polling) seta
    explicitamente `dry_run=False` quando estiver liberado pra produção.

    Retorna dict com `status` ∈ {'sucesso','falha','dry_run'},
    `erro`, `etapa`, `nome_cliente`, `id_cliente_hubsoft`.
    """
    usuario = os.environ.get('USUARIO', '')
    senha = os.environ.get('SENHA', '')
    if not usuario or not senha:
        raise SystemExit("USUARIO/SENHA não definidos no .env")

    dados = buscar_dados(upgrade_id)

    driver, tmp = configurar_driver(headless)
    wait = WebDriverWait(driver, TIMEOUT_PADRAO)

    shots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "screenshots_upgrade_plano")
    os.makedirs(shots_dir, exist_ok=True)
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
        fechar_pesquisa_nps(driver)   # NPS pode aparecer ao carregar a página
        etapa_atual = "localizar_card"
        localizar_card_servico(driver, wait, dados.id_cliente_servico); shot("03_card_localizado")
        etapa_atual = "abrir_menu_acoes"
        abrir_menu_acoes_do_servico(driver, wait, dados.id_cliente_servico); shot("04_menu_aberto")
        etapa_atual = "clicar_migrar"
        clicar_migrar_para_outro_servico(driver, wait); shot("05_wizard_migrar_aberto")
        etapa_atual = "selecionar_plano"
        fechar_pesquisa_nps(driver)
        selecionar_plano(driver, wait, dados.plano_novo_titulo); shot("06_plano_novo_ok")
        etapa_atual = "selecionar_vendedor"
        selecionar_vendedor(driver, wait, vendedor); shot("07_vendedor_ok")
        etapa_atual = "switch_migracao_imediata"
        ativar_switch_migracao_imediata(driver, wait); shot("08_switch_on")
        for i in range(avancos_pos_switch):
            etapa_atual = f"avancar_{i+1}"
            clicar_avancar(driver, wait, f"upgrade {i+1}/{avancos_pos_switch}")
            shot(f"09_avanco_{i+1}")

        if dry_run:
            log.info("════════════════════════════════════════════════════")
            log.info("✅ DRY-RUN OK — chegou no passo anterior ao SALVAR")
            log.info("   (o botão SALVAR final NÃO foi clicado)")
            log.info("════════════════════════════════════════════════════")
            resultado_status = 'dry_run'
        else:
            etapa_atual = "clicar_salvar"
            clicar_salvar(driver, wait); shot("10_salvar_clicado")
            log.info("════════════════════════════════════════════════════")
            log.info("✅ SALVO — upgrade aplicado no HubSoft")
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
    p = argparse.ArgumentParser(description="Webdriver upgrade de plano HubSoft")
    p.add_argument("--id", "--upgrade-id", dest="upgrade_id",
                   type=int, required=True,
                   help="ID da row em upgrade_plano")
    p.add_argument("--vendedor", default="Venda-Automática-Matrix")
    p.add_argument("--headless", action="store_true",
                   help="Roda sem janela (default: com janela)")
    p.add_argument("--avancos", type=int, default=6,
                   help="Quantos Avançar após ativar switch (default 6)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   default=True,
                   help="Não clica SALVAR (default ON — segurança)")
    p.add_argument("--salvar", dest="dry_run", action="store_false",
                   help="Clica o SALVAR final (modo produção)")
    p.add_argument("--manter-aberto", type=int, default=0,
                   help="Segundos pra manter navegador aberto no final")
    args = p.parse_args()

    res = executar(
        upgrade_id=args.upgrade_id,
        vendedor=args.vendedor,
        headless=args.headless,
        avancos_pos_switch=args.avancos,
        dry_run=args.dry_run,
        manter_aberto_segundos=args.manter_aberto,
    )
    log.info(f"RESULTADO: {res}")
    sys.exit(0 if res['status'] in ('sucesso', 'dry_run') else 1)


if __name__ == "__main__":
    main()
