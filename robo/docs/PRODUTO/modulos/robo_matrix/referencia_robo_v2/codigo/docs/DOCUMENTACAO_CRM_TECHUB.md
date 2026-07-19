# CRM do Robô de Vendas — Documentação Funcional

**Módulo:** CRM (Gestão de Relacionamento com o Cliente) · Robô V2 · TecHub
**Data:** 25/06/2026 · **atualizado em 10/07/2026**
**Versão do documento:** 1.1 (ver seção 8 — o que mudou desde a v1.0)
**Natureza:** Documento de **registro e explicação** da criação e existência do CRM.

> ⚠️ **Status: EM DESENVOLVIMENTO — ainda NÃO está em produção.**
> O CRM já existe e está funcional, porém **opera por enquanto somente através do
> console do robô** (também presente dentro do TecHub). Não foi liberado como produto
> de produção para uso amplo das equipes. **Novas versões e implementações estão em
> andamento.** Este documento descreve o estado atual e deve ser revisado a cada
> evolução.

---

## 1. Objetivo deste documento

Registrar a **criação e a existência** do módulo de CRM dentro do TecHub, explicar
**como ele funciona hoje** e deixar claro que se trata de uma entrega **em evolução**,
com versões futuras planejadas. O documento serve como referência inicial para a
gestão e para a equipe técnica, não como manual operacional definitivo.

---

## 2. O que é o CRM

O CRM é o módulo que dá **visão única e organizada da jornada de cada cliente** —
do primeiro contato no WhatsApp até o pós-venda — transformando as conversas e
processos do robô em **oportunidades** acompanháveis em um funil visual.

Em vez de os dados ficarem dispersos (lead, documentos, contrato, instalação,
upgrades), o CRM **centraliza tudo em uma oportunidade por cliente/processo**, que
caminha automaticamente pelos estágios conforme o robô avança o atendimento.

**Por que foi criado:** dar à área comercial e à gestão **rastreabilidade** (onde
cada cliente está), **organização** (funil por tipo de processo) e base para
**indicadores** futuros (conversão, perdas, tempo por etapa).

---

## 3. Status atual e forma de operação

| Aspecto | Situação atual |
|---|---|
| Existência do módulo | ✅ Criado e funcional |
| Forma de uso | **Somente pelo console do robô** (dentro do TecHub) |
| Liberação para produção | ❌ **Ainda não** — em desenvolvimento |
| Alimentação dos dados | Automática, a partir dos fluxos do robô |
| Evolução | 🔄 Em andamento — **novas versões previstas** |

**Importante:** hoje o CRM é acessado e administrado **através do console do robô**.
Ele ainda **não** é um produto independente publicado para as equipes operarem no
dia a dia — essa liberação faz parte das próximas versões.

---

## 4. Como o CRM funciona hoje

### 4.1. Funil em quatro pipelines
O CRM organiza as oportunidades em **4 funis** (pipelines), conforme o tipo de
processo, somando **18 estágios**:

| Pipeline | Estágios |
|---|---|
| **Aquisição** (cliente novo) | Novo Lead → Em Qualificação → Aguardando Assinatura → Aguardando Instalação → Cliente Ativo → Perdido |
| **Atendimento** | Em Atendimento → Concluído |
| **Novo Serviço** (cliente existente) | Coletando Dados → Criando Serviço no HubSoft → Abrindo Atendimento e O.S. → Concluído — Instalação Agendada → Serviço Ativo → Falha |
| **Upgrade de plano** | Coletando Dados → Migrando Plano no HubSoft → Concluído — Upgrade Aplicado → Falha |

Cada estágio tem **cor, ícone, ordem, probabilidade padrão e SLA** configuráveis, e
estágios marcados como **ganho** (ex.: Cliente Ativo) ou **perda** (ex.: Perdido/Falha).

### 4.2. Oportunidade — a unidade central
Cada cliente/processo vira uma **Oportunidade**, que carrega: lead vinculado, tipo
(aquisição/novo serviço/upgrade), estágio atual, responsável, título, valor estimado,
probabilidade, prioridade, data de entrada no estágio, plano de interesse e — em caso
de perda — o motivo. Oportunidades de **novo serviço** e **upgrade** ficam ligadas ao
respectivo registro do processo.

### 4.3. Automação — o funil anda sozinho
- **17 regras de automação** movem as oportunidades entre estágios com base em
  **condições** (ex.: documentos completos, contrato assinado, serviço criado).
- **Reconciliação automática:** um processo do robô roda periodicamente e **atualiza
  o estágio de cada oportunidade** conforme o processo real avança no HubSoft — sem
  necessidade de mover manualmente.
- **20 tags** classificam as oportunidades (ex.: *Lead Novo, CPF Validado, Docs
  Completos, Assinado, Instalação Agendada, Upgrade Aplicado, Falha*), facilitando
  filtros e leitura rápida do estado.

### 4.4. Recursos disponíveis no console
- **Funil visual (Kanban)** com as oportunidades por estágio e **movimentação**.
- **Lista e detalhe de oportunidades**, com atribuição de **responsável**.
- **Tarefas** (criar/concluir) e **notas internas** (com fixar) por oportunidade.
- Estruturas já previstas para **equipes/perfis de vendedor, metas, segmentos e
  alertas de retenção** (em maturação).

---

## 5. Onde fica

O CRM está embutido no **console do robô**, dentro do TecHub, sob o caminho `/crm/`.
É alimentado pelo mesmo banco isolado do robô (`robovendas_v2`), o que garante que a
operação do CRM **não interfere** em sistemas legados.

---

## 6. O que ainda virá (próximas versões)

Este é um **primeiro estágio**. Estão previstas, entre outras evoluções:

- **Liberação como produto de produção** para uso das equipes (hoje é console do robô).
- **Painel de indicadores** (conversão por etapa, perdas, tempo médio, metas).
- **Gestão de equipe e responsáveis** (distribuição, carteira, produtividade).
- **Tarefas e alertas proativos** (follow-up, retenção, SLA estourado).
- **Refinos de automação** e de regras de movimentação entre estágios.
- **Permissões e perfis de acesso** para diferentes papéis.

> As funcionalidades e estágios descritos podem mudar nas próximas versões — este
> documento acompanha a evolução do módulo.

---

## 7. Resumo

O CRM **já existe, está funcional e é alimentado automaticamente** pelos fluxos do
robô, organizando cada cliente em um funil de quatro pipelines com automação de
movimentação. **Por enquanto, opera somente pelo console do robô dentro do TecHub e
ainda não está em produção** — sua liberação ampla e novos recursos fazem parte das
próximas versões, em desenvolvimento.

---

## 8. Atualizações da v1.1 (10/07/2026) — o que mudou desde a v1.0

O CRM evoluiu de "funil automático de 4 pipelines" para **plataforma comercial
operada por pessoas**, com controle de acesso. Principais adições:

### 8.1. Pipeline de Indicações (5º pipeline — 100% manual)
Funil operado por pessoas: o operador cadastra a indicação (lead nasce com canal
`indicacao` + **código do indicador**), completa os dados num **painel central de
Ações do Operador** (modal), **converte em cliente** (prospecto → cliente no
HubSoft via automação) e **abre atendimento + O.S.**. A abertura só é liberada
quando o **contrato está aceito** (aceite feito pelo próprio cliente no app; o
CRM apenas monitora o status). Tags e estágios próprios; badges de contagem em
todas as abas de pipeline.

### 8.2. Controle de acesso (RBAC) + usuários do Portal TecHub
- **5 perfis** (Administrador, Gerente, Operador, Vendedor, Auditor) com **matriz
  configurável** de capacidades (ver/operar) e escopo de dados; tela em
  Administração → Perfis de Acesso.
- **Usuários = os do Portal TecHub** (SSO; sem senha local). Tela **Gestão de
  Usuários**: sincroniza as contas do portal, filtra pendentes e **libera o
  acesso em 1 clique** atribuindo perfil. **Sem perfil = sem acesso** (página
  "acesso pendente").
- **Notificações personalizadas por permissão** (entradas de pipeline, marcos,
  falhas para gerentes, atribuições para o responsável).

### 8.3. Personalização sem deploy
- **Mensagens de WhatsApp por pipeline** (botão verde da oportunidade abre com o
  texto configurado).
- **Central de Mensagens do Robô**: todos os textos que o robô envia no WhatsApp
  (perguntas, confirmações, erros, recontato, retomada) editáveis na ferramenta,
  com efeito imediato.

### 8.4. Métricas — hub Análises
Painel único com filtro de período: funil (venda real = cadastro no HubSoft),
indicações (ranking de indicadores), saúde da automação HubSoft, operação do CRM
(tempo por estágio, oportunidades paradas, carga) e atrito do robô por pergunta.

### 8.5. Robô — experiência de atendimento
Recontato escalonado no silêncio (3 tentativas → pausa), retomada de cadastro
(continuar/recomeçar/outro CPF), checagem de **viabilidade por cidade** no
confirmar-endereço (fora da área → transbordo), cliente inativo tratado como
cadastrado, URA estruturada no contrato da API (campo `ura`).

### 8.6. Manual do usuário
Central de Ajuda com 6 guias dinâmicos por perfil, dentro da própria ferramenta.

> Detalhamento técnico: `dashboard_comercial/gerenciador_vendas/docs/`
> (RELATORIO_IMPLEMENTACOES_2026-06-24.md e RELATORIO_IMPLEMENTACOES_2026-07-07.md)
> e `docs/RELATORIO_EXECUTIVO_ROBO_V2.md` (visão executiva, sempre a mais atual).

---

*Documento de registro — CRM do Robô de Vendas (TecHub) · v1.1 · 10/07/2026.*
