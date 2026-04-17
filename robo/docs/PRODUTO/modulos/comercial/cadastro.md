# Comercial — Cadastro

**App:** `apps/comercial/cadastro/`

Pagina publica de auto-cadastro para o site do provedor. O visitante preenche dados pessoais, endereco, seleciona plano/vencimento, envia documentos e aceita contrato. Gera lead automaticamente.

---

## Models (5)

### ConfiguracaoCadastro

**Tabela:** `configuracoes_cadastro` | Singleton por tenant

Configuracao completa da landing page de cadastro. 40+ campos.

| Grupo | Campos |
|-------|--------|
| **Visual** | empresa, titulo_pagina, subtitulo_pagina, logo_url, background_type (gradient/solid/image), cores (primary, secondary, success, error) |
| **Contato** | telefone_suporte, whatsapp_suporte, email_suporte |
| **Planos** | mostrar_selecao_plano, plano_padrao FK |
| **Campos** | cpf_obrigatorio, email_obrigatorio, telefone_obrigatorio, endereco_obrigatorio |
| **Validacoes** | validar_cep (ViaCEP), validar_cpf |
| **Documentacao** | solicitar_documentacao, texto_instrucao_selfie/doc_frente/doc_verso, tamanho_max_arquivo_mb, formatos_aceitos |
| **Contrato** | exibir_contrato, titulo_contrato, texto_contrato, tempo_minimo_leitura_segundos, texto_aceite_contrato |
| **Fluxo** | criar_lead_automatico, numero_etapas, mostrar_progress_bar |
| **Integracao** | id_origem, id_origem_servico, id_vendedor (IDs externos), origem_lead_padrao |
| **Mensagens** | mensagem_sucesso, instrucoes_pos_cadastro |
| **Seguranca** | captcha_obrigatorio, limite_tentativas_dia |

### PlanoInternet

**Tabela:** `planos_internet`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(100) | Ex: "Fibra 400MB" |
| `velocidade_download` / `velocidade_upload` | PositiveInteger | Mbps |
| `valor_mensal` | Decimal(8,2) | Preco mensal |
| `wifi_6` / `suporte_prioritario` / `suporte_24h` / `upload_simetrico` | BooleanField | Features |
| `destaque` | CharField | popular / premium / economico / recomendado (badge) |
| `ordem_exibicao` | PositiveInteger | Ordem na lista |
| `id_sistema_externo` | CharField(50) | ID no ERP |

**Metodos:** `get_valor_formatado()` → "R$ 99,90", `get_velocidade_formatada()` → "400MB" ou "1GB"

### OpcaoVencimento

**Tabela:** `opcoes_vencimento`

Dias de vencimento disponiveis (ex: dia 5, dia 10, dia 20).

### DocumentoLead

**Tabela:** `documentos_lead`

Documentos enviados durante o cadastro. Base64 encoded.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead |
| `tipo_documento` | CharField | selfie / doc_frente / doc_verso / comprovante_residencia / contrato_assinado / outro |
| `arquivo_base64` | TextField | Imagem em base64 |
| `status` | CharField | pendente / aprovado / rejeitado / em_analise |
| `nome_arquivo` / `tamanho_arquivo` / `formato_arquivo` | Metadados | Info do arquivo |

### CadastroCliente

**Tabela:** `cadastros_clientes`

Registra cada sessao de cadastro (mesmo incompleto). Status em 8 etapas.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| **Pessoal** | nome_completo, cpf, rg, email, telefone, data_nascimento |
| **Endereco** | cep, endereco, numero, bairro, cidade, estado |
| **Comercial** | plano_selecionado FK, vencimento_selecionado FK |
| **Status** | status (iniciado / dados_pessoais / endereco / documentacao / contrato / finalizado / erro / cancelado) |
| **Auditoria** | ip_cliente, user_agent, origem_cadastro, tempo_total_cadastro, tentativas_etapa (JSON), erros_validacao (JSON) |
| **Contrato** | contrato_aceito, tempo_leitura_contrato, ip_aceite_contrato |

**Metodos:** `finalizar_cadastro()`, `gerar_lead()`, `get_progresso_percentual()`, `validar_dados_pessoais()`, `validar_endereco()`

---

## APIs (12 endpoints)

| Grupo | Endpoints | Descricao |
|-------|-----------|-----------|
| **Publico** | cadastro/cliente (POST), planos (GET), vencimentos (GET), cep (GET) | Auto-cadastro + consultas |
| **Config** | 3 paginas + 3 APIs CRUD | Gerenciar config, planos, vencimentos |

---

## Consulta CEP

Multi-source com fallback automatico: **ViaCEP → CepAPI → BrasilAPI → Postmon → OpenCEP**. Primeira resposta valida retorna. Inclui headers CORS.

---

## Templates (4)

- `cadastro.html` — Landing page publica de auto-cadastro (multi-step form)
- `configuracoes/cadastro.html` — Config da landing page
- `configuracoes/planos.html` — CRUD de planos
- `configuracoes/vencimentos.html` — CRUD de vencimentos
