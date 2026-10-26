import { useEffect, useRef, useState } from 'react'
import { api, type AgentStep } from '../api'

const CHIP: Record<string, string> = {
  'Nemotron Nano': 'bg-[#76b900]/15 text-[#3d6200] border-[#76b900]/50',
  'Nemotron Super': 'bg-[#76b900]/15 text-[#3d6200] border-[#76b900]/50',
  'Tavily Search': 'bg-[#4f6bed]/10 text-[#2f45b8] border-[#4f6bed]/40',
}
const chip = (a: string) => CHIP[a] ?? 'bg-brand-soft text-brand border-brand/30'
const usd = (n: number) => (n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(3)}`)
const MODEL: Record<string, string> = {
  'NVIDIA-Nemotron-3-Nano-30B-A3B': 'Nemotron Nano 30B', 'nemotron-3-super-120b-a12b': 'Nemotron Super 120B', 'Nemotron-3-Ultra-550b-a55b': 'Nemotron Ultra 550B',
}

type Row = AgentStep & { state: 'waiting' | 'running' | 'done' | 'error'; err?: string }

export default function AgentRun({ caseId, autoStart = false, live = false, onDone }: { caseId: string; autoStart?: boolean; live?: boolean; onDone?: () => void }) {
  const [rows, setRows] = useState<Row[]>([])
  const [running, setRunning] = useState(false)
  const stop = useRef(false)
  const started = useRef(false)

  const run = async () => {
    stop.current = false
    setRunning(true)
    const plan = await api.agentPlan()
    setRows(plan.map(p => ({ ...p, state: 'waiting' } as Row)))
    for (const p of plan) {
      if (stop.current) break
      setRows(rs => rs.map(r => (r.n === p.n ? { ...r, state: 'running' } : r)))
      const t0 = performance.now()
      try {
        const res = await api.agentStep(caseId, p.n, live)
        // a recorded step is replayed with a short pause so each step can be read; it says so on screen
        const wait = res.cached ? Math.max(0, 700 - (performance.now() - t0)) : 0
        await new Promise(r => setTimeout(r, wait))
        setRows(rs => rs.map(r => (r.n === p.n ? { ...r, ...res, state: 'done' } : r)))
      } catch (e) {
        setRows(rs => rs.map(r => (r.n === p.n ? { ...r, state: 'error', err: String(e) } : r)))
        break
      }
    }
    setRunning(false)
    onDone?.()
  }

  useEffect(() => { if (autoStart && !started.current) { started.current = true; run() } }, [autoStart])

  const done = rows.filter(r => r.state === 'done')
  const tot = done.reduce((a, r) => ({
    usd: a.usd + (r.metrics?.usd ?? 0), ultra: a.ultra + (r.metrics?.ultra_usd ?? 0), frontier: a.frontier + (r.metrics?.frontier_usd ?? 0),
    tokens: a.tokens + (r.metrics ? r.metrics.prompt_tokens + r.metrics.completion_tokens : 0), seconds: a.seconds + (r.metrics?.seconds ?? 0),
  }), { usd: 0, ultra: 0, frontier: 0, tokens: 0, seconds: 0 })
  const finished = rows.length > 0 && done.length === rows.length
  const msg = rows.find(r => r.id === 'draft_message')?.output
  const pkg = rows.find(r => r.id === 'package')?.output

  if (!rows.length) {
    return (
      <button onClick={run} className="rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-white shadow-sm hover:opacity-90">
        ▶ Run the StayCovered agent on this case{live ? ' (live)' : ''}
      </button>
    )
  }

  return (
    <section className="rounded-2xl border border-brand/30 bg-white p-4 md:p-5" aria-label="Agent run">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">StayCovered agent · one case, end to end</h2>
        <span className="text-xs text-muted tabular-nums">Step {Math.min(done.length + (running ? 1 : 0), rows.length)} of {rows.length}</span>
        {running
          ? <button onClick={() => { stop.current = true }} className="ml-auto rounded-md border border-line px-3 py-1 text-xs hover:border-bad">Stop</button>
          : <button onClick={run} className="ml-auto rounded-md border border-line px-3 py-1 text-xs hover:border-brand">Run again</button>}
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-paper" aria-hidden="true">
        <div className="h-full bg-brand transition-all duration-500" style={{ width: `${(done.length / rows.length) * 100}%` }} />
      </div>

      <ol className="mt-4 space-y-2" aria-live="polite">
        {rows.map(r => {
          const o = r.output
          return (
            <li key={r.n} className={`rounded-xl border p-3 ${r.state === 'running' ? 'border-brand' : 'border-line'} ${r.state === 'waiting' ? 'opacity-50' : ''}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`grid h-6 w-6 place-items-center rounded-full text-[11px] font-bold ${r.state === 'done' ? (o?.skipped ? 'bg-line text-muted' : 'bg-ok text-white') : r.state === 'running' ? 'bg-brand text-white animate-pulse' : r.state === 'error' ? 'bg-bad text-white' : 'bg-paper text-muted'}`}>
                  {r.state === 'done' ? (o?.skipped ? '–' : '✓') : r.n + 1}
                </span>
                <span className="text-sm font-medium">{r.title}</span>
                <span className="flex flex-wrap gap-1">{r.actors.map(a => <span key={a} className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${chip(a)}`}>{a}</span>)}</span>
                {r.state === 'done' && r.metrics && !o?.skipped && (
                  <span className="ml-auto text-[11px] tabular-nums text-muted">
                    {r.metrics.llm_calls > 0 ? `${r.metrics.models.map(m => MODEL[m] ?? m).join(' + ')} · ${(r.metrics.prompt_tokens + r.metrics.completion_tokens).toLocaleString()} tokens · ${usd(r.metrics.usd)} · ` : ''}
                    {r.metrics.seconds.toFixed(1)}s{r.cached ? ' · recorded run' : ' · live'}
                  </span>
                )}
              </div>
              {r.state === 'done' && o && (
                o.skipped ? <p className="mt-1 pl-8 text-xs text-muted">Skipped: {o.skipped}</p> : (
                  <div className="mt-1 pl-8">
                    {r.id === 'draft_message'
                      ? <p className="inline-block max-w-xl rounded-2xl rounded-bl-sm bg-brand px-3 py-2 text-sm text-white">{o.headline}</p>
                      : <p className="text-sm">{o.headline}</p>}
                    {o.details && o.details.length > 0 && <ul className="mt-1 space-y-0.5 text-xs text-muted">{o.details.map((d, i) => <li key={i}>· {d}</li>)}</ul>}
                    {o.months && <div className="mt-2 flex gap-0.5" aria-hidden="true">{o.months.map(m => <span key={m.month} className={`h-3 flex-1 rounded-sm ${m.status === 'meets' ? 'bg-ok' : m.status === 'conditional' ? 'bg-warn' : m.status === 'does_not_meet' ? 'bg-bad' : 'bg-line'}`} />)}</div>}
                    {o.reused && <p className="mt-1 text-[11px] text-muted">↺ {o.reused}</p>}
                    {o.links && <div className="mt-2 flex flex-wrap gap-2">{o.links.map(l => <a key={l.href} href={l.href} className="rounded-lg border border-brand/40 px-3 py-1.5 text-xs text-brand hover:bg-brand-soft">{l.label}</a>)}</div>}
                  </div>
                )
              )}
              {r.state === 'error' && <p role="alert" className="mt-1 pl-8 text-xs text-bad">{r.err}</p>}
            </li>
          )
        })}
      </ol>

      {finished && (
        <div className="mt-4 rounded-xl bg-paper p-4">
          <div className="text-sm font-semibold">Receipt for this case</div>
          <p className="mt-0.5 text-xs text-muted">{tot.tokens.toLocaleString()} tokens across Nemotron Nano and Super, each step on the smallest model that does it well; {tot.seconds.toFixed(1)}s of work. The same tokens, priced:</p>
          <div className="mt-3 space-y-2">
            {[
              { label: 'StayCovered: right-sized Nemotron on Nebius Token Factory', v: tot.usd, cls: 'bg-brand' },
              { label: 'Every step on Nemotron Ultra 550B', v: tot.ultra, cls: 'bg-[#76b900]' },
              { label: 'Every step on a frontier API model', v: tot.frontier, cls: 'bg-muted/60' },
            ].map(b => (
              <div key={b.label}>
                <div className="flex items-baseline justify-between gap-2 text-xs"><span>{b.label}</span><b className="tabular-nums">{usd(b.v)}</b></div>
                <div className="mt-0.5 h-2.5 overflow-hidden rounded-full bg-white border border-line"><div className={`h-full ${b.cls}`} style={{ width: `${Math.max(1.5, (b.v / Math.max(tot.frontier, 1e-9)) * 100)}%` }} /></div>
              </div>
            ))}
          </div>
          {tot.usd > 0 && <p className="mt-2 text-xs"><b>{Math.round(tot.frontier / tot.usd)}× cheaper</b> than a frontier model for the same work, with every number computed by code and every quote checked.</p>}
          {msg && pkg && <p className="mt-1 text-[11px] text-muted">The client message above uses only numbers from the worksheet; the agent checked each one before showing it.</p>}
        </div>
      )}
    </section>
  )
}
