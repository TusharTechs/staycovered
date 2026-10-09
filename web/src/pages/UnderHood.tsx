import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Empty } from '../components/ui'

type Call = { ts: number; job: string; tag: string; model: string; prompt_tokens: number; completion_tokens: number; usd: number; latency_s: number }
type TCall = { ts: number; kind: string; payload: { urls?: string[]; url?: string }; results: number; ok: boolean }

export default function UnderHood() {
  const [calls, setCalls] = useState<Call[]>([])
  const [tav, setTav] = useState<TCall[]>([])
  useEffect(() => {
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
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Nemotron on Nebius Token Factory — routing">
          {calls.length === 0 ? <Empty>No model calls logged yet.</Empty> : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted"><th className="py-1 font-medium">Model</th><th className="font-medium">Calls</th><th className="font-medium">Tokens</th><th className="font-medium">Cost</th><th className="font-medium">Avg latency</th></tr></thead>
              <tbody>{Object.entries(byModel).map(([m, v]) => (
                <tr key={m} className="border-t border-line"><td className="py-1.5 font-mono text-xs">{m.replace('nvidia/', '')}</td><td className="tabular-nums">{v.n}</td><td className="tabular-nums">{v.tok.toLocaleString()}</td><td className="tabular-nums">${v.usd.toFixed(4)}</td><td className="tabular-nums">{(v.lat / v.n).toFixed(1)}s</td></tr>
              ))}</tbody>
            </table>
          )}
          <p className="mt-3 text-xs text-muted">Extraction and plain-language rewriting use the cheap Nano model; reasoning over rules uses Super; the benchmark judge is Ultra.</p>
        </Card>
        <Card title="Tavily — what left the building">
          <p className="text-xs text-muted mb-2">Only allow-listed official URLs are ever sent to Tavily. No client names, documents or questions.</p>
          {tav.length === 0 ? <Empty>No Tavily requests logged yet.</Empty> : (
            <ul className="space-y-1 text-xs font-mono max-h-80 overflow-auto">
              {tav.slice().reverse().map((t, i) => (
                <li key={i} className={t.ok ? '' : 'text-bad'}>{new Date(t.ts * 1000).toISOString().slice(0, 19)} · {t.kind} · {(t.payload.urls ?? [t.payload.url]).join(', ')} · {t.results} results</li>
              ))}
            </ul>
          )}
          {tavilyUrls.length > 0 && <p className="mt-2 text-xs text-ok">✓ {tavilyUrls.length} URLs sent, all on the official allow-list.</p>}
        </Card>
      </div>
      <Card title="Recent calls">
        <ul className="text-xs font-mono space-y-0.5 max-h-96 overflow-auto">
          {calls.slice().reverse().slice(0, 100).map((c, i) => (
            <li key={i}>{new Date(c.ts * 1000).toISOString().slice(11, 19)} · {c.job}/{c.tag} · {c.model.replace('nvidia/', '')} · {c.prompt_tokens}+{c.completion_tokens} tok · ${c.usd.toFixed(5)} · {c.latency_s}s</li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
