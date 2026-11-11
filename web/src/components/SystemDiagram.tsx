import type { State } from '../lib/types'
import { agentName, approx, classifyFull, viaSqlpp } from '../lib/models'

/*
  What the system is doing right now: passengers, the AI Data Plane, and the
  serverless models, with the models' requests in flight lit up live.

  The point it has to make without narration is that the models are used, not
  run: there is no fleet in the picture, only requests. On a normal morning the
  slots are dark and the spend meter reads zero; in the storm the classification model
  row fills and Claude's lights up for the few; afterwards both go dark again.

  Slots are requests in flight, not instances. Serverless has no instances to
  draw, and pretending otherwise would be the one lie in the diagram. The
  number of slots is the demo's own concurrency limit, which the caption says.

  Motion is deliberately limited to things switching on and off. Over a screen
  share, moving dots stutter and read as breakage; a light coming on reads as
  load.

  Colors: the classification model black, Claude red - the same as the cost chart, so a
  viewer who has seen one can read the other. Idle is the subtle surface.
*/

const RED = '#EC1218'
const INK = '#000000'
const IDLE = 'var(--surface-subtle)'
const IDLE_EDGE = '#D4D4D4'

export default function SystemDiagram({ state }: { state: State | null }) {
  const live = state?.live
  const inFlightC = live?.classify_in_flight ?? 0
  const inFlightA = live?.agent_in_flight ?? 0
  const slotsC = live?.classify_slots ?? 16
  const slotsA = live?.agent_slots ?? 8
  const arriving = (live?.arrivals_per_s ?? 0) > 0
  const classifying = inFlightC > 0 || (live?.classify_per_s ?? 0) > 0
  const deciding = inFlightA > 0
  const hitPct = state && state.funnel.classified
    ? Math.round((state.cache.hits / state.funnel.classified) * 100) : 0
  const local = state?.backend.models !== 'model_service'

  return (
    <figure style={{ margin: '20px 0 0' }}>
      <svg
        viewBox="0 0 1180 430"
        role="img"
        aria-label={
          'Live system diagram. Passenger messages land in the messages collection of the '
          + `Couchbase AI Data Plane. ${viaSqlpp(state) ? 'An AI Function in SQL++' : 'The app'} classifies each one, through a `
          + `semantic cache, using ${classifyFull(state)} in the serverless Model Service. A funnel `
          + 'query passes the few that need judgment to a recovery agent, which reads Agent '
          + `Memory and calls ${agentName(state)}. Lit slots show requests in flight.`
        }
        style={{ width: '100%', height: 'auto', color: 'var(--text-strong)' }}
      >
        <defs>
          <marker id="sd-arrow" viewBox="0 0 10 10" refX="9" refY="5"
                  markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" />
          </marker>
        </defs>

        {/* ------------------------------------------------ passengers */}
        <Node x={16} y={78} w={150} h={100} title="Passengers"
              sub="app, chat, email" active={arriving} />
        <text x={91} y={206} fontSize="15" fontWeight="700" textAnchor="middle" fill="currentColor">
          {fmtRate(live?.arrivals_per_s)} msg/s
        </text>

        {/* --------------------------------------------- AI Data Plane */}
        <rect x={196} y={24} width={560} height={396} rx={14}
              fill="none" stroke="currentColor" strokeWidth={2} />
        <text x={216} y={52} fontSize="14" fontWeight="700" letterSpacing="0.08em" fill="currentColor">
          COUCHBASE AI DATA PLANE
        </text>

        <Node x={216} y={90} w={150} h={76} title="messages" mono sub="lands as JSON" active={arriving} />
        <Node x={406} y={90} w={150} h={76} title={viaSqlpp(state) ? 'AI Function' : 'Classify'}
              sub={viaSqlpp(state) ? 'classify, in SQL++' : 'model called directly'} active={classifying} />
        <Node x={596} y={90} w={140} h={76} title="Semantic cache"
              sub={hitPct ? `${approx(state)}${hitPct}% answered here` : 'repeats answered here'} active={(live?.cache_per_s ?? 0) > 0} />
        <Node x={596} y={200} w={140} h={60} title="Agent Memory" sub="history, notes" active={deciding} />
        <Node x={406} y={300} w={150} h={76} title="Funnel query" sub="urgency + tier"
              active={classifying || deciding} />
        <Node x={596} y={300} w={140} h={76} title="Recovery agent" sub="+ partner routes"
              active={deciding} hot={deciding} />

        <Edge d="M166 128 L212 128" on={arriving} />
        <Edge d="M366 128 L402 128" on={classifying} />
        <Edge d="M556 128 L592 128" on={classifying} />
        <Edge d="M481 166 L481 296" on={classifying} />
        <EdgeLabel x={489} y={236} text="classified" />
        <Edge d="M556 338 L592 338" on={deciding} hot />
        <Edge d="M666 260 L666 296" on={deciding} />

        <text x={216} y={400} fontSize="14" fill="currentColor" opacity={0.6}>
          One cluster. Every step above is a document or a SQL++ statement.
        </text>

        {/* -------------------------------------------- Model Service */}
        <rect x={786} y={24} width={378} height={396} rx={14}
              fill="none" stroke={RED} strokeWidth={3} />
        <text x={806} y={52} fontSize="14" fontWeight="700" letterSpacing="0.08em" fill={RED}>
          MODEL SERVICE / SERVERLESS
        </text>
        <text x={806} y={72} fontSize="14" fill="currentColor" opacity={0.6}>
          Amazon Bedrock, billed per token. Nothing reserved.
        </text>

        <Edge d="M736 128 L796 128" on={(live?.classify_per_s ?? 0) > 0 || inFlightC > 0} />
        <Edge d="M736 338 L796 338" on={deciding} hot />

        <Lane y={100} name={classifyFull(state)} sub="every message the cache can't answer"
              slots={slotsC} lit={inFlightC} color={INK}
              caption={`${inFlightC} in flight / ${fmtRate(live?.classify_per_s)} calls/s`} />
        <Lane y={296} name={agentName(state)} sub="judgment, for the few"
              slots={slotsA} lit={inFlightA} color={RED}
              caption={`${inFlightA} in flight`} />
      </svg>

      {/* stat-row, not a bare grid: it cancels the .card + .card top margin,
          which otherwise pushes the second meter 16px lower than the first. */}
      <div className="stat-row" style={{ gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 14 }}>
        <Meter label="Spending right now" value={live?.spend_per_min ?? 0} color={RED}
               note={`last ${live?.window_s ?? 10}s, at list price`} />
        <Meter label="A reserved GPU, the same minute" value={live?.reserved_per_min ?? 0}
               color="#0266C2" note={`${state?.reserved.label ?? 'GPU instance'}, busy or idle`} />
      </div>

      <figcaption style={{ fontSize: 16, color: 'var(--text-muted)', marginTop: 12 }}>
        A lit slot is one request in flight. Serverless has no fleet to draw: capacity appears
        with the requests and disappears with them.
        {local && ' On this laptop the slots are capped by the local stand-in\'s concurrency (16 and 8); on Bedrock they are not.'}
      </figcaption>
    </figure>
  )
}

function Node({ x, y, w, h, title, sub, active, hot, mono }: {
  x: number; y: number; w: number; h: number; title: string; sub: string
  active: boolean; hot?: boolean; mono?: boolean
}) {
  const stroke = active ? (hot ? RED : INK) : IDLE_EDGE
  return (
    <g style={{ transition: 'opacity 300ms' }}>
      <rect x={x} y={y} width={w} height={h} rx={8}
            fill="var(--surface-page)" stroke={stroke} strokeWidth={active ? 3 : 2} />
      <text x={x + 12} y={y + (h > 64 ? 30 : 26)} fontSize="16" fontWeight="700" fill="currentColor"
            fontFamily={mono ? 'ui-monospace, Menlo, monospace' : undefined}>
        {title}
      </text>
      <text x={x + 12} y={y + (h > 64 ? 52 : 46)} fontSize="13.5" fill="currentColor" opacity={0.62}>
        {sub}
      </text>
    </g>
  )
}

function Edge({ d, on, hot }: { d: string; on: boolean; hot?: boolean }) {
  return (
    <path d={d} fill="none" markerEnd="url(#sd-arrow)"
          stroke={on ? (hot ? RED : INK) : IDLE_EDGE} strokeWidth={on ? 3 : 2}
          strokeDasharray={on ? undefined : '5 5'} />
  )
}

function EdgeLabel({ x, y, text }: { x: number; y: number; text: string }) {
  return <text x={x} y={y} fontSize="13" fill="currentColor" opacity={0.6}>{text}</text>
}

function Lane({ y, name, sub, slots, lit, color, caption }: {
  y: number; name: string; sub: string; slots: number; lit: number; color: string; caption: string
}) {
  const per = 8
  const w = 36, h = 22, gap = 6
  const rows = Math.ceil(slots / per)
  return (
    <g>
      <text x={806} y={y} fontSize="17" fontWeight="700" fill="currentColor">{name}</text>
      <text x={806} y={y + 20} fontSize="13.5" fill="currentColor" opacity={0.62}>{sub}</text>
      {Array.from({ length: slots }, (_, i) => {
        const r = Math.floor(i / per), c = i % per
        const on = i < lit
        return (
          <rect key={i} x={806 + c * (w + gap)} y={y + 34 + r * (h + gap)} width={w} height={h} rx={4}
                fill={on ? color : IDLE} stroke={on ? color : IDLE_EDGE} strokeWidth={1.5}
                style={{ transition: 'fill 250ms, stroke 250ms' }} />
        )
      })}
      <text x={806} y={y + 34 + rows * (h + gap) + 18} fontSize="14" fontWeight="600"
            fill="currentColor">
        {caption}
      </text>
    </g>
  )
}

function Meter({ label, value, color, note }: {
  label: string; value: number; color: string; note: string
}) {
  return (
    <div className="card" style={{ display: 'flex', alignItems: 'baseline', gap: 16, padding: '14px 18px' }}>
      <span style={{ fontSize: 34, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums', minWidth: 150 }}>
        {/* Four places below a cent: a trickle costs fractions of one, and
            rounding it to $0.000 would claim it is free. */}
        ${value < 0.01 ? value.toFixed(4) : value.toFixed(3)}<span style={{ fontSize: 16, color: 'var(--text-muted)' }}>/min</span>
      </span>
      <span>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-strong)' }}>{label}</div>
        <div style={{ fontSize: 14, color: 'var(--text-muted)' }}>{note}</div>
      </span>
    </div>
  )
}

function fmtRate(v?: number) {
  if (!v) return '0'
  return v < 10 ? v.toFixed(1) : Math.round(v).toString()
}
