# Robô de Vendas V2 — Relatório Executivo

**Projeto:** Automação de Vendas e Pós-Venda via WhatsApp (Robô V2 · TecHub)
**Data:** 10/07/2026
**Ambiente:** Produção (HubSoft real) · banco isolado `robovendas_v2`
**Status geral:** 🟢 **Operacional — ciclo de vendas automatizado + plataforma comercial configurável em produção**

---

## 1. Sumário Executivo

O Robô V2 passou a **fechar sozinho o ciclo completo de vendas** dentro do HubSoft —
da primeira mensagem do cliente no WhatsApp até a ordem de serviço de instalação
aberta — **sem intervenção humana** e **sem depender do robô antigo (webdrivers)**.

Os três fluxos comerciais estão **no ar e validados ponta a ponta**:
**aquisição** (cliente novo), **novo serviço** (cliente existente) e **upgrade de plano**.

Ganho central: a execução migrou de **webdriver (80–120s, frágil)** para **API interna
(~10–17s, estável)**, com o robô antigo mantido apenas como rede de segurança (fallback).

**Indicadores de prontidão:**

| Indicador | Situação |
|---|---|
| Serviços em produção | **7/7 ativos** e habilitados no boot |
| Fluxos comerciais automatizados | **3/3** (aquisição, novo serviço, upgrade) |
| Validação de documentos | **100% por IA** (humano só audita) |
| Tempo de execução por operação | **~10–17s** (antes: 80–120s) |
| Dependência do robô antigo | **Eliminada** para os leads do V2 |
| CRM (funil + automação) | **5 pipelines**, reconciliado automaticamente |
| Controle de acesso | **RBAC** com 5 perfis + notificações por permissão |
| Mensagens do robô | **Configuráveis pela equipe** (sem deploy) |
| Cobertura de viabilidade | **55/55 cidades** validadas no fluxo |

---

## 2. ✅ Entregue (em produção)

### 2.1. Motor de automação HubSoft próprio
Módulo interno (`posvenda_hubsoft`) que executa os processos no HubSoft por **API
interna** (rápida) com **fallback automático para webdriver**. Toda execução é
**auditada** (status, etapa, duração). Roda sobre o banco isolado `robovendas_v2`,
sem qualquer risco ao ambiente de produção legado.

### 2.2. Aquisição de cliente (ponta a ponta)
Fluxo completo automatizado: **conversa no WhatsApp → cadastro → documentos →
validação por IA → aceite de contrato → agendamento → ordem de serviço de instalação.**

### 2.3. Conversão Prospecto → Cliente via API (substitui o robô antigo)
- Novo serviço de conversão por API interna, **validado idêntico** ao webdriver,
  porém muito mais rápido.
- **Separação por vendedor** para coexistir com o robô antigo sem conflito:
  - **Vendedor 1613** → conversões do Robô V2 (nosso worker).
  - **Vendedor 1618** → robô antigo (`gestao_leads_bot`), restrito a esse vendedor.
- **Worker em produção** que pega os leads pendentes do próprio V2 e converte
  automaticamente, com proteção contra duplicidade.

### 2.4. Novo serviço e Upgrade de plano (via API)
- **Novo serviço** para cliente existente, automatizado por API.
- **Upgrade de plano** como **migração imediata** (decisão de negócio: upgrade
  **não abre** atendimento/O.S.), automatizado por API.

### 2.5. Validação de documentos 100% por IA
A IA valida os documentos e libera o contrato **sem conferência humana**. A tela
dos operadores passou a ser de **auditoria** (apontar processos a ajustar), não mais
um gargalo no fluxo.

### 2.6. Experiência de atendimento (chat)
- Pergunta se o atendimento é para o **CPF atual ou um novo CPF**.
- Opção de **voltar ao menu / desistir** a qualquer momento, com reset de fluxo.
- Mensagens de status corrigidas (sem duplicidade, sem transbordo indevido).

### 2.7. Simulador de chat (homologação)
Página de chat estilo WhatsApp para testes, com **inspetor de requisições** e
**exportação da conversa em PDF** — usada para validar comportamentos sem tocar no
ambiente real.

### 2.8. CRM de vendas e pós-venda (automatizado)
Funil comercial completo no CRM, **alimentado e reconciliado automaticamente** pelos
fluxos do robô — visão única de cada cliente, do primeiro contato ao pós-venda.
- **5 pipelines** e **25 estágios** cobrindo as jornadas: **aquisição**, **novo
  serviço**, **upgrade**, **atendimento** e **indicação** (este operado por pessoas).
- **17 regras de automação** que movem as oportunidades entre estágios, **23 tags**
  de classificação, **badges de contagem** por aba e estágios próprios de
  **Falha/Perdido** para gestão de exceções.
- **Reconciliação automática:** o worker de sincronização atualiza o CRM a cada
  ciclo, movendo a oportunidade conforme o processo avança no HubSoft — **sem
  trabalho manual**. Oportunidades já fluindo pelos estágios em produção.

### 2.11. Pipeline de Indicações (operado por pessoas)
Funil **manual** ponta a ponta: o operador cadastra a indicação (guardando o **código
do indicador**), completa os dados, **converte em cliente** (prospecto → cliente no
HubSoft) e **abre atendimento + O.S.** — tudo por um **painel central de ações**. A
abertura só libera quando o **contrato está aceito** (o cliente aceita no app; o
sistema monitora o status).

### 2.12. Permissões por perfil (RBAC) + notificações personalizadas
- **5 perfis** (Administrador, Gerente, Operador, Vendedor, Auditor) com **matriz
  configurável** — controla o que cada um **vê** e **opera**, com escopo de dados.
- **Notificações por permissão:** novas entradas nos pipelines, marcos (conversão,
  O.S.), falhas (para gerentes) e atribuições (para o responsável).

### 2.13. Central de Mensagens do Robô (personalização sem deploy)
A equipe edita, direto na ferramenta, **os textos que o robô envia no WhatsApp**
(perguntas, confirmações, erros, recontato, retomada). As mudanças valem **na hora**,
sem reiniciar nada. Confirmação deixada em branco = **nenhuma mensagem enviada**.

### 2.14. Reengajamento e retomada de atendimento
- **Recontato por tempo de espera:** se o cliente some, o robô manda mensagens de
  reengajamento **escalonadas** (3 tentativas) em vez de encerrar; depois pausa.
- **Retomada:** quem reabre um cadastro em andamento escolhe **continuar de onde
  parou, recomeçar ou trocar de CPF**.

### 2.15. Viabilidade técnica no fluxo (por cidade)
Ao **confirmar o endereço**, o robô checa a cobertura: **55/55 cidades** marcadas como
"atende cidade inteira". Endereço fora da área atendida (ou imóvel empresarial) **é
transferido para atendimento** — e o fluxo realmente para (não segue vendendo).

### 2.16. Manual do usuário embutido
**Central de Ajuda** com **6 guias dinâmicos por perfil** (inclui "Como o Robô Atende
no WhatsApp"), sugerindo automaticamente o guia certo para cada usuário.

### 2.17. Painel de Análises (hub único de métricas)
O **Análises** consolidou os relatórios num único painel com filtro de período:
funil de conversão (venda real = cadastro no HubSoft), canal de **Indicações** com
ranking de indicadores, **saúde da automação** (taxa de sucesso e últimas falhas),
**operação do CRM** (tempo por estágio, oportunidades paradas, carga por responsável)
e **atrito do robô** (em qual pergunta o cliente mais erra). Páginas de relatório
duplicadas/desatualizadas foram aposentadas com redirecionamento.

### 2.18. Usuários unificados com o Portal TecHub
Os usuários da ferramenta são **os mesmos do portal** (login via SSO, sem senha
local). Nova tela **Gestão de Usuários**: sincroniza as contas do portal (623
usuários importados), busca/filtra por situação e **libera o acesso em um clique**
atribuindo o perfil. **Sem perfil = sem acesso** (página "acesso pendente") — o
permissionamento é a porta de entrada da ferramenta.

### 2.19. URA estruturada para o fluxo de atendimento
O motor de conversa passou a devolver, junto de cada pergunta de múltipla escolha,
a **estrutura da URA** (título, pergunta e opções) — simplificando a montagem do
fluxo no Matrix e eliminando interpretação de texto do lado de lá.

### 2.9. Correções recentes de qualidade (entregues hoje)
- **Endereço do novo serviço:** passa a usar o endereço informado pelo cliente
  (não mais o endereço cadastral).
- **Acompanhamento de instalação:** cada O.S. exibe o **endereço real do seu
  serviço** (antes todas mostravam o mesmo endereço).
- **Opções de upgrade:** planos de mesma velocidade agora aparecem **diferenciados**
  pelo nome (ex.: "Fibra 1 Giga" × "1 Giga + Ponto Adicional").
- **Privacidade do agendamento:** passa a exibir **data + turno** (ex.: "29/06 - Tarde"),
  **sem o horário exato** interno.

### 2.10. Infraestrutura em produção
**7 serviços** ativos e habilitados no boot: aplicação web, motor de conversação (IA),
simulador, e **4 workers** (novo serviço, upgrade, conversão, sincronização de status).

---

## 3. 🟡 Parcialmente entregue

| Item | O que está pronto | O que falta |
|---|---|---|
| **Tela de auditoria humana** | IA validando e a tela disponível para auditoria | Definir com a gestão o **processo de auditoria** (quem revisa, frequência, o que aciona ajuste) |
| **Captura/monitoramento de APIs internas** | Ferramenta de captura usada nas implementações | Painel de **monitoramento contínuo** caso o HubSoft altere as APIs (hoje protegido pelo fallback webdriver) |
| **Correção de endereço já gravado** | Corrigido para **novos** atendimentos | Registros **antigos** com endereço errado não foram corrigidos (decisão: eram de teste) |

---

## 4. ⏳ Pendente

| Item | Descrição | Prioridade |
|---|---|---|
| **Limpeza dos dados de teste em produção** | Cancelar clientes/serviços de teste criados no HubSoft durante a homologação (Kevin, Martin, Cauê, Lorenzo e "Teste…"). Atendimentos/O.S. de teste **já foram encerrados**. | Média |
| ~~Métricas de negócio~~ | ✅ **Entregue em 08/07** — painel Análises (item 2.17) | — |
| **Homologação assistida final** | Acompanhamento de uma janela de produção real com clientes reais antes do volume pleno | Alta |
| **Robô antigo (decomissionamento)** | Após confiança plena, encerrar o `gestao_leads_bot` e centralizar tudo no V2 | Baixa (planejado) |

---

## 5. Riscos e mitigação

- **HubSoft é produção real (sem sandbox):** mitigado por execução auditada,
  separação por vendedor e fallback para webdriver.
- **APIs internas podem mudar:** o **fallback webdriver** mantém o fluxo funcionando
  caso a API mude; recomenda-se o painel de monitoramento (item parcial).
- **Coexistência com o robô antigo:** resolvida pela separação de vendedor
  (1613 × 1618) — sem disputa pelos mesmos prospectos.

---

## 6. Recomendação à gestão

1. **Aprovar a operação assistida** (homologação final com clientes reais).
2. **Definir o processo de auditoria** (papéis e cadência) para a tela já disponível.
3. **Priorizar o painel de métricas** para acompanhamento gerencial.
4. **Planejar o decomissionamento do robô antigo** após a janela de confiança.

> **Detalhamento técnico das últimas entregas:** ver
> `dashboard_comercial/gerenciador_vendas/docs/RELATORIO_IMPLEMENTACOES_2026-07-07.md`.

---

*Documento gerado automaticamente — Robô de Vendas V2 · 10/07/2026.*
