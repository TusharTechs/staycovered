import { useEffect, useState, useCallback } from 'react'
import { Card, Spinner } from '../components/ui'

type Item = { row: string; system: string; qid: string; as_of: string; question: string; criterion_kind: string; criterion: string; answer: string; human_pass: string }

export default function Grade() {
  const [items, setItems] = useState<Item[] | null>(null)
  const [i, setI] = useState(0)
  useEffect(() => {
    fetch('/api/grade/items').then(r => r.json()).then((xs: Item[]) => {
      setItems(xs)
      const first = xs.findIndex(x => !x.human_pass)
      setI(first < 0 ? 0 : first)
    })
  }, [])

  const mark = useCallback(async (v: 'y' | 'n') => {
    if (!items) return
    const it = items[i]
    await fetch(`/api/grade/${it.row}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ human_pass: v }) })
    const next = items.map((x, k) => (k === i ? { ...x, human_pass: v } : x))
    setItems(next)
    if (i + 1 < next.length) setI(i + 1)
  }, [items, i])

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (!items) return
      const isNeg = items[i]?.criterion_kind === 'must_not_claim'
      if (e.key === 'y' || e.key === 'Y') mark(isNeg ? 'n' : 'y')
      if (e.key === 'n' || e.key === 'N') mark(isNeg ? 'y' : 'n')
      if (e.key === 'ArrowLeft') setI(k => Math.max(0, k - 1))
      if (e.key === 'ArrowRight') setI(k => Math.min((items?.length ?? 1) - 1, k + 1))
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [mark, items, i])

  if (!items) return <Spinner />
  if (items.length === 0) return <p className="text-muted">No grading sheet found.</p>
  const it = items[i]
  const done = items.filter(x => x.human_pass).length
  const neg = it.criterion_kind === 'must_not_claim'
  // "Does not claim that X" -> "X" so the question has no double negative
  const claim = neg
    ? it.criterion.replace(/^(does not|do not|must not|doesn't|should not)\s+(claim|state|say|suggest|imply|assert|describe|tell)(s)?\s*(that\s+)?/i, '').replace(/^./, c => c.toUpperCase())
    : it.criterion
  // For wrong-claim items, "Yes, it says this" is a FAIL (n) and "No" is a PASS (y)
  const yes = () => mark(neg ? 'n' : 'y')
  const no = () => mark(neg ? 'y' : 'n')
  const chosenYes = neg ? it.human_pass === 'n' : it.human_pass === 'y'
  const chosenNo = neg ? it.human_pass === 'y' : it.human_pass === 'n'

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight">Check the grader</h1>
        <p className="text-muted text-sm mt-1">No Medicaid knowledge needed. For each item, just check whether the answer says (or avoids saying) one sentence. Your answers are compared with the AI grader's afterwards — you never see its verdicts.</p>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <div className="flex-1 h-2 rounded-full bg-line overflow-hidden"><div className="h-full bg-brand" style={{ width: `${(done / items.length) * 100}%` }} /></div>
        <span className="tabular-nums text-muted">{done} / {items.length} done</span>
      </div>

      <Card>
        <div className="pt-3 space-y-4">
          <div className="text-xs text-muted">Item {i + 1} of {items.length} · question asked as of {it.as_of}</div>
          <div className={`rounded-xl p-4 ${neg ? 'bg-bad-soft' : 'bg-ok-soft'}`}>
            <div className={`text-xs font-semibold uppercase tracking-wide ${neg ? 'text-bad' : 'text-ok'}`}>
              {neg ? 'Does the answer say this WRONG thing?' : 'Does the answer say this?'}
            </div>
            <p className="mt-1 text-lg leading-snug">{claim}</p>
            <p className="mt-2 text-xs text-muted">{neg
              ? 'This is a mistake an answer might make. Yes = the answer says it (or clearly implies it). No = the answer does not say it.'
              : 'Yes = the answer says this (other words are fine; numbers and dates must match). No = it is missing or says something different.'}</p>
          </div>
          <details className="text-sm"><summary className="cursor-pointer text-muted">Show the question that was asked</summary><p className="mt-1">{it.question}</p></details>
          <div>
            <div className="text-xs text-muted mb-1">The answer being checked</div>
            <div className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-paper p-3 text-sm leading-relaxed">{it.answer}</div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={yes} className={`flex-1 rounded-xl py-3 text-lg font-semibold ${chosenYes ? 'bg-ink text-white' : 'bg-paper border border-line hover:bg-ink hover:text-white'}`}>Yes (Y)</button>
            <button onClick={no} className={`flex-1 rounded-xl py-3 text-lg font-semibold ${chosenNo ? 'bg-ink text-white' : 'bg-paper border border-line hover:bg-ink hover:text-white'}`}>No (N)</button>
          </div>
          <div className="flex justify-between text-sm">
            <button disabled={i === 0} onClick={() => setI(i - 1)} className="text-brand disabled:text-muted">← Previous</button>
            <span className="text-xs text-muted">Not sure? Pick your best guess — that's what a grader would do.</span>
            <button disabled={i + 1 >= items.length} onClick={() => setI(i + 1)} className="text-brand disabled:text-muted">Next →</button>
          </div>
          {done === items.length && <p className="rounded-lg bg-ok-soft p-3 text-sm text-ok font-medium">All done — thank you! Tell Claude you've finished.</p>}
        </div>
      </Card>
    </div>
  )
}
