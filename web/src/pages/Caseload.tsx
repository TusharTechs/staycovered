import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, type CaseSummary } from '../api'
import { Card, Empty, Spinner, StatusPill } from '../components/ui'

export default function Caseload() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.cases().then(setCases).catch(e => setErr(String(e))) }, [])

  const urgent = cases?.filter(c => c.status !== 'meets' && c.days_left !== null && c.days_left <= 14).length ?? 0
  const flagged = cases?.filter(c => c.flags.length).length ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <h1 className="font-serif text-3xl tracking-tight">Caseload</h1>
          <p className="text-muted text-sm mt-1">Nebraska Medicaid work requirements · sorted by days left to respond</p>
        </div>
        <div className="ml-auto flex gap-3">
          <Stat n={cases?.length} label="clients" />
          <Stat n={urgent} label="due in 14 days" tone="bad" />
          <Stat n={flagged} label="re-check: rules changed" tone="warn" />
        </div>
      </div>

      {err && <p className="text-bad text-sm">Could not load cases: {err}</p>}
      {!cases && !err && <Spinner label="Loading caseload" />}
      {cases && cases.length === 0 && <Empty>No cases yet. Run <code>uv run python -m demo.seed</code> to load the synthetic demo caseload.</Empty>}

      {cases && cases.length > 0 && (
        <Card>
          <table className="w-full text-sm">
            <caption className="sr-only">Clients and their status</caption>
            <thead className="text-left text-xs text-muted">
              <tr className="border-b border-line">
                <th className="py-2 font-medium">Client</th><th className="font-medium">Situation</th>
                <th className="font-medium">Status</th><th className="font-medium">Respond by</th><th className="font-medium">Flags</th>
              </tr>
            </thead>
            <tbody>
              {cases.map(c => (
                <tr key={c.id} className="border-b border-line last:border-0 hover:bg-paper">
                  <td className="py-3"><Link to={`/cases/${c.id}`} className="font-medium text-brand hover:underline">{c.client_name}</Link>
                    {c.synthetic && <span className="ml-2 text-[10px] uppercase tracking-wide text-muted">synthetic</span>}</td>
                  <td className="text-muted">{c.event.replace(/_/g, ' ')} · {fmtDate(c.event_date)}</td>
                  <td><StatusPill status={c.status} />{c.possible_exemptions > 0 && <span className="ml-2 text-xs text-warn">possible exemption</span>}</td>
                  <td>{c.cure_deadline ? <><span className="font-medium">{fmtDate(c.cure_deadline)}</span>
                    <span className={`ml-2 text-xs ${c.days_left! <= 7 ? 'text-bad font-semibold' : 'text-muted'}`}>{c.days_left} days</span></> : <span className="text-muted">—</span>}</td>
                  <td className="text-xs">{c.flags.map((f, i) => <div key={i} className="text-warn">⟳ {f.message}</div>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}

function Stat({ n, label, tone }: { n?: number; label: string; tone?: 'bad' | 'warn' }) {
  const c = tone === 'bad' ? 'text-bad' : tone === 'warn' ? 'text-warn' : 'text-ink'
  return (
    <div className="bg-white border border-line rounded-xl px-4 py-2 min-w-28">
      <div className={`text-2xl font-semibold tabular-nums ${c}`}>{n ?? '–'}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  )
}
