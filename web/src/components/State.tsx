import { createContext, useContext, useState, type ReactNode } from 'react'

export type Juris = 'NE' | 'MT'
export const STATES: Record<Juris, { name: string; agency: string }> = {
  NE: { name: 'Nebraska', agency: 'Nebraska DHHS' },
  MT: { name: 'Montana', agency: 'Montana DPHHS' },
}
const KEY = 'staycovered-state'
const Ctx = createContext<{ state: Juris; setState: (s: Juris) => void } | null>(null)
export const useJuris = () => useContext(Ctx)!

export function StateProvider({ children }: { children: ReactNode }) {
  const [state, set] = useState<Juris>(() => {
    try { const v = localStorage.getItem(KEY); return v === 'MT' ? 'MT' : 'NE' } catch { return 'NE' }
  })
  const setState = (s: Juris) => { set(s); try { localStorage.setItem(KEY, s) } catch { /* private mode */ } }
  return <Ctx.Provider value={{ state, setState }}>{children}</Ctx.Provider>
}

export function StateSwitch() {
  const { state, setState } = useJuris()
  return (
    <div role="radiogroup" aria-label="State" className="inline-flex rounded-full border border-line bg-paper p-0.5 text-xs">
      {(Object.keys(STATES) as Juris[]).map(k => (
        <button key={k} role="radio" aria-checked={state === k} onClick={() => setState(k)}
          className={`rounded-full px-2.5 py-1 font-medium ${state === k ? 'bg-brand text-white' : 'text-muted hover:text-ink'}`}>
          {STATES[k].name}
        </button>
      ))}
    </div>
  )
}
