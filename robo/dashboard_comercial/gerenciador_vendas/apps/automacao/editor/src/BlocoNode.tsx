import { Fragment, useEffect } from 'react'
import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react'
import { saidasDeNo, ICONES, corDoTipo, ehTrigger } from './flow'

// Resumo curto mostrado embaixo do nome (estilo n8n: "POST: url", "5 minutos"...).
function resumo(tipo: string, config: any): string {
  config = config || {}
  if (tipo === 'http_request') return `${config.metodo || 'GET'}: ${config.url || ''}`
  if (tipo === 'if') return [config.esquerda, config.operador, config.direita].filter(Boolean).join(' ')
  if (tipo === 'delay') return config.valor ? `${config.valor} ${config.unidade || 'min'}` : ''
  if (tipo === 'set_fields') {
    const n = (config.campos || []).length || (config.campo ? 1 : 0)
    return n ? `${n} campo${n > 1 ? 's' : ''}` : ''
  }
  return ''
}

function corLabel(s: string): string {
  if (s === 'true' || s === 'sucesso') return '#1d7a43'
  if (s === 'false' || s === 'erro') return '#c0322b'
  return '#5b6472'
}

// Nó estilo n8n: card só com o ícone; nome + subtítulo embaixo; saídas na borda
// direita com rótulo do lado de fora (não competem mais com o título).
export function BlocoNode({ id, data, selected }: NodeProps) {
  const d = data as { tipo: string; nome?: string; config?: any }
  const saidas = saidasDeNo(d.tipo, d.config)
  // Saídas dinâmicas (switch): quando os casos mudam, reposiciona as portas/arestas.
  const updateInternals = useUpdateNodeInternals()
  useEffect(() => { updateInternals(id) }, [id, saidas.join('|'), updateInternals])
  const icone = ICONES[d.tipo] || 'bi-box'
  const cor = corDoTipo(d.tipo)
  const sub = resumo(d.tipo, d.config)
  const nome = d.nome || id
  const trigger = ehTrigger(d.tipo)

  return (
    <div className="bloco-wrap">
      <div className={`bloco-card ${selected ? 'sel' : ''} ${trigger ? 'trigger' : ''}`}>
        {!trigger && <Handle type="target" position={Position.Left} />}
        <i className={`bi ${icone}`} style={{ color: cor }} />
        {saidas.map((s, i) => {
          const top = `${((i + 1) / (saidas.length + 1)) * 100}%`
          return (
            <Fragment key={s}>
              <Handle id={s} type="source" position={Position.Right}
                className={`saida saida-${s}`} style={{ top }} />
              {saidas.length > 1 && (
                <span className="porta-label" style={{ top, color: corLabel(s) }}>{s}</span>
              )}
            </Fragment>
          )
        })}
      </div>
      <div className="bloco-rotulo">
        <div className="bloco-nome" title={`${nome} · ${id}`}>{nome}</div>
        {sub && <div className="bloco-sub" title={sub}>{sub}</div>}
      </div>
    </div>
  )
}
