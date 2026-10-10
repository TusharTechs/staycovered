import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, monthLabel, type CaseloadForecast, type Forecast, type Nearby, type PathOpt, type Plan, type Status } from '../api'
import { Card, Spinner, StatusPill } from './ui'

export const CELL: Record<string, string> = {
  meets: 'bg-ok', conditional: 'bg-warn', does_not_meet: 'bg-bad', insufficient_evidence: 'bg-line',
}
const WORD: Record<string, string> = {
  meets: 'meets', conditional: 'conditional', does_not_meet: 'falls short', insufficient_evidence: 'no evidence',
}
const EFFORT: Record<number, string> = { 1: 'One question', 2: 'One document', 3: 'New activity' }

export function Strip({ months, size = 'lg', changes, words = WORD, locale = 'en-US' }: { months: { month: string; status: Status }[]; size?: 'lg' | 'sm'; changes?: Set<string>; words?: Record<string, string>; locale?: string }) {
  return (
    <ol className="flex gap-1" aria-label="Month-by-month outlook">
      {months.map((m, i) => {
        const yearStart = i > 0 && m.month.endsWith('-01')
        return (
          <li key={m.month} className={`flex-1 min-w-0 ${yearStart ? 'ml-1.5' : ''}`}>
            {size === 'lg' && <div className={`h-3 text-center text-[11px] leading-3 ${changes?.has(m.month) ? 'text-brand' : 'text-transparent'}`} aria-hidden="true">◆</div>}
            <div className={`${CELL[m.status]} ${size === 'lg' ? 'h-8 rounded-md' : 'h-5 rounded'} ${m.status === 'insufficient_evidence' ? 'bg-[repeating-linear-gradient(45deg,#dfe5ea,#dfe5ea_3px,#f7f8f6_3px,#f7f8f6_6px)]' : ''}`}
              title={`${monthLabel(m.month)}: ${words[m.status]}`}>
              <span className="sr-only">{new Date(m.month + '-01T00:00:00').toLocaleDateString(locale, { month: 'long', year: 'numeric' })}: {words[m.status]}{changes?.has(m.month) ? ` (${words.change ?? 'rules change'})` : ''}</span>
            </div>
            {size === 'lg' && (
              <div className="mt-1 text-center text-[10px] text-muted" aria-hidden="true">
                {new Date(m.month + '-01T00:00:00').toLocaleDateString(locale, { month: 'narrow' })}
                {(i === 0 || yearStart) && <span className="block text-[9px]">{m.month.slice(0, 4)}</span>}
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-3 text-[11px] text-muted">
      {(['meets', 'conditional', 'does_not_meet'] as const).map(s => (
        <span key={s} className="inline-flex items-center gap-1"><span className={`h-2.5 w-2.5 rounded-sm ${CELL[s]}`} aria-hidden="true" />{WORD[s]}</span>
      ))}
      <span className="inline-flex items-center gap-1"><span className="text-brand" aria-hidden="true">◆</span>rules change</span>
    </div>
  )
}

export function ForecastCard({ f, caseId }: { f: Forecast; caseId: string }) {
  const changeMonths = new Set(f.months.filter(m => m.changes.length).map(m => m.month))
  return (
    <Card tour="forecast" title="Coverage forecast · same life, changing rules"
      actions={<a href={`/api/cases/${caseId}/reminders.ics`} className="text-xs text-brand hover:underline">Add reminders to calendar (.ics)</a>}>
      {!f.pattern_month ? (
        <p className="text-sm text-muted">{f.headline}</p>
      ) : (
        <div className="space-y-3">
          <p className="font-serif text-lg leading-snug">{f.headline}</p>
          <Strip months={f.months} changes={changeMonths} />
          <Legend />
          {f.months.filter(m => m.changes.length).map(m => (
            <div key={m.month} className="rounded-lg border border-brand/25 bg-brand-soft/50 p-3 text-sm">
              <div className="font-medium text-brand">◆ {monthLabel(m.month, 'long')}: the rules change</div>
              <ul className="mt-1 space-y-0.5">
                {m.changes.map(c => (
                  <li key={c.param}>{c.label}: <span className="text-muted line-through decoration-1">{c.before}</span> → <span className="font-medium">{c.after}</span>
                    {c.fact_id && <span className="ml-1 break-all font-mono text-[10px] text-muted">{c.fact_id}</span>}</li>
                ))}
              </ul>
              <Link to={`/time-machine?date=${m.month}-01`} className="mt-1 inline-block text-xs text-brand underline">See the rules on that date in the Time Machine</Link>
            </div>
          ))}
          <p className="text-[11px] text-muted">Holds {monthLabel(f.pattern_month, 'long')} constant and applies each month's published rules,
            so any change in colour is caused by the rules alone. {f.assumptions.slice(1).join(' ')}</p>
        </div>
      )}
    </Card>
  )
}

function NearbyBox({ caseId }: { caseId: string }) {
  const [res, setRes] = useState<Record<string, Nearby>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const go = async (kind: 'volunteer' | 'work_program') => {
    setBusy(kind); setErr('')
    try { const r = await api.nearby(caseId, kind); setRes(x => ({ ...x, [kind]: r })) } catch (e) { setErr(String(e)) } finally { setBusy(null) }
  }
  return (
    <div className="mt-2">
      <div className="flex flex-wrap gap-2">
        <button onClick={() => go('volunteer')} disabled={!!busy} className="rounded-full border border-brand/40 px-3 py-1 text-xs text-brand hover:bg-brand-soft disabled:opacity-50">Find volunteering nearby</button>
        <button onClick={() => go('work_program')} disabled={!!busy} className="rounded-full border border-brand/40 px-3 py-1 text-xs text-brand hover:bg-brand-soft disabled:opacity-50">Find job training nearby</button>
      </div>
      <div aria-live="polite">
        {busy && <Spinner label="Searching the web with Tavily" />}
        {err && <p role="alert" className="mt-1 text-xs text-bad">{err}</p>}
        {Object.values(res).map(r => (
          <div key={r.kind} className="mt-2 rounded-lg border border-line bg-paper p-3">
            <div className="text-xs text-muted">{r.rule} Searched {r.as_of} · sent to search: <span className="font-medium text-ink">{r.sent_to_search}</span></div>
            <ul className="mt-2 space-y-2">
              {r.options.map(o => (
                <li key={o.url} className="text-sm">
                  <a href={o.url} target="_blank" rel="noreferrer" className="font-medium text-brand underline">{o.name} ↗</a>
                  <span className="text-muted"> · {o.what}</span>
                  <div className="text-[11px] text-muted">From the page: <mark className="cite">{o.quote}</mark></div>
                </li>
              ))}
              {r.options.length === 0 && <li className="text-xs text-muted">No verifiable local options found.</li>}
            </ul>
            <p className="mt-2 text-[11px] text-muted">Each option quotes its own search result word for word{r.dropped_unverified ? `; ${r.dropped_unverified} that didn't were dropped` : ''}. Confirm with the agency that the activity counts.</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function PathRow({ p, caseId, showNearby }: { p: PathOpt; caseId: string; showNearby: boolean }) {
  return (
    <li className="rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-paper border border-line px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted">{EFFORT[p.effort]}</span>
        {p.proven
          ? <span className="rounded-full bg-ok-soft px-2 py-0.5 text-[10px] font-medium text-ok">✓ Proven: rules re-run → meets</span>
          : <span className="rounded-full bg-warn-soft px-2 py-0.5 text-[10px] font-medium text-warn">Agency decides</span>}
      </div>
      <div className="mt-1.5 text-sm font-medium">{p.title}</div>
      <div className="text-xs text-muted">{p.detail}</div>
      {p.questions.length > 0 && (
        <details className="mt-1 text-xs"><summary className="cursor-pointer text-brand">Show the questions</summary>
          <ul className="mt-1 list-disc pl-5 space-y-0.5">{p.questions.map(q => <li key={q}>{q}?</li>)}</ul></details>
      )}
      {showNearby && p.kind === 'hours' && <NearbyBox caseId={caseId} />}
    </li>
  )
}

export function PathsCard({ plan, caseId }: { plan: Plan; caseId: string }) {
  const next = plan.forecast.months.find(m => m.status !== 'meets' && m.paths.length)
  if (!plan.paths.length && !next) return null
  return (
    <Card tour="paths" title="Paths to stay covered">
      <p className="mb-3 text-xs text-muted">The smallest changes that would settle each month, easiest first. Each "proven" path was checked by
        re-running the rules engine with that change, not guessed by the AI.</p>
      <div className="space-y-4">
        {plan.paths.map(g => (
          <section key={g.month} aria-label={`Paths for ${monthLabel(g.month, 'long')}`}>
            <div className="mb-1.5 flex items-center gap-2 text-sm"><span className="font-medium">{monthLabel(g.month, 'long')}</span><StatusPill status={g.status} />
              <span className="text-xs text-muted">already past: settle it with proof</span></div>
            <ul className="space-y-2">{g.paths.map((p, i) => <PathRow key={i} p={p} caseId={caseId} showNearby={false} />)}</ul>
          </section>
        ))}
        {next && (
          <section aria-label="Paths for the months ahead">
            <div className="mb-1.5 flex items-center gap-2 text-sm"><span className="font-medium">From {monthLabel(next.month, 'long')} on</span><StatusPill status={next.status} />
              <span className="text-xs text-muted">ahead: plan it</span></div>
            <ul className="space-y-2">{next.paths.map((p, i) => <PathRow key={i} p={p} caseId={caseId} showNearby={plan.location !== ''} />)}</ul>
          </section>
        )}
      </div>
    </Card>
  )
}

export function CaseloadOutlook({ data }: { data: CaseloadForecast }) {
  if (!data.rows.length) return null
  const changeMonths = new Set(data.changes.map(c => c.month))
  const atRisk = data.rows.filter(r => r.first_risk).length
  return (
    <Card tour="outlook" title="12-month outlook · same lives, changing rules">
      <p className="mb-3 text-sm">
        <span className="font-serif text-lg">{atRisk} of {data.rows.length}</span> clients have a month ahead that isn't clearly covered if their lives stay as documented.
      </p>
      <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Caseload outlook by month">
        <table className="w-full min-w-[440px] border-separate border-spacing-y-1 text-sm">
          <thead>
            <tr>
              <th scope="col" className="w-28 sm:w-40 text-left align-bottom text-xs font-normal text-muted">Client</th>
              <th scope="col" className="text-left text-xs font-normal text-muted">
                <span className="sr-only">{monthLabel(data.months[0], 'long')} to {monthLabel(data.months[data.months.length - 1], 'long')}</span>
                <ol className="flex gap-1" aria-hidden="true">
                  {data.months.map((m, i) => (
                    <li key={m} className={`flex-1 min-w-0 text-center text-[10px] leading-tight ${i > 0 && m.endsWith('-01') ? 'ml-1.5' : ''}`}>
                      <span className={`block ${changeMonths.has(m) ? 'text-brand' : 'text-transparent'}`}>◆</span>
                      {new Date(m + '-01T00:00:00').toLocaleDateString('en-US', { month: 'narrow' })}
                      {(i === 0 || m.endsWith('-01')) && <span className="block text-[9px]">{m.slice(0, 4)}</span>}
                    </li>
                  ))}
                </ol>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map(r => (
              <tr key={r.id}>
                <th scope="row" className="pr-3 text-left font-normal"><Link to={`/cases/${r.id}`} className="text-brand hover:underline">{r.client_name}</Link></th>
                <td title={r.headline}>{r.months.length ? <Strip months={r.months} size="sm" /> : <span className="text-xs text-muted">no documented month yet: see the case</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2"><Legend /></div>
      {data.changes.map(c => (
        <p key={c.month + c.label} className="mt-2 text-xs"><span className="text-brand">◆ {monthLabel(c.month, 'long')}</span>: {c.label.toLowerCase()} goes from
          “{c.before}” to “{c.after}”. Affects {c.clients.join(', ')}.</p>
      ))}
      {!changeMonths.size && <p className="mt-2 text-xs text-muted">No scheduled rule change alters these clients' outcomes in the next 12 months.</p>}
    </Card>
  )
}
