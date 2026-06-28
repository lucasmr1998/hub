import { useState, useEffect } from 'react'
import type { Node } from '@xyflow/react'
import { buscarOpcoes, buscarAgenteResumo, type Campo, type EventoCatalogo, type Opcao, type AgenteResumo } from './api'

const OPERADORES = [
  'igual', 'diferente', 'contem', 'nao_contem',
  'maior', 'menor', 'maior_igual', 'menor_igual', 'vazio', 'nao_vazio',
]

function _vazio(v: any): boolean {
  return v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)
}

type Form = Record<string, any>

function initForm(config: Form, campos: Campo[]): Form {
  const f: Form = {}
  for (const c of campos) {
    const v = config[c.nome]
    if (c.tipo === 'keyvalue') {
      f[c.nome] = v && typeof v === 'object' && !Array.isArray(v)
        ? Object.entries(v).map(([k, val]) => ({ k, v: String(val) }))
        : []
    } else if (c.tipo === 'lista_campos' || c.tipo === 'filtros' || c.tipo === 'regras') {
      f[c.nome] = Array.isArray(v) ? v : []
    } else if (c.tipo === 'booleano') {
      f[c.nome] = !!v
    } else {
      f[c.nome] = v ?? ''
    }
  }
  return f
}

function formToConfig(form: Form, campos: Campo[]): Form {
  const cfg: Form = {}
  for (const c of campos) {
    const v = form[c.nome]
    if (c.tipo === 'keyvalue') {
      const obj: Form = {}
      for (const row of v || []) if (row.k) obj[row.k] = row.v
      cfg[c.nome] = obj
    } else if (c.tipo === 'lista_campos') {
      cfg[c.nome] = (v || []).filter((r: any) => r.nome)
    } else if (c.tipo === 'filtros') {
      cfg[c.nome] = (v || []).filter((r: any) => r.campo)
    } else if (c.tipo === 'regras') {
      cfg[c.nome] = (v || []).filter((r: any) => (r.saida || '').trim())
    } else if (c.tipo === 'numero') {
      cfg[c.nome] = v === '' ? '' : Number(v)
    } else {
      cfg[c.nome] = v
    }
  }
  return cfg
}

export function NodeModal({
  node, campos, label, icone, eventos, onConfig, onClose, onExecutar, webhookUrl,
}: {
  node: Node
  campos: Campo[]
  label: string
  icone: string
  eventos: EventoCatalogo[]
  onConfig: (cfg: Form) => void
  onClose: () => void
  onExecutar: () => Promise<any>
  webhookUrl?: string
}) {
  const [form, setForm] = useState<Form>(() => initForm((node.data as any).config ?? {}, campos))
  const [saida, setSaida] = useState<any>(null)
  const [rodando, setRodando] = useState(false)

  const atualizar = (nome: string, valor: any) => {
    const nf = { ...form, [nome]: valor }
    setForm(nf)
    onConfig(formToConfig(nf, campos))
  }

  const executar = async () => {
    setRodando(true)
    try {
      setSaida(await onExecutar())
    } finally {
      setRodando(false)
    }
  }

  const meuOutput = saida?.nodes?.[node.id]

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <span className="modal-titulo">
            <i className={`bi ${icone}`} /> {label}
            <code className="modal-handle">{node.id}</code>
          </span>
          <button className="modal-exec" onClick={executar} disabled={rodando}>
            {rodando ? '…' : '▶ Executar nó'}
          </button>
          <button className="modal-x" onClick={onClose}>×</button>
        </header>

        <div className="modal-corpo">
          <section className="modal-io">
            <div className="io-titulo">INPUT</div>
            <pre className="io-json">{saida ? JSON.stringify(saida.variaveis ?? {}, null, 2) : '—'}</pre>
          </section>

          <section className="modal-params">
            <div className="io-titulo">PARÂMETROS</div>
            {(node.data as any).tipo === 'webhook' && <WebhookPanel url={webhookUrl} />}
            {campos.length === 0 && (node.data as any).tipo !== 'webhook' && <div className="muted">Este nó não tem parâmetros.</div>}
            {campos.map((c) => (
              <div key={c.nome} className="campo">
                <label>{c.label}{c.obrigatorio && <span className="req"> *</span>}</label>
                {c.tipo === 'filtros' ? (
                  <FiltrosCampo
                    linhas={form[c.nome] ?? []}
                    subcampos={eventos.find((e) => e.tipo === form.evento)?.subcampos ?? []}
                    onChange={(ls) => atualizar(c.nome, ls)}
                  />
                ) : c.tipo === 'regras' ? (
                  <RegrasCampo
                    linhas={form[c.nome] ?? []}
                    onChange={(ls) => atualizar(c.nome, ls)}
                  />
                ) : (
                  renderCampo(c, form[c.nome], (v) => atualizar(c.nome, v))
                )}
                {c.obrigatorio && _vazio(form[c.nome]) && (
                  <div className="campo-req">obrigatório</div>
                )}
                {c.ajuda && <div className="campo-ajuda">{c.ajuda}</div>}
                {c.detalhe === 'agente' && <AgenteResumoBox agenteId={form[c.nome]} />}
              </div>
            ))}
            <details className="json-adv">
              <summary>config JSON (avançado)</summary>
              <pre className="io-json">{JSON.stringify(formToConfig(form, campos), null, 2)}</pre>
            </details>
          </section>

          <section className="modal-io">
            <div className="io-titulo">OUTPUT</div>
            {!saida && <div className="muted">Clique em "Executar nó".</div>}
            {saida && (
              <>
                <div className={`status status-${saida.status}`}>{saida.status}</div>
                {saida.erro && <div className="erro">{saida.erro}</div>}
                <pre className="io-json">{JSON.stringify(meuOutput ?? {}, null, 2)}</pre>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

function OpcoesSelect({ fonte, value, onChange, placeholder }: {
  fonte: string
  value: any
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [ops, setOps] = useState<Opcao[]>([])
  const [carregando, setCarregando] = useState(true)
  useEffect(() => {
    let vivo = true
    buscarOpcoes(fonte)
      .then((o) => { if (vivo) setOps(o) })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [fonte])
  return (
    <select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
      <option value="">{carregando ? 'carregando…' : (placeholder || '— selecione —')}</option>
      {value && !ops.some((o) => o.value === value) && <option value={value}>{value}</option>}
      {ops.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

function AgenteResumoBox({ agenteId }: { agenteId: any }) {
  const id = String(agenteId ?? '').trim()
  const [dados, setDados] = useState<AgenteResumo | null>(null)
  const [carregando, setCarregando] = useState(false)
  useEffect(() => {
    if (!id) { setDados(null); return }
    let vivo = true
    setCarregando(true)
    buscarAgenteResumo(id)
      .then((d) => { if (vivo) setDados(d) })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [id])
  if (!id) return null
  if (carregando) return <div className="agente-resumo muted">carregando agente…</div>
  if (!dados) return null
  return (
    <div className="agente-resumo">
      <div className="ar-meta">Modelo: <b>{dados.modelo}</b>{dados.integracao ? ` · ${dados.integracao}` : ''}</div>
      <div className="ar-tit">System prompt</div>
      <pre className="ar-prompt">{dados.system_prompt || '(vazio)'}</pre>
      <div className="ar-tit">Ferramentas ativas{dados.tools.length ? ` (${dados.tools.length})` : ''}</div>
      {dados.tools.length === 0
        ? <div className="muted">nenhuma — o agente só conversa</div>
        : dados.tools.map((t) => (
            <div key={t.chave} className="ar-tool"><b>{t.chave}</b> — {t.descricao}</div>
          ))}
      <div className="ar-tit">Base de conhecimento</div>
      <div className="ar-tool">{dados.base_categorias.length ? dados.base_categorias.join(', ') : 'base inteira do tenant'}</div>
      <div className="ar-rodape">Editar em <a href="/automacao/agentes/" target="_blank" rel="noreferrer">/automacao/agentes/</a></div>
    </div>
  )
}

function WebhookPanel({ url }: { url?: string }) {
  const [copiado, setCopiado] = useState(false)
  const path = url ? (url.split('/automacao/webhook/')[1] ?? '').replace(/\/$/, '') : ''
  const copiar = () => {
    if (!url) return
    navigator.clipboard?.writeText(url)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 1500)
  }
  return (
    <div className="wh-panel">
      <div className="wh-tit">URL do Webhook</div>
      {url ? (
        <div className="wh-row">
          <span className="wh-met">POST</span>
          <input className="wh-url" readOnly value={url} onFocus={(e) => e.currentTarget.select()} />
          <button className="wh-copy" onClick={copiar}>{copiado ? '✓ copiado' : 'copiar'}</button>
        </div>
      ) : (
        <div className="muted">Salve o fluxo (💾) pra gerar a URL.</div>
      )}
      <div className="wh-meta">Método <b>POST</b>{path ? <> · Path <code>{path}</code></> : null}</div>
      <div className="wh-meta muted">Um POST nessa URL inicia o fluxo. O corpo JSON vira <code>{'{{var.payload}}'}</code>.</div>
    </div>
  )
}

function renderCampo(c: Campo, valor: any, set: (v: any) => void) {
  if (c.fonte) {
    return <OpcoesSelect fonte={c.fonte} value={valor} onChange={set} placeholder={c.placeholder} />
  }
  if (c.tipo === 'select') {
    return (
      <select value={valor ?? ''} onChange={(e) => set(e.target.value)}>
        <option value="">—</option>
        {(c.opcoes ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    )
  }
  if (c.tipo === 'booleano') {
    return <input type="checkbox" checked={!!valor} onChange={(e) => set(e.target.checked)} />
  }
  if (c.tipo === 'numero') {
    return <input type="number" value={valor ?? ''} onChange={(e) => set(e.target.value)} />
  }
  if (c.tipo === 'textarea') {
    return (
      <textarea className="mono" rows={4} placeholder={c.placeholder} spellCheck={false}
        value={valor ?? ''} onChange={(e) => set(e.target.value)} />
    )
  }
  if (c.tipo === 'lista_campos') {
    const linhas: any[] = valor ?? []
    const set_ = (ls: any[]) => set(ls)
    return (
      <div className="repeater">
        {linhas.map((row, i) => (
          <div key={i} className="repeater-row">
            <input placeholder="nome" value={row.nome ?? ''}
              onChange={(e) => set_(linhas.map((r, j) => j === i ? { ...r, nome: e.target.value } : r))} />
            <input className="mono" placeholder="valor / {{expr}}" value={row.valor ?? ''}
              onChange={(e) => set_(linhas.map((r, j) => j === i ? { ...r, valor: e.target.value } : r))} />
            <button onClick={() => set_(linhas.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <button className="repeater-add" onClick={() => set_([...linhas, { nome: '', valor: '' }])}>+ campo</button>
      </div>
    )
  }
  if (c.tipo === 'keyvalue') {
    const linhas: any[] = valor ?? []
    const set_ = (ls: any[]) => set(ls)
    return (
      <div className="repeater">
        {linhas.map((row, i) => (
          <div key={i} className="repeater-row">
            <input placeholder="chave" value={row.k ?? ''}
              onChange={(e) => set_(linhas.map((r, j) => j === i ? { ...r, k: e.target.value } : r))} />
            <input className="mono" placeholder="valor / {{expr}}" value={row.v ?? ''}
              onChange={(e) => set_(linhas.map((r, j) => j === i ? { ...r, v: e.target.value } : r))} />
            <button onClick={() => set_(linhas.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <button className="repeater-add" onClick={() => set_([...linhas, { k: '', v: '' }])}>+ item</button>
      </div>
    )
  }
  // texto (default) — aceita expressões {{ }}
  return (
    <input className="mono" placeholder={c.placeholder} value={valor ?? ''}
      onChange={(e) => set(e.target.value)} />
  )
}

function FiltrosCampo({
  linhas, subcampos, onChange,
}: {
  linhas: any[]
  subcampos: Campo[]
  onChange: (ls: any[]) => void
}) {
  const set = (i: number, patch: any) =>
    onChange(linhas.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  return (
    <div className="repeater">
      {linhas.length === 0 && <div className="muted">Sem filtros — dispara sempre que o evento ocorre.</div>}
      {linhas.map((row, i) => {
        const sc = subcampos.find((s) => s.nome === row.campo)
        return (
        <div key={i} className="filtro-row">
          {subcampos.length > 0 ? (
            <select value={row.campo ?? ''} onChange={(e) => set(i, { campo: e.target.value, valor: '', operador: 'igual' })}>
              <option value="">campo…</option>
              {subcampos.map((s) => <option key={s.nome} value={s.nome}>{s.label}</option>)}
            </select>
          ) : (
            <input placeholder="campo" value={row.campo ?? ''} onChange={(e) => set(i, { campo: e.target.value })} />
          )}
          <select value={row.operador ?? 'igual'} onChange={(e) => set(i, { operador: e.target.value })}>
            {(sc?.fonte ? ['igual', 'diferente'] : OPERADORES).map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          {sc?.fonte ? (
            <OpcoesSelect fonte={sc.fonte} value={row.valor}
              onChange={(v) => set(i, { valor: v })} placeholder="valor" />
          ) : (
            <input className="mono" placeholder="valor" value={row.valor ?? ''}
              onChange={(e) => set(i, { valor: e.target.value })} />
          )}
          <button onClick={() => onChange(linhas.filter((_, j) => j !== i))}>×</button>
        </div>
        )
      })}
      <button className="repeater-add"
        onClick={() => onChange([...linhas, { campo: '', operador: 'igual', valor: '' }])}>
        + filtro
      </button>
    </div>
  )
}

// Regras do switch (modelo n8n): cada linha = esquerda [operador] direita → nome da saída.
// As saídas do nó (portas) vêm dos nomes das regras (saídas dinâmicas).
function RegrasCampo({
  linhas, onChange,
}: {
  linhas: any[]
  onChange: (ls: any[]) => void
}) {
  const set = (i: number, patch: any) =>
    onChange(linhas.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const semValor = (op: string) => op === 'vazio' || op === 'nao_vazio'
  return (
    <div className="repeater">
      {linhas.length === 0 && <div className="muted">Sem regras — tudo segue por "default".</div>}
      {linhas.map((row, i) => (
        <div key={i} className="filtro-row">
          <input className="mono" placeholder="{{valor}}" value={row.esquerda ?? ''}
            onChange={(e) => set(i, { esquerda: e.target.value })} />
          <select value={row.operador ?? 'igual'} onChange={(e) => set(i, { operador: e.target.value })}>
            {OPERADORES.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          {!semValor(row.operador ?? 'igual') && (
            <input className="mono" placeholder="comparar" value={row.direita ?? ''}
              onChange={(e) => set(i, { direita: e.target.value })} />
          )}
          <input placeholder="→ saída (ex: bug)" value={row.saida ?? ''}
            onChange={(e) => set(i, { saida: e.target.value })} />
          <button onClick={() => onChange(linhas.filter((_, j) => j !== i))}>×</button>
        </div>
      ))}
      <button className="repeater-add"
        onClick={() => onChange([...linhas, { esquerda: '', operador: 'igual', direita: '', saida: '' }])}>
        + regra
      </button>
    </div>
  )
}
