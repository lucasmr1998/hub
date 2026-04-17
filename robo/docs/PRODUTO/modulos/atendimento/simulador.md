# Atendimento — Simulador de teste

Botao "Testar" no toolbar do editor abre um modal chat para testar o fluxo sem precisar do WhatsApp.

- Configura nome e telefone fake
- Envia mensagens e ve resposta do bot em tempo real
- Cria `AtendimentoFluxo` com lead temporario
- API: `POST /api/fluxos/<id>/simular/`

Util durante desenvolvimento e revisao de prompts. O lead criado e identificado como temporario e pode ser limpo pelo admin.
