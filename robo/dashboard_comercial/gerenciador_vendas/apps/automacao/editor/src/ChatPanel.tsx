import { useState } from 'react'
import { chatTestar } from './api'
import type { RuntimeFluxo } from './flow'

type Turn = { de: 'user' | 'bot'; texto: string; trace?: any[]; status?: string }

// Resposta do bot = a última `resposta` de um nó Agente IA no caminho executado.
// (o classificador também devolve `resposta`, mas a última do caminho é a do especialista.)
function extrairResposta(res: any): { texto: string; trace: any[]; status: string } {
  const passos = res?.passos ?? []
  const nodes = res?.nodes ?? {}
  let texto = ''
  for (const p of passos) {
    const out = nodes[p.handle]
    if (out && typeof out.resposta === 'string' && out.resposta.trim()) texto = out.resposta
  }
  if (!texto) {
    texto = res?.erro
      ? `⚠ ${res.erro}`
      : `(fluxo terminou: ${res?.status ?? '—'} — nenhum agente respondeu)`
  }
  return { texto, trace: passos, status: res?.status ?? '—' }
}

export function ChatPanel({
  getFluxo, onRun, onClose,
}: {
  getFluxo: () => RuntimeFluxo
  onRun?: (res: any, mensagem: string) => void
  onClose: () => void
}) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [rodando, setRodando] = useState(false)

  const enviar = async () => {
    const msg = input.trim()
    if (!msg || rodando) return
    // conversa até aqui (antes desta msg) = a memória que vai pros agentes
    const turnos = turns.map((t) => ({ role: t.de === 'user' ? 'user' : 'assistant', content: t.texto }))
    setInput('')
    setTurns((t) => [...t, { de: 'user', texto: msg }])
    setRodando(true)
    try {
      const res = await chatTestar(getFluxo(), msg, turnos)
      const { texto, trace, status } = extrairResposta(res)
      setTurns((t) => [...t, { de: 'bot', texto, trace, status }])
      onRun?.(res, msg)  // estilo n8n: pinta o caminho verde + alimenta o INPUT dos nós
    } catch (e: any) {
      setTurns((t) => [...t, { de: 'bot', texto: `⚠ ${String(e)}`, status: 'erro' }])
    } finally {
      setRodando(false)
    }
  }

  return (
    <div className="chat-painel">
      <header className="chat-head">
        <span><i className="bi bi-chat-dots" /> Chat de teste</span>
        <div className="chat-head-acoes">
          <button onClick={() => setTurns([])} title="Limpar conversa">🗑</button>
          <button onClick={onClose} title="Fechar">×</button>
        </div>
      </header>
      <div className="chat-msgs">
        {turns.length === 0 && (
          <div className="muted">Digite uma mensagem — ela roda o fluxo como <code>{'{{var.conteudo}}'}</code>.</div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`chat-msg chat-${t.de}`}>
            <div className="chat-bolha">{t.texto}</div>
            {t.de === 'bot' && t.trace && t.trace.length > 0 && (
              <details className="chat-trace">
                <summary>trace · {t.status}</summary>
                <ol>
                  {t.trace.map((p: any, j: number) => (
                    <li key={j}><code>{p.handle}</code> [{p.tipo}] → {p.status}/{p.branch ?? '—'}</li>
                  ))}
                </ol>
              </details>
            )}
          </div>
        ))}
        {rodando && <div className="chat-msg chat-bot"><div className="chat-bolha chat-typing">…</div></div>}
      </div>
      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') enviar() }}
          placeholder="Mensagem de teste…"
          disabled={rodando}
        />
        <button onClick={enviar} disabled={rodando || !input.trim()}>➤</button>
      </div>
    </div>
  )
}
