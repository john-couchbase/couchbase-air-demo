import Stat from '../components/MetricCard'
import './Dashboard.css'
import FlightMap from '../components/FlightMap'
import { demoResolution } from '../lib/example'
import { useEffect, useState } from 'react'
import {
  Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis,
  YAxis,
} from 'recharts'
import * as api from '../lib/api'
import type { State, Timeline } from '../lib/types'
import { approx } from '../lib/models'

/*
  Beat 1 and 2: the burst, and the cheap model reading all of it.

  The chart is arrivals against classification on one axis, both counts per five
  seconds. Arrivals are stacked so the normal trickle stays visible underneath
  the surge: the ratio between the two is the "10x" and the room should be able
  to see it rather than be told it.

  Classification is a line, not a bar, because it is a rate the system achieves rather
  than something that happened to it. On the laptop the line lags the surge
  (one GPU); on the sandbox it tracks it.

  Colors: surge red, baseline light grey, classified black. Red and black are the
  only two that carry meaning; grey is context.
*/

const SURGE = '#EC1218'
const BASE = '#A6ADB2'
const CLASSIFIED = '#547D91'

export default function Storm({ state, onTrigger, onTour, example, onOpenRequest, returnedRequest }: { state: State | null; onTrigger: () => void; onTour: () => void; example: boolean; returnedRequest: string | null; onOpenRequest: (id: string) => void }) {
  const [tl, setTl] = useState<Timeline | null>(null)
  const [requests,setRequests] = useState<{id:string;name:string;dest_city:string}[]>([])

  useEffect(() => {
    const load = () => {
      api.getTimeline().then(setTl).catch(() => {})
      if(!example) api.getResolutions().then(setRequests).catch(()=>{})
    }
    load()
    const t = window.setInterval(load, 1500)
    return () => window.clearInterval(t)
  }, [])

  const rows = (tl?.rows ?? []).map((r) => ({ ...r, x: r.t }))
  // The chart shows a rolling window, so a demo left running for an hour still
  // shows the storm at a readable width. The stats above use the whole run.
  const lastT = rows.length ? rows[rows.length - 1].t : 0
  const shown = rows.filter((r) => r.t > lastT - CHART_WINDOW_S)
  const stormX = tl?.storm_at_s != null ? Math.floor(tl.storm_at_s / tl.bucket_s) * tl.bucket_s : null
  const f = state?.funnel
  const hitRate = state && state.funnel.classified
    ? Math.round((state.cache.hits / state.funnel.classified) * 100) : 0

  // Peak against normal, both per bucket, from what actually arrived. The
  // normal trickle keeps running through the storm, so its average is taken
  // over the whole run rather than the few buckets before the storm.
  const baseAvg = Math.max(0.5, avg(rows.map((r) => r.baseline)))
  const peak = Math.max(0, ...rows.map((r) => r.baseline + r.surge))
  const ratio = example && tl?.storm_at_s != null ? Math.round(peak / baseAvg) : null


  return (
    <div className="fade-in">
      <header className="dashboard-heading"><div className="banner-copy">
        <div className="eyebrow">AIDP AIR</div>
        <h1>A smoother recovery, thoughtfully.</h1>
        <p className="lede">Airline support, powered by context.</p>
        <button type="button" className="btn red dashboard-storm-trigger" onClick={onTrigger} disabled={!state || state.phase !== 'normal'}>{!state ? 'Connecting…' : state.phase === 'normal' ? 'Trigger storm' : state.phase === 'quiet' ? 'Storm complete' : 'Storm running'}</button>

        </div>
        <svg className="air-banner-art" viewBox="0 0 400 190" fill="none" aria-hidden="true">
          <g className="banner-tiles">
            <g className="banner-tile tile-one"><rect x="284" y="12" width="56" height="40" rx="8" fill="#E4CDB0"/><path d="M296 25h30m-30 10h19" stroke="#655747" strokeWidth="3" strokeLinecap="round"/></g>
            <g className="banner-tile tile-two"><rect x="334" y="66" width="52" height="44" rx="8" fill="#547D91"/><path d="M345 95v-9m10 9V78m10 17V83m10 12V74" stroke="#fff" strokeWidth="3" strokeLinecap="round"/></g>
            <g className="banner-tile tile-three"><rect x="284" y="132" width="62" height="36" rx="8" fill="#F0B665"/><circle cx="297" cy="150" r="4" fill="#655747"/><path d="M309 150h23" stroke="#655747" strokeWidth="3" strokeLinecap="round"/></g>
          </g>
          <ellipse cx="211" cy="157" rx="133" ry="9" fill="#655747" opacity=".08"/>
          <path d="M22 142C96 142 122 116 168 112" stroke="#547D91" strokeOpacity=".35" strokeWidth="1.5" strokeDasharray="4 6"/>
          <g transform="translate(-8 12) scale(.86) rotate(-9 200 95)">
            {/* Far wing, vertical tail and rear stabilizer behind the fuselage. */}
            <path d="M194 91 153 37 170 36 242 91Z" fill="#C8CDD0" stroke="#8A969C" strokeWidth="1.2"/>
            <path d="M70 94 45 37 64 38 107 93Z" fill="#EC1218"/>
            <path d="M76 102 44 79 58 77 106 98Z" fill="#DCE1E3" stroke="#8A969C" strokeWidth="1.2"/>
            {/* Long cabin, tapered tail and rounded cockpit. */}
            <path d="M53 94 279 87C303 87 321 94 336 104 343 109 339 115 325 117L99 117C80 116 65 110 53 103Z" fill="#FAFAF7" stroke="#849198" strokeWidth="1.5"/>
            <path d="M78 108H333C331 112 326 114 317 115H102Z" fill="#E2E7E8"/>
            <path d="M292 90 307 93 317 100 296 100Z" fill="#395866"/>
            <path d="M287 90 290 100H281V90Z" fill="#395866"/>
            {/* Passenger windows and doors. */}
            {[117,130,143,156,169,182,195,208,221,234,247,260].map(x=><rect key={x} x={x} y="96" width="6" height="5" rx="2" fill="#547D91"/>)}
            <rect x="102" y="94" width="7" height="17" rx="2" stroke="#8A969C"/>
            <rect x="269" y="92" width="7" height="18" rx="2" stroke="#8A969C"/>
            {/* Near swept wing and cylindrical engine nacelle. */}
            <path d="M204 104 149 154 171 156 252 108Z" fill="#D8DFE2" stroke="#849198" strokeWidth="1.3"/>
            <path d="M169 151 166 163 174 162 181 150Z" fill="#EC1218"/>
            <path d="M225 125H247C255 125 256 141 247 142H225Z" fill="#F8F8F4" stroke="#849198" strokeWidth="1.3"/>
            <ellipse cx="247" cy="133.5" rx="5" ry="8.5" fill="#547D91"/>
            <ellipse cx="247" cy="133.5" rx="2.5" ry="5.5" fill="#263C47"/>
            <path d="M59 101 31 119 49 122 95 108" fill="#D8DFE2" stroke="#849198" strokeWidth="1.2"/>
          </g>
        </svg>
      </header>

      <div className="dashboard-visuals"><FlightMap returnedRequest={returnedRequest} state={state} onTour={onTour} onOpenRequest={onOpenRequest} />
      <div className="card message-traffic" data-tour-target="requests" style={{ marginTop: 24 }}>
        <h3 style={{ marginBottom: 4 }}>Message activity</h3>
        <p style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', marginBottom: 14 }}>
          Counts every {tl?.bucket_s ?? 5} seconds over the last {CHART_WINDOW_S / 60} minutes.
        </p>
        <div className="chart-legend">
          <Key color={BASE} label="Normal traffic" />
          <Key color={SURGE} label="Storm traffic" />
          <Key color={CLASSIFIED} label="Classified" line />
        </div>
        <div className="message-chart" style={{ height: 280 }}>
          {shown.length === 0 && <div className="message-chart-empty"><strong>{state ? 'Waiting for messages' : 'Awaiting connection'}</strong><span>Incoming traffic and classifications appear here.</span></div>}
          <ResponsiveContainer>
            <ComposedChart data={shown} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--border-subtle)" strokeWidth={2} />
              <XAxis dataKey="x" tick={{ fontSize: 14, fill: '#595953' }}
                     tickFormatter={clock} stroke="var(--border-subtle)" strokeWidth={2}
                     minTickGap={40} />
              <YAxis tick={{ fontSize: 14, fill: '#595953' }} allowDecimals={false}
                     stroke="var(--border-subtle)" strokeWidth={2} width={40} />
              <Tooltip labelFormatter={(v) => clock(Number(v))}
                       contentStyle={{ fontSize: 'var(--ui-label)', borderRadius: 8 }} />
              {stormX != null && shown.length > 0 && stormX >= shown[0].t && (
                <ReferenceLine x={stormX}
                               stroke={SURGE} strokeDasharray="4 4" strokeWidth={2}
                               label={{ value: 'Storm', position: 'insideTopLeft', fill: SURGE, fontSize: 14 }} />
              )}
              <Bar dataKey="baseline" name="Normal" stackId="a" fill={BASE} isAnimationActive={false} />
              <Bar dataKey="surge" name="Storm" stackId="a" fill={SURGE} isAnimationActive={false} />
              <Line dataKey="classified" name="Classified" stroke={CLASSIFIED} strokeWidth={2.5}
                    dot={false} isAnimationActive={false} type="monotone" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

      </div>

      </div>
      <div className="dashboard-overview">

      <div className="stat-row dashboard-stats" data-tour-target="classification">
        <Stat value={f ? f.inbound.toLocaleString() : '–'} label="Messages in" />
        <Stat value={ratio ? `${ratio}x` : '–'} label="Peak vs normal" warm={!!ratio} />
        <Stat value={f ? f.classified.toLocaleString() : '–'} label="Messages classified" />
        <Stat value={state ? `${approx(state)}${hitRate}%` : '–'} label="Answered from cache" />
      </div>

      </div>

        <nav className="message-shortcuts" aria-label="Passenger conversations">
          {(example ? ['sample-001','sample-002','sample-003','sample-004'].map(demoResolution) : requests).map(r=><button key={r.id} type="button" onClick={()=>onOpenRequest(r.id)} aria-label={`View ${r.name}'s conversation`}><span><strong>{r.dest_city}</strong><span>{r.name}</span></span><span className="shortcut-action">View conversation</span></button>)}
        </nav>
    </div>
  )
}

export function Key({ color, label, line }: { color: string; label: string; line?: boolean }) {
  return (
    <span className="chart-key">
      <span aria-hidden="true" style={line
        ? { width: 24, height: 3, background: color, borderRadius: 2 }
        : { width: 12, height: 12, background: color, borderRadius: 3 }} />
      {label}
    </span>
  )
}

// How much of the demo's clock the rolling charts show: Storm's messages and
// Cost's spend per interval. Cost's summed chart keeps the whole run.
export const CHART_WINDOW_S = 15 * 60

export function clock(s: number) {
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

function avg(xs: number[]) {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0
}
