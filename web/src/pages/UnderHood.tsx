import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Empty } from '../components/ui'

type Call = { ts: number; job: string; tag: string; model: string; prompt_tokens: number; completion_tokens: number; usd: number; latency_s: number }
type TCall = { ts: number; kind: string; payload: { urls?: string[]; url?: string; query?: string }; results: number; ok: boolean }


const LIMITS: [string, string][] = [
  ['No real users yet', 'Every client is synthetic. Navigator and legal-aid outreach has started, but no one has used StayCovered on a real case.'],
  ['Two states modelled in full', 'Nebraska and Montana have full rule packs. Arkansas, Iowa and Georgia pages are monitored but not yet modelled.'],
  ['Rules need a human after a rewrite', "drift-watch flags changes and stale quotes but never edits rule facts itself. After Nebraska's Oct 23 rewrite, 14 facts await re-verification."],
  ['Our own benchmark', 'WorkReqBench is self-built. The human check was one non-expert grading 40 criteria blind (67.5% agreement with the AI grader). No expert review yet.'],
  ['Documents are synthetic', "Extraction scores 0.995 F1 on unseen synthetic formats, but real phone photos and unusual pay stubs are untested. On Rosa's case 2 of 5 numbers need a human look."],
  ['Interpretations we chose', "Income converts to hours as the larger of documented paid hours and income ÷ $7.25; weeks crossing months are split by days. Both are flagged 'confirm with the agency'."],
  ['Exemptions are screening only', "StayCovered lists possible exemptions to raise; it doesn't decide them, and medical frailty is not assessed."],
  ['Not production-ready', 'No sign-in or real client data. Real use needs Zero Data Retention on Token Factory and agency-specific review.'],
]

export default function UnderHood() {
  const [calls, setCalls] = useState<Call[]>([])
  const [tav, setTav] = useState<TCall[]>([])
  const [sum, setSum] = useState<{ generated: string; total_calls: number; total_usd: number; rows: { model: string; job: string; calls: number; tokens: number; usd: number; p50_latency_s: number }[]; tavily: { ts: number; kind: string; urls: string[]; query?: string | null; results: number; ok: boolean }[] } | null>(null)
  useEffect(() => {
    fetch('/api/log/summary').then(r => r.json()).then(setSum).catch(() => {})
    api.calls().then(x => setCalls(x as unknown as Call[]))
    api.tavily().then(x => setTav(x as unknown as TCall[]))
  }, [])

  const byModel: Record<string, { n: number; usd: number; tok: number; lat: number }> = {}
  for (const c of calls) {
    const m = (byModel[c.model] ??= { n: 0, usd: 0, tok: 0, lat: 0 })
    m.n++; m.usd += c.usd; m.tok += (c.prompt_tokens ?? 0) + (c.completion_tokens ?? 0); m.lat += c.latency_s
  }
  const tavilyUrls = tav.flatMap(t => t.payload.urls ?? (t.payload.url ? [t.payload.url] : []))

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-3xl tracking-tight">Under the hood</h1>
        <p className="text-muted text-sm mt-1">Every model call and every web request, as logged by the backend.</p>
      </div>
      <div className="grid gap-5 lg:grid-cols-2 [&>*]:min-w-0">
        <Card tour="models" title="Nemotron on Nebius Token Factory — routing">
          {calls.length === 0 ? <Empty>No model calls logged yet.</Empty> : (
            <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Model routing"><table className="w-full min-w-[420px] text-sm">
              <thead><tr className="text-left text-xs text-muted"><th className="py-1 font-medium">Model</th><th className="font-medium">Calls</th><th className="font-medium">Tokens</th><th className="font-medium">Cost</th><th className="font-medium">Avg latency</th></tr></thead>
              <tbody>{Object.entries(byModel).map(([m, v]) => (
                <tr key={m} className="border-t border-line"><td className="py-1.5 font-mono text-xs">{m.replace('nvidia/', '')}</td><td className="tabular-nums">{v.n}</td><td className="tabular-nums">{v.tok.toLocaleString()}</td><td className="tabular-nums">${v.usd.toFixed(4)}</td><td className="tabular-nums">{(v.lat / v.n).toFixed(1)}s</td></tr>
              ))}</tbody>
            </table></div>
          )}
          <p className="mt-3 text-xs text-muted">Extraction and plain-language rewriting use the cheap Nano model; reasoning over rules uses Super; the benchmark judge is Ultra.</p>
        </Card>
        <Card title="Tavily — what left the building">
          <p className="text-xs text-muted mb-2">Rule monitoring (Extract, Map) sends only allow-listed official URLs. The nearby search sends only a city and the kind of activity. No client names, documents or questions ever leave.</p>
          {tav.length === 0 ? <Empty>No Tavily requests logged yet.</Empty> : (
            <ul tabIndex={0} aria-label="Tavily request log" className="space-y-1 text-xs font-mono max-h-80 overflow-auto">
              {tav.slice().reverse().map((t, i) => (
                <li key={i} className={t.ok ? '' : 'text-bad'}>{new Date(t.ts * 1000).toISOString().slice(0, 19)} · {t.kind} · {t.payload.query ? `“${t.payload.query}”` : (t.payload.urls ?? [t.payload.url]).join(', ')} · {t.results} results</li>
              ))}
            </ul>
          )}
          {tavilyUrls.length > 0 && <p className="mt-2 text-xs text-ok">✓ {tavilyUrls.length} URLs sent, all on the official allow-list{tav.some(t => t.payload.query) ? '; searches carry only a city name' : ''}.</p>}
        </Card>
      </div>
      {sum?.rows?.length ? (
        <Card title={`Logged usage while building and evaluating · ${sum.total_calls.toLocaleString()} calls · $${sum.total_usd.toFixed(2)} total`}>
          <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Logged usage by model and job"><table className="w-full min-w-[520px] text-sm">
            <thead><tr className="text-left text-xs text-muted"><th className="py-1 font-medium">Model</th><th className="font-medium">Job</th><th className="font-medium">Calls</th><th className="font-medium">Tokens</th><th className="font-medium">Cost</th><th className="font-medium">p50 latency</th></tr></thead>
            <tbody>{sum.rows.map((r, i) => (
              <tr key={i} className="border-t border-line"><td className="py-1.5 font-mono text-xs">{r.model.replace('nvidia/', '')}</td><td className="text-xs">{r.job}</td><td className="tabular-nums">{r.calls}</td><td className="tabular-nums">{r.tokens.toLocaleString()}</td><td className="tabular-nums">${r.usd.toFixed(3)}</td><td className="tabular-nums">{r.p50_latency_s}s</td></tr>
            ))}</tbody>
          </table></div>
          {sum.tavily?.length > 0 && <div className="mt-3 text-xs"><div className="font-medium">Tavily requests (official URLs for rule monitoring; city-only searches for nearby programs)</div>
            <ul tabIndex={0} aria-label="Tavily requests while building" className="mt-1 max-h-60 overflow-auto font-mono space-y-0.5">{sum.tavily.map((t, i) => <li key={i}>{new Date(t.ts * 1000).toISOString().slice(0, 16)} · {t.kind} · {t.query ? `“${t.query}”` : `${t.urls.length} official URLs`} · {t.results} results</li>)}</ul></div>}
          <p className="mt-2 text-[11px] text-muted">Snapshot generated {sum.generated}. Live calls on this server appear in the cards above.</p>
        </Card>
      ) : null}
      <Card title="Limitations: what isn't done yet" actions={<span className="text-xs text-muted">documented on purpose</span>}>
        <ul className="grid gap-3 sm:grid-cols-2">
          {LIMITS.map(([t, d]) => <li key={t} className="text-sm"><div className="font-medium">{t}</div><div className="text-xs text-muted">{d}</div></li>)}
        </ul>
      </Card>
      <Card title="Recent calls">
        <ul tabIndex={0} aria-label="Recent model calls" className="text-xs font-mono space-y-0.5 max-h-96 overflow-auto">
          {calls.slice().reverse().slice(0, 100).map((c, i) => (
            <li key={i}>{new Date(c.ts * 1000).toISOString().slice(11, 19)} · {c.job}/{c.tag} · {c.model.replace('nvidia/', '')} · {c.prompt_tokens}+{c.completion_tokens} tok · ${c.usd.toFixed(5)} · {c.latency_s}s</li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
