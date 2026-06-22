import { useEffect, useState } from 'react'
import { listarExecucoes, type ExecucaoResumo } from './api'

const STATUS = ['', 'pendente', 'rodando', 'aguardando', 'completado', 'erro']

function corStatus(s: string): string {
  if (s === 'completado') return '#1d7a43'
  if (s === 'erro') return '#c0322b'
  if (s === 'aguardando' || s === 'pendente') return '#9a6700'
  return '#5b6472'
}

export default function ExecucoesPanel({ fluxoId }: { fluxoId: number | null }) {
  const [execs, setExecs] = useState<ExecucaoResumo[]>([])
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState('')
  const [status, setStatus] = useState('')
  const [soDoFluxo, setSoDoFluxo] = useState<boolean>(fluxoId != null)
  const [aberta, setAberta] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    setErro('')
    listarExecucoes(soDoFluxo ? fluxoId : null, status)
      .then(setExecs)
      .catch((e) => setErro(String(e)))
      .finally(() => setLoading(false))
  }, [status, soDoFluxo, fluxoId])

  return (
    <div className="exec-panel">
      <div className="exec-bar">
        {fluxoId != null && (
          <label className="exec-toggle">
            <input type="checkbox" checked={soDoFluxo} onChange={(e) => setSoDoFluxo(e.target.checked)} />
            só deste fluxo
          </label>
        )}
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS.map((s) => <option key={s} value={s}>{s || 'todos os status'}</option>)}
        </select>
        <button onClick={() => { setLoading(true); listarExecucoes(soDoFluxo ? fluxoId : null, status).then(setExecs).catch((e) => setErro(String(e))).finally(() => setLoading(false)) }}>↻ Atualizar</button>
        <span className="exec-count">{execs.length} execução(ões)</span>
      </div>

      {loading && <div className="muted pad">carregando…</div>}
      {erro && <div className="erro pad">{erro}</div>}
      {!loading && !erro && execs.length === 0 && (
        <div className="muted pad">
          Nenhuma execução ainda. Quando um fluxo rodar (gatilho, webhook ou cron) ele aparece aqui.
          O "Testar" não persiste.
        </div>
      )}

      <div className="exec-lista">
        {execs.map((e) => (
          <div key={e.id} className="exec-item">
            <div className="exec-item-head" onClick={() => setAberta(aberta === e.id ? null : e.id)}>
              <span className="exec-badge" style={{ background: corStatus(e.status) }}>{e.status}</span>
              <span className="exec-fluxo">{e.fluxo}</span>
              <span className="exec-quando">{e.quando}</span>
              <span className="exec-passos">{e.trace.length} passo(s)</span>
              <span className="exec-chevron">{aberta === e.id ? '▾' : '▸'}</span>
            </div>
            {aberta === e.id && (
              <div className="exec-detalhe">
                {e.erro && <div className="erro">{e.erro}</div>}
                {e.trace.length === 0 && <div className="muted">sem passos registrados</div>}
                <ol>
                  {e.trace.map((p, i) => (
                    <li key={i}>
                      <code>{p.handle}</code> · {p.tipo} → {p.branch || '—'}
                      {p.status === 'erro' && <span style={{ color: '#c0322b' }}> (erro)</span>}
                      {p.erro && <div className="muted">{p.erro}</div>}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
