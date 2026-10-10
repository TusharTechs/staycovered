import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type CaseloadForecast } from '../api'
import { Strip } from '../components/Plan'
import { useTour } from '../components/Tour'
import { LastChecked } from '../components/ui'

type Sys = { system: string; score: number; drift_sensitive_score?: number | null; model: string }

export default function Home() {
  const tour = useTour()
  const [bench, setBench] = useState<{ split?: string; n_questions?: number; systems?: Sys[] } | null>(null)
  useEffect(() => { api.bench().then(b => setBench(b as typeof bench)).catch(() => {}) }, [])
  const [outlook, setOutlook] = useState<CaseloadForecast | null>(null)
  useEffect(() => { api.forecast('NE').then(setOutlook).catch(() => {}) }, [])
  const row = (id: string) => outlook?.rows.find(r => r.id === id)
  const changesFor = (id: string) => new Set(outlook?.changes.filter(c => c.clients.includes(row(id)?.client_name ?? '')).map(c => c.month) ?? [])
  const sc = bench?.systems?.find(s => s.system === 'staycovered')
  const fr = bench?.systems?.find(s => s.system === 'frozen-frontier')

  return (
    <div className="space-y-10">
      <section className="pt-6 md:pt-10">
        <div className="flex flex-wrap items-center gap-3"><p className="text-sm font-medium text-brand">Medicaid work requirements · Nebraska and Montana</p><LastChecked /></div>
        <h1 className="mt-2 font-serif text-4xl md:text-6xl tracking-tight leading-[1.05] max-w-4xl">
          AI models are frozen at their training date.<br /><span className="text-brand">Medicaid rules aren't.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted leading-relaxed">
          StayCovered helps the navigators who keep people covered: it reads clients' messy documents, applies the official rules
          <em> as of the date that matters</em>, cites every number and rule, and re-checks cases when the rules change.
          People without a navigator can check themselves, in English or Spanish, with nothing saved.
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          <button onClick={tour.start} className="rounded-xl bg-brand px-5 py-3 text-base font-semibold text-white shadow-sm hover:opacity-90">
            ▶ Take the guided tour
          </button>
          <Link to="/caseload" className="rounded-xl border border-line bg-white px-5 py-3 text-base font-medium hover:border-brand">Open the caseload</Link>
          <Link to="/time-machine" className="rounded-xl border border-line bg-white px-5 py-3 text-base font-medium hover:border-brand">Rule Time Machine</Link>
          <Link to="/check" className="rounded-xl border border-line bg-white px-5 py-3 text-base font-medium hover:border-brand">Check your own coverage <span lang="es" className="text-muted">· en español</span></Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Stat big="Jan 1, 2027" label="Every Medicaid expansion state must start verifying 80 hours of work or activity (or ~$580/month income)." />
        <Stat big="Paperwork" label="In Nebraska's early rollout, most coverage losses came from people not responding to requests — not from being found non-compliant." />
        <Stat big="9 changes" label="Substantive changes to Nebraska's official work-requirements page between Dec 2025 and Oct 2026, plus federal rule, correction and CMS guidance." />
      </section>

      {sc && fr && (
        <section className="rounded-2xl border border-line bg-white p-6">
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="font-serif text-2xl">WorkReqBench</h2>
            <span className="text-sm text-muted">{bench?.n_questions} dated questions · {bench?.split} split</span>
            <Link to="/bench" className="ml-auto text-sm text-brand hover:underline">See the benchmark →</Link>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Bar label="StayCovered · Nemotron Super + rules as of the date" v={sc.score} d={sc.drift_sensitive_score} ours />
            <Bar label={`Frontier model answering from memory · ${fr.model}`} v={fr.score} d={fr.drift_sensitive_score} />
          </div>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        <Link to="/cases/dani-ortiz" className="group rounded-2xl border border-line bg-white p-6 hover:border-brand">
          <div className="text-xs font-medium uppercase tracking-wide text-brand">Paths to stay covered</div>
          <div className="mt-2 font-serif text-2xl leading-snug">Dani is $70 a month from keeping her health insurance.</div>
          {row('dani-ortiz') && <div className="mt-4" aria-hidden="true"><Strip months={row('dani-ortiz')!.months} changes={changesFor('dani-ortiz')} /></div>}
          <p className="mt-2 text-sm text-muted">The engine searches for the smallest fixes and re-runs the rules to prove each one: five more paid hours,
            or 28 volunteer hours at real places nearby, found with Tavily. <span className="text-brand group-hover:underline">Open Dani's case →</span></p>
        </Link>
        <Link to="/cases/tom-becker" className="group rounded-2xl border border-line bg-white p-6 hover:border-brand">
          <div className="text-xs font-medium uppercase tracking-wide text-brand">Coverage forecast</div>
          <div className="mt-2 font-serif text-2xl leading-snug">Same life, changing rules.</div>
          {row('tom-becker') && <div className="mt-4" aria-hidden="true"><Strip months={row('tom-becker')!.months} changes={changesFor('tom-becker')} /></div>}
          <p className="mt-2 text-sm text-muted">Tom's household stays exactly the same for twelve months; only the published rules move. In January 2027 he
            becomes clearly covered, and the forecast names the rule that did it. <span className="text-brand group-hover:underline">Open Tom's case →</span></p>
        </Link>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 text-sm">
        {[
          ['Reads documents', 'Gig statements, pay stubs, letters → labelled numbers with exact source lines (Nemotron Nano).'],
          ['Code does the math', 'Deterministic rules engine; "meets only if…" instead of a false yes.'],
          ['Answers as of a date', 'Grounded in dated official snapshots; quotes verified word for word (Nemotron Super).'],
          ['Watches the rules', 'Tavily + archives detect official changes every day; affected cases are flagged for re-check.'],
          ['Finds the smallest fix', 'Counterfactual search over the rules engine; every suggested path is proven by re-running it.'],
          ['Forecasts the year', 'Twelve months ahead under rules already published, with calendar reminders for the client.'],
          ['Tests policy choices', 'A sandbox flips the options federal law leaves to states and re-runs the whole caseload: who is short, and who is at risk only for paperwork.'],
          ['Serves people directly', 'A bilingual, anonymous self-check: status, smallest fix and a 12-month forecast, with nothing saved.'],
        ].map(([t, b]) => (
          <div key={t} className="rounded-xl border border-line bg-white p-4"><div className="font-semibold">{t}</div><div className="mt-1 text-muted">{b}</div></div>
        ))}
      </section>

      <p className="text-xs text-muted">Built on NVIDIA Nemotron (Nano · Super · Ultra) via Nebius Token Factory, and Tavily. Demo clients are synthetic. StayCovered never decides eligibility — the state agency does.</p>
    </div>
  )
}

function Stat({ big, label }: { big: string; label: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="font-serif text-3xl text-ink">{big}</div>
      <p className="mt-2 text-sm text-muted leading-relaxed">{label}</p>
    </div>
  )
}

function Bar({ label, v, d, ours }: { label: string; v: number; d?: number | null; ours?: boolean }) {
  return (
    <div>
      <div className="flex items-baseline gap-2 text-sm"><span className={ours ? 'font-semibold text-brand' : ''}>{label}</span><span className="ml-auto text-2xl font-semibold tabular-nums">{(v * 100).toFixed(0)}%</span></div>
      <div className="mt-1 h-3 rounded-full bg-paper border border-line overflow-hidden"><div className={`h-full ${ours ? 'bg-brand' : 'bg-muted/60'}`} style={{ width: `${v * 100}%` }} /></div>
      {d != null && <div className="mt-1 text-xs text-muted">Questions whose answer changed over time: <b className="text-ink">{(d * 100).toFixed(0)}%</b></div>}
    </div>
  )
}
