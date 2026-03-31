# TecHub / AuroraISP — Análise de Mercado & Go-to-Market

> Contexto de mercado, posicionamento, personas e estratégia de entrada para a venda do produto a outros ISPs.

---

## 1. Contexto: de uso interno a produto

O sistema nasceu como solução interna da **Megalink Telecom** (Teresina/PI) para resolver o caos do processo comercial: leads chegando pelo WhatsApp sem rastreamento, documentos sendo coletados manualmente, contratos assinados sem integração com o HubSoft.

Hoje o sistema está em produção, processando leads reais, e o código já aponta para uma segunda identidade: **AuroraISP** (`aurora.consulteplus.com`, v2.2.0). Isso indica que a intenção de vender para outros ISPs já existe.

O go-to-market é a formalização dessa transição: de ferramenta interna → produto SaaS para provedores.

---

## 2. Mercado-alvo

### 2.1 Brasil tem ~14.000 ISPs registrados

Segundo dados da Anatel (2024), o Brasil tem aproximadamente:
- **14.000 provedores** com outorga ativa
- ~85% são pequenos/médios regionais (menos de 50 mil clientes)
- Concentração no interior do Brasil (Sul, Nordeste, Centro-Oeste)
- Grande parte opera com equipes de vendas de 2 a 20 pessoas

### 2.2 Problema universal no setor

Independente do tamanho, todo ISP tem o mesmo gargalo no processo comercial:

| Etapa | Problema atual |
|-------|---------------|
| Captura de lead | WhatsApp Business sem CRM → leads se perdem |
| Qualificação | Manual, por texto, sem padronização |
| Coleta de documentos | Via WhatsApp, sem validação, arquivado no celular |
| Contrato | PDF enviado por e-mail ou assinado na visita |
| Ativação no ERP | Digitação manual no HubSoft/Ispfy |
| Acompanhamento | Planilha, quando tem |

**Resultado:** tempo de conversão longo, leads esquecidos, erros na ativação, time sem visibilidade do funil.

### 2.3 Por que HubSoft como foco inicial

O **HubSoft** é o ERP mais usado por ISPs de médio porte no Brasil. A integração nativa com HubSoft é o maior diferencial técnico do produto — resolve um problema que nenhuma ferramenta genérica de CRM resolve: **enviar documentos e aceitar contratos diretamente no HubSoft via API**.

ISPs que usam HubSoft e ainda não têm um processo comercial estruturado são o segmento de entrada.

**Estimativa de mercado endereçável (TAM inicial):**
- ~3.000 a 5.000 ISPs usando HubSoft ativamente
- Ticket médio SaaS B2B: R$ 300–800/mês
- TAM inicial: R$ 10M a R$ 50M/ano (conservador)

---

## 3. Personas

### Persona 1 — O Dono do Provedor Regional
- ISP com 500 a 5.000 clientes ativos
- Time comercial de 2 a 8 pessoas
- Usa HubSoft para faturamento e ativação
- WhatsApp é o canal principal de vendas
- **Dor:** "Meus vendedores perdem lead, não sei o que está acontecendo no comercial"
- **Ganho esperado:** visibilidade do funil, menos leads perdidos, menos trabalho manual

### Persona 2 — O Gerente Comercial
- Responsável pelo time de vendas
- Quer saber taxa de conversão, origem dos leads, ranking de vendedores
- Hoje usa planilha ou zero ferramenta
- **Dor:** "Não consigo cobrar o time porque não tenho dado nenhum"
- **Ganho esperado:** dashboard de vendas, relatórios de conversão, gestão por pipeline

### Persona 3 — O Vendedor / Atendente
- Atende no WhatsApp, coleta dados, pede documentos
- Hoje faz tudo na mão, erra na digitação, esquece follow-up
- **Dor:** "Fico perdido, não sei qual lead devo ligar agora"
- **Ganho esperado:** fila de atividades, lembretes automáticos, painel claro

### Persona 4 — O Técnico/TI do Provedor
- Quem vai instalar/configurar o sistema
- Quer API documentada, fácil deploy, sem complicação
- **Dor:** "Não quero ter que dar manutenção em coisa que não é meu core"
- **Ganho esperado:** SaaS pronto, suporte, documentação clara

---

## 4. Proposta de valor

### Para o dono/gestor:
> "Transforme seu WhatsApp em uma máquina de vendas. Cada lead que entra pelo WhatsApp é qualificado, documentado e ativado no HubSoft automaticamente — sem planilha, sem digitação manual, sem lead perdido."

### Para o time de vendas:
> "Saiba exatamente o que fazer em cada momento: quem ligar, quem está aguardando documento, quem está perto de fechar. Tudo em uma tela."

### Para o técnico:
> "Deploy em 1 hora, integração HubSoft nativa, N8N configurado, documentação completa. Você não precisa construir nada."

---

## 5. Diferenciais competitivos

| Diferencial | Genérico (Pipedrive, RD Station) | AuroraISP |
|-------------|----------------------------------|-----------|
| Integração HubSoft nativa | ❌ Não tem | ✅ Nativo |
| Bot de qualificação via WhatsApp | ❌ Requer customização cara | ✅ Incluído |
| Coleta e validação de documentos | ❌ Não tem | ✅ Nativo |
| Envio automático de contrato ao ERP | ❌ Não tem | ✅ Nativo |
| Fluxos configuráveis sem código | ⚠️ Parcial | ✅ Completo |
| Feito para ISP (terminologia, fluxo) | ❌ Genérico | ✅ Específico |
| Preço acessível para ISP médio | ❌ Caro | ✅ Acessível |

**Competidores diretos reais:** quase nenhum. O mercado de ISP pequeno/médio usa:
- Planilhas
- Grupos de WhatsApp
- CRMs genéricos mal configurados
- Sistemas próprios mal documentados

Isso é oportunidade: a concorrência é principalmente o "não ter nada".

---

## 6. Modelo de negócio sugerido

### 6.1 SaaS com planos por volume de leads

| Plano | Leads/mês | Usuários | Preço sugerido |
|-------|-----------|----------|----------------|
| **Starter** | até 200 | 3 usuários | R$ 297/mês |
| **Crescimento** | até 1.000 | 10 usuários | R$ 597/mês |
| **Escala** | ilimitado | ilimitado | R$ 997/mês |
| **Enterprise** | ilimitado + suporte dedicado | ilimitado | sob consulta |

### 6.2 Implantação como serviço adicional
- Setup + configuração do N8N: R$ 500 a R$ 1.500 (único)
- Configuração do fluxo de atendimento: R$ 300 a R$ 800 (único)
- Treinamento do time: R$ 400 (único)

### 6.3 Receita estimada para 50 clientes (cenário conservador)
- Mix de planos Starter/Crescimento: média R$ 450/mês por cliente
- MRR: R$ 22.500
- ARR: R$ 270.000

---

## 7. Canais de aquisição

### Canal 1 — Comunidades de provedores
- Grupos de WhatsApp/Telegram de ISPs (existem centenas no Brasil)
- ABRINT, ABRI — associações do setor
- Eventos: ISP Summit, MeetISP, feiras regionais
- **Custo:** baixo, requer presença e credibilidade

### Canal 2 — Parceria com revenda HubSoft
- HubSoft tem rede de revendas e parceiros
- Um parceiro que vende HubSoft pode incluir AuroraISP no pacote
- Modelo comissão: 20-30% MRR para o parceiro
- **Custo:** baixo, alta qualificação do lead

### Canal 3 — Inbound (SEO + conteúdo)
- Blog com dicas para ISP ("como não perder lead no WhatsApp", "como vender mais fibra")
- YouTube mostrando o produto em ação
- **Custo:** médio, retorno a médio prazo

### Canal 4 — Outbound direto
- Abordagem direta em grupos de WhatsApp de ISPs
- Demo gratuita de 30 dias
- Proposta de ROI: "se você converter 2 leads a mais por mês já paga o plano"
- **Custo:** baixo, conversão depende de execução

### Canal 5 — Proof of concept com Megalink
- Usar a Megalink como caso de sucesso com dados reais
- "341 leads processados, 12 contratos enviados ao HubSoft automaticamente"
- Video case de 2 minutos mostrando o produto funcionando

---

## 8. Objeções comuns e respostas

| Objeção | Resposta |
|---------|----------|
| "Já uso o WhatsApp Business" | O WhatsApp Business não tem CRM, não valida documentos, não integra com HubSoft. São complementares. |
| "Minha equipe não vai aprender" | A interface foi desenhada para vendedores sem conhecimento técnico. Bot + painel simples. |
| "E se meu N8N cair?" | O sistema funciona independente do N8N para cadastro manual. N8N é para automação, não para operação básica. |
| "Vocês ficam com meus dados?" | SaaS auto-hospedado disponível. Você pode rodar no seu servidor. |
| "Não tenho técnico para configurar" | A implantação é nossa responsabilidade. Você paga o setup e nós configuramos. |
| "E se eu quiser sair?" | Exportação completa dos dados em CSV/JSON a qualquer momento. |

---

## 9. O que precisa estar pronto antes do GTM

### Produto (obrigatório)
- [ ] Multi-tenancy (separação de dados por empresa)
- [ ] Plano de onboarding documentado
- [ ] Módulo CRM com pipeline (diferencial competitivo vs. planilha)
- [ ] Landing page clara com demo em vídeo

### Negócio (obrigatório)
- [ ] Contrato de serviço / termos de uso
- [ ] Política de privacidade (LGPD)
- [ ] Suporte definido (SLA, canais, horário)
- [ ] Processo de onboarding (quem faz, quanto tempo)

### Marketing (recomendado)
- [ ] Caso de uso Megalink documentado com números
- [ ] Video demo de 2 minutos
- [ ] Página de preços clara

---

## 10. Cronograma sugerido de GTM

| Fase | Período | O que fazer |
|------|---------|-------------|
| **Produto** | Meses 1-2 | Multi-tenancy + CRM pipeline + polish do frontend |
| **Validação** | Mês 3 | 3-5 clientes beta (ISPs conhecidos, preço simbólico) |
| **Lançamento** | Mês 4 | Caso de sucesso + vídeo + abordagem em comunidades |
| **Escala** | Meses 5-6 | Parcerias HubSoft + inbound + outbound |
