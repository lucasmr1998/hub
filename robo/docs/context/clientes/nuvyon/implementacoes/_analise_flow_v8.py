#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analise da logica do fluxo Matrix da Nuvyon (flow_103_hubtrix_v8.json).

Console e cp1252: toda saida de texto vinda do fluxo passa por SAFE() pra nao quebrar.
"""
import json
import re
import sys
from collections import Counter, defaultdict

PATH = "flow_103_hubtrix_v8.json"


def SAFE(s):
    """Torna qualquer string ascii-safe pro console cp1252."""
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return s.encode("ascii", "replace").decode()


def trunc(s, n=90):
    s = SAFE(s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:n] + "...") if len(s) > n else s


def P(*a):
    print(*[SAFE(x) if isinstance(x, str) else x for x in a])


METHODS = {0: "GET?", 1: "POST", 2: "PUT", 3: "PATCH", 4: "GET", 5: "DELETE"}

COMP_LABEL = {
    "": "aresta/raiz (edge) ou no-bot raiz",
    "1": "Mensagem (envia texto ao cliente)",
    "2": "Captura/entrada do usuario (variable + validacao)",
    "4": "Finalizar atendimento (categorizacao/pesquisa/tags)",
    "7": "Transbordo p/ fila de servico (service)",
    "8": "Decisao/condicao logica (dec_*)",
    "9": "API (variante; mesmo schema do 18)",
    "10": "Menu/URA (botoes ou pergunta com opcoes)",
    "13": "Set de variaveis (var_* - define textos/constantes)",
    "14": "Horario de atendimento (schedule)",
    "15": "Config STT",
    "17": "Conexao condicional (rota um ramo p/ outro componente)",
    "18": "API (request HTTP - leads/historico/imagens/hubsoft/matrix)",
    "26": "Espera/delay (wait - num_wait segundos)",
}


def load():
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def section(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main():
    d = load()
    flow = d["flow"]
    variaveis = d.get("variaveis", {})
    byid = {n["id"]: n for n in flow}

    # mapa id_variavel -> nome legivel
    varname = {}
    for vid, vdef in variaveis.items():
        if isinstance(vdef, dict):
            nm = vdef.get("name") or vdef.get("identifier") or vdef.get("key")
            varname[str(vid)] = nm or vid
        else:
            varname[str(vid)] = str(vdef)

    # =====================================================================
    section("1. TIPOS DE NO (cod_componente)")
    cnt = Counter(str(n.get("cod_componente")) for n in flow)
    edges = [n for n in flow if n.get("edge")]
    nodes = [n for n in flow if not n.get("edge")]
    P("Total entradas no 'flow': %d  (nos reais: %d | arestas: %d)" % (len(flow), len(nodes), len(edges)))
    P("")
    for k, v in cnt.most_common():
        P("  cod=%-4s x%-4d  %s" % (k, v, COMP_LABEL.get(k, "?")))

    # =====================================================================
    section("2. NOS DE API (data.api.url) - em ordem aproximada de id")
    api_nodes = []
    for n in flow:
        data = n.get("data")
        if isinstance(data, dict) and isinstance(data.get("api"), dict) and data["api"].get("url"):
            api_nodes.append(n)
    P("Total de chamadas de API encontradas: %d" % len(api_nodes))
    P("")

    def classify(url):
        u = url.lower()
        if "/api/leads/registrar" in u:
            return "HUBTRIX leads/registrar"
        if "/api/leads/atualizar" in u:
            return "HUBTRIX leads/atualizar"
        if "/api/leads/imagens" in u:
            return "HUBTRIX leads/imagens"
        if "/api/leads/tags" in u:
            return "HUBTRIX leads/tags"
        if "/api/consultar/leads" in u:
            return "HUBTRIX consultar/leads"
        if "/api/historicos" in u:
            return "HUBTRIX historicos"
        if "hubsoft-status" in u or "/integracoes/" in u:
            return "HUBTRIX integracoes (hubsoft-status)"
        if any(x in u for x in ["abrir_os", "abrir_atendimento", "consultar_agenda", "consultar_datas", "matrix"]):
            return "MATRIX (agenda/OS)"
        return "AURORA/N8N ou outro"

    grp = defaultdict(list)
    rows = []
    for n in sorted(api_nodes, key=lambda x: x["id"]):
        api = n["data"]["api"]
        ident = api.get("identifier", "?")
        method = METHODS.get(api.get("method"), str(api.get("method")))
        url = api.get("url", "")
        klass = classify(url)
        grp[klass].append(ident)
        rows.append((n["id"], n.get("cod_componente"), ident, method, klass, url))

    P("Por categoria (identifier):")
    for k in sorted(grp):
        P("  %-38s -> %s" % (k, ", ".join(sorted(set(grp[k])))))
    P("")
    P("Detalhe (id no | cod | identifier | metodo | URL):")
    for nid, cod, ident, method, klass, url in rows:
        P("  no#%-5s c%-3s %-22s %-5s %s" % (nid, cod, ident, method, trunc(url, 70)))

    # =====================================================================
    section("3. MENUS/URA e MENSAGENS-CHAVE")
    # cod 10 = menus, cod 1 = mensagens
    P(">> URAs/Menus (cod=10):")
    for n in flow:
        if str(n.get("cod_componente")) == "10" and isinstance(n.get("data"), dict):
            dt = n["data"]
            ident = dt.get("identifier")
            msg = dt.get("message") or ""
            msgs = dt.get("messages")
            if not msg and isinstance(msgs, list) and msgs:
                msg = msgs[0] if isinstance(msgs[0], str) else json.dumps(msgs[0], ensure_ascii=True)
            botoes = dt.get("list_button_text") or []
            ura = dt.get("bol_botoes_ura")
            P("  no#%-5s %-14s ura=%s  msg: %s" % (n["id"], SAFE(str(ident)), ura, trunc(msg, 80)))
            if botoes:
                bl = [trunc(b, 30) for b in botoes if b]
                if bl:
                    P("        botoes: %s" % " | ".join(bl))

    P("")
    P(">> Mensagens (cod=1) - primeiras linhas:")
    shown = 0
    for n in sorted(flow, key=lambda x: x["id"]):
        if str(n.get("cod_componente")) == "1" and isinstance(n.get("data"), dict):
            dt = n["data"]
            msgs = dt.get("messages") or []
            txt = ""
            if isinstance(msgs, list):
                parts = []
                for m in msgs:
                    if isinstance(m, str):
                        parts.append(m)
                    elif isinstance(m, dict):
                        parts.append(json.dumps(m, ensure_ascii=True))
                txt = " ".join(parts)
            P("  no#%-5s %-16s %s" % (n["id"], SAFE(str(dt.get("identifier"))), trunc(txt, 80)))
            shown += 1
            if shown >= 45:
                P("  ... (%d nos de mensagem no total)" % cnt["1"])
                break

    # =====================================================================
    section("4. POLLING POS-CONTRATACAO (hubsoft-status / api_21)")
    poll = [n for n in flow if isinstance(n.get("data"), dict)
            and isinstance(n["data"].get("api"), dict)
            and "hubsoft-status" in (n["data"]["api"].get("url") or "").lower()]
    P("Nos que chamam hubsoft-status: %d" % len(poll))
    for n in poll:
        api = n["data"]["api"]
        P("  no#%-5s id=%s url=%s store_returned=%s store_var=%s" % (
            n["id"], api.get("identifier"),
            trunc(api.get("url"), 60),
            n["data"].get("store", {}).get("returned"),
            n["data"].get("store", {}).get("variable"),
        ))

    # condicoes que testam eh_cliente_hubsoft / documentacao_validada / total_doc_rejeitado
    P("")
    P(">> Condicoes/labels que mencionam variaveis do polling:")
    poll_terms = ["hubsoft", "documenta", "doc_rejeit", "rejeit", "validad", "cliente"]
    for n in flow:
        val = n.get("value")
        if val and any(t in SAFE(val).lower() for t in poll_terms):
            P("  edge#%-5s src=%s->tgt=%s value=%r" % (n["id"], n.get("source"), n.get("target"), trunc(val, 50)))

    # waits (delay = intervalo do polling)
    P("")
    P(">> Nos de espera (cod=26 - intervalo do loop):")
    for n in flow:
        if str(n.get("cod_componente")) == "26" and isinstance(n.get("data"), dict):
            P("  no#%-5s %s  num_wait=%s s" % (n["id"], n["data"].get("identifier"), n["data"].get("num_wait")))

    # tentativas maximas: procurar variaveis/constantes com 'tentativa' ou contadores
    P("")
    P(">> Variaveis/contadores relacionados a tentativas/contador:")
    for vid, nm in varname.items():
        low = SAFE(nm).lower()
        if any(t in low for t in ["tentativa", "contador", "count", "polling", "loop", "max", "limite"]):
            P("  var %s = %s" % (vid, SAFE(nm)))

    # =====================================================================
    section("5. ETAPA DE INSTALACAO / OS (Matrix)")
    matrix_terms = ["consultar_datas", "consultar_agenda", "abrir_atendimento", "abrir_os"]
    for term in matrix_terms:
        hits = [n for n in flow if isinstance(n.get("data"), dict)
                and isinstance(n["data"].get("api"), dict)
                and term in (n["data"]["api"].get("url") or "").lower()]
        P(">> %s : %d no(s)" % (term, len(hits)))
        for n in hits:
            api = n["data"]["api"]
            P("    no#%-5s id=%s %s %s" % (
                n["id"], api.get("identifier"),
                METHODS.get(api.get("method"), api.get("method")),
                trunc(api.get("url"), 70)))

    # =====================================================================
    section("6. IDs ENVIADOS NO REGISTRAR/ATUALIZAR DO LEAD")
    for n in flow:
        data = n.get("data")
        if not (isinstance(data, dict) and isinstance(data.get("api"), dict)):
            continue
        url = (data["api"].get("url") or "").lower()
        if "/api/leads/registrar" in url or "/api/leads/atualizar" in url:
            body = data.get("body", {}).get("body", "")
            found = {}
            for key in ["id_vendedor_rp", "id_origem_servico", "id_origem", "id_plano_rp", "id_dia_vencimento"]:
                m = re.search(r'"%s"\s*:\s*("?[^",\n}]+"?)' % key, body)
                if m:
                    found[key] = m.group(1).strip()
            if found:
                P("  no#%-5s %s -> %s" % (
                    n["id"], data["api"].get("identifier"),
                    ", ".join("%s=%s" % (k, SAFE(v)) for k, v in found.items())))

    # =====================================================================
    section("7. TRANSBORDOS PARA HUMANO")
    # cod 7 = service/transbordo; tambem mensagens com 'transferir/atendente'
    P(">> Nos de fila/servico (cod=7):")
    for n in flow:
        if str(n.get("cod_componente")) == "7" and isinstance(n.get("data"), dict):
            dt = n["data"]
            P("  no#%-5s %s service=%s priority=%s transbordo=%s pesquisa=%s parent=%s" % (
                n["id"], dt.get("identifier"), dt.get("service"), dt.get("priority"),
                dt.get("transbordo"), dt.get("pesquisa"), n.get("parent")))
    P("")
    P(">> Mensagens que mencionam transferencia/atendente/consultor:")
    seen = set()
    for n in flow:
        data = n.get("data")
        if isinstance(data, dict):
            blob = json.dumps(data, ensure_ascii=True).lower()
            if any(t in blob for t in ["transferir para", "atendente", "consultor", "transbordo", "humano"]):
                ident = data.get("identifier") or (data.get("api", {}) or {}).get("identifier")
                key = (n.get("cod_componente"), str(ident))
                if key in seen:
                    continue
                seen.add(key)
                P("  no#%-5s c%-3s %s" % (n["id"], n.get("cod_componente"), SAFE(str(ident))))

    # =====================================================================
    section("8. SEQUENCIA LOGICA (ordenada por id - rota principal de APIs)")
    P("Ordem das chamadas de API (proxy da jornada):")
    for nid, cod, ident, method, klass, url in rows:
        P("  %-22s %-5s %-38s [no#%s]" % (ident, method, klass, nid))


if __name__ == "__main__":
    main()
