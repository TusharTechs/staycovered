import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, fmtDate, today, type CaseSummary, type DriftEvent, type Fact } from '../api'
import { Card, Cite, LastChecked, Spinner, StatusPill } from '../components/ui'
import { STATES, useJuris, type Juris } from '../components/State'
import AskBox from '../components/AskBox'

type Milestone = { date: string; label: string; detail: string }

// Hand-curated labels for the real policy timeline; every date also comes from cited rule facts or snapshots.
const FEDERAL: Record<string, string> = {
  '2025-07-04': 'H.R.1 signed',
  '2026-06-03': 'Federal rule published',
  '2026-06-29': 'Federal rule corrected',
  '2026-07-31': 'Federal rule effective',
  '2026-09-08': 'CMS frailty guidance',
  '2027-01-01': 'Nationwide start',
  '2028-01-01': 'Documentation required',
}

const MT_LABELS: Record<string, string> = {
  ...FEDERAL,
  '2026-06-30': 'Montana FAQ published',
  '2026-07-01': 'Montana starts (grace period)',
  '2026-08-31': 'Montana: existing clients at redetermination',
  '2026-10-01': 'Montana enforcement + claims-based frailty check',
  '2027-01-01': 'Nationwide start; Montana 6-month renewals',
}

const NE_LABELS: Record<string, string> = {
  '2025-07-04': 'H.R.1 signed',
  '2025-12-17': 'Nebraska announces work requirements',
  '2026-04-14': 'Nebraska page rewritten',
  '2026-04-29': 'Nebraska: May/June renewals deferred',
  '2026-05-01': 'Nebraska starts (new applicants)',
  '2026-05-12': 'Nebraska FAQ: household income "may count"',
  '2026-06-03': 'Federal rule published',
  '2026-06-29': 'Federal rule corrected',
  '2026-07-22': 'Nebraska: Dawson County hardship',
  '2026-07-31': 'Federal rule effective; NE renewals begin',
  '2026-09-08': 'CMS frailty guidance',
  '2026-09-12': 'Nebraska: 14-county hardship',
  '2026-09-15': 'Nebraska frailty process updated',
  '2027-01-01': 'Nationwide start',
  '2028-01-01': 'Documentation required',
}

const LABELS_BY: Record<Juris, Record<string, string>> = { NE: NE_LABELS, MT: MT_LABELS }
const SUGGEST: Record<Juris, string[]> = {
  NE: ['When do Nebraska Medicaid work requirements start for people already enrolled?', 'How is medical frailty verified?', 'Does a spouse\'s income count toward the $580 income test?'],
  MT: ['When does Montana start denying coverage for not meeting the requirement?', 'How does Montana verify medical frailty?', 'Does a spouse\'s income count toward the $580 income test in Montana?'],
}

const TOPIC_ORDER = ['timeline', 'applicability', 'requirement', 'income_alternative', 'lookback', 'verification', 'exemption', 'good_cause', 'notice', 'cure', 'reporting', 'process', 'contact']

export default function TimeMachine() {
  const { state } = useJuris()
  const LABELS = LABELS_BY[state]
  const [dates, setDates] = useState<string[]>([])
  const [idx, setIdx] = useState(0)
  const [facts, setFacts] = useState<Fact[] | null>(null)
  const [prevIds, setPrevIds] = useState<Set<string>>(new Set())
  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [prevCases, setPrevCases] = useState<Record<string, string>>({})
  const [playing, setPlaying] = useState(false)
  const [events, setEvents] = useState<DriftEvent[]>([])
  const timer = useRef<number | null>(null)
  const [params] = useSearchParams()
  const wanted = params.get('date')

  useEffect(() => { api.replay(state).then(setEvents).catch(() => setEvents([])) }, [state])
  useEffect(() => {
    api.timeline(state).then(t => {
      const ds = new Set<string>(Object.keys(LABELS))
      t.dates.forEach(d => { if (d.date >= '2025-07-01' && d.date <= '2028-06-30') ds.add(d.date) })
      ds.add(today())
      const sorted = [...ds].sort()
      setDates(sorted)
      setIdx(sorted.indexOf(wanted && sorted.includes(wanted) ? wanted : today()))
    })
  }, [state])

  useEffect(() => { if (wanted && dates.includes(wanted)) { setPlaying(false); setIdx(dates.indexOf(wanted)) } }, [wanted, dates])

  const asOf = dates[idx]
  useEffect(() => {
    if (!asOf) return
    const before = new Set((facts ?? []).map(f => f.id + (f.effective_from ?? '')))
    const beforeCases = Object.fromEntries((cases ?? []).map(c => [c.id, c.status]))
    api.facts(asOf, state).then(fs => { setPrevIds(before); setFacts(fs) })
    api.cases(asOf, state).then(cs => { setPrevCases(beforeCases); setCases(cs) })
  }, [asOf, state])

  useEffect(() => {
    if (!playing) { if (timer.current) window.clearInterval(timer.current); return }
    timer.current = window.setInterval(() => setIdx(i => (i + 1 < dates.length ? i + 1 : (setPlaying(false), i))), 2600)
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [playing, dates.length])

  const grouped = useMemo(() => {
    const g: Record<string, Fact[]> = {}
    for (const f of facts ?? []) (g[f.topic] ??= []).push(f)
    return TOPIC_ORDER.filter(t => g[t]).map(t => [t, g[t]] as const)
  }, [facts])

  const milestones: Milestone[] = dates.map(d => ({ date: d, label: LABELS[d] ?? (d === today() ? 'Today' : ''), detail: '' }))
  const isNew = (f: Fact) => prevIds.size > 0 && !prevIds.has(f.id + (f.effective_from ?? ''))

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-3"><h1 className="font-serif text-3xl tracking-tight">Rule Time Machine</h1><LastChecked /></div>
        <p className="text-muted text-sm mt-1 max-w-3xl">{STATES[state].name} + federal rules. AI models are frozen at their training date. Medicaid rules aren't. Move through the real policy timeline and watch the official sources, the answers and the caseload change with it.</p>
      </div>

      <Card tour="timeline">
        <div className="flex flex-wrap items-center gap-4 pt-3">
          <button onClick={() => setPlaying(p => !p)} className="rounded-full bg-brand text-white h-10 w-10 grid place-items-center" aria-label={playing ? 'Pause' : 'Play timeline'}>
            {playing ? '❚❚' : '▶'}
          </button>
          <div>
            <div className="text-xs text-muted">Rules as of</div>
            <div className="text-2xl font-semibold tabular-nums">{fmtDate(asOf)}</div>
          </div>
          <div className="text-sm text-brand font-medium">{LABELS[asOf] ?? (asOf === today() ? 'Today' : '')}</div>
        </div>
        <div className="mt-4">
          <label htmlFor="tm" className="sr-only">Timeline position</label>
          <input id="tm" type="range" min={0} max={Math.max(0, dates.length - 1)} value={idx} onChange={e => { setPlaying(false); setIdx(+e.target.value) }}
            className="w-full accent-[#0f5d5d]" aria-valuetext={fmtDate(asOf)} />
          <ol className="mt-2 flex flex-wrap gap-1.5">
            {milestones.filter(m => m.label).map(m => (
              <li key={m.date}>
                <button onClick={() => { setPlaying(false); setIdx(dates.indexOf(m.date)) }}
                  className={`rounded-full border px-2.5 py-1 text-[11px] ${m.date === asOf ? 'border-brand bg-brand text-white' : m.date < asOf ? 'border-brand/30 bg-brand-soft text-brand' : 'border-line bg-white text-muted'}`}>
                  <span className="tabular-nums">{m.date}</span> · {m.label}
                </button>
              </li>
            ))}
          </ol>
        </div>
      </Card>

      <RuleChanges events={events.filter(e => e.new_as_of <= asOf && (e.summary?.substantive ?? true))} asOf={asOf} />

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3" title={`What the official rules said on ${fmtDate(asOf)}`} actions={facts && <span className="text-xs text-muted">{facts.length} facts in force or announced</span>}>
          {!facts && <Spinner />}
          {facts && facts.length === 0 && <p className="text-sm text-muted">Nothing had been published yet on this date.</p>}
          <div className="space-y-4 max-h-[34rem] overflow-auto pr-1">
            {grouped.map(([topic, fs]) => (
              <div key={topic}>
                <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted mb-1">{topic.replace(/_/g, ' ')}</h3>
                <ul className="space-y-1.5">
                  {fs.map(f => (
                    <li key={f.id + f.effective_from} className={`rounded-md px-2 py-1.5 text-sm ${isNew(f) ? 'bg-warn-soft ring-1 ring-warn/40' : ''}`}>
                      {isNew(f) && <span className="mr-1 rounded bg-warn px-1 text-[10px] font-semibold text-white">NEW</span>}
                      <span className={f.jurisdiction === 'US' ? '' : 'font-medium'}>{f.jurisdiction !== 'US' && <span className="text-brand">[{f.jurisdiction}] </span>}{f.statement}</span>
                      {f.effective_from && f.effective_from > asOf && <span className="ml-1 text-[11px] text-muted">(takes effect {fmtDate(f.effective_from)})</span>}
                      {f.citations[0] && <Cite sourceId={f.citations[0].source_id} quote={f.citations[0].quote} label="source" />}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>

        <div className="lg:col-span-2 space-y-5">
          <Card tour="ask" title="Ask — frozen model vs. rules as of this date">
            <AskBox key={asOf + state} asOf={asOf} compare jurisdiction={state} suggestions={SUGGEST[state]} />
          </Card>
          <Card title="Caseload on this date">
            {!cases && <Spinner />}
            <ul className="space-y-1.5 text-sm">
              {cases?.map(c => {
                const changed = prevCases[c.id] && prevCases[c.id] !== c.status
                return (
                  <li key={c.id} className={`flex items-center gap-2 rounded px-2 py-1 ${changed ? 'bg-warn-soft' : ''}`}>
                    <span className="flex-1">{c.client_name}</span>
                    {changed && <span className="text-[10px] font-semibold text-warn">CHANGED</span>}
                    <StatusPill status={c.status} />
                  </li>
                )
              })}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}

function RuleChanges({ events, asOf }: { events: DriftEvent[]; asOf: string }) {
  if (events.length === 0) return null
  const latest = [...events].reverse()
  return (
    <Card tour="changes" title="Official pages that changed (detected by drift-watch)" actions={<span className="text-xs text-muted">{events.length} change{events.length > 1 ? 's' : ''} up to {fmtDate(asOf)}</span>}>
      <ol className="space-y-3">
        {latest.slice(0, 4).map(e => (
          <li key={e.new_id} className={`rounded-lg border p-3 ${e.new_as_of === asOf ? 'border-warn bg-warn-soft/60' : 'border-line'}`}>
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-xs tabular-nums text-muted">{e.old_as_of} → {e.new_as_of}</span>
              <span className="text-sm font-medium">{e.summary?.headline ?? `${e.title} changed`}</span>
            </div>
            {e.summary?.details?.length ? <ul className="mt-1 list-disc pl-5 text-xs space-y-0.5">{e.summary.details.slice(0, 4).map((d, i) => <li key={i}>{d}</li>)}</ul> : null}
            {e.summary?.navigator_action && <p className="mt-1 text-xs"><b>Navigator action:</b> {e.summary.navigator_action}</p>}
            {e.affected_cases.length > 0 && (
              <p className="mt-1 text-xs text-warn">⟳ Re-check {e.affected_cases.length} case{e.affected_cases.length > 1 ? 's' : ''}: {e.affected_cases.map(c => c.client_name).join(', ')}</p>
            )}
            <details className="mt-1 text-[11px] text-muted"><summary className="cursor-pointer">Exact text added / removed</summary>
              <div className="grid md:grid-cols-2 gap-2 mt-1">
                <div><div className="font-semibold text-bad">Removed</div>{e.removed.slice(0, 8).map((x, i) => <p key={i} className="line-through decoration-bad/50">{x}</p>)}</div>
                <div><div className="font-semibold text-ok">Added</div>{e.added.slice(0, 8).map((x, i) => <p key={i}>{x}</p>)}</div>
              </div>
            </details>
          </li>
        ))}
      </ol>
    </Card>
  )
}
