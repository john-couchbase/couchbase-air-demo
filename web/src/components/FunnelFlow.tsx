import type { State } from '../lib/types'
import { approx, classifyName, viaSqlpp } from '../lib/models'

/*
  The funnel as a left-to-right flow, with the live count under each stage.

  Every stage is the same size. They used to step down in height as the flow
  went right, to draw the narrowing, and it read as untidy rather than as a
  funnel. The counts carry the narrowing on their own: hundreds on the left,
  a few dozen in red on the right.
*/

type Stage = {
  key: string; title: string; who: string | ((s: State | null) => string)
  count: (s: State) => number; hot?: boolean
}

const STAGES: Stage[] = [
  { key: 'land', title: 'Messages land', who: 'Couchbase, as JSON',
    count: (s) => s.funnel.inbound },
  { key: 'classify', title: 'Every one classified', who: (s) => `${classifyName(s)}, ${viaSqlpp(s) ? 'from SQL++' : 'called directly'}`,
    count: (s) => s.funnel.classified },
  { key: 'cache', title: 'Answered from cache', who: 'Semantic cache',
    count: (s) => s.cache.hits },
  { key: 'escalate', title: 'Need judgment', who: 'Funnel query joins tier',
    count: (s) => s.funnel.escalated + s.funnel.in_agent, hot: true },
  { key: 'decide', title: 'Decision drafted', who: 'Claude, with Agent Memory',
    count: (s) => s.funnel.escalated, hot: true },
  { key: 'approve', title: 'Approved', who: 'A person, writing memory',
    count: (s) => s.funnel.approved },
]

export default function FunnelFlow({ state }: { state: State | null }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: `repeat(${STAGES.length}, 1fr)`, gap: 10,
      marginTop: 20, alignItems: 'start',
    }}>
      {STAGES.map((st, i) => {
        return (
          <div key={st.key}>
            <div style={{
              height: 150, borderRadius: 'var(--radius-lg)', padding: '14px 14px',
              display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
              background: st.hot ? 'var(--cb-red)' : i === 0 ? 'var(--cb-black)' : 'var(--surface-subtle)',
              color: st.hot || i === 0 ? '#fff' : 'var(--text-strong)',
            }}>
              <div style={{ fontSize: 16, fontWeight: 700, lineHeight: 1.2 }}>{st.title}</div>
              <div style={{
                fontSize: 40, fontWeight: 600, lineHeight: 1, fontVariantNumeric: 'tabular-nums',
              }}>
                {state ? `${st.key === 'cache' ? approx(state) : ''}${st.count(state).toLocaleString()}` : '–'}
              </div>
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-muted)', fontWeight: 600, marginTop: 8 }}>
              {typeof st.who === 'function' ? st.who(state) : st.who}
            </div>
          </div>
        )
      })}
    </div>
  )
}
