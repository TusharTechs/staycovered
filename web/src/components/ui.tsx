import { useState, type ReactNode } from 'react'
import { api, fmtDate } from '../api'

export function Card({ title, children, actions, className = '', tour }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string; tour?: string }) {
  return (
    <section data-tour={tour} className={`bg-white border border-line rounded-xl ${className}`}>
      {(title || actions) && (
        <div className="flex items-center gap-3 px-4 pt-3 pb-2">
          {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          <div className="ml-auto">{actions}</div>
        </div>
      )}
      <div className="px-4 pb-4">{children}</div>
    </section>
  )
}

const statusStyle: Record<string, string> = {
  meets: 'bg-ok-soft text-ok',
  does_not_meet: 'bg-bad-soft text-bad',
  at_risk: 'bg-bad-soft text-bad',
  insufficient_evidence: 'bg-warn-soft text-warn',
  conditional: 'bg-warn-soft text-warn',
}
const statusLabel: Record<string, string> = {
  meets: 'Meets', does_not_meet: 'Short', at_risk: 'At risk', insufficient_evidence: 'Needs evidence', conditional: 'Conditional',
}

export function StatusPill({ status }: { status: string }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusStyle[status] ?? 'bg-paper text-muted'}`}>{statusLabel[status] ?? status}</span>
}

export function Cite({ sourceId, quote, label }: { sourceId: string; quote: string; label?: string }) {
  const [open, setOpen] = useState(false)
  const [ctx, setCtx] = useState<{ context: string; title: string; url: string; as_of: string } | null>(null)
  const [err, setErr] = useState('')
  const toggle = async () => {
    setOpen(o => !o)
    if (!ctx && !err) {
      try { setCtx(await api.locate(sourceId, quote)) } catch { setErr('Quote not found in the captured source') }
    }
  }
  return (
    <span className="inline">
      <button type="button" onClick={toggle} aria-expanded={open}
        className="ml-1 inline-flex items-center gap-1 rounded border border-line bg-paper px-1.5 py-0 text-[11px] text-brand hover:border-brand align-baseline">
        <svg viewBox="0 0 16 16" className="h-3 w-3" aria-hidden="true"><path fill="currentColor" d="M3 2h7l3 3v9H3zM10 2v3h3" opacity=".9" /></svg>
        {label ?? sourceId}
      </button>
      {open && (
        <span role="note" className="block mt-1 mb-2 rounded-lg border border-line bg-paper p-3 text-xs text-ink">
          {err && <span className="text-bad">{err}</span>}
          {ctx && (
            <>
              <span className="block font-medium">{ctx.title} <span className="text-muted font-normal">· as of {fmtDate(ctx.as_of)}</span></span>
              <span className="block mt-1 leading-relaxed">{highlight(ctx.context, quote)}</span>
              <a className="mt-1 inline-block text-brand underline" href={ctx.url} target="_blank" rel="noreferrer">Open official source ↗</a>
            </>
          )}
          {!ctx && !err && 'Loading…'}
        </span>
      )}
    </span>
  )
}

function norm(s: string) { return s.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/\s+/g, ' ').trim() }

function highlight(context: string, quote: string) {
  const q = norm(quote)
  const i = context.indexOf(q)
  if (i < 0) return context
  return <>…{context.slice(0, i)}<mark className="cite">{q}</mark>{context.slice(i + q.length)}…</>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{children}</div>
}

export function Spinner({ label = 'Working' }: { label?: string }) {
  return <span role="status" className="inline-flex items-center gap-2 text-sm text-muted"><span className="h-3 w-3 animate-spin rounded-full border-2 border-brand border-t-transparent" />{label}…</span>
}
