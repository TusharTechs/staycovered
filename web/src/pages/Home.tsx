import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useTour } from '../components/Tour'

type Sys = { system: string; score: number; drift_sensitive_score?: number | null; model: string }

export default function Home() {
  const tour = useTour()
  const [bench, setBench] = useState<{ split?: string; n_questions?: number; systems?: Sys[] } | null>(null)
  useEffect(() => { api.bench().then(b => setBench(b as typeof bench)).catch(() => {}) }, [])
  const sc = bench?.systems?.find(s => s.system === 'staycovered')
  const fr = bench?.systems?.find(s => s.system === 'frozen-frontier')

  return (
    <div className="space-y-10">
      <section className="pt-6 md:pt-10">
        <p className="text-sm font-medium text-brand">Medicaid work requirements · Nebraska first</p>
        <h1 className="mt-2 font-serif text-4xl md:text-6xl tracking-tight leading-[1.05] max-w-4xl">
          AI models are frozen at their training date.<br /><span className="text-brand">Medicaid rules aren't.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted leading-relaxed">
          StayCovered helps the navigators who keep people covered: it reads clients' messy documents, applies the official rules
          <em> as of the date that matters</em>, cites every number and rule, and re-checks cases when the rules change.
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          <button onClick={tour.start} className="rounded-xl bg-brand px-5 py-3 text-base font-semibold text-white shadow-sm hover:opacity-90">
            ▶ Take the 90-second tour
          </button>
          <Link to="/caseload" className="rounded-xl border border-line bg-white px-5 py-3 text-base font-medium hover:border-brand">Open the caseload</Link>
          <Link to="/time-machine" className="rounded-xl border border-line bg-white px-5 py-3 text-base font-medium hover:border-brand">Rule Time Machine</Link>
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

      <section className="grid gap-4 md:grid-cols-4 text-sm">
        {[
          ['Reads documents', 'Gig statements, pay stubs, letters → labelled numbers with exact source lines (Nemotron Nano).'],
          ['Code does the math', 'Deterministic rules engine; "meets only if…" instead of a false yes.'],
          ['Answers as of a date', 'Grounded in dated official snapshots; quotes verified word for word (Nemotron Super).'],
          ['Watches the rules', 'Tavily + archives detect official changes; affected cases are flagged for re-check.'],
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
