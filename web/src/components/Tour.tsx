import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useJuris } from './State'

export type Step = { path: string; target: string; title: string; body: string }

export const STEPS: Step[] = [
  { path: '/cases/maria-lopez?run=1', target: 'agent', title: 'One notice, handled end to end', body: 'The agent reads Maria\'s notice and gig statements (Nemotron Nano), applies the rules in code, finds the smallest proven fix, checks the rule against official text (Super + Nano), and drafts her a message in Spanish. Each step shows its model, tokens and cost.' },
  { path: '/cases/maria-lopez', target: 'todo', title: 'What to do now, first', body: 'Deadline, smallest fix and what to send sit at the top. The evidence, with every number tied to its line in her documents, is below.' },
  { path: '/cases/tom-becker', target: 'forecast', title: 'Same life, changing rules', body: 'Tom\'s household is held constant for 12 months; only the published rules move. In January 2027 the federal household-income rule takes over and he becomes clearly covered.' },
  { path: '/time-machine?date=2026-10-10', target: 'ask', title: 'Frozen model vs. rules as of a date', body: 'Ask whether a spouse\'s income counts: the frozen model answers from memory; StayCovered quotes the official text in force on the date, and shows its evidence check.' },
  { path: '/sandbox?income_to_hours=true', target: 'levers', title: 'What if the state chose differently?', body: 'Flip a state policy choice (each cited to the federal rule) and the caseload re-runs. It separates people who are short from people at risk only for paperwork.' },
  { path: '/check', target: 'selfcheck', title: 'For people without a navigator', body: 'Phone-first, English or Spanish: status, smallest fix and a 12-month forecast. No name, nothing stored, and no AI call for the check itself.' },
  { path: '/bench', target: 'results', title: 'Measured, not claimed', body: 'WorkReqBench: 171 dated questions, committed before any benchmark run. Grounded Nemotron beats a frontier model answering from memory, and the ranking holds under three graders.' },
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
    let ro: ResizeObserver | null = null
    const find = () => {
      const el = document.querySelector(`[data-tour="${step.target}"]`) as HTMLElement | null
      if (el) {
        el.scrollIntoView({ block: 'center', behavior: 'auto' })
        requestAnimationFrame(() => requestAnimationFrame(() => setRect(el.getBoundingClientRect())))
        ro = new ResizeObserver(() => setRect(el.getBoundingClientRect()))  // the target can grow, e.g. the agent run
        ro.observe(el)
      } else if (tries++ < 60) raf = window.setTimeout(find, 100)
      else setRect(null)
    }
    setRect(null)
    find()
    return () => { clearTimeout(raf); ro?.disconnect() }
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
  const tall = !!rect && rect.height > window.innerHeight * 0.6  // a tall target: keep the card in a corner, off its content
  const cardTop = !rect ? window.innerHeight / 2 - 100
    : below + CARD_H < window.innerHeight ? below
    : above > 16 ? above
    : Math.max(16, window.innerHeight - CARD_H - 16)
  const cardLeft = tall ? Math.max(16, window.innerWidth - 396)
    : rect ? Math.max(16, Math.min(window.innerWidth - 400, rect.left)) : window.innerWidth / 2 - 190

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
