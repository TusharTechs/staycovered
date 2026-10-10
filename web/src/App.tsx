import { NavLink, Route, Routes } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from './api'
import Caseload from './pages/Caseload'
import CasePage from './pages/CasePage'
import TimeMachine from './pages/TimeMachine'
import Bench from './pages/Bench'
import UnderHood from './pages/UnderHood'
import Grade from './pages/Grade'
import Home from './pages/Home'
import Check from './pages/Check'
import Sandbox from './pages/Sandbox'
import { useTour } from './components/Tour'
import { StateSwitch } from './components/State'

function Logo() {
  // An umbrella over four month blocks: covered, month after month.
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#0f5d5d" />
      <path d="M5 16.5A11 10 0 0 1 27 16.5Q23.3 14.2 19.7 16.5Q16 14.2 12.3 16.5Q8.7 14.2 5 16.5Z" fill="#fff" />
      <g fill="#7fe0b5">
        <rect x="7" y="19.5" width="3.4" height="6" rx="1" /><rect x="11.5" y="19.5" width="3.4" height="6" rx="1" />
        <rect x="16" y="19.5" width="3.4" height="6" rx="1" /><rect x="20.5" y="19.5" width="3.4" height="6" rx="1" />
      </g>
      <circle cx="16" cy="6.2" r="1.1" fill="#fff" />
    </svg>
  )
}

const nav = [
  { to: '/caseload', label: 'Caseload' },
  { to: '/check', label: 'Self-check' },
  { to: '/time-machine', label: 'Rule Time Machine' },
  { to: '/sandbox', label: 'Policy sandbox' },
  { to: '/bench', label: 'WorkReqBench' },
  { to: '/under-the-hood', label: 'Under the hood' },
]

export default function App() {
  const [health, setHealth] = useState<{ nebius: boolean; tavily: boolean; sources: number; facts: number } | null>(null)
  const tour = useTour()
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])
  return (
    <div className="min-h-full flex flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2 focus:bg-white">Skip to content</a>
      <header className="bg-white border-b border-line">
        <div className="mx-auto max-w-7xl px-4 pt-2.5 flex flex-wrap items-center gap-x-4 gap-y-2">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-ink">
            <Logo /> <span className="text-lg tracking-tight">Stay<span className="text-brand">Covered</span></span>
          </NavLink>
          <div className="hidden lg:flex items-center gap-3 text-xs text-muted">
            {health && <span>{health.sources} official sources · {health.facts} rule facts</span>}
            <span className="inline-flex items-center gap-1 rounded-full bg-paper px-2 py-0.5 border border-line">
              <span className={`h-1.5 w-1.5 rounded-full ${health?.nebius ? 'bg-ok' : 'bg-warn'}`} /> Nemotron · Nebius
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-paper px-2 py-0.5 border border-line">
              <span className={`h-1.5 w-1.5 rounded-full ${health?.tavily ? 'bg-ok' : 'bg-warn'}`} /> Tavily
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <StateSwitch />
            <button onClick={tour.start} className="rounded-full bg-amber-400 px-3 py-1 text-xs font-semibold text-ink hover:bg-amber-300">▶ Tour</button>
          </div>
        </div>
        <nav aria-label="Main" className="mx-auto max-w-7xl px-2 sm:px-3 mt-1.5 flex gap-1 overflow-x-auto">
          {nav.map(n => (
            <NavLink key={n.to} to={n.to}
              className={({ isActive }) => `-mb-px border-b-2 px-3 py-2 text-sm whitespace-nowrap ${isActive ? 'border-brand text-brand font-medium' : 'border-transparent text-muted hover:text-ink'}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main id="main" className="flex-1 mx-auto w-full max-w-7xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/caseload" element={<Caseload />} />
          <Route path="/check" element={<Check />} />
          <Route path="/sandbox" element={<Sandbox />} />
          <Route path="/cases/:id" element={<CasePage />} />
          <Route path="/time-machine" element={<TimeMachine />} />
          <Route path="/bench" element={<Bench />} />
          <Route path="/under-the-hood" element={<UnderHood />} />
          <Route path="/grade" element={<Grade />} />
        </Routes>
      </main>
      <footer className="border-t border-line bg-white text-xs text-muted">
        <div className="mx-auto max-w-7xl px-4 py-3">
          StayCovered organises evidence against published rules. It does not decide eligibility — the state agency does. Demo cases are synthetic.
        </div>
      </footer>
    </div>
  )
}
