export type Status = 'meets' | 'conditional' | 'does_not_meet' | 'insufficient_evidence'

export interface CaseSummary {
  id: string
  client_name: string
  event: string
  event_date: string
  cure_deadline: string | null
  days_left: number | null
  status: 'meets' | 'at_risk' | 'insufficient_evidence' | 'conditional'
  possible_exemptions: number
  flags: { kind: string; message: string; date?: string; facts?: string[] }[]
  synthetic: boolean
}

export interface Contribution { entry_id: string; member_id: string; kind: string; amount: number; share: number; doc_id: string | null; span: string }
export interface MonthResult {
  month: string; member_id: string; status: Status; path: string | null; conditions: string[]
  activity_hours: number; own_income: number; own_gross_self_employment: number; household_other_income: number
  income_threshold: number; income_hours_equivalent: number; combined_hours: number; seasonal_average_income: number | null
  expense_headroom: number | null; contributions: Contribution[]; ambiguities: string[]; facts_used: string[]
}
export interface Worksheet {
  case_id: string; jurisdiction: string; as_of: string; review: string; months: string[]; results: MonthResult[]; overall: Status; cure_note: string
  exemptions: { member_id: string; key: string; label: string; fact_ids: string[]; action: string }[]
  cure_deadline: string | null
  params: Record<string, { value: unknown; fact_id: string | null; verified: boolean; label: string }>
  warnings: string[]
}
export interface Member { id: string; name: string; age: number | null; applicable_adult: boolean; seasonal_worker: boolean }
export interface Doc { id: string; name: string; kind: string; member_id: string | null; text: string; extracted: Record<string, unknown> | null; problems: string[] }
export interface CaseRecord {
  case: { id: string; jurisdiction: string; household: Member[]; client_id: string; event: string; event_date: string; notice_date: string | null; ledger: unknown[] }
  client_name: string; navigator: string; language: string; documents: Doc[]
  notice: Record<string, unknown> | null; flags: CaseSummary['flags']; synthetic: boolean
}

export interface Fact {
  id: string; jurisdiction: string; topic: string; statement: string; value: unknown; unit: string | null
  effective_from: string | null; effective_to: string | null; known_from: string | null
  citations: { source_id: string; quote: string }[]; confidence: string; notes: string
}

export interface Grounded {
  question: string; jurisdiction: string; as_of: string; answer: string; plain_language: string
  citations: { source_id: string; quote: string; title: string; url: string; as_of: string }[]
  dropped_citations: number; unsupported: boolean; confirm_with_agency: boolean
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const t = await r.text()
    let msg = t
    try { msg = JSON.parse(t).detail ?? t } catch { /* not JSON */ }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return r.json() as Promise<T>
}

const q = (o: Record<string, string | undefined>) =>
  '?' + Object.entries(o).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v!)}`).join('&')

export const api = {
  health: () => fetch('/api/health').then(j<{ ok: boolean; nebius: boolean; tavily: boolean; sources: number; facts: number }>),
  cases: (as_of?: string) => fetch('/api/cases' + q({ as_of })).then(j<CaseSummary[]>),
  case: (id: string, as_of?: string) => fetch(`/api/cases/${id}` + q({ as_of })).then(j<{ record: CaseRecord; worksheet: Worksheet }>),
  facts: (as_of: string, jurisdiction = 'NE') => fetch('/api/facts' + q({ as_of, jurisdiction })).then(j<Fact[]>),
  timeline: (jurisdiction = 'NE') => fetch('/api/timeline' + q({ jurisdiction })).then(j<{ dates: { date: string; facts: { id: string; kind: string; statement: string }[] }[]; snapshot_changes: Record<string, unknown>[] }>),
  ask: (question: string, as_of: string, compare = false, jurisdiction = 'NE') =>
    fetch('/api/ask', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ question, as_of, jurisdiction, compare_closed_book: compare }) })
      .then(j<{ grounded: Grounded; closed_book?: string }>),
  locate: (source_id: string, quote: string) => fetch(`/api/sources/${source_id}/locate` + q({ quote })).then(j<{ context: string; title: string; url: string; as_of: string }>),
  addDoc: (id: string, body: { name: string; kind: string; member_id?: string; text: string }) =>
    fetch(`/api/cases/${id}/documents`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(j<{ worksheet: Worksheet }>),
  replay: (jurisdiction = 'NE') => fetch('/api/drift/replay' + q({ jurisdiction })).then(j<DriftEvent[]>),
  explain: (id: string, lang: 'en' | 'es') => fetch(`/api/cases/${id}/explain` + q({ lang }), { method: 'POST' }).then(j<{ summary: string; what_to_do: string[]; deadline_sentence: string; keep_in_mind: string[]; spans: string[] }>),
  extraction: () => fetch('/api/extraction/results').then(j<Record<string, { model: string; docs: number; row_precision: number; row_recall: number; row_f1: number; doc_exact: number; injected_docs: number; injected_exact: number; usd: number }>>),
  calls: () => fetch('/api/log/calls').then(j<Record<string, unknown>[]>),
  tavily: () => fetch('/api/log/tavily').then(j<Record<string, unknown>[]>),
  bench: () => fetch('/api/bench/results').then(j<Record<string, unknown>>),
}

export const fmtDate = (s: string | null | undefined) =>
  s ? new Date(s + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
export const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }

export interface DriftEvent {
  url: string; title: string; jurisdiction: string; old_id: string | null; new_id: string
  old_as_of: string | null; new_as_of: string; added: string[]; removed: string[]; stale_facts: string[]
  summary: { headline: string; details: string[]; who_is_affected: string; navigator_action: string; substantive: boolean } | null
  affected_cases: { case_id: string; client_name: string; reasons: string[] }[]
}
