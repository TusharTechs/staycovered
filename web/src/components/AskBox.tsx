import { useState } from 'react'
import { api, fmtDate, type Grounded } from '../api'
import { Cite, Spinner } from './ui'

export default function AskBox({ asOf, suggestions = [], compare = false, jurisdiction = 'NE' }: { asOf: string; suggestions?: string[]; compare?: boolean; jurisdiction?: string }) {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<{ grounded: Grounded; closed_book?: string } | null>(null)
  const [err, setErr] = useState('')
  const [plain, setPlain] = useState(false)

  const ask = async (question: string) => {
    setQ(question); setBusy(true); setErr(''); setRes(null)
    try { setRes(await api.ask(question, asOf, compare, jurisdiction)) } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={e => { e.preventDefault(); if (q.trim()) ask(q.trim()) }} className="flex gap-2">
        <label className="sr-only" htmlFor="ask">Question</label>
        <input id="ask" value={q} onChange={e => setQ(e.target.value)} placeholder="Ask about the rules…"
          className="flex-1 rounded-lg border border-line px-3 py-2 text-sm" />
        <button disabled={busy} className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Ask</button>
      </form>
      {suggestions.length > 0 && !res && !busy && (
        <div className="flex flex-wrap gap-2">{suggestions.map(s => (
          <button key={s} onClick={() => ask(s)} className="rounded-full border border-line bg-paper px-3 py-1 text-xs hover:border-brand">{s}</button>
        ))}</div>
      )}
      <div aria-live="polite" aria-atomic="false">
      {busy && <Spinner label="Reading the official sources" />}
      {err && <p role="alert" className="text-bad text-sm">{err}</p>}
      {res && (
        <div className={`grid gap-3 ${res.closed_book !== undefined ? 'md:grid-cols-2' : ''}`}>
          {res.closed_book !== undefined && (
            <div className="rounded-xl border border-line bg-paper p-3">
              <div className="text-xs font-semibold text-frozen uppercase tracking-wide">Frozen model · no sources</div>
              <p className="mt-2 text-sm whitespace-pre-wrap text-ink/80">{res.closed_book.replace(/<think>[\s\S]*?<\/think>/g, '').trim()}</p>
            </div>
          )}
          <div className="rounded-xl border border-brand/30 bg-brand-soft/40 p-3">
            <div className="flex items-center gap-2">
              <div className="text-xs font-semibold text-brand uppercase tracking-wide">StayCovered · rules as of {fmtDate(res.grounded.as_of)}</div>
              <button onClick={() => setPlain(p => !p)} className="ml-auto text-[11px] text-brand underline">{plain ? 'Navigator view' : 'Client-friendly'}</button>
            </div>
            {res.grounded.unsupported && <p className="mt-2 text-xs text-warn font-medium">The official sources available on this date don't settle this.</p>}
            <p className="mt-2 text-sm">{plain ? res.grounded.plain_language : res.grounded.answer}</p>
            {res.grounded.citations.length > 0 && (
              <div className="mt-2 text-xs text-muted">Sources:{res.grounded.citations.map((c, i) => <Cite key={i} sourceId={c.source_id} quote={c.quote} label={`${c.title.slice(0, 40)} (${c.as_of})`} />)}</div>
            )}
            {res.grounded.dropped_citations > 0 && <p className="mt-1 text-[11px] text-muted">{res.grounded.dropped_citations} citation(s) removed because the quote was not found verbatim in the source.</p>}
            {res.grounded.confirm_with_agency && <p className="mt-2 text-[11px] text-muted">Confirm with {jurisdiction === 'MT' ? 'Montana DPHHS' : 'Nebraska DHHS'} before acting.</p>}
          </div>
        </div>
      )}
      </div>
    </div>
  )
}
