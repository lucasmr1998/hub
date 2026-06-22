import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState,
  type Connection, type Edge, type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { BlocoNode } from './BlocoNode'
import { NodeModal } from './NodeModal'
import ExecucoesPanel from './ExecucoesPanel'
import {
  buscarCatalogo, buscarEventos, testarFluxo, listarFluxos, getFluxo, criarFluxo, atualizarFluxo,
  type NoCatalogo, type FluxoResumo, type EventoCatalogo,
} from './api'
import { paraRuntime, deRuntime, ICONES, GRUPOS, CORES_GRUPO, SAIDAS, TRIGGERS, slug } from './flow'

function recomputarContadores(nodes: Node[]): Record<string, number> {
  const c: Record<string, number> = {}
  for (const n of nodes) {
    const m = /^(.*)_(\d+)$/.exec(n.id)
    if (m) c[m[1]] = Math.max(c[m[1]] ?? 0, Number(m[2]))
  }
  return c
}

const nodeTypes = { bloco: BlocoNode }

export function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [catalogo, setCatalogo] = useState<NoCatalogo[]>([])
  const [eventos, setEventos] = useState<EventoCatalogo[]>([])
  const [selId, setSelId] = useState<string | null>(null)
  const [resultado, setResultado] = useState<any>(null)
  const [paletaAberta, setPaletaAberta] = useState(false)
  const [lista, setLista] = useState<FluxoResumo[]>([])
  const [fluxoId, setFluxoId] = useState<number | null>(null)
  const [nome, setNome] = useState('')
  const [msg, setMsg] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [editId, setEditId] = useState<string | null>(null)
  const [aba, setAba] = useState<'editor' | 'execucoes'>('editor')
  const contadores = useRef<Record<string, number>>({})

  const urlWebhook = (token: string) =>
    token ? `${window.location.origin}/automacao/webhook/${token}/` : ''

  useEffect(() => {
    buscarCatalogo().then((cat) => {
      setCatalogo(cat)
      cat.forEach((c) => {
        ICONES[c.tipo] = c.icone
        GRUPOS[c.tipo] = c.grupo
        SAIDAS[c.tipo] = c.saidas
        TRIGGERS[c.tipo] = c.is_trigger
      })
    }).catch((e) => console.error('catálogo:', e))
    buscarEventos().then(setEventos).catch((e) => console.error('eventos:', e))
    listarFluxos().then(setLista).catch((e) => console.error('fluxos:', e))
  }, [])

  const novo = () => {
    setNodes([]); setEdges([]); setFluxoId(null); setNome(''); setSelId(null)
    setWebhookUrl('')
    contadores.current = {}
  }

  const excluirNo = (id: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== id))
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
    setSelId(null)
    setEditId(null)
  }

  const carregar = async (id: number) => {
    const f = await getFluxo(id)
    const { nodes: ns, edges: es } = deRuntime(f.grafo)
    setNodes(ns); setEdges(es); setFluxoId(f.id); setNome(f.nome); setSelId(null)
    setWebhookUrl(urlWebhook(f.webhook_token))
    contadores.current = recomputarContadores(ns)
  }

  const salvar = async () => {
    const grafo = paraRuntime(nodes, edges)
    const nomeFinal = nome.trim() || 'Sem nome'
    try {
      const r = fluxoId
        ? await atualizarFluxo(fluxoId, nomeFinal, grafo)
        : await criarFluxo(nomeFinal, grafo)
      if (!fluxoId) setFluxoId(r.id)
      setWebhookUrl(urlWebhook(r.webhook_token))
      setNome(nomeFinal)
      setMsg('salvo ✓')
      setTimeout(() => setMsg(''), 2000)
      listarFluxos().then(setLista)
    } catch (e) {
      setMsg('erro ao salvar')
    }
  }

  const onConnect = useCallback(
    (c: Connection) =>
      setEdges((eds) => addEdge({ ...c, label: c.sourceHandle ?? '' }, eds)),
    [setEdges],
  )

  const addNode = (tipo: string, label: string) => {
    const n = (contadores.current[tipo] ?? 0) + 1
    contadores.current[tipo] = n
    const id = `${tipo}_${n}`
    setNodes((nds) =>
      nds.concat({
        id,
        type: 'bloco',
        position: { x: 160 + (nds.length % 4) * 60, y: 90 + nds.length * 40 },
        data: { tipo, nome: label, config: {} },
      }),
    )
    setSelId(id)
    setPaletaAberta(false)
  }

  const atualizarConfig = (cfg: unknown) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === editId ? { ...n, data: { ...n.data, config: cfg } } : n)),
    )
  }

  // Nome de exibição (livre) — só visual, não afeta referências.
  const setNomeExib = (nome: string) => {
    setNodes((nds) => nds.map((n) => (n.id === selId ? { ...n, data: { ...n.data, nome } } : n)))
  }

  // Handle (referência {{nodes.<handle>}}) — sempre slug seguro; reescreve as arestas.
  const renomearHandle = (novo: string) => {
    novo = slug(novo)
    if (!selId || !novo || novo === selId || nodes.some((n) => n.id === novo)) return
    setNodes((nds) => nds.map((n) => (n.id === selId ? { ...n, id: novo } : n)))
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        source: e.source === selId ? novo : e.source,
        target: e.target === selId ? novo : e.target,
      })),
    )
    setSelId(novo)
  }

  const rodar = async () => {
    setResultado({ status: 'rodando...' })
    try {
      setResultado(await testarFluxo(paraRuntime(nodes, edges)))
    } catch (e: any) {
      setResultado({ status: 'erro', erro: String(e) })
    }
  }

  const exportar = () => {
    const json = JSON.stringify(paraRuntime(nodes, edges), null, 2)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([json], { type: 'application/json' }))
    a.download = 'fluxo.json'
    a.click()
  }

  const selecionado = nodes.find((n) => n.id === selId) ?? null

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-esq">
          <button className="btn-add" onClick={() => setPaletaAberta((v) => !v)}>
            <span className="plus">＋</span> Adicionar nó
          </button>
          <input
            className="nome-fluxo"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome do fluxo"
          />
          <select
            className="sel-fluxo"
            value={fluxoId ?? ''}
            onChange={(e) => (e.target.value === '' ? novo() : carregar(Number(e.target.value)))}
          >
            <option value="">— novo —</option>
            {lista.map((f) => (
              <option key={f.id} value={f.id}>{f.nome}</option>
            ))}
          </select>
        </div>
        <div className="topbar-tabs">
          <button className={`topbar-tab ${aba === 'editor' ? 'ativo' : ''}`}
                  onClick={() => setAba('editor')}>Editor</button>
          <button className={`topbar-tab ${aba === 'execucoes' ? 'ativo' : ''}`}
                  onClick={() => setAba('execucoes')}>Execuções</button>
        </div>
        <div className="topbar-acoes">
          {msg && <span className="topbar-msg">{msg}</span>}
          <button onClick={salvar}>💾 Salvar</button>
          <button className="primary" onClick={rodar}>▶ Testar</button>
          <button onClick={exportar}>Exportar JSON</button>
        </div>
      </header>

      <div className="corpo" style={{ display: aba === 'editor' ? 'grid' : 'none' }}>
        <main className="canvas">
          {paletaAberta && (
            <NodePanel
              catalogo={catalogo}
              onAdd={addNode}
              onClose={() => setPaletaAberta(false)}
            />
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSelId(n.id)}
            onNodeDoubleClick={(_, n) => setEditId(n.id)}
            onPaneClick={() => { setSelId(null); setPaletaAberta(false) }}
            nodeTypes={nodeTypes}
            deleteKeyCode={['Backspace', 'Delete']}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </main>

        <aside className="painel">
          {selecionado ? (
            <ConfigPanel
              key={selecionado.id}
              node={selecionado}
              onNome={setNomeExib}
              onHandle={renomearHandle}
              onAbrir={() => setEditId(selecionado.id)}
              onExcluir={() => excluirNo(selecionado.id)}
            />
          ) : (
            <div className="muted">Selecione um nó. Duplo-clique abre o editor.</div>
          )}

          {selecionado && (selecionado.data as any).tipo === 'webhook' && (
            <div className="webhook-sec">
              <h4>URL do Webhook</h4>
              {webhookUrl ? (
                <input
                  className="webhook-url"
                  readOnly
                  value={webhookUrl}
                  onFocus={(e) => e.currentTarget.select()}
                />
              ) : (
                <div className="muted">Salve o fluxo (💾) pra gerar a URL.</div>
              )}
              <div className="muted">POST aqui dispara o fluxo. O corpo vira {'{{var.payload}}'}.</div>
            </div>
          )}

          {resultado && (
            <div className="resultado">
              <h4>Resultado</h4>
              <div className={`status status-${resultado.status}`}>{resultado.status}</div>
              {resultado.erro && <div className="erro">{resultado.erro}</div>}
              {resultado.passos && (
                <ol className="trace">
                  {resultado.passos.map((p: any, i: number) => (
                    <li key={i}>
                      <code>{p.handle}</code> [{p.tipo}] → {p.status}/{p.branch}
                    </li>
                  ))}
                </ol>
              )}
              {resultado.variaveis && (
                <pre className="vars">{JSON.stringify(resultado.variaveis, null, 2)}</pre>
              )}
            </div>
          )}
        </aside>
      </div>

      {aba === 'execucoes' && <ExecucoesPanel fluxoId={fluxoId} />}

      {editId && (() => {
        const n = nodes.find((x) => x.id === editId)
        if (!n) return null
        const cat = catalogo.find((c) => c.tipo === (n.data as any).tipo)
        return (
          <NodeModal
            node={n}
            campos={cat?.campos ?? []}
            label={cat?.label ?? (n.data as any).tipo}
            icone={cat?.icone ?? 'bi-box'}
            eventos={eventos}
            onConfig={atualizarConfig}
            onClose={() => setEditId(null)}
            onExecutar={async () => await testarFluxo(paraRuntime(nodes, edges))}
          />
        )
      })()}
    </div>
  )
}

const GRUPO_INFO: Record<string, { icone: string; descricao: string; ordem: number }> = {
  Gatilho: { icone: 'bi-lightning-charge', descricao: 'O que inicia o fluxo', ordem: 0 },
  Core: { icone: 'bi-box', descricao: 'HTTP, integrações genéricas', ordem: 1 },
  Fluxo: { icone: 'bi-signpost-split', descricao: 'Condição, espera, ramificação', ordem: 2 },
  'Transformação': { icone: 'bi-pencil-square', descricao: 'Definir e mexer em variáveis', ordem: 3 },
  'Integrações': { icone: 'bi-plug', descricao: 'WhatsApp, ERPs, provedores', ordem: 4 },
  Comercial: { icone: 'bi-briefcase', descricao: 'Tarefas, oportunidades, CRM', ordem: 5 },
  'Notificações': { icone: 'bi-bell', descricao: 'Avisar a equipe', ordem: 6 },
  CS: { icone: 'bi-gift', descricao: 'Clube, pontos, benefícios', ordem: 7 },
}

// Grupos com 3 níveis no picker: grupo → provedor (subgrupo) → ações.
// Pros demais, o picker fica em 2 níveis (grupo → nós).
const TRES_NIVEIS = new Set(['Integrações'])

function NodePanel({
  catalogo, onAdd, onClose,
}: {
  catalogo: NoCatalogo[]
  onAdd: (tipo: string, label: string) => void
  onClose: () => void
}) {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState<string | null>(null)
  const [prov, setProv] = useState<string | null>(null)   // 3º nível: provedor (subgrupo)
  const termo = q.trim().toLowerCase()

  const itemNo = (c: NoCatalogo) => (
    <button key={c.tipo} className="nodepanel-item" onClick={() => onAdd(c.tipo, c.label)}>
      <i className={`bi ${c.icone} ni-icone`} style={{ color: CORES_GRUPO[c.grupo] ?? '#5b6472' }} />
      <span className="ni-text">
        <strong>{c.label}</strong>
        <span className="muted">{c.tipo}</span>
      </span>
    </button>
  )

  // Busca achata tudo (vai direto no nó).
  const filtrados = catalogo.filter(
    (c) => c.label.toLowerCase().includes(termo) || c.tipo.includes(termo),
  )
  // Categorias (grupos) ordenadas — Gatilho primeiro.
  const grupos = Array.from(new Set(catalogo.map((c) => c.grupo)))
    .sort((a, b) => (GRUPO_INFO[a]?.ordem ?? 99) - (GRUPO_INFO[b]?.ordem ?? 99))

  // Grupo de 3 níveis (ex: Integrações) → o subgrupo é um provedor clicável.
  const ehTres = !!cat && TRES_NIVEIS.has(cat)
  const provedores = cat
    ? Array.from(new Set(catalogo.filter((c) => c.grupo === cat).map((c) => c.subgrupo || '—'))).sort()
    : []
  // Grupo de 2 níveis: nós por subgrupo (cabeçalho inline).
  const porSub: Record<string, NoCatalogo[]> = {}
  if (cat && !ehTres) for (const c of catalogo.filter((c) => c.grupo === cat)) {
    (porSub[c.subgrupo || '—'] ??= []).push(c)
  }

  const voltar = () => { if (prov) setProv(null); else setCat(null) }

  return (
    <div className="nodepanel">
      <div className="nodepanel-head">
        {cat && !termo ? (
          <button className="np-voltar" onClick={voltar}>← {prov ? `${cat} › ${prov}` : cat}</button>
        ) : (
          <strong>Adicionar nó</strong>
        )}
        <button className="x" onClick={onClose}>×</button>
      </div>
      <input
        className="nodepanel-search"
        autoFocus
        placeholder="Buscar nós…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="nodepanel-list">
        {catalogo.length === 0 && (
          <div className="muted pad">carregando… (faça login no Django)</div>
        )}

        {/* BUSCA → lista achatada */}
        {!!termo && (filtrados.length ? filtrados.map(itemNo)
          : <div className="muted pad">nada encontrado</div>)}

        {/* SEM BUSCA, SEM CATEGORIA → lista de categorias (drill-in) */}
        {!termo && !cat && grupos.map((g) => {
          const info = GRUPO_INFO[g]
          return (
            <button
              key={g}
              className={`np-cat ${g === 'Gatilho' ? 'np-cat-trigger' : ''}`}
              onClick={() => { setCat(g); setProv(null) }}
            >
              <i className={`bi ${info?.icone ?? 'bi-grid'} np-cat-ic`}
                 style={{ color: CORES_GRUPO[g] ?? '#5b6472' }} />
              <span className="np-cat-txt">
                <strong>{g}</strong>
                <span className="muted">{info?.descricao ?? ''}</span>
              </span>
              <i className="bi bi-chevron-right np-cat-arrow" />
            </button>
          )
        })}

        {/* NÍVEL 2 (3 níveis): provedores do grupo (ex: WhatsApp · Uazapi, HubSoft) */}
        {!termo && cat && ehTres && !prov && provedores.map((p) => (
          <button key={p} className="np-cat" onClick={() => setProv(p)}>
            <i className="bi bi-box-seam np-cat-ic" style={{ color: CORES_GRUPO[cat ?? ''] ?? '#5b6472' }} />
            <span className="np-cat-txt">
              <strong>{p}</strong>
              <span className="muted">
                {catalogo.filter((c) => c.grupo === cat && (c.subgrupo || '—') === p).length} ação(ões)
              </span>
            </span>
            <i className="bi bi-chevron-right np-cat-arrow" />
          </button>
        ))}

        {/* NÍVEL FINAL (3 níveis): nós do provedor escolhido */}
        {!termo && cat && ehTres && prov &&
          catalogo.filter((c) => c.grupo === cat && (c.subgrupo || '—') === prov).map(itemNo)}

        {/* NÍVEL FINAL (2 níveis): nós por subgrupo (cabeçalho inline) */}
        {!termo && cat && !ehTres && Object.entries(porSub).map(([s, list]) => (
          <div key={s} className="nodepanel-subbloco">
            {s !== '—' && <div className="nodepanel-sub">{s}</div>}
            {list.map(itemNo)}
          </div>
        ))}
      </div>
    </div>
  )
}

function ConfigPanel({
  node, onNome, onHandle, onAbrir, onExcluir,
}: {
  node: Node
  onNome: (nome: string) => void
  onHandle: (novo: string) => void
  onAbrir: () => void
  onExcluir: () => void
}) {
  const [nome, setNome] = useState((node.data as any).nome ?? node.id)
  const [handle, setHandle] = useState(node.id)

  return (
    <div className="config">
      <h4>Nó</h4>
      <label>Nome (exibição)</label>
      <input
        value={nome}
        onChange={(e) => { setNome(e.target.value); onNome(e.target.value) }}
        placeholder="Ex: Enviar Typing"
      />
      <label>Handle (referência — {'{{nodes.<handle>}}'})</label>
      <div className="row">
        <input value={handle} onChange={(e) => setHandle(e.target.value)} />
        <button onClick={() => onHandle(handle)}>aplicar</button>
      </div>
      <div className="muted">ref: {'{{nodes.' + node.id + '.…}}'} · tipo: {(node.data as any).tipo}</div>
      <button className="primary editar-btn" onClick={onAbrir}>Editar parâmetros</button>
      <button className="excluir-btn" onClick={onExcluir}>🗑 Excluir nó</button>
    </div>
  )
}
