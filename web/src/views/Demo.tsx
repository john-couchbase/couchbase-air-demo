import { exampleActive } from '../lib/example'
import type { State } from '../lib/types'
import FunnelFlow from '../components/FunnelFlow'
import SystemDiagram from '../components/SystemDiagram'
import { agentName, classifyName } from '../lib/models'

/*
  What to look for, stated before anything moves.

  The three tenets are the three things a provisioned endpoint cannot match,
  in the order the storm reaches them. Each card names the screen where the
  room can check it for themselves, and the same word is repeated in that
  screen's eyebrow so the connection survives twenty minutes of demo.
*/

export const TENETS: { name: string; claim: string; where: string }[] = [
  {
    name: 'Burst',
    claim: 'Handle a sudden surge without reserving model capacity.',
    where: 'Dashboard',
  },
  {
    name: 'Model per task',
    claim: 'Classify every message; use the reasoning model for escalations.',
    where: 'Dashboard / Recovery',
  },
  {
    name: 'Inside the data',
    claim: 'AI Functions can classify messages through SQL++.',
    where: 'SQL++',
  },
]

// off: available but not used in this run (shown as Off, not Stand-in).
type Row = { name: string; what: string; live: boolean; off?: boolean; note: string }

function components(state: State | null): Row[] {
  const local = state?.backend.models !== 'model_service'
  const gateway = state?.backend.models === 'gateway_standin'
  return [
    { name: 'Couchbase cluster', what: 'Messages, flights, bookings, passengers, the meter',
      live: true, note: 'Every figure on screen is read back from it in SQL++' },
    { name: 'travel-sample', what: 'Partner routes the agent can rebook onto',
      live: true, note: 'Real route data, queried at decision time' },
    { name: 'AI Functions', what: 'Classifying messages inside a SQL++ statement',
      live: state?.backend.ai_functions === 'query_service',
      off: state?.backend.classify_via !== 'sqlpp',
      note: state?.backend.classify_via === 'sqlpp'
        ? (gateway ? 'The statement runs in the Query service; ai_completion is a local UDF calling the gateway stand-in'
           : local ? 'The statement runs in the Query service; ai_completion is a local UDF calling LM Studio'
                 : 'The statement runs in the Query service')
        : `Available; this run calls ${classifyName(state)} directly with the same prompt, so the cache's verdict is visible` },
    { name: `Model Service: ${classifyName(state)}`, what: 'Classifying every message',
      live: !local, note: gateway ? 'Stand-in: local gateway over LM Studio' : local ? `Stand-in: ${state?.backend.stand_ins[state.models.classify] ?? 'local model'}` : 'Bedrock, serverless' },
    { name: `Model Service: ${agentName(state)}`, what: 'Recovery decisions for escalations',
      live: !local, note: gateway ? 'Stand-in: local gateway over LM Studio' : local ? `Stand-in: ${state?.backend.stand_ins[state.models.agent] ?? 'local model'}` : 'Bedrock, serverless' },
    { name: 'Semantic cache', what: 'Repeated questions answered once',
      live: state?.backend.cache === 'model_service', note: gateway
        ? (state?.backend.cache_estimated ? 'Gateway stand-in, exact match as on sbx-27; hits estimated from response time (SQL++ returns no verdict)'
                                         : 'Gateway stand-in, exact match as on sbx-27; verdict read from x-cache')
        : local ? 'Emulated in the backend, same threshold logic'
        : state?.backend.cache_estimated ? 'Semantic, at the gateway; hits estimated from response time (SQL++ returns no verdict)'
        : 'Semantic, chosen at deployment' },
    { name: 'Agent Memory', what: 'Prior disruptions, preferences, notes',
      live: true, note: (state?.backend.memory ?? 'collection') === 'collection'
        ? 'A collection in the cluster; approval writes to it'
        : 'The hosted AgentMemory service on Capella: semantic recall; approval writes to it' },
    // Listed only when it is in use: an unconnected server is not part of the story.
    ...(state?.backend.agent_via === 'mcp' ? [{
      name: 'MCP server', what: 'Tools the agent uses to look things up itself',
      live: true, note: 'Hosted on Capella; read-only tools, SELECT only' }] : []),
  ]
}

export default function Demo({ state }: { state: State | null }) {
  if (exampleActive()) return <div className="fade-in learn-view">
    <div className="eyebrow">AIDP Air / Simulation guide</div>
    <h1 style={{marginTop:8,marginBottom:6}}>How this demo works</h1>
    <p className="lede">Storm → tool checks → demo adjustment.</p>
    <div className="reference-grid how-it-works-summary">
      {[
        ['Disruption','Cancellations, a weather delay, and a gate change bring different requests.'],
        ['Tool checks','Check bookings and seats. Retry failures or flag a handoff.'],
        ['Demo adjustment','The conversation confirms the scripted booking update or staff handoff.'],
      ].map(([title,body])=><section className="card" key={title}><h3>{title}</h3><p>{body}</p></section>)}
    </div>
    <details className="simulation-disclosure"><summary><span>About this simulation</span></summary><div className="simulation-disclosure-body">
      <p className="reference-note">Alex gets a replacement offer. Sam needs staff help. A routine gate question uses a cached answer.</p>
      <p className="reference-note">All data and costs are fictional. No AI calls, database writes, or real bookings. Use More to restart or pause.</p>
    </div></details>
  </div>

  return (
    <div className="fade-in learn-view">
      <div className="eyebrow">Couchbase AI Data Plane / AIDP Air</div>
      <h1 style={{ marginTop: 8, marginBottom: 6 }}>A storm nobody planned for</h1>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-body)' }}>
        A winter storm cancels 52 flights at O’Hare. Follow the requests from classification to recovery.
      </p>

      <div className="stat-row" style={{
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))', marginTop: 24,
      }}>
        {TENETS.map((t) => (
          <div key={t.name} className="card" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="eyebrow" style={{ color: 'var(--cb-red)' }}>{t.name}</div>
            <p style={{ fontSize: 'var(--ui-body)', margin: '8px 0 12px', lineHeight: 1.55 }}>{t.claim}</p>
            {/* Pinned to the bottom so the three line up across the row. */}
            <div style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', fontWeight: 600, marginTop: 'auto' }}>
              {t.where}
            </div>
          </div>
        ))}
      </div>

      {/* Before the funnel counts: the counts say how much, this says where it
          is happening and on what. It is live, so the presenter can come back to
          it mid-storm and the room sees the models light up. */}
      <h2 style={{ marginTop: 28, marginBottom: 6 }}>What happens when the storm hits</h2>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
        Classify requests, identify escalations, and draft a response for human approval.
      </p>
      <details className="evidence-disclosure"><summary>Explore the system</summary><div className="diagram-scroll"><SystemDiagram state={state} /></div></details>

      <h2 style={{ marginTop: 28, marginBottom: 6 }}>The funnel</h2>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
        Cheap model for volume, frontier model for judgment, a person for the decision. Counts appear when connected.
      </p>
      <div className="funnel-responsive"><FunnelFlow state={state} /></div>

      <h2 style={{ marginTop: 28, marginBottom: 6 }}>What is running right now</h2>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
        Reported from the running system, including anything that is a stand-in.
      </p>
      <div className="card" style={{ marginTop: 16, padding: '8px 12px' }}>
        {!state ? <p className="empty-note">Connect the backend to see service status.</p> : <div className="table-scroll" tabIndex={0} role="region" aria-label="Connected services"><table className="table">
          <thead>
            <tr><th>Component</th><th>Used for</th><th>State</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {components(state).map((c) => (
              <tr key={c.name}>
                <td style={{ fontWeight: 700, color: 'var(--text-strong)' }}>{c.name}</td>
                <td>{c.what}</td>
                <td>
                  <span className="tag" style={c.off
                    ? { background: 'transparent', color: 'var(--text-muted)', border: '2px solid var(--border-subtle)' }
                    : c.live
                      ? { background: 'var(--cb-black)', color: '#fff' }
                      : { background: 'var(--cb-peach)', color: 'var(--cb-burgundy)' }}>
                    {c.off ? 'Off' : c.live ? 'Live' : 'Stand-in'}
                  </span>
                </td>
                <td style={{ color: 'var(--text-muted)' }}>{c.note}</td>
              </tr>
            ))}
          </tbody>
        </table></div>}
      </div>
    </div>
  )
}
