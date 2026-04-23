# Atendimento — Simulador de teste

Botao "Testar" no toolbar do editor abre um modal chat para testar o fluxo sem precisar do WhatsApp.

- Configura nome e telefone fake
- Envia mensagens e ve resposta do bot em tempo real
- Cria `AtendimentoFluxo` com lead temporario
- API: `POST /api/fluxos/<id>/simular/`

Util durante desenvolvimento e revisao de prompts. O lead criado e identificado como temporario e pode ser limpo pelo admin.

## Simulador de prompts (management command)

Para validar mudanca de prompt_validacao/system_prompt sem expor a api_key do tenant fora do container, existe o command `simular_prompts_fatepi`:

```bash
docker exec <container-app> python manage.py simular_prompts_fatepi
```

Compara prompts ATUAL vs NOVO chamando `_chamar_llm_simples` do engine (mesma pilha de IntegracaoAPI que producao usa). Casos de teste embutidos no proprio command (`CASOS_CURSO`, `CASOS_FALLBACK`). Output mostra placar ATUAL/NOVO por caso. Custo ~$0.003 por rodada (gpt-4o-mini).

Usado em 23/04/2026 para validar o fix do classificador de curso e dos fallbacks IA do fluxo v3 FATEPI antes do UPDATE em producao. Replicar o padrao para outros tenants copiando `CASOS_*` e renomeando o command.
