---
name: criar-no-automacao
description: Scaffolda um novo nó ("quadradinho" estilo n8n) da engine de automação unificada em apps/automacao, seguindo o contrato BaseNode/NodeResult completo (ícone, grupo/subgrupo, saídas, campos_config, is_trigger). Gera a classe registrada, o teste isolado, a entrada no catálogo da doc e roda o gate. Use quando for criar um bloco novo da engine de automação (apps/automacao/nodes).
---

# Criar nó da engine de automação

Receita pra criar um nó **idêntico e completo**, seguindo o contrato atual. NÃO improvise: leia o contrato e um nó de referência antes.

## 0. Leia o contrato (obrigatório)
Paths relativos a `robo/dashboard_comercial/gerenciador_vendas/`.
1. `apps/automacao/nodes/base.py` — `BaseNode`, `NodeResult`, `@registrar`.
2. `robo/docs/PRODUTO/modulos/automacao/README.md` — contrato híbrido, princípios, catálogo.
3. Um nó de **referência** parecido com o que você vai criar:
   - simples / transformação → `set_fields.py`
   - rede + segredos (SSRF + mascaramento) → `http_request.py`
   - ramificação (saídas múltiplas) → `if_node.py`
   - **domínio / integração** (reusa service) → `whatsapp.py` + `services/whatsapp.py`
   - **gatilho** (sem entrada) → `webhook_trigger.py`, `evento_trigger.py`
   - **pausa / aguardar** → `delay.py` (timer) e `whatsapp.py` `WhatsappPerguntaNode` (resposta)

## 1. Colete a spec (pergunte ao usuário se faltar, numa pergunta agrupada)
- `tipo`: slug único snake_case · `label`: nome amigável · `icone`: Bootstrap Icon (`bi-*`)
- `grupo` (categoria no menu: Core | Transformação | Fluxo | Gatilho | WhatsApp…) + `subgrupo`
- `categoria` (gating por tenant: core | comercial | marketing | atendimento)
- `saidas`: as branches (ex: `['sucesso','erro']`, `['true','false']`, `['default']`)
- `is_trigger`? (gatilho = sem porta de entrada, é o início do fluxo)
- `campos_config`: cada campo `{nome, label, tipo, opcoes?, placeholder?, ajuda?, obrigatorio?}`
  - tipos: `texto` | `textarea` | `numero` | `booleano` | `select`(+`opcoes`) | `keyvalue` | `lista_campos` | `filtros`
  - `texto`/`textarea` aceitam expressões `{{...}}`
- **toca ORM?** (tenant explícito) · **faz rede/segredos?** (SSRF + mascaramento) · **pausa?** (espera)

## 2. Crie a classe `apps/automacao/nodes/<tipo>.py`
```python
from .base import BaseNode, NodeResult, registrar

@registrar
class MeuNode(BaseNode):
    tipo = "meu_no"
    label = "Meu nó"
    icone = "bi-..."
    categoria = "core"
    grupo = "Core"
    subgrupo = "..."
    saidas = ["sucesso", "erro"]
    is_trigger = False

    def campos_config(self) -> list:
        return [{'nome': 'x', 'label': 'X', 'tipo': 'texto', 'obrigatorio': True}]

    def validar_config(self, config) -> list:
        return [] if config.get('x') else ['`x` é obrigatório.']

    def executar(self, config, entrada, contexto) -> NodeResult:
        valor = contexto.resolver(config.get('x', ''))   # resolve {{...}}
        return NodeResult(output={'ok': True}, branch='sucesso')
```
- **Domínio/integração:** NUNCA fale com API/ORM direto. Crie/usе um service em `apps/automacao/services/` (ex: `uazapi_do_tenant`) — **executor de domínio único**. Tenant via `contexto.tenant`, nunca thread-local.
- **Pausa:** `return NodeResult(status='aguardando', espera={'tipo':'timer','segundos':N})` ou `{'tipo':'resposta','chave':<tel>,'segundos':timeout}`. As saídas viram os branches da retoma (ex: `resposta`/`timeout`).
- **Gatilho** (`is_trigger=True`): sem entrada; `executar` só repassa o contexto do disparo.

## 3. Registre em `apps/automacao/nodes/__init__.py`
`from . import <tipo>  # noqa: F401,E402`

## 4. Teste `tests/test_automacao_<tipo>.py` (puro unit, sem DB)
Espelhe `test_automacao_set_fields.py` / `test_automacao_whatsapp.py` (mock do service). Cobre: registrado, caminho feliz (branch certo), branch de erro, `validar_config` rejeita inválido; se faz rede → mock + SSRF + mascaramento; se domínio → mock do service.

## 5. Catálogo na doc
Adicione a linha na tabela "Catálogo de nós" do `README.md` do módulo (com grupo › subgrupo + status).

## 6. Invariantes (checklist "feature completa")
- Tenant explícito se toca ORM (`contexto.tenant`); nunca `get_current_tenant()`.
- Mascarar `Authorization`/`Cookie` se expõe headers/segredos.
- Sem `print`/debug; sem imports/variáveis sobrando.

## 7. Gate (de `robo/dashboard_comercial/gerenciador_vendas/`)
```bash
python manage.py check --settings=gerenciador_vendas.settings_local
python -m pytest tests/test_automacao_<tipo>.py -q
python manage.py testar_no --tipo <tipo> --tenant <slug> --config '{...}' --settings=gerenciador_vendas.settings_local   # opcional
```
Editor servido: rebuild com `npm run build` em `apps/automacao/editor/` pro nó aparecer em `/automacao/editor/`.

## 8. Doc alterada → `python scripts/gerar_hub.py` (da raiz)

Só pronto com check limpo + pytest verde + o nó aparecendo na paleta.
