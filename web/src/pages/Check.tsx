import { useState } from 'react'
import { api, type Nearby, type PathOpt, type SelfCheckIn, type SelfCheckOut } from '../api'
import { CELL, Strip } from '../components/Plan'
import { Spinner } from '../components/ui'
import { STATES, useJuris, type Juris } from '../components/State'

type Lang = 'en' | 'es'
const money = (n: number) => `$${n.toLocaleString('en-US', { minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2 })}`
const num = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 1 })

const T = {
  en: {
    title: 'Will I keep my Medicaid?', lede: 'Medicaid now asks many adults to show 80 hours a month of work, volunteering, school or job training, or about $580 a month in income. Check where you stand in about a minute.',
    privacy: 'Nothing is saved. No name, no account. The check uses no AI: plain code applies the official rules. (The optional nearby search sends only your city.)',
    state: 'Where do you live?', usual: 'In a usual month…', job: 'Paid job', hours: 'hours', pay: 'pay before taxes ($)',
    gig: 'Gig apps (DoorDash, Uber, Instacart…)', gigHours: 'hours online', gigPay: 'payouts ($)', volunteer: 'Volunteering', training: 'Job training program',
    school: 'School', schoolHours: 'hours in class', credits: 'or credit hours this term', other: 'Other income, like unemployment ($)',
    partner: 'Spouse or partner you live with: their pay ($)', seasonal: 'My work is seasonal (more in some months than others)',
    any: 'Are any of these true for you?', check: 'Check',
    lang: 'Español', yourMonth: 'Your usual month', of: 'of', hoursLbl: 'hours', incomeLbl: 'income',
    status: {
      meets: ['Yes, your usual month meets the rule.', 'Keep proof each month, and answer any letter from the state on time.'],
      conditional_expenses: ['Probably, if your gig costs are low enough.', 'App payouts count after your costs, like gas and phone.'],
      conditional_household: ['Maybe. It depends on whether the state counts your partner\'s income.', 'Ask the state. From January 2027, household income counts.'],
      does_not_meet: ['Not yet, but you may be close.', 'Here is the smallest change that would get you there.'],
      insufficient_evidence: ['Tell us about a usual month.', 'Add your hours or income above, or check the questions about exemptions.'],
      exempt: ['You may not have to meet this rule at all.', 'Tell the state, and keep proof. The state decides.'],
    },
    fix: 'The smallest fix, each month', proven: 'Checked by re-running the official rules with this change.',
    forecast: 'Your next 12 months, if nothing changes', change: 'rules change',
    proof: 'What to keep as proof', reminders: 'Add monthly reminders to my calendar',
    near: 'Find places near me to get hours', city: 'Your city', vol: 'Volunteering', jobs: 'Job training', find: 'Search',
    nearNote: 'Only the city is sent to the search.',
    help: 'Questions? Contact', notDecision: 'This is not a decision. Only the state decides who keeps coverage.',
    words: { meets: 'meets', conditional: 'depends', does_not_meet: 'short', insufficient_evidence: 'no info', change: 'rules change' },
  },
  es: {
    title: '¿Mantendré mi Medicaid?', lede: 'Medicaid ahora pide a muchos adultos demostrar 80 horas al mes de trabajo, voluntariado, estudios o capacitación laboral, o unos $580 al mes de ingresos. Vea cómo está en un minuto.',
    privacy: 'No se guarda nada. Sin nombre, sin cuenta, sin IA: las reglas oficiales se aplican con código simple.',
    state: '¿Dónde vive?', usual: 'En un mes normal…', job: 'Trabajo pagado', hours: 'horas', pay: 'pago antes de impuestos ($)',
    gig: 'Apps de trabajo (DoorDash, Uber, Instacart…)', gigHours: 'horas conectado', gigPay: 'pagos ($)', volunteer: 'Voluntariado', training: 'Programa de capacitación laboral',
    school: 'Estudios', schoolHours: 'horas de clase', credits: 'o créditos este periodo', other: 'Otros ingresos, como desempleo ($)',
    partner: 'Cónyuge o pareja con quien vive: su pago ($)', seasonal: 'Mi trabajo es de temporada (más en unos meses que en otros)',
    any: '¿Alguna de estas situaciones es su caso?', check: 'Revisar',
    lang: 'English', yourMonth: 'Su mes normal', of: 'de', hoursLbl: 'horas', incomeLbl: 'ingresos',
    status: {
      meets: ['Sí, su mes normal cumple la regla.', 'Guarde comprobantes cada mes y responda a tiempo cualquier carta del estado.'],
      conditional_expenses: ['Probablemente, si sus gastos del trabajo por app son bajos.', 'Los pagos de las apps cuentan después de sus gastos, como gasolina y teléfono.'],
      conditional_household: ['Tal vez. Depende de si el estado cuenta los ingresos de su pareja.', 'Pregunte al estado. Desde enero de 2027, se cuentan los ingresos del hogar.'],
      does_not_meet: ['Todavía no, pero puede estar cerca.', 'Este es el cambio más pequeño para lograrlo.'],
      insufficient_evidence: ['Cuéntenos sobre un mes normal.', 'Agregue sus horas o ingresos arriba, o revise las preguntas sobre exenciones.'],
      exempt: ['Puede que no tenga que cumplir esta regla.', 'Avise al estado y guarde comprobantes. El estado decide.'],
    },
    fix: 'El cambio más pequeño, cada mes', proven: 'Comprobado aplicando de nuevo las reglas oficiales con este cambio.',
    forecast: 'Sus próximos 12 meses, si nada cambia', change: 'cambian las reglas',
    proof: 'Qué guardar como comprobante', reminders: 'Agregar recordatorios mensuales a mi calendario',
    near: 'Buscar lugares cerca para conseguir horas', city: 'Su ciudad', vol: 'Voluntariado', jobs: 'Capacitación laboral', find: 'Buscar',
    nearNote: 'Solo se envía la ciudad a la búsqueda.',
    help: '¿Preguntas? Contacte a', notDecision: 'Esto no es una decisión. Solo el estado decide quién mantiene la cobertura.',
    words: { meets: 'cumple', conditional: 'depende', does_not_meet: 'falta', insufficient_evidence: 'sin datos', change: 'cambian las reglas' },
  },
}

const EXEMPT: { key: string; en: string; es: string }[] = [
  { key: 'pregnant_or_postpartum', en: 'I\'m pregnant or recently had a baby', es: 'Estoy embarazada o tuve un bebé hace poco' },
  { key: 'caretaker_of_young_child', en: 'I care for a child 13 or younger', es: 'Cuido a un niño de 13 años o menos' },
  { key: 'caretaker_of_disabled_person', en: 'I care for someone with a disability', es: 'Cuido a una persona con discapacidad' },
  { key: 'serious_medical_condition', en: 'I have a serious or complex medical condition', es: 'Tengo una condición médica grave o compleja' },
  { key: 'veteran_total_disability', en: 'I\'m a veteran with a total disability rating', es: 'Soy veterano/a con una calificación de discapacidad total' },
  { key: 'american_indian_alaska_native', en: 'I\'m American Indian or Alaska Native', es: 'Soy indígena americano/a o nativo/a de Alaska' },
  { key: 'in_sud_treatment', en: 'I\'m in treatment for substance use', es: 'Estoy en tratamiento por uso de sustancias' },
  { key: 'meets_snap_or_tanf_work_rules', en: 'I meet SNAP or TANF work rules', es: 'Cumplo las reglas de trabajo de SNAP o TANF' },
  { key: 'recently_incarcerated', en: 'I was released from jail or prison in the last 3 months', es: 'Salí de la cárcel o prisión en los últimos 3 meses' },
]

function fixText(p: PathOpt, lang: Lang): string {
  const a = p.amount ?? 0
  if (p.kind === 'hours') return lang === 'en'
    ? `${num(a)} more hours a month of work, volunteering, school or job training (about ${num(p.per_week ?? 0)} a week)`
    : `${num(a)} horas más al mes de trabajo, voluntariado, estudios o capacitación (unas ${num(p.per_week ?? 0)} por semana)`
  if (p.kind === 'income') {
    const base = lang === 'en' ? `${money(a)} more income a month` : `${money(a)} más de ingresos al mes`
    if (!p.paid_hours || !p.wage) return base
    return lang === 'en' ? `${base}: about ${p.paid_hours} more paid hours at ${money(p.wage)}/hr` : `${base}: unas ${p.paid_hours} horas pagadas más a ${money(p.wage)}/hora`
  }
  if (p.kind === 'expenses') return lang === 'en'
    ? `Keep receipts or a mileage log. If your gig costs are ${money(a)} or less a month, you meet the rule.`
    : `Guarde recibos o un registro de millas. Si sus gastos son ${money(a)} o menos al mes, cumple la regla.`
  if (p.kind === 'household') return lang === 'en'
    ? 'Ask the state to count your partner\'s income. From January 2027 it counts automatically.'
    : 'Pida al estado que cuente los ingresos de su pareja. Desde enero de 2027 se cuentan automáticamente.'
  return p.title
}

const PROOF: Record<string, { en: string; es: string; when: (x: SelfCheckIn) => boolean }> = {
  job: { en: 'Pay stubs for every pay period', es: 'Talones de pago de cada periodo', when: x => x.wages > 0 || x.work_hours > 0 },
  gig: { en: 'The app\'s weekly or monthly earnings statements, plus a log of gas and other costs', es: 'Los resúmenes de ganancias de la app, más un registro de gasolina y otros gastos', when: x => x.gig_payouts > 0 || x.gig_hours > 0 },
  vol: { en: 'A signed letter from where you volunteer, with your hours each month', es: 'Una carta firmada del lugar donde es voluntario/a, con sus horas de cada mes', when: x => x.volunteer_hours > 0 },
  train: { en: 'An attendance record or letter from the training program', es: 'Un registro de asistencia o carta del programa de capacitación', when: x => x.training_hours > 0 },
  school: { en: 'A letter or schedule from your school showing your classes or credit hours', es: 'Una carta u horario de su escuela con sus clases o créditos', when: x => x.school_hours > 0 || x.credits > 0 },
  partner: { en: 'Your partner\'s pay stubs', es: 'Los talones de pago de su pareja', when: x => x.partner_income > 0 },
}

function ics(out: SelfCheckOut, lang: Lang): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//StayCovered//Self-check//EN', 'CALSCALE:GREGORIAN']
  out.forecast.slice(1, 7).forEach((m, i) => {
    const [y, mo] = m.month.split('-').map(Number)
    const title = lang === 'en' ? 'Medicaid: save proof of last month\'s hours and income' : 'Medicaid: guarde comprobantes de horas e ingresos del mes pasado'
    lines.push('BEGIN:VEVENT', `UID:selfcheck-${m.month}-${i}@staycovered`, `DTSTAMP:${y}${pad(mo)}01T000000Z`,
      `DTSTART;VALUE=DATE:${y}${pad(mo)}01`, `SUMMARY:${title}`, 'END:VEVENT')
  })
  lines.push('END:VCALENDAR')
  return lines.join('\r\n') + '\r\n'
}

function Field({ label, value, onChange, step = 1, id }: { label: string; value: number; onChange: (v: number) => void; step?: number; id: string }) {
  return (
    <label htmlFor={id} className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span>{label}</span>
      <input id={id} type="number" inputMode="decimal" min={0} step={step} value={value || ''} placeholder="0"
        onChange={e => onChange(Math.max(0, Number(e.target.value) || 0))}
        className="w-28 rounded-lg border border-line bg-white px-3 py-2 text-right tabular-nums" />
    </label>
  )
}

export default function Check() {
  const { state, setState } = useJuris()
  const [lang, setLang] = useState<Lang>('en')
  const t = T[lang]
  const [x, setX] = useState<SelfCheckIn>({ jurisdiction: state, work_hours: 0, wages: 0, gig_hours: 0, gig_payouts: 0, volunteer_hours: 0,
    training_hours: 0, school_hours: 0, credits: 0, other_income: 0, partner_income: 0, seasonal: false, exemptions: {}, serious_medical_condition: null })
  const [out, setOut] = useState<SelfCheckOut | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [city, setCity] = useState('')
  const [near, setNear] = useState<Nearby | null>(null)
  const [nearErr, setNearErr] = useState('')
  const set = (k: keyof SelfCheckIn) => (v: number) => setX(o => ({ ...o, [k]: v }))
  const juris = (j: Juris) => { setState(j); setX(o => ({ ...o, jurisdiction: j })); setOut(null) }

  const run = async () => {
    setBusy(true); setErr('')
    try { setOut(await api.selfcheck({ ...x, jurisdiction: state })) } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }
  const findNear = async (kind: 'volunteer' | 'work_program') => {
    setNearErr(''); setNear(null)
    try { setNear(await api.nearbyCity(`${city.trim()}, ${state}`, kind)) } catch (e) { setNearErr(String(e)) }
  }

  const statusKey = !out ? null
    : out.exemptions.length && out.status !== 'meets' ? 'exempt'
    : out.status === 'conditional' ? (out.numbers.expense_headroom != null ? 'conditional_expenses' : 'conditional_household')
    : out.status
  const tone = !out ? '' : out.status === 'meets' ? 'border-ok/40 bg-ok-soft' : out.status === 'does_not_meet' ? 'border-bad/30 bg-bad-soft' : 'border-warn/40 bg-warn-soft'
  const changes = out?.forecast.filter(m => m.changes.length) ?? []

  return (
    <div className="mx-auto max-w-xl space-y-6" lang={lang} data-tour="selfcheck">
      <div className="flex items-start gap-3 pt-2">
        <div>
          <h1 className="font-serif text-3xl md:text-4xl tracking-tight">{t.title}</h1>
          <p className="mt-2 text-muted leading-relaxed">{t.lede}</p>
        </div>
        <button onClick={() => setLang(lang === 'en' ? 'es' : 'en')} lang={lang === 'en' ? 'es' : 'en'}
          className="ml-auto shrink-0 rounded-full border border-line bg-white px-3 py-1 text-sm hover:border-brand">{t.lang}</button>
      </div>
      <p className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand">🔒 {t.privacy}</p>

      <form className="space-y-5" onSubmit={e => { e.preventDefault(); run() }}>
        <fieldset className="min-w-0 rounded-xl border border-line bg-white p-4">
          <legend className="px-1 text-sm font-semibold">{t.state}</legend>
          <div className="flex gap-2">
            {(Object.keys(STATES) as Juris[]).map(j => (
              <button type="button" key={j} onClick={() => juris(j)} aria-pressed={state === j}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm ${state === j ? 'border-brand bg-brand text-white' : 'border-line bg-white'}`}>{STATES[j].name}</button>
            ))}
          </div>
        </fieldset>

        <fieldset className="min-w-0 rounded-xl border border-line bg-white p-4">
          <legend className="px-1 text-sm font-semibold">{t.usual}</legend>
          <div className="divide-y divide-line">
            <div className="pb-2"><div className="text-sm font-medium">{t.job}</div>
              <Field id="wh" label={t.hours} value={x.work_hours} onChange={set('work_hours')} />
              <Field id="wp" label={t.pay} value={x.wages} onChange={set('wages')} step={0.01} /></div>
            <div className="py-2"><div className="text-sm font-medium">{t.gig}</div>
              <Field id="gh" label={t.gigHours} value={x.gig_hours} onChange={set('gig_hours')} />
              <Field id="gp" label={t.gigPay} value={x.gig_payouts} onChange={set('gig_payouts')} step={0.01} /></div>
            <div className="py-2">
              <Field id="vh" label={`${t.volunteer} (${t.hours})`} value={x.volunteer_hours} onChange={set('volunteer_hours')} />
              <Field id="th" label={`${t.training} (${t.hours})`} value={x.training_hours} onChange={set('training_hours')} /></div>
            <div className="py-2"><div className="text-sm font-medium">{t.school}</div>
              <Field id="sh" label={t.schoolHours} value={x.school_hours} onChange={set('school_hours')} />
              <Field id="cr" label={t.credits} value={x.credits} onChange={set('credits')} /></div>
            <div className="pt-2">
              <Field id="oi" label={t.other} value={x.other_income} onChange={set('other_income')} step={0.01} />
              <Field id="pi" label={t.partner} value={x.partner_income} onChange={set('partner_income')} step={0.01} />
              <label className="mt-1 flex items-center gap-2 text-sm"><input type="checkbox" checked={x.seasonal} onChange={e => setX(o => ({ ...o, seasonal: e.target.checked }))} />{t.seasonal}</label>
            </div>
          </div>
        </fieldset>

        <fieldset className="min-w-0 rounded-xl border border-line bg-white p-4">
          <legend className="px-1 text-sm font-semibold">{t.any}</legend>
          <div className="space-y-1.5">
            {EXEMPT.map(e => {
              const on = e.key === 'serious_medical_condition' ? !!x.serious_medical_condition : !!x.exemptions[e.key]
              return (
                <label key={e.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={on} onChange={ev => setX(o => e.key === 'serious_medical_condition'
                    ? { ...o, serious_medical_condition: ev.target.checked || null }
                    : { ...o, exemptions: { ...o.exemptions, [e.key]: ev.target.checked || null } })} />
                  {e[lang]}
                </label>
              )
            })}
          </div>
        </fieldset>

        <button disabled={busy} className="w-full rounded-xl bg-brand px-5 py-3 text-base font-semibold text-white hover:opacity-90 disabled:opacity-50">
          {t.check}
        </button>
      </form>

      <div aria-live="polite" className="space-y-5">
        {busy && <Spinner label="…" />}
        {err && <p role="alert" className="text-sm text-bad">{err}</p>}
        {out && statusKey && (
          <>
            <section className={`rounded-2xl border p-5 ${tone}`} aria-label={t.yourMonth}>
              <h2 className="font-serif text-2xl leading-snug">{t.status[statusKey as keyof typeof t.status][0]}</h2>
              <p className="mt-1 text-sm">{t.status[statusKey as keyof typeof t.status][1]}</p>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-white/70 p-3"><div className="text-xs text-muted">{t.hoursLbl}</div>
                  <div className="text-xl font-semibold tabular-nums">{num(out.numbers.activity_hours)} <span className="text-sm font-normal text-muted">{t.of} {num(out.numbers.hours_required)}</span></div></div>
                <div className="rounded-lg bg-white/70 p-3"><div className="text-xs text-muted">{t.incomeLbl}</div>
                  <div className="text-xl font-semibold tabular-nums">{money(out.numbers.own_income + out.numbers.gig_payouts)} <span className="text-sm font-normal text-muted">{t.of} {money(out.numbers.threshold)}</span></div></div>
              </div>
            </section>

            {out.plan.length > 0 && (
              <section className="rounded-xl border border-line bg-white p-4">
                <h2 className="text-sm font-semibold">{t.fix}</h2>
                <ul className="mt-2 space-y-2">
                  {out.plan.map((p, i) => <li key={i} className="rounded-lg border border-line p-3 text-sm">{fixText(p, lang)}
                    {p.proven && <div className="mt-1 text-[11px] text-ok">✓ {t.proven}</div>}</li>)}
                </ul>
                {out.plan.some(p => p.kind === 'hours') && (
                  <div className="mt-3 border-t border-line pt-3">
                    <div className="text-sm font-medium">{t.near}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <label htmlFor="city" className="sr-only">{t.city}</label>
                      <input id="city" value={city} onChange={e => setCity(e.target.value)} placeholder={state === 'NE' ? 'Omaha' : 'Billings'}
                        className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 text-sm" />
                      <button type="button" disabled={!city.trim()} onClick={() => findNear('volunteer')} className="rounded-lg border border-brand/40 px-3 py-2 text-sm text-brand disabled:opacity-50">{t.vol}</button>
                      <button type="button" disabled={!city.trim()} onClick={() => findNear('work_program')} className="rounded-lg border border-brand/40 px-3 py-2 text-sm text-brand disabled:opacity-50">{t.jobs}</button>
                    </div>
                    <p className="mt-1 text-[11px] text-muted">{t.nearNote}</p>
                    {nearErr && <p role="alert" className="mt-1 text-xs text-bad">{nearErr}</p>}
                    {near && (
                      <ul className="mt-2 space-y-2">
                        {near.options.map(o => <li key={o.url} className="text-sm"><a href={o.url} target="_blank" rel="noreferrer" className="font-medium text-brand underline">{o.name} ↗</a>
                          <div className="text-xs text-muted">{o.what}</div></li>)}
                        {near.options.length === 0 && <li className="text-xs text-muted">—</li>}
                      </ul>
                    )}
                  </div>
                )}
              </section>
            )}

            {out.forecast.length > 0 && (
              <section className="rounded-xl border border-line bg-white p-4">
                <h2 className="mb-3 text-sm font-semibold">{t.forecast}</h2>
                <Strip months={out.forecast} changes={new Set(changes.map(c => c.month))} words={t.words} locale={lang === 'en' ? 'en-US' : 'es-US'} />
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted">
                  {(['meets', 'conditional', 'does_not_meet'] as const).map(s => <span key={s} className="inline-flex items-center gap-1"><span className={`h-2.5 w-2.5 rounded-sm ${CELL[s]}`} aria-hidden="true" />{t.words[s]}</span>)}
                  {changes.length > 0 && <span><span className="text-brand" aria-hidden="true">◆</span> {t.change}</span>}
                </div>
              </section>
            )}

            <section className="rounded-xl border border-line bg-white p-4">
              <h2 className="text-sm font-semibold">{t.proof}</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {Object.values(PROOF).filter(p => p.when(x)).map(p => <li key={p.en}>{p[lang]}</li>)}
              </ul>
              <a download="medicaid-reminders.ics" href={`data:text/calendar;charset=utf-8,${encodeURIComponent(ics(out, lang))}`}
                className="mt-3 inline-block rounded-lg border border-brand/40 px-3 py-2 text-sm text-brand hover:bg-brand-soft">📅 {t.reminders}</a>
            </section>

            <p className="text-xs text-muted">{t.help} {out.agency}. {t.notDecision}</p>
          </>
        )}
      </div>
    </div>
  )
}
