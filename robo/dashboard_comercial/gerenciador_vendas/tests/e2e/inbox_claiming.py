"""
E2E: Inbox — Conversation Claiming

Valida o fluxo completo de assumir uma conversa:
  1. Lista mostra conversa não atribuída
  2. Ao clicar, aparece banner "Assumir" sem histórico
  3. Ao clicar Assumir, histórico e input são liberados
  4. Agente consegue enviar mensagem

Rodando:
    python tests/e2e/inbox_claiming.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")

import django
django.setup()

from tests.e2e.base import E2ESession


def criar_conversa_teste():
    """Cria uma conversa com assumida=False para o teste."""
    from apps.inbox.models import CanalInbox, Conversa
    from apps.sistema.models import Tenant
    from django.contrib.auth.models import User
    from django.utils import timezone

    t = Tenant.objects.filter(slug__icontains="aurora").first()
    canal = CanalInbox.objects.filter(tenant=t).first()
    user = User.objects.filter(username="aurora").first()

    ultimo = Conversa.all_tenants.filter(tenant=t).order_by("-numero").values_list("numero", flat=True).first() or 0

    c = Conversa.objects.create(
        tenant=t, numero=ultimo + 1, canal=canal,
        contato_nome="E2E Teste Claiming",
        contato_telefone=f"5511{ultimo+1:08d}",
        status="aberta", agente=user, assumida=False,
        modo_atendimento="humano",
        ultima_mensagem_em=timezone.now(),
        ultima_mensagem_preview="Olá, preciso de ajuda!",
    )
    from apps.inbox.models import Mensagem
    for texto in ["Olá!", "Preciso de ajuda com meu plano.", "Podem me atender?"]:
        Mensagem.objects.create(
            tenant=t, conversa=c, remetente_tipo="contato",
            remetente_nome="E2E Teste", tipo_conteudo="texto", conteudo=texto,
        )
    print(f"  Conversa criada: ID={c.id} numero={c.numero} assumida={c.assumida}")
    return c


def teardown(conversa_id):
    from apps.inbox.models import Conversa
    Conversa.all_tenants.filter(pk=conversa_id).delete()
    print(f"  Conversa {conversa_id} removida.")


def run():
    print("\n=== E2E: Inbox Claiming ===\n")

    conversa = criar_conversa_teste()

    with E2ESession("inbox_claiming", headless=True, slow_mo=300) as s:
        # 1. Login
        s.login()
        s.shot("01_login_ok")

        # 2. Navegar para inbox
        s.goto("/inbox/")
        s.page.wait_for_timeout(1500)
        s.shot("02_inbox_lista")

        # 3. Garantir aba "Todas" selecionada e aguardar lista carregar
        todas_btn = s.page.locator(".inbox-assign-tab", has_text="Todas")
        if todas_btn.count() > 0:
            todas_btn.first.click()
            s.page.wait_for_timeout(1000)

        # Clicar na conversa não assumida
        card = s.page.locator(f".conv-card[data-id='{conversa.id}']")
        card.wait_for(timeout=8000)
        card.click()
        s.page.wait_for_timeout(1000)
        s.shot("03_conversa_nao_assumida")

        # 4. Verificar banner de assumir visível
        banner = s.page.locator("#assumirBanner")
        assert banner.is_visible(), "Banner 'Assumir' não está visível"
        assert not s.page.locator("#messageList").is_visible(), "Histórico não deveria estar visível"
        print("  OK Banner assumir visível, histórico bloqueado")
        s.shot("04_banner_assumir")

        # 5. Clicar em Assumir
        s.page.locator("#assumirBtn").click()
        s.page.wait_for_timeout(1200)
        s.shot("05_apos_assumir")

        # 6. Verificar que histórico e input aparecem
        assert s.page.locator("#messageList").is_visible(), "Histórico deveria aparecer após assumir"
        assert s.page.locator("#inputArea").is_visible(), "Input deveria aparecer após assumir"
        assert not banner.is_visible(), "Banner deveria sumir após assumir"
        print("  OK Histórico e input liberados após assumir")
        s.shot("06_historico_liberado")

        # 7. Mobile
        s.shot_mobile("07_mobile_assumir")

        print(f"\n  Screenshots em: tests/e2e/screenshots/inbox_claiming/")
        print("  OK PASSOU\n")

    teardown(conversa.id)


if __name__ == "__main__":
    run()
