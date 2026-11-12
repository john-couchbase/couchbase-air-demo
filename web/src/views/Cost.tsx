import { exampleActive } from '../lib/example'
import './Cost.css'
import Stat from '../components/MetricCard'
import { useEffect, useState } from 'react'
import Projection from '../components/Projection'
import {
  Bar, CartesianGrid, ComposedChart, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'
import * as api from '../lib/api'
import type { Bill, State, Timeline } from '../lib/types'
import { CHART_WINDOW_S, Key, clock } from './Storm'

/*
  The big finish: the queue drains, calls drop, and so does spend.

  Two charts, both on the demo's own clock and both in USD on one axis.

  The first is spend per interval. Serverless spend is bars, stacked by job,
  so the room sees it rise with the storm and fall back to the floor after it.
  The reserved GPU is a flat line at its hourly rate, which is what an
  instance costs whether or not anything is running on it. That contrast is
  the point of the whole demo.

  The second is the same thing summed. It is there because the first chart is
  unfair to the GPU during the burst - serverless is dearer per minute at the
  peak - and the room should see that too. What matters is the total over a
  day that is mostly quiet.

  Nothing here is projected. Tokens are measured per call, prices are Bedrock
  list, and the GPU rate is a number in config, labelled as such.

  Colors: classifying black, agent red, reserved GPU blue (the palette's one cool
  accent, so it reads as "the other option" rather than part of the bill).
*/

const CLASSIFY = '#547D91'
const AGENT = '#EC1218'
const GPU = '#547D91'

export default function Cost({ state }: { state: State | null }) {
  const [tl, setTl] = useState<Timeline | null>(null)
  const [bill, setBill] = useState<Bill | null>(null)

  useEffect(() => {
    const load = () => {
      api.getTimeline().then(setTl).catch(() => {})
      api.getBill().then(setBill).catch(() => {})
    }
    load()
    const t = window.setInterval(load, 2000)


  return () => window.clearInterval(t)
  }, [])

  const rows = (tl?.rows ?? []).map((r) => ({ ...r, x: r.t }))
  // Spend per interval rolls, like the Storm chart, so a long run still shows
  // the storm at a readable width; the summed chart below needs the whole run.
  const lastT = rows.length ? rows[rows.length - 1].t : 0
  const recent = rows.filter((r) => r.t > lastT - CHART_WINDOW_S)
  const phase = state?.phase ?? 'normal'
  const spend = state?.spend.total ?? 0
  const reserved = state?.reserved.so_far ?? 0
  const perMsg = state && state.funnel.classified ? spend / state.funnel.classified : 0
  // Whether serverless ever out-spent the reserved rate in one interval. The
  // copy under the summed chart says whichever is true for this run.
  const peakBucket = Math.max(0, ...rows.map((r) => r.classify_usd + r.agent_usd))
  const overAtPeak = rows.length > 0 && peakBucket > (rows[0]?.reserved_rate ?? 0)

    if(state?.cost_estimated) return <div className="fade-in cost-view">
    <h1>Model usage</h1><p className="lede">Recorded tokens. Estimated model costs.</p>
    <div className="stat-row cost-stats"><Stat value={usd(spend + (bill?.rows.reduce((sum,r)=>sum+(r.estimated_sql_usd ?? 0),0) ?? 0))} label="Estimated model cost" warm /><Stat value={String(bill?.tracking?.attempts ?? state.tokens.classify.calls+state.tokens.agent.calls)} label="Model attempts" /></div>
    <section className="card"><h3>Usage breakdown</h3>{bill?.tracking && <p className="reference-note">{bill.tracking.measured} attempts with measured tokens{bill.tracking.unknown > 0 ? `; ${bill.tracking.estimated ?? 0} estimated, ${bill.tracking.unknown-(bill.tracking.estimated ?? 0)} unavailable` : ''}.</p>}<div className="table-scroll" tabIndex={0} role="region" aria-label="Usage breakdown"><table className="table"><thead><tr><th>Task</th><th>Model</th><th>Calls</th><th>Input tokens</th><th>Output tokens</th><th>Estimate</th></tr></thead><tbody>{bill?.rows.map(r=><tr key={r.job}><td>{r.label ?? (r.job==='classify'?'Classification':'Recovery')}</td><td>{r.model}</td><td>{r.calls}</td><td>{r.estimated_calls ? '~'+r.estimated_tokens_in : r.usage_available === false && !r.measured_calls ? 'Unavailable' : r.tokens_in}</td><td>{r.estimated_calls ? '~'+r.estimated_tokens_out : r.usage_available === false && !r.measured_calls ? 'Unavailable' : r.tokens_out}</td><td>{r.estimated_calls ? '~$'+(r.estimated_sql_usd ?? 0).toFixed(6) : r.usage_available === false && !r.measured_calls ? 'Not included' : '$'+r.spend_usd.toFixed(4)}</td></tr>)}</tbody></table></div><p className="reference-note">SQL uses a rough text-size estimate (4 bytes per token), not measured tokens. Nova Micro reference rates: $0.035 input / $0.14 output per million tokens. Failed SQL attempts remain unpriced. Estimates are not your Capella invoice; database and hosting are separate.</p></section>
  </div>
  return (
    <div className="fade-in cost-view">
      <h1 style={{ marginTop: 8, marginBottom: 6 }}>
        {phase === 'quiet' ? 'Final model cost' : 'Model costs'}
      </h1>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
        Compare model usage with the configured reserved-GPU cost. Infrastructure costs are separate.
      </p>

      <div className="stat-row cost-stats">
        <Stat value={state ? usd(spend) : '–'} label="Serverless usage" warm />
        <Stat value={state ? usd(reserved) : '–'} label="Reserved GPU estimate" />
        <Stat value={state ? usd(state.cache.avoided_usd) : '–'} label="Cache savings" />
        <Stat value={perMsg ? `$${(perMsg * 1000).toFixed(2)}` : '–'} label="Per 1,000 messages" />
      </div>

      {state && !exampleActive() && <Projection state={state} />}

      <div className="cost-charts">
      <div className="card cost-chart">
        <h3 style={{ marginBottom: 4 }}>Spend per {tl?.bucket_s ?? 5} seconds</h3>
        <p style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', marginBottom: 14 }}>
          Usage and reserved capacity over the last {CHART_WINDOW_S / 60} minutes.
        </p>
        <div className="chart-legend">
          <Key color={CLASSIFY} label="Classify messages" />
          <Key color={AGENT} label="Resolve requests" />
          <Key color={GPU} label="Reserved GPU" line />
        </div>
        <div style={{ height: 280 }}>
          <ResponsiveContainer>
            <ComposedChart data={recent} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeWidth={2} />
              <XAxis dataKey="x" tickFormatter={clock} minTickGap={40}
                     tick={{ fontSize: 14, fill: 'var(--text-muted)' }} stroke="var(--border-subtle)" strokeWidth={2} />
              <YAxis tickFormatter={(v: number) => `$${v.toFixed(3)}`} width={64}
                     tick={{ fontSize: 14, fill: 'var(--text-muted)' }} stroke="var(--border-subtle)" strokeWidth={2} />
              <Tooltip labelFormatter={(v) => clock(Number(v))}
                       formatter={(v) => `$${Number(v).toFixed(5)}`}
                       contentStyle={{ fontSize: 'var(--ui-label)', borderRadius: 8 }} />
              {tl?.storm_at_s != null && recent.length > 0
                && Math.floor(tl.storm_at_s / tl.bucket_s) * tl.bucket_s >= recent[0].t && (
                <ReferenceLine x={Math.floor(tl.storm_at_s / tl.bucket_s) * tl.bucket_s}
                               stroke={AGENT} strokeOpacity={0.25} strokeWidth={2} />
              )}
              <Bar dataKey="classify_usd" name="Classify messages" stackId="a" fill={CLASSIFY} isAnimationActive={false} />
              <Bar dataKey="agent_usd" name="Resolve requests" stackId="a" fill={AGENT} isAnimationActive={false} />
              <Line dataKey="reserved_rate" name="Reserved GPU" stroke={GPU} strokeWidth={3}
                    dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card cost-chart">
        <h3 style={{ marginBottom: 4 }}>Total cost over time</h3>
        <p style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', marginBottom: 14 }}>
          {!rows.length ? 'Run the demo to compare cumulative costs.' : overAtPeak
            ? 'Serverless peaked above reserved capacity. Compare the totals.'
            : 'Serverless stayed below the reserved rate in the observed intervals.'}
        </p>
        <div className="chart-legend">
          <Key color={AGENT} label="Serverless total" line />
          <Key color={GPU} label="Reserved GPU total" line />
        </div>
        <div style={{ height: 240 }}>
          <ResponsiveContainer>
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeWidth={2} />
              <XAxis dataKey="x" tickFormatter={clock} minTickGap={40}
                     tick={{ fontSize: 14, fill: 'var(--text-muted)' }} stroke="var(--border-subtle)" strokeWidth={2} />
              <YAxis tickFormatter={(v: number) => `$${v.toFixed(2)}`} width={64}
                     tick={{ fontSize: 14, fill: 'var(--text-muted)' }} stroke="var(--border-subtle)" strokeWidth={2} />
              <Tooltip labelFormatter={(v) => clock(Number(v))}
                       formatter={(v) => `$${Number(v).toFixed(4)}`}
                       contentStyle={{ fontSize: 'var(--ui-label)', borderRadius: 8 }} />
              <Line dataKey="serverless_cum" name="Serverless" stroke={AGENT} strokeWidth={3}
                    dot={false} isAnimationActive={false} />
              <Line dataKey="reserved_cum" name="Reserved GPU" stroke={GPU} strokeWidth={3}
                    dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <h3 style={{ marginBottom: 4 }}>Usage breakdown</h3>
        <p style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', marginBottom: 12 }}>
          {exampleActive() ? 'Calls, tokens, and cost by task.' : 'Calls, tokens, and costs recorded in Couchbase.'}
        </p>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Usage breakdown"><table className="table">
          <thead>
            <tr>
              <th>Job</th><th>Model</th><th className="num">Calls</th><th className="num">Cache hits</th>
              <th className="num">Tokens in</th><th className="num">Tokens out</th>
              <th className="num">Spend</th><th className="num">Avoided</th>
            </tr>
          </thead>
          <tbody>
            {!bill?.rows.length && <tr><td colSpan={8} className="empty-note">Awaiting usage data</td></tr>}
            {(bill?.rows ?? []).map((r) => (
              <tr key={r.job + r.model}>
                <td style={{ fontWeight: 700 }}>{r.job==='Classification'?'Classify messages':r.job==='Decisions'?'Resolve requests':r.job}</td>
                <td>{r.model}</td>
                <td className="num">{r.calls.toLocaleString()}</td>
                <td className="num">{r.estimated && r.job === 'classify' ? '≈' : ''}{r.cache_hits.toLocaleString()}</td>
                <td className="num">{r.estimated ? '≈' : ''}{r.tokens_in.toLocaleString()}</td>
                <td className="num">{r.estimated ? '≈' : ''}{r.tokens_out.toLocaleString()}</td>
                <td className="num">${r.spend_usd.toFixed(4)}</td>
                <td className="num">${r.avoided_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {bill?.rows.some((r) => r.estimated) && (
          <p style={{ fontSize: 'var(--ui-label)', color: 'var(--cb-burgundy)', marginTop: 10, marginBottom: 0 }}>
            ≈ Estimated. Classification ran as a SQL++ statement, which does not report token usage
            or the cache verdict back to the caller: tokens are estimated from text length, and a
            classification that came back in under {state?.backend.cache_hit_ms ?? 300} ms
            is counted as a cache hit.
          </p>
        )}
        {bill?.statement && <details className="evidence-disclosure">
          <summary>View SQL++ query</summary>
          <pre className="code" style={{ marginTop: 10 }}>{bill?.statement}</pre>
        </details>}
      </div>

      <div className="card" style={{ marginTop: 24, background: 'var(--surface-subtle)' }}>
        <h3 style={{ marginBottom: 6 }}>When to use reserved capacity</h3>
        <p style={{ fontSize: 'var(--ui-body)', marginBottom: 8 }}>
          Provisioned capacity can suit steady workloads or deployments on your own hardware. Compare costs for your actual usage.
        </p>
        <p style={{ fontSize: 'var(--ui-label)', color: 'var(--text-muted)', marginBottom: 0 }}>
          {exampleActive() ? '' : 'Model costs use configured list prices; SQL++ usage may be estimated. The reserved comparison uses an open-weight model, not Claude.'}
          {state && ` Configured rate: $${state.reserved.per_hour}/hour.`}
        </p>
      </div>
    </div>
  )
}


function usd(v: number) {
  return v < 10 ? `$${v.toFixed(2)}` : `$${Math.round(v)}`
}
