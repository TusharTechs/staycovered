import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDate, type CaseRecord, type MonthResult, type Worksheet } from '../api'
import { Card, Spinner, StatusPill } from '../components/ui'
import AskBox from '../components/AskBox'

const PATH: Record<string, string> = {
  hours: '80+ activity hours', household_income: 'household income ≥ threshold',
  combined: 'activity hours + income converted to hours', seasonal_average: 'seasonal 6-month average',
}

export default function CasePage() {
  const { id } = useParams()
  const [data, setData] = useState<{ record: CaseRecord; worksheet: Worksheet } | null>(null)
  const [err, setErr] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const load = () => api.case(id!).then(setData).catch(e => setErr(String(e)))
  useEffect(() => { load() }, [id])

  if (err) return <p className="text-bad">{err}</p>
  if (!data) return <Spinner label="Loading case" />
  const { record: rec, worksheet: ws } = data
  const docs = Object.fromEntries(rec.documents.map(d => [d.id, d]))

  return (
    <div className="space-y-5">
      <div className="text-sm"><Link to="/" className="text-brand hover:underline">← Caseload</Link></div>
      <div className="flex flex-wrap items-start gap-4">
        <div>
          <h1 className="font-serif text-3xl tracking-tight">{rec.client_name}</h1>
          <p className="text-muted text-sm mt-1">
            {rec.case.event.replace(/_/g, ' ')} · {fmtDate(rec.case.event_date)} · household of {rec.case.household.length}
            {rec.synthetic && <span className="ml-2 rounded bg-paper border border-line px-1.5 text-[10px] uppercase">synthetic demo</span>}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {ws.cure_deadline && (
            <div className="rounded-xl border border-bad/30 bg-bad-soft px-4 py-2 text-bad">
              <div className="text-xs">Respond by</div>
              <div className="text-lg font-semibold">{fmtDate(ws.cure_deadline)}</div>
            </div>
          )}
          <a href={`/api/cases/${rec.case.id}/packet.pdf`} className="rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white hover:opacity-90">Download packet (PDF)</a>
        </div>
      </div>

      {rec.flags.length > 0 && (
        <div role="alert" className="rounded-xl border border-warn/40 bg-warn-soft p-3 text-sm text-warn">
          {rec.flags.map((f, i) => <div key={i}>⟳ {f.message}</div>)}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-5">
          {rec.notice && <NoticeCard notice={rec.notice} caseId={rec.case.id} />}

          <Card title="Attestation worksheet" actions={<span className="text-xs text-muted">rules in force {fmtDate(ws.as_of)}</span>}>
            <p className="text-xs text-muted mb-3">Arithmetic is done by code, never by the AI. Click a month to see every number's source.</p>
            <div className="space-y-2">
              {ws.results.map(r => <MonthRow key={r.month} r={r} open={open === r.month} onToggle={() => setOpen(open === r.month ? null : r.month)} docs={docs} />)}
            </div>
            {ws.warnings.length > 0 && (
              <details className="mt-3 text-xs text-muted"><summary className="cursor-pointer">Assumptions ({ws.warnings.length})</summary>
                <ul className="list-disc pl-5 mt-1 space-y-0.5">{ws.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></details>
            )}
          </Card>

          <Card title="Ask about this case's rules">
            <AskBox asOf={ws.as_of} suggestions={[
              'Does my client\'s spouse\'s income count toward the $580?',
              'How long does my client have to respond to a noncompliance notice?',
              'What documents can prove gig work hours in Nebraska?',
            ]} />
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Household">
            <ul className="space-y-1 text-sm">
              {rec.case.household.map(m => (
                <li key={m.id} className="flex justify-between"><span>{m.name}{m.id === rec.case.client_id && <span className="text-muted"> (client)</span>}</span>
                  <span className="text-muted text-xs">{m.age ?? '?'} · {m.applicable_adult ? 'subject to rule' : 'not subject'}{m.seasonal_worker ? ' · seasonal' : ''}</span></li>
              ))}
            </ul>
          </Card>

          {ws.exemptions.length > 0 && (
            <Card title="Possible exemptions">
              <ul className="space-y-2 text-sm">{ws.exemptions.map((e, i) => (
                <li key={i} className="rounded-lg bg-warn-soft p-2"><div className="font-medium text-warn">{e.label}</div><div className="text-xs text-ink mt-0.5">{e.action}</div></li>
              ))}</ul>
            </Card>
          )}

          <Card title={`Documents (${rec.documents.length})`} actions={<button className="text-xs text-brand hover:underline" onClick={() => setAdding(a => !a)}>{adding ? 'Close' : '+ Add document'}</button>}>
            {adding && <AddDoc caseId={rec.case.id} members={rec.case.household} onDone={() => { setAdding(false); load() }} />}
            <ul className="space-y-2 text-sm">
              {rec.documents.map(d => (
                <li key={d.id}>
                  <details>
                    <summary className="cursor-pointer"><span className="font-medium">{d.name}</span> <span className="text-xs text-muted">{d.kind}</span></summary>
                    <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-paper p-2 text-[11px]">{d.text}</pre>
                    {d.problems.map((p, i) => <div key={i} className="text-xs text-bad">{p}</div>)}
                  </details>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}

function MonthRow({ r, open, onToggle, docs }: { r: MonthResult; open: boolean; onToggle: () => void; docs: Record<string, { name: string }> }) {
  const label = useMemo(() => new Date(r.month + '-01T00:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' }), [r.month])
  return (
    <div className="rounded-lg border border-line">
      <button onClick={onToggle} aria-expanded={open} className="w-full flex flex-wrap items-center gap-3 px-3 py-2.5 text-left hover:bg-paper">
        <span className="font-medium w-36">{label}</span>
        <StatusPill status={r.status} />
        {r.path && <span className="text-xs text-muted">via {PATH[r.path]}</span>}
        <span className="ml-auto flex gap-4 text-xs tabular-nums text-muted">
          <span><b className="text-ink">{r.activity_hours}</b> hrs</span>
          <span><b className="text-ink">${r.household_income.toLocaleString()}</b> / ${r.income_threshold} household income</span>
          <span><b className="text-ink">{r.combined_hours}</b> combined hrs</span>
        </span>
      </button>
      {r.status === 'depends_on_expenses' && r.expense_headroom !== null && (
        <div className="border-t border-line bg-warn-soft/60 px-3 py-2 text-sm">
          <b>Meets if business expenses for the month are ${r.expense_headroom.toLocaleString(undefined, { maximumFractionDigits: 2 })} or less.</b>{' '}
          <span className="text-muted">${r.gross_self_employment.toLocaleString()} is gig payout before fuel, mileage and phone costs. Ask the client for a mileage log or expense records.</span>
        </div>
      )}
      {open && (
        <div className="border-t border-line px-3 py-3 text-sm space-y-3">
          {r.contributions.length === 0 && <p className="text-muted text-xs">No documents cover this month yet.</p>}
          {r.contributions.length > 0 && (
            <table className="w-full text-xs">
              <thead className="text-muted text-left"><tr><th className="font-medium py-1">Counted</th><th className="font-medium">Type</th><th className="font-medium">From</th><th className="font-medium">Exact text in the document</th></tr></thead>
              <tbody>{r.contributions.map(c => (
                <tr key={c.entry_id} className="border-t border-line align-top">
                  <td className="py-1.5 tabular-nums">{c.kind.includes('hours') ? `${c.amount} hrs` : `$${c.amount.toLocaleString()}`}{c.share < 1 && <span className="text-muted"> ({Math.round(c.share * 100)}% of period)</span>}</td>
                  <td>{c.kind.replace(/_/g, ' ')}</td>
                  <td>{docs[c.doc_id ?? '']?.name ?? c.doc_id}</td>
                  <td><mark className="cite">{c.span}</mark></td>
                </tr>
              ))}</tbody>
            </table>
          )}
          {r.ambiguities.length > 0 && (
            <div className="rounded bg-warn-soft p-2 text-xs text-warn"><div className="font-medium mb-0.5">Confirm with the agency</div>
              <ul className="list-disc pl-4 space-y-0.5">{r.ambiguities.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
          )}
          <div className="text-[11px] text-muted">Rules used: {r.facts_used.join(', ') || 'defaults'}</div>
        </div>
      )}
    </div>
  )
}

function NoticeCard({ notice, caseId }: { notice: Record<string, unknown>; caseId: string }) {
  const items = (notice.requested_items as string[]) ?? []
  const how = (notice.how_to_respond as string[]) ?? []
  const [view, setView] = useState<'nav' | 'en' | 'es'>('nav')
  const [ex, setEx] = useState<Record<string, Awaited<ReturnType<typeof api.explain>>>>({})
  const [busy, setBusy] = useState(false)
  const pick = async (v: 'nav' | 'en' | 'es') => {
    setView(v)
    if (v !== 'nav' && !ex[v]) { setBusy(true); try { const r = await api.explain(caseId, v); setEx(e => ({ ...e, [v]: r })) } finally { setBusy(false) } }
  }
  const tabs = [['nav', 'Navigator'], ['en', 'For the client'], ['es', 'Para el cliente (español)']] as const
  const cur = view !== 'nav' ? ex[view] : null
  return (
    <Card title="What the notice says" actions={
      <div role="tablist" className="flex gap-1">{tabs.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={view === k} onClick={() => pick(k)}
          className={`rounded-md px-2 py-1 text-xs ${view === k ? 'bg-brand text-white' : 'text-muted hover:bg-paper'}`}>{l}</button>
      ))}</div>}>
      {view !== 'nav' && (busy && !cur ? <Spinner label="Rewriting in plain language" /> : cur && (
        <div className="space-y-2 text-[15px] leading-relaxed" lang={view}>
          <p>{cur.summary}</p>
          {cur.deadline_sentence && <p className="font-semibold text-bad">{cur.deadline_sentence}</p>}
          <ol className="list-decimal pl-5 space-y-1">{cur.what_to_do.map((x, i) => <li key={i}>{x}</li>)}</ol>
          <ul className="text-sm text-muted list-disc pl-5">{cur.keep_in_mind.map((x, i) => <li key={i}>{x}</li>)}</ul>
          <details className="text-xs text-muted"><summary className="cursor-pointer">Based on these exact words in the letter</summary>
            <ul className="mt-1 space-y-1">{cur.spans.map((x, i) => <li key={i}><mark className="cite">{x}</mark></li>)}</ul></details>
        </div>
      ))}
      {view === 'nav' && <>
      <div className="grid sm:grid-cols-3 gap-3 text-sm">
        <div><div className="text-xs text-muted">Type</div><div className="font-medium">{String(notice.notice_type ?? '').replace(/_/g, ' ')}</div></div>
        <div><div className="text-xs text-muted">Dated</div><div className="font-medium">{fmtDate(notice.notice_date as string)}</div></div>
        <div><div className="text-xs text-muted">Respond by (as stated)</div><div className="font-medium">{fmtDate(notice.respond_by as string)}</div></div>
      </div>
      {items.length > 0 && <><div className="mt-3 text-xs text-muted">They are asking for</div><ul className="list-disc pl-5 text-sm">{items.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
      {how.length > 0 && <><div className="mt-3 text-xs text-muted">How to respond</div><ul className="list-disc pl-5 text-sm">{how.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
      </>}
    </Card>
  )
}

function AddDoc({ caseId, members, onDone }: { caseId: string; members: CaseRecord['case']['household']; onDone: () => void }) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState('income')
  const [member, setMember] = useState(members[0]?.id ?? '')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const submit = async () => {
    setBusy(true); setErr('')
    try { await api.addDoc(caseId, { name: name || 'Document', kind, member_id: member, text }); onDone() }
    catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }
  return (
    <div className="mb-3 space-y-2 rounded-lg bg-paper p-3 text-sm">
      <label className="block">Name<input className="mt-0.5 w-full rounded border border-line px-2 py-1" value={name} onChange={e => setName(e.target.value)} /></label>
      <div className="flex gap-2">
        <label className="flex-1">Type<select className="mt-0.5 w-full rounded border border-line px-2 py-1" value={kind} onChange={e => setKind(e.target.value)}>
          <option value="income">Income / activity</option><option value="notice">State notice</option></select></label>
        <label className="flex-1">Whose<select className="mt-0.5 w-full rounded border border-line px-2 py-1" value={member} onChange={e => setMember(e.target.value)}>
          {members.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      </div>
      <label className="block">Text of the document<textarea rows={6} className="mt-0.5 w-full rounded border border-line px-2 py-1 font-mono text-xs" value={text} onChange={e => setText(e.target.value)} /></label>
      {err && <p className="text-bad text-xs">{err}</p>}
      <button disabled={busy || !text} onClick={submit} className="rounded bg-brand px-3 py-1.5 text-white disabled:opacity-50">{busy ? 'Reading with Nemotron…' : 'Extract'}</button>
    </div>
  )
}
