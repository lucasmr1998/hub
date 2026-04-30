"""
Importa os e-mails do Paper.design pro Workspace (pasta Marketing > Design de E-mails).

JSX de cada e-mail está embutido neste arquivo (capturado via MCP do Paper em 29/04/2026).
Os PNGs foram exportados pelo Paper para ~/Downloads/.

Uso:
    python manage.py importar_emails_paper [--tenant "Aurora HQ"] [--png-dir "C:/Users/lucas/Downloads"] [--dry-run]
"""
import re
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.sistema.models import Tenant
from apps.workspace.models import AnexoDocumento, Documento, PastaDocumento


# ---------------------------------------------------------------------------
# JSX → HTML converter
# ---------------------------------------------------------------------------

def _camel_to_css_prop(name: str) -> str:
    if name.startswith('Moz'):
        return '-moz-' + _camel_to_css_prop(name[3:])
    if name.startswith('Webkit'):
        return '-webkit-' + _camel_to_css_prop(name[6:])
    return re.sub(r'([A-Z])', r'-\1', name).lower()


def _parse_style_block(block: str) -> str:
    props = []
    for m in re.finditer(r"(\w+):\s*'([^']*)'", block):
        prop = _camel_to_css_prop(m.group(1))
        # Aspas duplas dentro do valor quebram o atributo style="..."
        # Trocar por aspas simples (válidas em CSS pra font-family).
        val = m.group(2).replace('"', "'")
        props.append(f'{prop}: {val}')
    return '; '.join(props)


def jsx_to_html(jsx: str) -> str:
    html = jsx.strip()
    if html.startswith('('):
        html = html[1:]
    if html.endswith(')'):
        html = html[:-1]
    html = html.strip()

    def replace_style(m):
        css = _parse_style_block(m.group(1))
        return f'style="{css}"'

    html = re.sub(r'style=\{\{(.*?)\}\}', replace_style, html, flags=re.DOTALL)
    html = re.sub(r'<(div|span)([^>]*)\/>', r'<\1\2></\1>', html)
    html = html.replace('<br />', '<br>')
    return html


# ---------------------------------------------------------------------------
# Paleta Hubtrix v2 — substituições do cobalto/azul pelas cores da marca
# ---------------------------------------------------------------------------

# Mapeamento das cores antigas (paleta indigo/cobalto v1) pra paleta v2 (tinta + sienna + branco)
PALETTE_V2 = {
    '#1D4ED8': '#252020',  # cobalto primary -> tinta
    '#0B1220': '#252020',  # azul navy quase preto -> tinta
    '#60A5FA': '#E76F51',  # azul claro accent -> sienna
    '#93C5FD': '#E76F51',  # azul mais claro -> sienna
    '#BFDBFE': '#FED7AA',  # azul soft bg -> sienna soft
    '#DBEAFE': '#FED7AA',  # azul muito soft bg -> sienna soft
    '#FFFFFF1F': '#FFFFFF1F',  # mantem (transparencias)
    '#FFFFFF14': '#FFFFFF14',
    '#FFFFFF26': '#FFFFFF26',
}


def aplicar_paleta_v2(html: str) -> str:
    """Substitui cores cobalto/indigo pela paleta v2 (tinta + sienna + branco)."""
    for antiga, nova in PALETTE_V2.items():
        if antiga != nova:
            html = html.replace(antiga, nova)
    return html


def extrair_corpo_email(html: str) -> str:
    """Remove o wrapper outer F8FAFC do e-mail, devolve só o card interno + conteudo.

    Os e-mails JSX vêm com estrutura:
        <div bg=#F8FAFC pad=32>     ← outer wrapper a remover
          <div bg=#FFF radius=12>    ← card a manter
            ...
          </div>
        </div>
    """
    h = html.strip()
    # Remove o primeiro <div ...> (outer)
    first_close = h.index('>') + 1
    # Remove o último </div> (fecha outer)
    last_open = h.rfind('</div>')
    return h[first_close:last_open].strip()


# Header v2 e Footer v2 — versão pré-convertida sem o pré-processamento do paleta
# (eles já estão em paleta v2 nativa)
def _gerar_header_v2_html() -> str:
    return jsx_to_html(_EMAIL_HEADER)


def _gerar_footer_v2_html() -> str:
    return jsx_to_html(_EMAIL_FOOTER)


def montar_email_v2(corpo_html: str, header_html: str, footer_html: str) -> str:
    """Monta um e-mail completo: wrapper F8FAFC + Header v2 + corpo (card) + Footer v2."""
    return (
        '<div style="background-color: #F8FAFC; box-sizing: border-box; '
        'padding: 0; width: 640px; margin: 0 auto;">'
        '\n  <!-- Header v2 -->\n  '
        + header_html.strip()
        + '\n\n  <!-- Corpo do e-mail -->\n  '
        '<div style="padding: 0 32px 32px;">'
        + corpo_html.strip()
        + '</div>\n\n  <!-- Footer v2 -->\n  '
        + footer_html.strip()
        + '\n</div>'
    )


# ---------------------------------------------------------------------------
# JSX dos e-mails (capturado do Paper via MCP em 29/04/2026)
# ---------------------------------------------------------------------------

_EMAIL_BOAS_VINDAS = r"""(
    <div style={{ backgroundColor: '#F8FAFC', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', paddingBlock: '32px', paddingInline: '32px', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: '12px', borderStyle: 'solid', borderWidth: '1px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', overflow: 'clip' }}>
        <div style={{ alignItems: 'center', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', justifyContent: 'space-between', paddingBlock: '24px', paddingInline: '32px' }}>
          <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', gap: '8px' }}>
            <div style={{ backgroundColor: '#1D4ED8', borderRadius: '6px', boxSizing: 'border-box', flexShrink: '0', height: '24px', width: '24px' }}></div>
            <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em', lineHeight: '22px' }}>hubtrix</div>
          </div>
          <div style={{ boxSizing: 'border-box', color: '#94A3B8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>hubtrix.com.br</div>
        </div>
        <div style={{ backgroundColor: '#FFFFFF', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '48px' }}>
          <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', lineHeight: '14px', textTransform: 'uppercase' }}>Bem-vindo</div>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '36px', fontWeight: '800', letterSpacing: '-0.025em', lineHeight: '110%' }}>Bom te ver por aqui, Lucas.</div>
          <div style={{ boxSizing: 'border-box', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '16px', lineHeight: '160%' }}>Sua conta no Hubtrix tá pronta. Em 15 minutos seu provedor começa a vender, atender e fidelizar com IA conectada ao que você já usa.</div>
        </div>
        <div style={{ backgroundColor: '#0B1220', borderRadius: '12px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '0px', marginLeft: '32px', marginRight: '32px', marginTop: '0px', paddingBlock: '24px', paddingInline: '24px' }}>
          <div style={{ boxSizing: 'border-box', color: '#60A5FA', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', lineHeight: '14px', textTransform: 'uppercase' }}>Seus acessos</div>
          <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ boxSizing: 'border-box', color: '#FFFFFF99', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>URL da plataforma</div>
            <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"JetBrains Mono", system-ui, sans-serif', fontSize: '14px', lineHeight: '18px' }}>app.hubtrix.com.br/seuprovedor</div>
          </div>
          <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ boxSizing: 'border-box', color: '#FFFFFF99', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>Login</div>
            <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"JetBrains Mono", system-ui, sans-serif', fontSize: '14px', lineHeight: '18px' }}>lucas@seuprovedor.com.br</div>
          </div>
          <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', gap: '12px', marginTop: '8px' }}>
            <div style={{ backgroundColor: '#1D4ED8', borderRadius: '8px', boxSizing: 'border-box', paddingBlock: '14px', paddingInline: '24px' }}>
              <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', fontWeight: '600', lineHeight: '18px' }}>Entrar na plataforma →</div>
            </div>
          </div>
        </div>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px', paddingBlock: '32px', paddingInline: '32px' }}>
          <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ boxSizing: 'border-box', color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '22px', fontWeight: '700', letterSpacing: '-0.015em', lineHeight: '120%' }}>Os próximos 15 minutos.</div>
            <div style={{ boxSizing: 'border-box', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '160%' }}>A equipe de onboarding já marcou um papo com você. Mas se quiser começar a olhar antes, é por aqui:</div>
          </div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', gap: '16px', paddingBlock: '16px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#DBEAFE', borderRadius: '99px', boxSizing: 'border-box', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}>
              <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700', lineHeight: '18px' }}>1</div>
            </div>
            <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '15px', fontWeight: '600', lineHeight: '18px' }}>Conecta seu ERP</div>
              <div style={{ boxSizing: 'border-box', color: '#475569', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>HubSoft, SGP, MK-Auth ou IXC. A IA puxa cliente, plano e viabilidade sozinha.</div>
            </div>
          </div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', gap: '16px', paddingBlock: '16px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#DBEAFE', borderRadius: '99px', boxSizing: 'border-box', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}>
              <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700', lineHeight: '18px' }}>2</div>
            </div>
            <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '15px', fontWeight: '600', lineHeight: '18px' }}>Pluga seu canal de atendimento</div>
              <div style={{ boxSizing: 'border-box', color: '#475569', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>A IA entra na plataforma que você já usa. Não troca nada.</div>
            </div>
          </div>
          <div style={{ boxSizing: 'border-box', display: 'flex', gap: '16px', paddingBlock: '16px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#DBEAFE', borderRadius: '99px', boxSizing: 'border-box', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}>
              <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700', lineHeight: '18px' }}>3</div>
            </div>
            <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '15px', fontWeight: '600', lineHeight: '18px' }}>Solta a IA pra qualificar lead</div>
              <div style={{ boxSizing: 'border-box', color: '#475569', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>Treinada pra ISP. 8 perguntas de qualificação. Recontato automático.</div>
            </div>
          </div>
        </div>
        <div style={{ backgroundColor: '#F8FAFC', borderLeftColor: '#E76F51', borderLeftStyle: 'solid', borderLeftWidth: '3px', borderRadius: '12px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '32px', marginLeft: '32px', marginRight: '32px', marginTop: '0px', paddingBlock: '20px', paddingInline: '24px' }}>
          <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px', lineHeight: '100%' }}>↘ a gente atende</div>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '160%' }}>Travou em alguma coisa? Responde esse e-mail. Ou chama no WhatsApp (86) 9 9999-9999. Quem responde é gente, não bot.</div>
        </div>
        <div style={{ borderTopColor: '#E2E8F0', borderTopStyle: 'solid', borderTopWidth: '1px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '12px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '24px' }}>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700', letterSpacing: '-0.01em', lineHeight: '18px' }}>hubtrix</div>
          <div style={{ boxSizing: 'border-box', color: '#94A3B8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '160%' }}>Vende mais. Perde menos. Fideliza sempre.<br />Teresina, PI · hubtrix.com.br</div>
          <div style={{ boxSizing: 'border-box', color: '#CBD5E1', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', lineHeight: '14px', marginTop: '4px' }}>Você recebe esse e-mail porque criou uma conta no Hubtrix. Cancelar inscrição</div>
        </div>
      </div>
    </div>
  )"""

_EMAIL_ATENDIMENTO = r"""(
    <div style={{ backgroundColor: '#F8FAFC', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', paddingBlock: '32px', paddingInline: '32px', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: '12px', borderStyle: 'solid', borderWidth: '1px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', overflow: 'clip' }}>
        <div style={{ alignItems: 'center', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', justifyContent: 'space-between', paddingBlock: '24px', paddingInline: '32px' }}>
          <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', gap: '8px' }}>
            <div style={{ backgroundColor: '#1D4ED8', borderRadius: '6px', boxSizing: 'border-box', flexShrink: '0', height: '24px', width: '24px' }}></div>
            <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em', lineHeight: '22px' }}>hubtrix</div>
          </div>
          <div style={{ boxSizing: 'border-box', color: '#94A3B8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>hubtrix.com.br</div>
        </div>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '48px' }}>
          <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', lineHeight: '14px', textTransform: 'uppercase' }}>Módulo 01 ativo · Atendimento</div>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '36px', fontWeight: '800', letterSpacing: '-0.025em', lineHeight: '110%' }}>Sua IA já tá conversando.</div>
          <div style={{ boxSizing: 'border-box', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '16px', lineHeight: '160%' }}>Conectamos a IA no canal de atendimento que você já usa. Ela qualifica, agenda visita técnica e recontata sozinho. Olha o que aconteceu na primeira hora.</div>
        </div>
        <div style={{ backgroundColor: '#0B1220', borderRadius: '12px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '0px', marginLeft: '32px', marginRight: '32px', marginTop: '0px', paddingBlock: '28px', paddingInline: '28px' }}>
          <div style={{ boxSizing: 'border-box', color: '#60A5FA', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', lineHeight: '14px', textTransform: 'uppercase' }}>Primeira hora rodando</div>
          <div style={{ alignItems: 'flex-end', boxSizing: 'border-box', display: 'flex', gap: '16px', justifyContent: 'space-between' }}>
            <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: '100%' }}>12</div>
              <div style={{ boxSizing: 'border-box', color: '#FFFFFF99', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>Leads recebidos</div>
            </div>
            <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: '100%' }}>9</div>
              <div style={{ boxSizing: 'border-box', color: '#FFFFFF99', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>Qualificados</div>
            </div>
            <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ boxSizing: 'border-box', color: '#60A5FA', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: '100%' }}>3</div>
              <div style={{ boxSizing: 'border-box', color: '#FFFFFF99', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '16px' }}>Prontos pra fechar</div>
            </div>
          </div>
          <div style={{ alignSelf: 'flex-start', backgroundColor: '#1D4ED8', borderRadius: '8px', boxSizing: 'border-box', paddingBlock: '14px', paddingInline: '22px' }}>
            <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', fontWeight: '600', lineHeight: '18px' }}>Ver conversas →</div>
          </div>
        </div>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '16px', paddingBlock: '32px', paddingInline: '32px' }}>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '20px', fontWeight: '700', letterSpacing: '-0.015em', lineHeight: '120%' }}>Ajustes rápidos pra essa semana</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#DBEAFE', borderRadius: '99px', boxSizing: 'border-box', display: 'flex', flexShrink: '0', height: '28px', justifyContent: 'center', width: '28px' }}>
              <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '13px', fontWeight: '700', lineHeight: '16px' }}>1</div>
            </div>
            <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%' }}>Revise as 8 perguntas de qualificação. Treinamos pra ISP em geral, mas seu provedor tem nuance.</div>
          </div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#DBEAFE', borderRadius: '99px', boxSizing: 'border-box', display: 'flex', flexShrink: '0', height: '28px', justifyContent: 'center', width: '28px' }}>
              <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '13px', fontWeight: '700', lineHeight: '16px' }}>2</div>
            </div>
            <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%' }}>Defina quando recontatar. Padrão: 3h, 24h, 72h. Você pode encurtar ou esticar.</div>
          </div>
          <div style={{ boxSizing: 'border-box', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#DBEAFE', borderRadius: '99px', boxSizing: 'border-box', display: 'flex', flexShrink: '0', height: '28px', justifyContent: 'center', width: '28px' }}>
              <div style={{ boxSizing: 'border-box', color: '#1D4ED8', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '13px', fontWeight: '700', lineHeight: '16px' }}>3</div>
            </div>
            <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%' }}>Ajuste horário de pico. Lead que cai fora do expediente cai num fluxo diferente.</div>
          </div>
        </div>
        <div style={{ backgroundColor: '#F8FAFC', borderLeftColor: '#E76F51', borderLeftStyle: 'solid', borderLeftWidth: '3px', borderRadius: '12px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '32px', marginLeft: '32px', marginRight: '32px', marginTop: '0px', paddingBlock: '20px', paddingInline: '24px' }}>
          <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px', lineHeight: '100%' }}>↘ a gente atende</div>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '160%' }}>Travou? Responde esse e-mail. Quem responde é gente, não bot.</div>
        </div>
        <div style={{ borderTopColor: '#E2E8F0', borderTopStyle: 'solid', borderTopWidth: '1px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '24px' }}>
          <div style={{ boxSizing: 'border-box', color: '#0B1220', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700', letterSpacing: '-0.01em', lineHeight: '18px' }}>hubtrix</div>
          <div style={{ boxSizing: 'border-box', color: '#94A3B8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px', lineHeight: '160%' }}>Vende mais. Perde menos. Fideliza sempre.</div>
        </div>
      </div>
    </div>
  )"""

_EMAIL_CRM = r"""(
    <div style={{ backgroundColor: '#F8FAFC', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', paddingBlock: '32px', paddingInline: '32px', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: '12px', borderStyle: 'solid', borderWidth: '1px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', overflow: 'clip' }}>
        <div style={{ alignItems: 'center', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', boxSizing: 'border-box', display: 'flex', justifyContent: 'space-between', paddingBlock: '24px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '18px', fontWeight: '800', letterSpacing: '-0.02em' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>hubtrix.com.br</div>
        </div>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '48px' }}>
          <div style={{ color: '#1D4ED8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Módulo 02 ativo · CRM Comercial</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '36px', fontWeight: '800', letterSpacing: '-0.025em', lineHeight: '110%' }}>Seu pipeline tá montado.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '16px', lineHeight: '160%' }}>Importamos seus leads do HubSoft. CTO, viabilidade técnica e plano combo já estão organizados por estágio. Sem mexer no seu ERP.</div>
        </div>
        <div style={{ backgroundColor: '#0B1220', borderRadius: '12px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px', marginLeft: '32px', marginRight: '32px', paddingBlock: '28px', paddingInline: '28px' }}>
          <div style={{ color: '#60A5FA', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Importação concluída</div>
          <div style={{ alignItems: 'flex-end', display: 'flex', gap: '16px', justifyContent: 'space-between' }}>
            <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: '100%' }}>248</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Leads importados</div></div>
            <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: '100%' }}>18</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Oportunidades quentes</div></div>
            <div><div style={{ color: '#60A5FA', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800', letterSpacing: '-0.03em', lineHeight: '100%' }}>R$47k</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Pipeline aberto</div></div>
          </div>
          <div style={{ alignSelf: 'flex-start', backgroundColor: '#1D4ED8', borderRadius: '8px', paddingBlock: '14px', paddingInline: '22px' }}>
            <div style={{ color: '#FFFFFF', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', fontWeight: '600' }}>Abrir pipeline →</div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', paddingBlock: '32px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '20px', fontWeight: '700', letterSpacing: '-0.015em', lineHeight: '120%' }}>Próximos passos</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>1. Revise os estágios. Padrão é Qualificado → Viabilidade → Proposta → Fechado. Customizável.</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>2. Atribua leads pra equipe. Distribuição automática por carteira ou manual.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>3. Defina meta do mês. Vendedor vê em tempo real quanto falta. Sem planilha.</div>
        </div>
        <div style={{ backgroundColor: '#F8FAFC', borderLeftColor: '#E76F51', borderLeftStyle: 'solid', borderLeftWidth: '3px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '32px', marginLeft: '32px', marginRight: '32px', paddingBlock: '20px', paddingInline: '24px' }}>
          <div style={{ color: '#E76F51', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px' }}>↘ tá faltando algo?</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '160%' }}>Lead que ficou de fora ou campo que precisa ajustar? Responde esse e-mail.</div>
        </div>
        <div style={{ borderTopColor: '#E2E8F0', borderTopStyle: 'solid', borderTopWidth: '1px', display: 'flex', flexDirection: 'column', gap: '8px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '24px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Vende mais. Perde menos. Fideliza sempre.</div>
        </div>
      </div>
    </div>
  )"""

_EMAIL_FIDELIZACAO = r"""(
    <div style={{ backgroundColor: '#F8FAFC', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', paddingBlock: '32px', paddingInline: '32px', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: '12px', borderStyle: 'solid', borderWidth: '1px', display: 'flex', flexDirection: 'column', overflow: 'clip' }}>
        <div style={{ alignItems: 'center', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', justifyContent: 'space-between', paddingBlock: '24px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '18px', fontWeight: '800' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>hubtrix.com.br</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '48px' }}>
          <div style={{ color: '#1D4ED8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Módulo 03 ativo · Fidelização</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '36px', fontWeight: '800', lineHeight: '110%' }}>Seu clube tá no ar.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '16px', lineHeight: '160%' }}>Ativamos NPS automático, programa de indicação e clube de benefícios. Seus clientes ativos já têm acesso. Hora de virar churn em advocacy.</div>
        </div>
        <div style={{ backgroundColor: '#0B1220', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '20px', marginLeft: '32px', marginRight: '32px', paddingBlock: '28px', paddingInline: '28px' }}>
          <div style={{ color: '#60A5FA', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Status do clube</div>
          <div style={{ alignItems: 'flex-end', display: 'flex', gap: '16px', justifyContent: 'space-between' }}>
            <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800' }}>8.234</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Clientes ativos</div></div>
            <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800' }}>23</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Parceiros locais</div></div>
            <div><div style={{ color: '#60A5FA', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '48px', fontWeight: '800' }}>NPS</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Rodando 24/7</div></div>
          </div>
          <div style={{ alignSelf: 'flex-start', backgroundColor: '#1D4ED8', borderRadius: '8px', paddingBlock: '14px', paddingInline: '22px' }}>
            <div style={{ color: '#FFFFFF', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', fontWeight: '600' }}>Abrir o clube →</div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', paddingBlock: '32px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '20px', fontWeight: '700' }}>Pra encher o clube essa semana</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>1. Adicione mais parceiros locais. Restaurante, farmácia, posto. Cliente sente o valor na rua.</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>2. Defina prêmio de indicação. Padrão: 1 mês grátis. Você pode trocar por desconto, upgrade ou voucher.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>3. Customize a mensagem do NPS. Default funciona, mas com sua voz performa mais.</div>
        </div>
        <div style={{ backgroundColor: '#F8FAFC', borderLeftColor: '#E76F51', borderLeftStyle: 'solid', borderLeftWidth: '3px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '32px', marginLeft: '32px', marginRight: '32px', paddingBlock: '20px', paddingInline: '24px' }}>
          <div style={{ color: '#E76F51', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px' }}>↘ dica</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '160%' }}>Cliente que entra no clube nos primeiros 30 dias tem 3x menos churn no primeiro ano. Manda um SMS e empurra todo mundo pra dentro logo.</div>
        </div>
        <div style={{ borderTopColor: '#E2E8F0', borderTopStyle: 'solid', borderTopWidth: '1px', display: 'flex', flexDirection: 'column', gap: '8px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '24px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Vende mais. Perde menos. Fideliza sempre.</div>
        </div>
      </div>
    </div>
  )"""

_EMAIL_AUTOMACAO = r"""(
    <div style={{ backgroundColor: '#F8FAFC', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', paddingBlock: '32px', paddingInline: '32px', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: '12px', borderStyle: 'solid', borderWidth: '1px', display: 'flex', flexDirection: 'column', overflow: 'clip' }}>
        <div style={{ alignItems: 'center', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', justifyContent: 'space-between', paddingBlock: '24px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '18px', fontWeight: '800' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>hubtrix.com.br</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '48px' }}>
          <div style={{ color: '#1D4ED8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Módulo 04 ativo · Automação</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '36px', fontWeight: '800', lineHeight: '110%' }}>3 fluxos prontos rodando.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '16px', lineHeight: '160%' }}>Ativamos os fluxos que mais funcionam pra provedor: recuperação de orçamento, régua de boas-vindas e recontato de inadimplência leve. Sem código. Você só edita o que quiser.</div>
        </div>
        <div style={{ backgroundColor: '#1D4ED8', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '20px', marginLeft: '32px', marginRight: '32px', paddingBlock: '28px', paddingInline: '28px' }}>
          <div style={{ color: '#BFDBFE', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Fluxos ativos</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ alignItems: 'center', borderBottomColor: '#FFFFFF26', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', justifyContent: 'space-between', paddingBlock: '12px' }}>
              <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '15px', fontWeight: '600' }}>Recuperação de orçamento</div><div style={{ color: '#BFDBFE', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Dispara 24h após orçamento sem resposta</div></div>
              <div style={{ color: '#86EFAC', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase' }}>Ativo</div>
            </div>
            <div style={{ alignItems: 'center', borderBottomColor: '#FFFFFF26', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', justifyContent: 'space-between', paddingBlock: '12px' }}>
              <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '15px', fontWeight: '600' }}>Boas-vindas em 5 toques</div><div style={{ color: '#BFDBFE', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>D+0, D+3, D+7, D+15, D+30 pós ativação</div></div>
              <div style={{ color: '#86EFAC', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase' }}>Ativo</div>
            </div>
            <div style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between', paddingBlock: '12px' }}>
              <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '15px', fontWeight: '600' }}>Recontato de inadimplência leve</div><div style={{ color: '#BFDBFE', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Lembrete amigável até 5 dias de atraso</div></div>
              <div style={{ color: '#86EFAC', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', textTransform: 'uppercase' }}>Ativo</div>
            </div>
          </div>
          <div style={{ alignSelf: 'flex-start', backgroundColor: '#FFFFFF', borderRadius: '8px', paddingBlock: '14px', paddingInline: '22px' }}>
            <div style={{ color: '#1D4ED8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', fontWeight: '600' }}>Abrir editor de fluxos →</div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', paddingBlock: '32px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '20px', fontWeight: '700' }}>Pra deixar sua cara</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>1. Edite o tom das mensagens. O default é direto. Se sua marca é mais informal, ajuste.</div>
          <div style={{ borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>2. Conecte gatilhos com o CRM. Lead que mudou de estágio dispara fluxo. Sem precisar mexer.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', lineHeight: '150%', paddingBlock: '14px' }}>3. Crie o seu próprio. Editor visual, sem código, IA sugere o próximo passo conforme você desenha.</div>
        </div>
        <div style={{ backgroundColor: '#F8FAFC', borderLeftColor: '#E76F51', borderLeftStyle: 'solid', borderLeftWidth: '3px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '32px', marginLeft: '32px', marginRight: '32px', paddingBlock: '20px', paddingInline: '24px' }}>
          <div style={{ color: '#E76F51', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px' }}>↘ ideia</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '160%' }}>Provedor que liga os 3 fluxos prontos no primeiro mês cresce ticket médio em 8% só com isso.</div>
        </div>
        <div style={{ borderTopColor: '#E2E8F0', borderTopStyle: 'solid', borderTopWidth: '1px', display: 'flex', flexDirection: 'column', gap: '8px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '24px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Vende mais. Perde menos. Fideliza sempre.</div>
        </div>
      </div>
    </div>
  )"""

_EMAIL_IA = r"""(
    <div style={{ backgroundColor: '#F8FAFC', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', paddingBlock: '32px', paddingInline: '32px', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: '12px', borderStyle: 'solid', borderWidth: '1px', display: 'flex', flexDirection: 'column', overflow: 'clip' }}>
        <div style={{ alignItems: 'center', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', justifyContent: 'space-between', paddingBlock: '24px', paddingInline: '32px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '18px', fontWeight: '800' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>hubtrix.com.br</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '24px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '48px' }}>
          <div style={{ color: '#1D4ED8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.16em', textTransform: 'uppercase' }}>Inteligência artificial</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '38px', fontWeight: '800', letterSpacing: '-0.025em', lineHeight: '105%' }}>Da primeira mensagem ao técnico chegando.</div>
          <div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '17px', lineHeight: '155%' }}>A IA do Hubtrix faz a venda inteira. Sem atendente no meio. Sem pula-pula entre sistema, planilha e WhatsApp.</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', paddingBottom: '24px', paddingLeft: '32px', paddingRight: '32px' }}>
          <div style={{ alignItems: 'flex-start', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#0B1220', borderRadius: '99px', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>1</div></div>
            <div><div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '16px', fontWeight: '700' }}>Atende</div><div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>Responde WhatsApp em segundos, qualquer horário, qualquer canal.</div></div>
          </div>
          <div style={{ alignItems: 'flex-start', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#0B1220', borderRadius: '99px', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>2</div></div>
            <div><div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '16px', fontWeight: '700' }}>Qualifica</div><div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>8 perguntas treinadas pra ISP. Confirma viabilidade técnica por CEP.</div></div>
          </div>
          <div style={{ alignItems: 'flex-start', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#0B1220', borderRadius: '99px', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>3</div></div>
            <div><div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '16px', fontWeight: '700' }}>Cadastra no ERP</div><div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>Cliente entra no HubSoft, SGP, MK-Auth ou IXC sem ninguém digitar.</div></div>
          </div>
          <div style={{ alignItems: 'flex-start', borderBottomColor: '#E2E8F0', borderBottomStyle: 'solid', borderBottomWidth: '1px', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#0B1220', borderRadius: '99px', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>4</div></div>
            <div><div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '16px', fontWeight: '700' }}>Valida contrato</div><div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>Manda link de assinatura. Confere se o cliente assinou. Avisa se demorou.</div></div>
          </div>
          <div style={{ alignItems: 'flex-start', display: 'flex', gap: '14px', paddingBlock: '14px' }}>
            <div style={{ alignItems: 'center', backgroundColor: '#1D4ED8', borderRadius: '99px', display: 'flex', flexShrink: '0', height: '32px', justifyContent: 'center', width: '32px' }}><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>5</div></div>
            <div><div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '16px', fontWeight: '700' }}>Abre O.S. de instalação</div><div style={{ color: '#475569', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '150%' }}>Equipe técnica recebe a O.S. com endereço, CEP, plano e horário marcado.</div></div>
          </div>
        </div>
        <div style={{ backgroundColor: '#0B1220', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '16px', marginLeft: '32px', marginRight: '32px', paddingBlock: '24px', paddingInline: '24px' }}>
          <div style={{ color: '#93C5FD', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Resultado</div>
          <div style={{ alignItems: 'flex-end', display: 'flex', gap: '12px', justifyContent: 'space-between' }}>
            <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '38px', fontWeight: '800', letterSpacing: '-0.03em' }}>15min</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px' }}>Lead até técnico agendado</div></div>
            <div><div style={{ color: '#FFFFFF', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '38px', fontWeight: '800', letterSpacing: '-0.03em' }}>0</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px' }}>Atendentes envolvidos</div></div>
            <div><div style={{ color: '#93C5FD', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '38px', fontWeight: '800', letterSpacing: '-0.03em' }}>24/7</div><div style={{ color: '#FFFFFF99', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px' }}>Sem feriado, sem pausa</div></div>
          </div>
          <div style={{ alignSelf: 'flex-start', backgroundColor: '#1D4ED8', borderRadius: '8px', paddingBlock: '14px', paddingInline: '22px' }}>
            <div style={{ color: '#FFFFFF', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '14px', fontWeight: '600' }}>Ver isso ao vivo →</div>
          </div>
        </div>
        <div style={{ backgroundColor: '#F8FAFC', borderLeftColor: '#E76F51', borderLeftStyle: 'solid', borderLeftWidth: '3px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '32px', marginLeft: '32px', marginRight: '32px', marginTop: '24px', paddingBlock: '20px', paddingInline: '24px' }}>
          <div style={{ color: '#E76F51', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px' }}>↘ atendente humano não some</div>
          <div style={{ color: '#0B1220', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '160%' }}>Quando o cliente trava, pede algo fora do roteiro ou tem objeção forte, a IA passa a conversa pro humano com todo o contexto. Sem cliente repetir nada.</div>
        </div>
        <div style={{ borderTopColor: '#E2E8F0', borderTopStyle: 'solid', borderTopWidth: '1px', display: 'flex', flexDirection: 'column', gap: '8px', paddingBottom: '32px', paddingLeft: '32px', paddingRight: '32px', paddingTop: '24px' }}>
          <div style={{ color: '#0B1220', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '14px', fontWeight: '700' }}>hubtrix</div>
          <div style={{ color: '#94A3B8', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '12px' }}>Vende mais. Perde menos. Fideliza sempre.</div>
        </div>
      </div>
    </div>
  )"""

_EMAIL_HEADER = r"""(
    <div style={{ backgroundColor: '#FFFFFF', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', justifyContent: 'space-between', paddingBottom: '28px', paddingLeft: '56px', paddingRight: '56px', paddingTop: '48px' }}>
        <div style={{ alignItems: 'baseline', boxSizing: 'border-box', display: 'flex', gap: '4px' }}>
          <div style={{ boxSizing: 'border-box', color: '#252020', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '32px', fontWeight: '800', letterSpacing: '-0.02em', lineHeight: '32px' }}>hubtrix</div>
          <div style={{ backgroundColor: '#E76F51', borderRadius: '50%', boxSizing: 'border-box', flexShrink: '0', height: '8px', marginBottom: '2px', width: '8px' }}></div>
        </div>
        <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '22px', fontWeight: '500', lineHeight: '22px' }}>para provedores que crescem.</div>
      </div>
      <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', height: '4px', width: '100%' }}>
        <div style={{ backgroundColor: '#E76F51', boxSizing: 'border-box', flexShrink: '0', height: '2px', width: '96px' }}></div>
        <div style={{ backgroundColor: '#E2E8F0', boxSizing: 'border-box', flexGrow: '1', height: '1px' }}></div>
      </div>
      <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', justifyContent: 'space-between', paddingBottom: '32px', paddingLeft: '56px', paddingRight: '56px', paddingTop: '20px' }}>
        <div style={{ boxSizing: 'border-box', color: '#475569', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', fontWeight: '600', letterSpacing: '0.12em', lineHeight: '11px', textTransform: 'uppercase' }}>Boletim do operador · Edição #{{numero}}</div>
        <div style={{ boxSizing: 'border-box', color: '#94A3B8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', letterSpacing: '0.04em', lineHeight: '11px' }}>{{data}}</div>
      </div>
    </div>
  )"""

_EMAIL_FOOTER = r"""(
    <div style={{ backgroundColor: '#252020', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', fontSize: '12px', fontSynthesis: 'none', height: 'fit-content', lineHeight: '16px', MozOsxFontSmoothing: 'grayscale', overflow: 'clip', WebkitFontSmoothing: 'antialiased', width: '640px' }}>
      <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', justifyContent: 'space-between', paddingBottom: '28px', paddingLeft: '56px', paddingRight: '56px', paddingTop: '40px' }}>
        <div style={{ alignItems: 'baseline', boxSizing: 'border-box', display: 'flex', gap: '4px' }}>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter Tight", system-ui, sans-serif', fontSize: '28px', fontWeight: '800', letterSpacing: '-0.02em', lineHeight: '28px' }}>hubtrix</div>
          <div style={{ backgroundColor: '#E76F51', borderRadius: '50%', boxSizing: 'border-box', flexShrink: '0', height: '7px', marginBottom: '2px', width: '7px' }}></div>
        </div>
        <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Caveat", system-ui, sans-serif', fontSize: '18px', fontWeight: '500', lineHeight: '18px' }}>camada que conecta.</div>
      </div>
      <div style={{ alignItems: 'center', boxSizing: 'border-box', display: 'flex', height: '1px', width: '100%' }}>
        <div style={{ boxSizing: 'border-box', flexShrink: '0', height: '1px', width: '56px' }}></div>
        <div style={{ backgroundColor: '#E76F51', boxSizing: 'border-box', flexShrink: '0', height: '2px', width: '96px' }}></div>
        <div style={{ backgroundColor: '#FFFFFF1F', boxSizing: 'border-box', flexGrow: '1', height: '1px' }}></div>
        <div style={{ boxSizing: 'border-box', flexShrink: '0', height: '1px', width: '56px' }}></div>
      </div>
      <div style={{ alignItems: 'flex-start', boxSizing: 'border-box', display: 'flex', gap: '32px', justifyContent: 'space-between', paddingBottom: '24px', paddingLeft: '56px', paddingRight: '56px', paddingTop: '32px' }}>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '10px', fontWeight: '600', letterSpacing: '0.16em', lineHeight: '10px', textTransform: 'uppercase' }}>Contato</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>contato@hubtrix.com.br</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFFB8', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', lineHeight: '20px' }}>Seg a sex · 9h às 18h</div>
        </div>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '10px', fontWeight: '600', letterSpacing: '0.16em', lineHeight: '10px', textTransform: 'uppercase' }}>Recursos</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>Site oficial</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>Central de ajuda</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>Casos reais</div>
        </div>
        <div style={{ boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ boxSizing: 'border-box', color: '#E76F51', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '10px', fontWeight: '600', letterSpacing: '0.16em', lineHeight: '10px', textTransform: 'uppercase' }}>Acompanhe</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>Instagram @hubtrix</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>LinkedIn /hubtrix</div>
          <div style={{ boxSizing: 'border-box', color: '#FFFFFF', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '13px', fontWeight: '500', lineHeight: '20px' }}>YouTube /hubtrix</div>
        </div>
      </div>
      <div style={{ borderTopColor: '#FFFFFF14', borderTopStyle: 'solid', borderTopWidth: '1px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '8px', paddingBottom: '36px', paddingLeft: '56px', paddingRight: '56px', paddingTop: '20px' }}>
        <div style={{ boxSizing: 'border-box', color: '#FFFFFF8F', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', lineHeight: '16px' }}>Você recebe este email porque é cliente ou demonstrou interesse no Hubtrix.</div>
        <div style={{ boxSizing: 'border-box', color: '#FFFFFF66', display: 'inline-block', fontFamily: '"Inter", system-ui, sans-serif', fontSize: '11px', lineHeight: '16px' }}>Hubtrix Tecnologia Ltda · CNPJ 00.000.000/0001-00 · hubtrix.com.br</div>
      </div>
    </div>
  )"""


# Mapa: dados de cada e-mail
EMAILS = [
    {
        'titulo': 'Email - Boas-vindas',
        'slug': 'email-boas-vindas',
        'categoria': 'template',
        'resumo': 'Primeiro e-mail da jornada de onboarding. Disparado quando o cliente cria conta no Hubtrix. Apresenta credenciais de acesso e os próximos 3 passos de setup.',
        'jsx': _EMAIL_BOAS_VINDAS,
        'png': 'Email - Boas-vindas@2x.png',
        'subpasta': 'Onboarding',
    },
    {
        'titulo': 'Email 02 - Atendimento',
        'slug': 'email-02-atendimento',
        'categoria': 'template',
        'resumo': 'Módulo 01 ativo. Enviado após ativação do módulo de atendimento com IA. Mostra métricas da primeira hora (12 leads, 9 qualificados, 3 prontos pra fechar) e sugere 3 ajustes rápidos.',
        'jsx': _EMAIL_ATENDIMENTO,
        'png': 'Email 02 - Atendimento@2x.png',
        'subpasta': 'Onboarding',
    },
    {
        'titulo': 'Email 03 - CRM',
        'slug': 'email-03-crm',
        'categoria': 'template',
        'resumo': 'Módulo 02 ativo. Enviado após ativação do CRM Comercial. Confirma importação de leads e exibe pipeline montado (248 leads, 18 oportunidades, R$47k).',
        'jsx': _EMAIL_CRM,
        'png': 'Email 03 - CRM@2x.png',
        'subpasta': 'Onboarding',
    },
    {
        'titulo': 'Email 04 - Fidelização',
        'slug': 'email-04-fidelizacao',
        'categoria': 'template',
        'resumo': 'Módulo 03 ativo. Enviado após ativação do Clube de Fidelização. Informa status do clube e sugere ações para a primeira semana.',
        'jsx': _EMAIL_FIDELIZACAO,
        'png': 'Email 04 - Fidelizacao@2x.png',
        'subpasta': 'Onboarding',
    },
    {
        'titulo': 'Email 05 - Automação',
        'slug': 'email-05-automacao',
        'categoria': 'template',
        'resumo': 'Módulo 04 ativo. Enviado após ativação das automações. Lista os 3 fluxos ativos e sugere personalização.',
        'jsx': _EMAIL_AUTOMACAO,
        'png': 'Email 05 - Automacao@2x.png',
        'subpasta': 'Onboarding',
    },
    {
        'titulo': 'Email - IA Fluxo Completo',
        'slug': 'email-ia-fluxo-completo',
        'categoria': 'template',
        'resumo': 'E-mail standalone de produto. Apresenta o fluxo completo da IA em 5 etapas. Resultado: lead até técnico em 15min, 0 atendentes, 24/7.',
        'jsx': _EMAIL_IA,
        'png': 'Email - IA fluxo completo@2x.png',
        'subpasta': 'Campanhas',
    },
    {
        'titulo': 'Email Header v2',
        'slug': 'email-header-v2',
        'categoria': 'referencia',
        'resumo': 'Componente de header para e-mails Hubtrix (v2). Logo wordmark + tagline Caveat + linha divisória sienna. Usado nos newsletters Boletim do Operador.',
        'jsx': _EMAIL_HEADER,
        'png': 'Email Header v2@2x.png',
        'subpasta': 'Componentes',
    },
    {
        'titulo': 'Email Footer v2',
        'slug': 'email-footer-v2',
        'categoria': 'referencia',
        'resumo': 'Componente de footer para e-mails Hubtrix (v2). Fundo tinta #252020, 3 colunas (Contato, Recursos, Acompanhe), rodapé legal.',
        'jsx': _EMAIL_FOOTER,
        'png': 'Email Footer v2@2x.png',
        'subpasta': 'Componentes',
    },
]


class Command(BaseCommand):
    help = 'Importa e-mails do Paper.design pro Workspace (Marketing > Design de E-mails)'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Aurora HQ', help='Nome do tenant')
        parser.add_argument(
            '--png-dir',
            default=str(Path.home() / 'Downloads'),
            help='Diretório com os PNGs exportados pelo Paper (default: ~/Downloads)',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        png_dir = Path(options['png_dir'])

        try:
            tenant = Tenant.objects.get(nome=options['tenant'])
        except Tenant.DoesNotExist:
            tenant = Tenant.objects.filter(ativo=True).order_by('id').first()
            if not tenant:
                raise CommandError('Tenant não encontrado.')
            self.stdout.write(self.style.WARNING(f'Tenant "{options["tenant"]}" não encontrado. Usando: {tenant.nome}'))

        admin = User.objects.filter(is_superuser=True).first()

        self.stdout.write(f'Tenant: {tenant.nome}')
        self.stdout.write(f'PNG dir: {png_dir}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — nada será gravado\n'))
            for e in EMAILS:
                png_ok = (png_dir / e['png']).exists()
                status = 'OK' if png_ok else 'FALTA PNG'
                self.stdout.write(f'  {status}  [{e["subpasta"]}] {e["titulo"]}')
            return

        with transaction.atomic():
            # Pasta raiz Marketing (deve existir do importar_docs_drive)
            pasta_marketing = PastaDocumento.all_tenants.filter(
                tenant=tenant, slug='03-marketing',
            ).first()
            if not pasta_marketing:
                pasta_marketing = PastaDocumento.all_tenants.create(
                    tenant=tenant, slug='03-marketing', nome='03. Marketing',
                    icone='bi-megaphone', cor='#E76F51', ordem=3,
                )

            # Pasta pai: Marketing > Design de E-mails
            pasta_emails = self._get_or_create(
                tenant, slug='03-marketing-design-emails',
                defaults=dict(nome='Design de E-mails', pai=pasta_marketing,
                              icone='bi-envelope-paper', cor='#E76F51', ordem=1),
            )

            # Subpastas
            subpastas = {}
            for i, nome_sub in enumerate(['Onboarding', 'Campanhas', 'Componentes'], 1):
                subpastas[nome_sub] = self._get_or_create(
                    tenant, slug=slugify(f'emails-{nome_sub}'),
                    defaults=dict(nome=nome_sub, pai=pasta_emails,
                                  icone='bi-folder', cor='#475569', ordem=i),
                )

            criados = atualizados = anexos_ok = anexos_miss = 0

            # Pré-gera header e footer v2 (paleta já é v2 nativa)
            header_v2 = _gerar_header_v2_html()
            footer_v2 = _gerar_footer_v2_html()

            for email in EMAILS:
                html_bruto = jsx_to_html(email['jsx'])

                # Componentes (Header/Footer v2) ficam standalone, sem wrap
                if email['subpasta'] == 'Componentes':
                    html_final = aplicar_paleta_v2(html_bruto)
                else:
                    # E-mails completos: aplica paleta v2 + extrai corpo + wrap com header/footer
                    html_v2 = aplicar_paleta_v2(html_bruto)
                    corpo = extrair_corpo_email(html_v2)
                    html_final = montar_email_v2(corpo, header_v2, footer_v2)

                conteudo = (
                    f'<!-- HTML do e-mail Hubtrix v2 (Header v2 + body + Footer v2) -->\n'
                    f'<!-- Paleta v2: tinta #252020 + sienna #E76F51 + branco. Atualizado em 29/04/2026 -->\n\n'
                    f'{html_final}'
                )

                doc, created = Documento.all_tenants.update_or_create(
                    tenant=tenant,
                    slug=email['slug'],
                    defaults={
                        'titulo': email['titulo'],
                        'resumo': email['resumo'],
                        'categoria': email['categoria'],
                        'formato': 'html',
                        'pasta': subpastas[email['subpasta']],
                        'conteudo': conteudo,
                        'visivel_agentes': False,
                        'criado_por': admin,
                    },
                )

                if created:
                    criados += 1
                    self.stdout.write(f'  + criado:     {email["titulo"]}')
                else:
                    atualizados += 1
                    self.stdout.write(f'  ~ atualizado: {email["titulo"]}')

                # Anexar PNG
                png_path = png_dir / email['png']
                if png_path.exists():
                    # Remove versão anterior do mesmo PNG para ser idempotente
                    AnexoDocumento.all_tenants.filter(
                        tenant=tenant, documento=doc, tipo='imagem',
                        nome_original=png_path.name,
                    ).delete()
                    img_bytes = png_path.read_bytes()
                    anexo = AnexoDocumento(
                        tenant=tenant,
                        documento=doc,
                        tipo='imagem',
                        nome_original=png_path.name,
                        mime_type='image/png',
                        tamanho_bytes=len(img_bytes),
                        criado_por=admin,
                    )
                    anexo.arquivo.save(png_path.name, ContentFile(img_bytes), save=True)
                    self.stdout.write(f'    PNG: {png_path.name}')
                    anexos_ok += 1
                else:
                    self.stdout.write(self.style.WARNING(f'    PNG ausente: {png_path}'))
                    anexos_miss += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nOK: +{criados} criados, ~{atualizados} atualizados, '
            f'{anexos_ok} PNGs anexados'
            + (f', {anexos_miss} PNGs ausentes' if anexos_miss else '') + '.'
        ))

    def _get_or_create(self, tenant, slug, defaults):
        obj, _ = PastaDocumento.all_tenants.get_or_create(
            tenant=tenant, slug=slug, defaults=defaults,
        )
        return obj
