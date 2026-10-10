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
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#0f5d5d" />
      <path d="M16 6l9 4v6c0 5.5-3.8 9.2-9 10-5.2-.8-9-4.5-9-10v-6z" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M11.5 16.2l3.2 3.2 5.8-6.2" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
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
        <div className="mx-auto max-w-7xl px-4 min-h-14 py-2 flex flex-wrap items-center gap-x-6 gap-y-2">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-ink">
            <Logo /> <span className="text-lg tracking-tight">StayCovered</span>
          </NavLink>
          <nav aria-label="Main" className="order-3 w-full lg:order-none lg:w-auto flex gap-1 overflow-x-auto">
            {nav.map(n => (
              <NavLink key={n.to} to={n.to}
                className={({ isActive }) => `px-3 py-1.5 rounded-md text-sm whitespace-nowrap ${isActive ? 'bg-brand-soft text-brand font-medium' : 'text-muted hover:text-ink hover:bg-paper'}`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto"><StateSwitch /></div>
          <button onClick={tour.start} className=" rounded-full bg-amber-400 px-3 py-1 text-xs font-semibold text-ink hover:bg-amber-300">▶ Tour</button>
          <div className="hidden xl:flex items-center gap-3 text-xs text-muted">
            {health && <span>{health.sources} official sources · {health.facts} rule facts</span>}
            <span className="inline-flex items-center gap-1 rounded-full bg-paper px-2 py-0.5 border border-line">
              <span className={`h-1.5 w-1.5 rounded-full ${health?.nebius ? 'bg-ok' : 'bg-warn'}`} /> Nemotron · Nebius
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-paper px-2 py-0.5 border border-line">
              <span className={`h-1.5 w-1.5 rounded-full ${health?.tavily ? 'bg-ok' : 'bg-warn'}`} /> Tavily
            </span>
          </div>
        </div>
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
