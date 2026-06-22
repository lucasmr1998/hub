import type { Edge, Node } from '@xyflow/react'

// Saídas (branches) por tipo de nó — preenchido pelo App a partir do catálogo
// (cada nó declara suas saídas no backend). Nada hardcoded aqui.
export const SAIDAS: Record<string, string[]> = {}

export function saidasDe(tipo: string): string[] {
  return SAIDAS[tipo] ?? ['sucesso']
}

// Handle seguro pra referência ({{nodes.<handle>}}): sem espaço/acento/símbolo.
export function slug(s: string): string {
  const r = (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return r || 'no'
}

// Mapas preenchidos pelo App ao carregar o catálogo.
export const ICONES: Record<string, string> = {}   // tipo → ícone (bi-*)
export const GRUPOS: Record<string, string> = {}    // tipo → grupo (categoria do menu)
export const TRIGGERS: Record<string, boolean> = {} // tipo → é gatilho (sem porta de entrada)

export function ehTrigger(tipo: string): boolean {
  return !!TRIGGERS[tipo]
}

// Cor por categoria (grupo). Gatilho/Fim ficam pra quando existir o nó de trigger.
export const CORES_GRUPO: Record<string, string> = {
  Core: '#2f6df6',          // azul
  Fluxo: '#7c3aed',         // roxo
  'Transformação': '#0d9488', // verde-água
  Gatilho: '#ea580c',       // laranja
  'Integrações': '#16a34a', // verde (provedores: WhatsApp, ERPs)
  Comercial: '#c2410c',     // âmbar/CRM
  'Notificações': '#0891b2', // ciano
  CS: '#db2777',            // rosa (clube/benefícios)
}

export function corDoTipo(tipo: string): string {
  return CORES_GRUPO[GRUPOS[tipo]] ?? '#5b6472'
}

export interface RuntimeFluxo {
  inicio: string
  nodes: Record<string, { tipo: string; config: unknown; pos?: unknown; nome?: string }>
  conexoes: { de: string; para: string; saida: string }[]
}

// Converte o grafo do React Flow no JSON que o runtime (executar_fluxo) consome.
// Guarda `pos`/`nome` por nó (o runtime ignora) pra preservar layout/exibição.
export function paraRuntime(nodes: Node[], edges: Edge[]): RuntimeFluxo {
  const runtimeNodes: RuntimeFluxo['nodes'] = {}
  for (const n of nodes) {
    const d = n.data as { tipo: string; config?: unknown; nome?: string }
    runtimeNodes[n.id] = { tipo: d.tipo, config: d.config ?? {}, pos: n.position, nome: d.nome }
  }
  const conexoes = edges.map((e) => ({
    de: e.source,
    para: e.target,
    saida: e.sourceHandle ?? 'sucesso',
  }))
  const alvos = new Set(edges.map((e) => e.target))
  const raiz = nodes.find((n) => !alvos.has(n.id))
  return {
    inicio: raiz?.id ?? nodes[0]?.id ?? '',
    nodes: runtimeNodes,
    conexoes,
  }
}

// Inverso: grafo persistido → nós/arestas do React Flow.
export function deRuntime(grafo: any): { nodes: Node[]; edges: Edge[] } {
  const entradas = Object.entries(grafo?.nodes ?? {})
  const nodes: Node[] = entradas.map(([id, def]: [string, any], i) => ({
    id,
    type: 'bloco',
    position: def?.pos ?? { x: 150 + (i % 4) * 220, y: 90 + Math.floor(i / 4) * 140 },
    data: { tipo: def?.tipo, nome: def?.nome ?? def?.label ?? id, config: def?.config ?? {} },
  }))
  const edges: Edge[] = (grafo?.conexoes ?? []).map((c: any, i: number) => ({
    id: `e_${i}_${c.de}_${c.para}`,
    source: c.de,
    target: c.para,
    sourceHandle: c.saida,
    label: c.saida,
  }))
  return { nodes, edges }
}
