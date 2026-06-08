"""
Refator: substitui ia_respondedor (apresenta_planos e confirma_plano) por questao/texto
com IA extrair. Elimina o problema de re-turno automatico do ia_respondedor.

Antes: apresenta_planos (ia_respondedor) -> escolha_plano (questao) -> confirma_plano (ia_respondedor) -> pede_endereco
Depois: apresenta_planos (questao/texto com IA extrair) -> pede_endereco
"""
from django.db import transaction
from apps.comercial.atendimento.models import NodoFluxoAtendimento, ConexaoNodoAtendimento

FLUXO_ID = 23
IA_ID = 15

APRESENTA = 631
ESCOLHA = 632
CONFIRMA = 644
PEDE_ENDERECO = 633

PLANOS_TEXTO = (
    "Boa notícia 😊 Sua região aparece dentro da área de atendimento da Vero. "
    "A disponibilidade final será confirmada pelo endereço completo, "
    "mas já vou te mostrar os planos disponíveis:\n\n"
    "1. 550 Mega + Wi-Fi 6 — R$ 113,90/mês\n"
    "2. 550 Mega + Chip 10GB — R$ 118,90/mês\n"
    "3. 750 Mega + Wi-Fi 6 — R$ 122,90/mês\n"
    "4. 800 Mega + YouTube Premium — R$ 134,90/mês\n"
    "5. 800 Mega + Max — R$ 134,90/mês\n"
    "6. 800 Mega + Telecine — R$ 134,90/mês\n"
    "7. 800 Mega + Globoplay Canais + Chip 20GB — R$ 139,90/mês\n"
    "8. 800 Mega + Disney Padrão + Chip 20GB — R$ 139,90/mês\n"
    "9. 800 Mega + Globoplay Canais Premium + HBO Max + Chip 60GB — R$ 149,90/mês\n"
    "10. 800 Mega + Premiere — R$ 150,00/mês\n"
    "11. 800 Mega + Disney Plus — R$ 155,00/mês\n\n"
    "Me responde com o número do plano que você quer 😊"
)

PEDE_ENDERECO_TEXTO = (
    "Perfeito 😊\n\n"
    "Agora preciso do seu endereço completo para seguir com a conferência.\n\n"
    "Me manda assim, por favor:\n"
    "Rua:\nNúmero:\nBairro:\nCidade:\nComplemento (se tiver):"
)

with transaction.atomic():
    # 1. apresenta_planos: ia_respondedor -> questao/texto com IA extrair numero
    apresenta = NodoFluxoAtendimento.objects.get(id=APRESENTA)
    apresenta.tipo = "questao"
    apresenta.subtipo = "texto"
    apresenta.configuracao = {
        "titulo": PLANOS_TEXTO,
        "espera_resposta": True,
        "integracao_ia_id": IA_ID,
        "ia_acao": "extrair",
        "ia_modelo": "gpt-4o-mini",
        "ia_campos_extrair": [
            {"nome": "oport.dados_custom.plano_escolhido", "descricao": "Numero do plano (1 a 11)", "tipo": "string"},
        ],
        "ia_salvar_no_lead": True,
        "prompt_validacao": "Extraia o numero do plano escolhido (1 a 11). Se nao for numero valido, retorne vazio.",
    }
    apresenta.save()
    print(f"OK: nodo {APRESENTA} (apresenta_planos) convertido pra questao/texto + IA extrair")

    # 2. pede_endereco atualizado
    pede_end = NodoFluxoAtendimento.objects.get(id=PEDE_ENDERECO)
    pede_end.configuracao = {
        "titulo": PEDE_ENDERECO_TEXTO,
        "espera_resposta": True,
        "integracao_ia_id": IA_ID,
        "ia_acao": "extrair",
        "ia_modelo": "gpt-4o-mini",
        "ia_campos_extrair": [
            {"nome": "oport.dados_custom.endereco_rua", "descricao": "Nome da rua", "tipo": "string"},
            {"nome": "oport.dados_custom.endereco_numero", "descricao": "Numero da casa/apto", "tipo": "string"},
            {"nome": "oport.dados_custom.endereco_bairro", "descricao": "Bairro", "tipo": "string"},
            {"nome": "oport.dados_custom.endereco_cidade", "descricao": "Cidade", "tipo": "string"},
            {"nome": "oport.dados_custom.endereco_complemento", "descricao": "Complemento", "tipo": "string"},
        ],
        "ia_salvar_no_lead": True,
        "prompt_validacao": "Extraia os campos do endereco residencial brasileiro.",
    }
    pede_end.save()
    print(f"OK: nodo {PEDE_ENDERECO} (pede_endereco) atualizado")

    # 3. Remove conexoes envolvendo escolha_plano e confirma_plano
    n_rem_o = ConexaoNodoAtendimento.objects.filter(
        fluxo_id=FLUXO_ID, nodo_origem_id__in=[APRESENTA, ESCOLHA, CONFIRMA]
    ).delete()
    n_rem_d = ConexaoNodoAtendimento.objects.filter(
        fluxo_id=FLUXO_ID, nodo_destino_id__in=[ESCOLHA, CONFIRMA]
    ).delete()
    print(f"Conexoes removidas: origem={n_rem_o}, destino={n_rem_d}")

    # 4. apresenta_planos -> pede_endereco
    apresenta = NodoFluxoAtendimento.objects.get(id=APRESENTA)
    pede_end = NodoFluxoAtendimento.objects.get(id=PEDE_ENDERECO)
    nova = ConexaoNodoAtendimento.objects.create(
        tenant=apresenta.tenant, fluxo_id=FLUXO_ID,
        nodo_origem=apresenta, nodo_destino=pede_end, tipo_saida="default",
    )
    print(f"Conexao criada: {APRESENTA} -> {PEDE_ENDERECO} (id={nova.id})")

    # 5. Deleta nodos escolha_plano e confirma_plano
    n_del = NodoFluxoAtendimento.objects.filter(id__in=[ESCOLHA, CONFIRMA]).delete()
    print(f"Nodos deletados: {n_del}")

print()
print("=" * 50)
print("REFATOR OK — apresenta_planos agora capta o numero direto")
print("=" * 50)
