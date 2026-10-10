import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type Outcome, type Sandbox as SB, type SandboxTotals } from '../api'
import { Card, Cite, Spinner } from '../components/ui'
import { Strip } from '../components/Plan'
import { STATES, useJuris } from '../components/State'

const OUT: Record<Outcome, { label: string; cls: string; text: string }> = {
  covered: { label: 'Covered', cls: 'bg-ok', text: 'text-ok' },
  protected: { label: 'Exempt, confirmed from data', cls: 'bg-[#3056a6]', text: 'text-[#3056a6]' },
  depends: { label: 'Depends on an agency decision', cls: 'bg-warn', text: 'text-warn' },
  short: { label: 'Falls short', cls: 'bg-bad', text: 'text-bad' },
  paperwork: { label: 'At risk for paperwork only', cls: 'bg-frozen', text: 'text-frozen' },
}
const ORDER: Outcome[] = ['covered', 'protected', 'depends', 'paperwork', 'short']

function Bar({ t, label }: { t: SandboxTotals; label: string }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs text-muted"><span>{label}</span><span>{t.clients} clients</span></div>
      <div className="flex h-7 overflow-hidden rounded-lg border border-line" role="img"
        aria-label={`${label}: ` + ORDER.filter(o => t[o]).map(o => `${t[o]} ${OUT[o].label.toLowerCase()}`).join(', ')}>
        {ORDER.filter(o => t[o]).map(o => (
          <div key={o} className={`${OUT[o].cls} flex items-center justify-center text-xs font-semibold text-white transition-all duration-500`} style={{ width: `${(t[o] / t.clients) * 100}%` }}>{t[o]}</div>
        ))}
      </div>
    </div>
  )
}

export default function Sandbox() {
  const { state } = useJuris()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<SB | null>(null)
  const [err, setErr] = useState('')
  const levers = Object.fromEntries([...params.entries()].filter(([k]) => ['income_to_hours', 'household_income', 'required_months', 'ex_parte'].includes(k)))
  const key = JSON.stringify(levers)

  useEffect(() => { api.sandbox(state, levers).then(setData).catch(e => setErr(String(e))) }, [state, key])
  const set = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v === null) p.delete(k); else p.set(k, v)
    setParams(p, { replace: true })
  }

  if (err) return <p className="text-bad">{err}</p>
  if (!data) return <Spinner label="Running the rules" />
  const b = data.baseline.totals, s = data.scenario.totals
  const dm = s.covered_months - b.covered_months
  const changed = data.levers.some(l => l.value !== l.default)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-3xl tracking-tight">Policy sandbox</h1>
        <p className="mt-1 max-w-3xl text-muted">What if {STATES[state].name} chose differently? Each switch is a choice the federal rule leaves to states,
          cited below. The same engine re-runs every client in the caseload. The demo clients are synthetic, so this shows <em>how</em> each choice
          works, not how many real people it affects.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-2" data-tour="levers">
          {data.levers.map(l => {
            const on = l.value !== l.default
            return (
              <fieldset key={l.key} className={`rounded-xl border bg-white p-4 ${on ? 'border-brand' : 'border-line'}`}>
                <legend className="sr-only">{l.label}</legend>
                <div className="flex items-start gap-3">
                  <div className="flex-1">
                    <div className="text-sm font-semibold">{l.label}</div>
                    <p className="mt-0.5 text-xs text-muted">{l.help}</p>
                  </div>
                  {l.kind === 'bool' ? (
                    <button type="button" role="switch" aria-checked={!!l.value} aria-label={l.label}
                      onClick={() => set(l.key, l.value === l.default ? String(!l.value) : null)}
                      className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors ${l.value ? 'bg-brand' : 'bg-line'}`}>
                      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${l.value ? 'left-[22px]' : 'left-0.5'}`} />
                    </button>
                  ) : (
                    <div className="flex shrink-0 overflow-hidden rounded-lg border border-line" role="radiogroup" aria-label={l.label}>
                      {l.options!.map(o => (
                        <button type="button" key={o} role="radio" aria-checked={l.value === o}
                          onClick={() => set(l.key, o === l.default ? null : String(o))}
                          className={`px-3 py-1 text-sm ${l.value === o ? 'bg-brand text-white' : 'bg-white'}`}>{o}</button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="mt-2 text-[11px] text-muted">
                  {STATES[state].name} today: <b className="text-ink">{l.kind === 'bool' ? (l.default ? 'yes' : 'no') : l.default}</b>
                  <span className="ml-1">· Federal rule</span><Cite sourceId={l.source_id} quote={l.quote} label={l.fact_id.replace('US.', '')} />
                </div>
              </fieldset>
            )
          })}
          {changed && <button onClick={() => setParams(new URLSearchParams(), { replace: true })} className="text-sm text-brand underline">Reset to {STATES[state].name}'s published rules</button>}
        </div>

        <div className="space-y-5 lg:col-span-3">
          <Card title="The caseload, before and after">
            <div aria-live="polite" className="space-y-3">
              <Bar t={b} label={`${STATES[state].name}'s published rules`} />
              <Bar t={s} label={changed ? 'With your choices' : 'With your choices (flip a switch)'} />
              <div className="flex flex-wrap gap-3 pt-1 text-[11px] text-muted">
                {ORDER.map(o => <span key={o} className="inline-flex items-center gap-1"><span className={`h-2.5 w-2.5 rounded-sm ${OUT[o].cls}`} aria-hidden="true" />{OUT[o].label}</span>)}
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div className="rounded-lg bg-paper p-3"><div className="text-xs text-muted">Covered client-months, next 12 months</div>
                  <div className="text-2xl font-semibold tabular-nums">{s.covered_months}
                    {dm !== 0 && <span className={`ml-2 text-base ${dm > 0 ? 'text-ok' : 'text-bad'}`}>{dm > 0 ? '+' : ''}{dm}</span>}</div></div>
                <div className="rounded-lg bg-paper p-3"><div className="text-xs text-muted">At risk for paperwork only</div>
                  <div className="text-2xl font-semibold tabular-nums">{s.paperwork}
                    {s.paperwork !== b.paperwork && <span className={`ml-2 text-base ${s.paperwork < b.paperwork ? 'text-ok' : 'text-bad'}`}>{s.paperwork > b.paperwork ? '+' : ''}{s.paperwork - b.paperwork}</span>}</div></div>
              </div>
            </div>
          </Card>

          <Card title={data.flips.length ? `Who changes (${data.flips.length})` : 'Who changes'}>
            {data.flips.length === 0 ? <p className="text-sm text-muted">No one yet. Flip a switch on the left.</p> : (
              <ul className="space-y-2" aria-live="polite">
                {data.flips.map(f => (
                  <li key={f.id} className="rounded-lg border border-line p-3 text-sm">
                    <Link to={`/cases/${f.id}`} className="font-medium text-brand hover:underline">{f.client_name}</Link>
                    <span className="ml-2"><span className={OUT[f.before].text}>{OUT[f.before].label}</span> → <b className={OUT[f.after].text}>{OUT[f.after].label}</b></span>
                    {f.months_delta !== 0 && <span className={`ml-2 text-xs ${f.months_delta > 0 ? 'text-ok' : 'text-bad'}`}>{f.months_delta > 0 ? '+' : ''}{f.months_delta} covered months</span>}
                    <div className="text-xs text-muted">{f.why}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Every client, next 12 months">
            <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Every client's next 12 months under your choices">
              <table className="w-full min-w-[440px] border-separate border-spacing-y-1 text-sm">
                <thead><tr><th scope="col" className="w-28 sm:w-40 text-left text-xs font-normal text-muted">Client</th><th scope="col" className="text-left text-xs font-normal text-muted">Outcome and months</th></tr></thead>
                <tbody>
                  {data.scenario.clients.map(c => (
                    <tr key={c.id}>
                      <th scope="row" className="pr-3 text-left font-normal align-top"><Link to={`/cases/${c.id}`} className="text-brand hover:underline">{c.client_name}</Link></th>
                      <td>
                        <div className={`text-xs font-medium ${OUT[c.outcome].text}`}>{OUT[c.outcome].label}</div>
                        {c.outcome === 'protected' ? <div className="mt-1 h-5 rounded bg-[#3056a6]" title="Exempt all year" />
                          : c.months.length ? <div className="mt-1"><Strip months={c.months} size="sm" /></div>
                          : <div className="mt-1 text-xs text-muted">no documented month yet</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
