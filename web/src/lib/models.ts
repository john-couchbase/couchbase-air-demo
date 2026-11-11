import type { State } from './types'

/*
  Display names for the two models in use, from the server's catalog, so every
  label follows the configured models (Nova Micro locally, Nova Pro on the
  us-east-2 Model Service). The fallbacks cover the first render, before state.
*/
export const classifyName = (s: State | null) => s?.model_names?.classify.short ?? 'Nova Micro'
export const classifyFull = (s: State | null) => s?.model_names?.classify.name ?? 'Amazon Nova Micro'
export const agentName = (s: State | null) => s?.model_names?.agent.short ?? 'Claude Sonnet'

// "≈" in front of cache figures when they are estimated (the SQL++ path, where
// the gateway's verdict does not come back and hits are inferred from timing).
export const approx = (s: State | null) => (s?.backend.cache_estimated ? '≈' : '')

// Whether classification runs as the AI Function in SQL++ (CLASSIFY_VIA=sqlpp)
// or the app calls the model directly with the same prompt (the direct path).
export const viaSqlpp = (s: State | null) => s?.backend.classify_via === 'sqlpp'
