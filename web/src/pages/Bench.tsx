import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Empty, Spinner } from '../components/ui'

type SystemRow = { system: string; model: string; score: number; ci_low: number; ci_high: number; n: number; usd_per_question?: number; unsupported_rate?: number; citation_validity?: number }
type Results = { version?: string; split?: string; date?: string; n_questions?: number; systems?: SystemRow[]; by_category?: Record<string, Record<string, number>>; judge?: { model: string; human_agreement?: number | null }; notes?: string[] }

export default function Bench() {
  const [r, setR] = useState<Results | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.bench().then(x => setR(x as Results)).finally(() => setLoading(false)) }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-3xl tracking-tight">WorkReqBench</h1>
        <p className="text-muted text-sm mt-1 max-w-3xl">The first open benchmark for Medicaid work requirements. Every question has an "as of" date, and every grading criterion is cited to official text. Questions and rubrics were committed before the system was tuned; final numbers come from a held-out split.</p>
      </div>
      {loading && <Spinner />}
      {!loading && !r?.systems && <Empty>No results yet. Run <code>uv run python -m bench.run</code>.</Empty>}
      {r?.systems && (
        <>
          <Card title={`Results · ${r.split ?? ''} split · ${r.n_questions ?? ''} questions · ${r.date ?? ''}`}>
            <div className="space-y-3">
              {r.systems.map(s => (
                <div key={s.system}>
                  <div className="flex items-baseline gap-2 text-sm">
                    <span className="font-medium">{s.system}</span><span className="text-xs text-muted">{s.model}</span>
                    <span className="ml-auto tabular-nums font-semibold">{(s.score * 100).toFixed(1)}%</span>
                    <span className="text-xs text-muted tabular-nums">95% CI {(s.ci_low * 100).toFixed(1)}–{(s.ci_high * 100).toFixed(1)}</span>
                  </div>
                  <div className="relative mt-1 h-3 rounded-full bg-paper border border-line overflow-hidden" aria-hidden="true">
                    <div className="absolute inset-y-0 left-0 bg-brand/80" style={{ width: `${s.score * 100}%` }} />
                    <div className="absolute inset-y-0 bg-ink/20" style={{ left: `${s.ci_low * 100}%`, width: `${(s.ci_high - s.ci_low) * 100}%` }} />
                  </div>
                  <div className="mt-0.5 flex gap-4 text-[11px] text-muted">
                    {s.usd_per_question !== undefined && <span>${s.usd_per_question.toFixed(4)} / question</span>}
                    {s.citation_validity !== undefined && <span>{(s.citation_validity * 100).toFixed(0)}% citations verified verbatim</span>}
                    {s.unsupported_rate !== undefined && <span>{(s.unsupported_rate * 100).toFixed(0)}% "can't confirm"</span>}
                  </div>
                </div>
              ))}
            </div>
          </Card>
          {r.by_category && (
            <Card title="By category">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-muted"><th className="py-1 font-medium">Category</th>{r.systems.map(s => <th key={s.system} className="font-medium">{s.system}</th>)}</tr></thead>
                <tbody>{Object.entries(r.by_category).map(([cat, row]) => (
                  <tr key={cat} className="border-t border-line"><td className="py-1.5">{cat.replace(/_/g, ' ')}</td>{r.systems!.map(s => <td key={s.system} className="tabular-nums">{row[s.system] !== undefined ? `${(row[s.system] * 100).toFixed(0)}%` : '—'}</td>)}</tr>
                ))}</tbody>
              </table>
            </Card>
          )}
          <Card title="How it was built">
            <ul className="list-disc pl-5 text-sm space-y-1">
              {(r.notes ?? []).map((n, i) => <li key={i}>{n}</li>)}
              {r.judge && <li>Judge: {r.judge.model}{r.judge.human_agreement != null ? ` · agreement with human grading on a sample: ${(r.judge.human_agreement * 100).toFixed(0)}%` : ''}</li>}
            </ul>
          </Card>
        </>
      )}
    </div>
  )
}
