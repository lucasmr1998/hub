function csrftoken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

function headersJSON(): Record<string, string> {
  return { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken() }
}

export interface Campo {
  nome: string
  label: string
  tipo: string
  opcoes?: string[]
  placeholder?: string
  ajuda?: string
  obrigatorio?: boolean
}

export interface NoCatalogo {
  tipo: string
  label: string
  icone: string
  grupo: string
  subgrupo: string
  categoria: string
  saidas: string[]
  is_trigger: boolean
  campos: Campo[]
}

export async function buscarCatalogo(): Promise<NoCatalogo[]> {
  const r = await fetch('/automacao/api/nodes/', { credentials: 'include' })
  if (!r.ok) throw new Error('catálogo HTTP ' + r.status)
  return (await r.json()).nodes
}

export interface EventoCatalogo {
  tipo: string
  label: string
  grupo: string
  descricao: string
  subcampos: Campo[]
}

export async function buscarEventos(): Promise<EventoCatalogo[]> {
  const r = await fetch('/automacao/api/eventos/', { credentials: 'include' })
  if (!r.ok) throw new Error('eventos HTTP ' + r.status)
  return (await r.json()).eventos
}

export async function testarFluxo(fluxo: unknown): Promise<unknown> {
  const r = await fetch('/automacao/api/testar-fluxo/', {
    method: 'POST',
    headers: headersJSON(),
    credentials: 'include',
    body: JSON.stringify({ fluxo }),
  })
  return r.json()
}

export interface FluxoResumo {
  id: number
  nome: string
  ativo: boolean
  atualizado_em: string
}

export async function listarFluxos(): Promise<FluxoResumo[]> {
  const r = await fetch('/automacao/api/fluxos/', { credentials: 'include' })
  if (!r.ok) throw new Error('fluxos HTTP ' + r.status)
  return (await r.json()).fluxos
}

export async function getFluxo(
  id: number,
): Promise<{ id: number; nome: string; grafo: any; webhook_token: string }> {
  const r = await fetch(`/automacao/api/fluxos/${id}/`, { credentials: 'include' })
  return r.json()
}

export async function ativarWebhook(id: number): Promise<{ webhook_token: string; url: string }> {
  const r = await fetch(`/automacao/api/fluxos/${id}/webhook/`, {
    method: 'POST',
    headers: headersJSON(),
    credentials: 'include',
  })
  return r.json()
}

interface SalvarResp { id: number; nome: string; webhook_token: string }

export async function criarFluxo(nome: string, grafo: unknown): Promise<SalvarResp> {
  const r = await fetch('/automacao/api/fluxos/', {
    method: 'POST',
    headers: headersJSON(),
    credentials: 'include',
    body: JSON.stringify({ nome, grafo }),
  })
  return r.json()
}

export async function atualizarFluxo(id: number, nome: string, grafo: unknown): Promise<SalvarResp> {
  const r = await fetch(`/automacao/api/fluxos/${id}/`, {
    method: 'PUT',
    headers: headersJSON(),
    credentials: 'include',
    body: JSON.stringify({ nome, grafo }),
  })
  return r.json()
}

export interface PassoTrace {
  handle: string
  tipo: string
  status: string
  branch: string | null
  erro?: string | null
}

export interface ExecucaoResumo {
  id: number
  fluxo: string
  fluxo_id: number
  status: string
  quando: string
  erro: string
  trace: PassoTrace[]
}

export async function listarExecucoes(fluxoId?: number | null, status?: string): Promise<ExecucaoResumo[]> {
  const p = new URLSearchParams()
  if (fluxoId) p.set('fluxo', String(fluxoId))
  if (status) p.set('status', status)
  const r = await fetch('/automacao/api/execucoes/?' + p.toString(), { credentials: 'include' })
  if (!r.ok) throw new Error('execuções HTTP ' + r.status)
  return (await r.json()).execucoes
}
