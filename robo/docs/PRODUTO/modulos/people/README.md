# People, gestao de pessoas

Modulo de RH do Hubtrix, portado do departamento pessoal da Visio. Cobre o ciclo
de vida do colaborador, de cadastro a desligamento.

**Estado**: fundacao e cadastro construidos e funcionando. Admissao,
desligamento, experiencia, freelancers e escala ainda nao. Ver `GAPS-VISIO.md`
pro mapa completo do que falta e por que.

- **Rota**: `/people/`
- **Modulo comercializavel**: `tenant.modulo_people`
- **Tarefas**: 205 (fundacao, concluida) e 208 (gaps remanescentes)

---

## As duas regras que valem pro modulo inteiro

### 1. `Colaborador` e fonte unica

Toda Tool que precisar criar pessoa (feedback, recrutamento, treinamento) passa
por `apps.people.services.registrar_colaborador`, que pesquisa antes de criar.
Ninguem escreve na tabela direto, e ninguem cria cadastro paralelo pra sua
propria Tool.

O dedup vive em tres camadas:

| Camada | O que garante |
|---|---|
| `UniqueConstraint(tenant, cpf)` | Intransponivel. CPF ausente e `NULL` (varias pessoas podem estar sem), presente e unico |
| `CheckConstraint` de formato | Impede gravar `''` por atalho e detonar a unique com erro incompreensivel longe da causa |
| `registrar_colaborador` | Decide entre criar, reaproveitar, readmitir ou devolver conflito |

Match por CPF resolve sozinho. Match fraco (telefone, ou nome mais nascimento)
**nunca** reaproveita calado: devolve conflito com os candidatos e deixa um
humano decidir. Telefone se repete em familia e em telefone de loja.

### 2. Colaborador nao se apaga, se desliga

Desativar e gravar `situacao='desligado'`, preservando a linha. E isso que
viabiliza readmissao e o reaproveitamento como freelancer. FK vinda de outro app
deve ser `PROTECT`, nunca `CASCADE`.

---

## Como o codigo esta organizado

| Arquivo | Papel |
|---|---|
| `estados.py` | **A fonte da verdade do ciclo de vida.** Situacoes, transicoes, pontos de entrada, pre condicoes. Python puro, testavel sem banco |
| `services/colaboradores.py` | Unico caminho de escrita: `buscar`, `registrar`, `mover_situacao` |
| `services/links.py` | Ciclo de vida dos links publicos |
| `services/configuracao.py` | `config_efetiva(unidade)`: global do tenant com override por unidade |
| `campos_formulario.py` | Catalogo dos campos do formulario publico |
| `analises.py` | Metricas, todas saindo do `HistoricoSituacao` |
| `telemetria.py` | Ponto unico de emissao de evento |
| `permissoes.py` | Gate que exige contratacao E permissao |
| `tenant_scope.py` | Escopo de tenant pra request sem usuario logado |
| `consultas.py` | Consultas nomeadas, pra que `filter(situacao=)` nao se espalhe |

### A guarda de situacao

`situacao` so muda por `mover_situacao()`, porque toda transicao precisa gerar
historico e telemetria. Um `save()` que mexeu nela sem autorizacao levanta
`TransicaoNaoAutorizada`.

O que a guarda NAO cobre e `queryset.update(situacao=...)`, que nao passa por
`save()`. Esse buraco e fechado por varredura de codigo em
`tests/test_people_contrato.py`, que tambem proibe criar `Colaborador` fora dos
servicos e usar `filter(situacao=)` fora de `apps/people/`.

---

## O ciclo de vida

Sete situacoes, uma geracao de vocabulario so:

```
cadastro → em_admissao → em_experiencia → efetivado → em_desligamento → desligado
                                             ↕
                                    ferias / afastamento
```

Mais `freelancer`, pra quando o banco de freelancers existir.

**Tres pontos de entrada**, nao um. A tela pergunta "esse colaborador ja comecou
a trabalhar?" e cada resposta entra numa fase diferente. O auto cadastro sempre
entra em `cadastro`, porque quem preenche e o proprio colaborador e ele nao
decide a propria fase.

**Ferias e afastamento sao interrupcoes, nao fases.** A pessoa sai de `efetivado`
e volta pra `efetivado`, entao nao viram coluna no board: aparecem na coluna de
origem com um badge. Voltar emite `retornou` e nao `efetivado` de novo, senao o
funil contaria a mesma efetivacao duas vezes.

**Prorrogar nao e estado**, e a auto transicao `em_experiencia → em_experiencia`.
Uma coluna "Prorrogado" racharia a populacao "quem esta em experiencia" em duas,
e toda consulta de RH e de alerta teria que somar as duas.

---

## Telemetria

`HistoricoSituacao` e a **fonte primaria**: queryavel, com timestamp e snapshot
do que a transicao mexeu. `LogSistema` (categoria `people`) e a engine de
automacao sao canais derivados e blindados. Se os dois cairem, o funil continua
reconstituivel, e ha teste provando isso com ambos mortos por monkeypatch.

Doze eventos emitidos, quatro no catalogo do editor de fluxos. Os outros entram
quando as fases correspondentes forem construidas: poluir o editor com evento
morto e pior que faltar.

---

## O formulario publico

O colaborador de loja geralmente nao tem login. Recebe o link por WhatsApp, abre
no celular e preenche os proprios dados.

Tres cuidados que valem revisar antes de mexer ali:

1. **O tenant vem do token**, nao da sessao. Sem usuario, o `TenantManager` nao
   filtra nada e o `TenantMixin` nao preenche tenant. Duas defesas somadas:
   escopo (`tenant_scope.py`) e tenant explicito em toda leitura e escrita.
2. **A resposta de conflito e generica.** Dizer que o CPF ja existe
   transformaria a pagina num oraculo de quem trabalha na empresa. Os 404 sao
   indistinguiveis entre token invalido, expirado e desativado pelo mesmo motivo.
3. **Anti abuso**: rate limit por IP e por token, honeypot, teto de submissoes.
   Rejeicao nao conta no teto, senao um robo derrubaria o link da loja so
   mandando lixo.

---

## Como rodar e testar

```bash
docker start hubtrix-pg17
cd robo/dashboard_comercial/gerenciador_vendas
python manage.py migrate --settings=gerenciador_vendas.settings_local
python manage.py seed_people_funcionalidades --settings=gerenciador_vendas.settings_local
python manage.py seed_people_demo --limpar --settings=gerenciador_vendas.settings_local
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```

O tenant precisa de `modulo_people=True` (toggle em `/aurora-admin/`).

Testes:

```bash
python -m pytest tests/test_people_*.py -q
```

Onze arquivos, 293 testes. Os que mais importam:

| Arquivo | O que protege |
|---|---|
| `test_people_estados.py` | A maquina, sem banco. Inclui varredura de grafo (todo estado alcancavel, ninguem preso) |
| `test_people_dedup.py` | As quatro clausulas da regra de fonte unica |
| `test_people_contrato.py` | Varredura de codigo: ninguem fura o servico |
| `test_people_publico.py` | Isolamento com thread local sujo de proposito |
| `test_people_configuracao.py` | Render de todas as telas, porque `check` nao compila template |
