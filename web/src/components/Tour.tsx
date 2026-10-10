import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useJuris } from './State'

export type Step = { path: string; target: string; title: string; body: string }

export const STEPS: Step[] = [
  { path: '/caseload', target: 'caseload', title: '1 · A navigator\'s caseload', body: 'Six synthetic Nebraska clients facing Medicaid work requirements, sorted by how many days are left to respond.' },
  { path: '/cases/maria-lopez', target: 'conditional', title: '2 · The honest answer', body: 'Nemotron read Maria\'s two gig-app statements; plain code did the math. She is 15 hours short and her $813 is gig payout before expenses, so: she qualifies only if her expenses were $233.31 or less. Click the month to see every number\'s source line.' },
  { path: '/cases/maria-lopez', target: 'notice', title: '3 · In the client\'s language', body: 'The state\'s notice, rewritten at a 6th-grade level in English or Spanish, tied to the exact words of the letter.' },
  { path: '/cases/maria-lopez', target: 'form', title: '4 · The real state form', body: 'Nebraska\'s actual MLTC-118 declaration, pre-filled only where evidence exists, with a reason for every field.' },
  { path: '/time-machine?date=2026-05-12', target: 'timeline', title: '5 · Rules move. Models don\'t.', body: 'Jump through the real 2026 timeline. Here, Nebraska\'s FAQ started saying household income "may count" — drift-watch caught the change and flagged the cases that depend on it.' },
  { path: '/time-machine?date=2026-05-12', target: 'changes', title: '6 · What changed, and who to re-check', body: 'Each change is detected from dated official snapshots (Tavily + archives), summarised by Nemotron, and linked to affected clients.' },
  { path: '/time-machine?date=2026-10-10', target: 'ask', title: '7 · Frozen model vs. rules as of a date', body: 'Ask the spouse-income question: the frozen model answers from memory; StayCovered answers from the official text in force on the chosen date, quoted verbatim.' },
  { path: '/bench', target: 'results', title: '8 · Measured, not claimed', body: 'WorkReqBench: 171 dated questions, rubrics cited to official text, frozen before tuning. Grounded Nemotron vs. a frontier model answering from memory — and the ranking holds under three different graders.' },
  { path: '/under-the-hood', target: 'models', title: '9 · Under the hood', body: 'Nano reads documents, Super reasons, Ultra grades — all NVIDIA Nemotron on Nebius Token Factory. Tavily only ever sees official URLs, never client data.' },
]

type Ctx = { active: boolean; index: number; start: () => void; stop: () => void; next: () => void; back: () => void }
const TourCtx = createContext<Ctx | null>(null)
export const useTour = () => useContext(TourCtx)!

const SEEN = 'staycovered-tour-seen'

export function TourProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState(false)
  const [index, setIndex] = useState(0)
  const nav = useNavigate()
  const { setState } = useJuris()
  const go = useCallback((i: number) => { setIndex(i); nav(STEPS[i].path) }, [nav])
  const start = useCallback(() => { setState('NE'); setActive(true); go(0) }, [go, setState])
  const stop = useCallback(() => { setActive(false); try { localStorage.setItem(SEEN, '1') } catch { /* private mode */ } }, [])
  const next = useCallback(() => (index + 1 < STEPS.length ? go(index + 1) : stop()), [index, go, stop])
  const back = useCallback(() => index > 0 && go(index - 1), [index, go])
  return (
    <TourCtx.Provider value={{ active, index, start, stop, next, back }}>
      {children}
      {active && <Overlay step={STEPS[index]} index={index} next={next} back={back} stop={stop} />}
    </TourCtx.Provider>
  )
}

export function tourSeen(): boolean {
  try { return localStorage.getItem(SEEN) === '1' } catch { return true }
}

function Overlay({ step, index, next, back, stop }: { step: Step; index: number; next: () => void; back: () => void; stop: () => void }) {
  const [rect, setRect] = useState<DOMRect | null>(null)
  const loc = useLocation()

  useLayoutEffect(() => {
    let tries = 0
    let raf = 0
    const find = () => {
      const el = document.querySelector(`[data-tour="${step.target}"]`) as HTMLElement | null
      if (el) {
        el.scrollIntoView({ block: 'center', behavior: 'auto' })
        requestAnimationFrame(() => requestAnimationFrame(() => setRect(el.getBoundingClientRect())))
      } else if (tries++ < 60) raf = window.setTimeout(find, 100)
      else setRect(null)
    }
    setRect(null)
    find()
    return () => clearTimeout(raf)
  }, [step, loc.pathname, loc.search])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') stop()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'ArrowLeft') back()
    }
    const onScroll = () => {
      const el = document.querySelector(`[data-tour="${step.target}"]`) as HTMLElement | null
      if (el) setRect(el.getBoundingClientRect())
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('scroll', onScroll, true); window.removeEventListener('resize', onScroll) }
  }, [next, back, stop, step.target])

  const pad = 8
  const CARD_H = 220
  const below = rect ? rect.bottom + 14 : 0
  const above = rect ? rect.top - CARD_H - 14 : 0
  const cardTop = !rect ? window.innerHeight / 2 - 100
    : below + CARD_H < window.innerHeight ? below
    : above > 16 ? above
    : Math.max(16, window.innerHeight - CARD_H - 16)
  const cardLeft = rect ? Math.max(16, Math.min(window.innerWidth - 400, rect.left)) : window.innerWidth / 2 - 190

  return (
    <div className="fixed inset-0 z-50 pointer-events-none" role="dialog" aria-modal="false" aria-label={step.title}>
      {rect && (
        <div className="absolute rounded-xl ring-4 ring-amber-400 transition-all duration-300"
          style={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + 2 * pad, height: rect.height + 2 * pad, boxShadow: '0 0 0 9999px rgba(15,23,42,0.45)' }} />
      )}
      <div className="pointer-events-auto absolute w-[min(380px,calc(100vw-32px))] rounded-xl bg-white p-4 shadow-2xl border border-line"
        style={{ top: Math.max(16, cardTop), left: cardLeft }}>
        <div className="text-[11px] text-muted">Guided tour · {index + 1} of {STEPS.length}</div>
        <h2 className="mt-1 font-semibold text-ink">{step.title}</h2>
        <p className="mt-1 text-sm text-ink/80 leading-relaxed">{step.body}</p>
        <div className="mt-3 flex items-center gap-2">
          <button onClick={stop} className="text-xs text-muted hover:text-ink">Skip tour</button>
          <div className="ml-auto flex gap-2">
            {index > 0 && <button onClick={back} className="rounded-md border border-line px-3 py-1.5 text-sm">Back</button>}
            <button onClick={next} autoFocus className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white">{index + 1 < STEPS.length ? 'Next →' : 'Finish'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
