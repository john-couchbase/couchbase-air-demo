export type Phase = 'normal' | 'storm' | 'recovering' | 'quiet'

export interface Backend {
  models: 'local_standin' | 'gateway_standin' | 'model_service'
  cache: 'local_standin' | 'gateway_standin' | 'model_service'
  ai_functions: 'local_standin' | 'query_service' | 'disabled'
  classify_via: 'backend' | 'sqlpp'
  cache_estimated?: boolean  // sqlpp path: hits inferred from response time
  cache_hit_ms?: number      // ...under this many milliseconds
  cache_per_run?: boolean
  memory?: 'collection' | 'ams' | 'mcp'  // where Agent Memory lives
  agent_via?: 'prefetch' | 'mcp'          // how the agent gathers its context
  endpoint: string
  stand_ins: Record<string, string>
}

export interface State {
  sql_evidence?: { enabled: boolean; completed: number; fallbacks: number }
  usage_incomplete?: boolean
  generation?: string
  run_status?: string
  error?: string
  cost_estimated?: boolean
  phase: Phase
  paused?: 'idle' | 'user' | null  // idle: nobody watching; user: the Pause button
  idle_pause_min?: number
  elapsed_s: number
  storm_at_s: number | null
  quiet_at_s: number | null
  funnel: {
    inbound: number; classified: number; surge: number
    escalated: number; in_agent: number; approved: number
  }
  cache: { hits: number; misses: number; entries: number; avoided_usd: number }
  spend: { classify: number; agent: number; total: number }
  tokens: Record<'classify' | 'agent', { in: number; out: number; calls: number }>
  reserved: { label: string; per_hour: number; so_far: number }
  models: { classify: string; agent: string }
  model_names?: { classify: { name: string; short: string }; agent: { name: string; short: string } }
  backend: Backend
  live: Live
}

export interface Live {
  window_s: number
  arrivals_per_s: number
  classify_per_s: number
  cache_per_s: number
  classify_in_flight: number
  classify_slots: number
  agent_in_flight: number
  agent_slots: number
  spend_per_min: number
  reserved_per_min: number
}

export interface Bucket {
  t: number
  baseline: number
  surge: number
  classified: number
  hits: number
  classify_usd: number
  agent_usd: number
  agent_calls: number
  serverless_cum: number
  reserved_cum: number
  reserved_rate: number
}

export interface Timeline {
  bucket_s: number
  rows: Bucket[]
  storm_at_s: number | null
  quiet_at_s: number | null
}

export interface Classification {
  intent: string
  urgency: number
  sentiment: string
  needs: string[]
  language: string
  summary: string
  model?: string
  cache?: 'hit' | 'miss' | 'n/a'
  tokens_in?: number
  tokens_out?: number
}

export interface FeedRow {
  id: string
  ts: number
  kind: 'baseline' | 'surge'
  channel: string
  language: string
  text: string
  classification?: Classification
  escalated: boolean
  tier: string
  flight_no: string
  dest_city: string
}

export interface ResolutionRow {
  id: string
  name: string
  tier: string
  flight_no: string
  dest_city: string
  status: 'drafting' | 'drafted' | 'approved'
  created: number
  urgency: number
  summary: string
  needs: string[]
  chosen: string
  hero?: boolean
  message?: string  // drafting rows only: the passenger's words, for the panel
}

export interface Option {
  id: string
  carrier: string
  flight: string
  when: string
  seats: string
}

export interface Decision {
  recommended_option: string
  why: string
  backup_option: string
  goodwill_miles: number
  vouchers: string[]
  actions: string[]
  reply: string
  memory_note: string
}

export interface Disruption { when: string; what: string; goodwill: string }

export interface Resolution {
  id: string
  name: string
  tier: string
  flight_no: string
  dest_city: string
  message: string
  classification: Classification
  options: Option[]
  decision: Decision
  memory_used: { disruptions: Disruption[]; preferences: Record<string, string | null>; notes: string[]
                 source?: 'collection' | 'collection_fallback' | 'disabled' | 'ams' | 'mcp' }
  agent_via?: 'prefetch' | 'mcp' | 'prefetch_fallback'
  tool_calls?: { tool: string; args: Record<string, unknown>; ms: number; chars: number
                 error: boolean; preview: string }[]
  prompt: string
  model: string
  tokens_in: number
  tokens_out: number
  latency_ms: number
  status: 'drafted' | 'approved'
}

export interface Bill {
  tracking?: { attempts:number; measured:number; unknown:number }
  statement: string
  rows: {
    job: string; label?: string; usage_available?: boolean; measured_calls?: number; model: string; calls: number; cache_hits: number
    tokens_in: number; tokens_out: number; spend_usd: number; avoided_usd: number
    estimated: boolean
  }[]
}

export interface Sqlpp {
  classify: string
  classify_prompt: string
  funnel: string
  context: string
  partners: string
  policy: string
}

export interface CatalogModel {
  id: string
  name: string
  provider: string
  role: string
  in_per_m: number
  out_per_m: number
  used_for: string[]
  local_standin: string | null
}

export interface ModelsInfo { catalog: CatalogModel[]; backend: Backend }
