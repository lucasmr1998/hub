---
name: "Prompt Agente Pedro FATEPI"
description: "Indice dos arquivos de configuracao do agente IA da FATEPI no N8N"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Agente Pedro — FATEPI/FAESPI

Arquivos separados para facilitar copiar e colar no N8N:

1. **System Prompt** (colar no campo "System Prompt" do no do agente): [fatepi_system_prompt.md](fatepi_system_prompt.md)
2. **Tools N8N** (configuracao das HTTP Request Tools): [fatepi_tools_n8n.md](fatepi_tools_n8n.md)

---

## Notas de implementacao

1. O lead_id e oportunidade_id vem no payload que nosso sistema envia ao N8N (campo _aurora)
2. A oportunidade e criada automaticamente pelo nosso sistema quando o lead entra (automacao lead_criado -> criar_oportunidade)
3. A API aceita campos flat com prefixo "dados_custom." e converte para JSON aninhado automaticamente
4. Campos vazios sao ignorados pela API
5. O no do agente IA deve ser versao 2.0+ (recriar o no se estiver na versao 1.x)
