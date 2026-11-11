import { useState } from 'react'
import type { State } from '../lib/types'

/*
  What the run means at a customer's scale. The demo storm is a few hundred
  messages and costs cents; a hub closure is tens of thousands. Everything here
  is projected from this run's measured cost per message, escalation share and
  cost per decision, never invented, and the assumptions are on screen and
  editable so a room can put in its own numbers.

  Serverless scales with the messages. The reserved fleet is sized for the peak
  and paid every hour of the year, storm or not, which is the point.

  Normal days are charged at the storm's average cost per message, which
  includes the storm's escalations; real quiet days escalate less, so the
  serverless figure is high and the saving shown is conservative.
*/

type Preset = 'run' | 'storm' | 'year'

const HOURS_PER_YEAR = 24 * 365

// Until the run has measured enough (a Reset with no storm yet), project from a
// typical storm instead: the measured unit costs of a real one, said so on
// screen. From the us-east-2 storm of 2026-10-07 (Nova 2 Lite + Claude Sonnet 5,
// fresh cache): 364 messages, $0.1034 classifying, 16 decisions, $0.1792.
const TYPICAL = {
  perMsg: 0.1034 / 364, escShare: 16 / 364, perDecision: 0.1792 / 16,
  source: 'a typical storm (us-east-2, Nova 2 Lite and Claude Sonnet 5, 7 Oct 2026)',
}

export default function Projection({ state }: { state: State | null }) {
  const [preset, setPreset] = useState<Preset>('year')
  const [stormMsgs, setStormMsgs] = useState(50_000)
  const [stormsPerYear, setStormsPerYear] = useState(12)
  const [normalPerDay, setNormalPerDay] = useState(2_000)
  const [gpus, setGpus] = useState(4)  // instances, e.g. g6e.12xlarge = 4 GPUs each

  const msgs = state?.funnel.classified ?? 0
  const decisions = state?.tokens.agent.calls ?? 0
  const classifyUsd = state?.spend.classify ?? 0
  const agentUsd = state?.spend.agent ?? 0
  const perHour = state?.reserved.per_hour ?? 0
  const measured = msgs >= 50 && decisions > 0

  // Unit costs: this run's once it has measured enough, a typical storm's before.
  const perMsg = measured ? classifyUsd / msgs : TYPICAL.perMsg
  const escShare = measured ? decisions / msgs : TYPICAL.escShare
  const perDecision = measured ? agentUsd / decisions : TYPICAL.perDecision
  const perMsgAll = perMsg + escShare * perDecision

  const storm = stormMsgs * perMsgAll
  const year = stormsPerYear * storm + 365 * normalPerDay * perMsgAll
  const fleetYear = gpus * perHour * HOURS_PER_YEAR

  const view = {
    run: {
      serverless: state?.spend.total ?? 0, reserved: state?.reserved.so_far ?? 0,
      what: 'This demo run, measured.',
      vs: 'One reserved GPU instance over the same minutes',
    },
    storm: {
      serverless: storm, reserved: fleetYear,
      what: `One storm of ${stormMsgs.toLocaleString()} messages, at this run's cost per message.`,
      vs: `${gpus} reserved GPU instances, sized for that peak, for a year`,
    },
    year: {
      serverless: year, reserved: fleetYear,
      what: `${stormsPerYear} storms of ${stormMsgs.toLocaleString()} messages, plus `
        + `${normalPerDay.toLocaleString()} messages on every normal day.`,
      vs: `${gpus} reserved GPU instances, sized for the peak, every hour of the year`,
    },
  }[preset]
  const projected = preset !== 'run'
  const ratio = view.serverless > 0 ? view.reserved / view.serverless : 0

  return (
    <div className="card" style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
        <h3 style={{ marginBottom: 4 }}>Estimate at your scale</h3>
        <div role="group" aria-label="Scale" className="projection-presets">
          {([['run', 'This run'], ['storm', 'One hub storm'], ['year', 'One year']] as const).map(([k, label]) => (
            <button key={k} onClick={() => setPreset(k)} aria-pressed={preset === k} style={{
              fontFamily: 'inherit', fontSize: 'var(--ui-label)', fontWeight: 700, cursor: 'pointer',
              padding: '6px 14px', borderRadius: 'var(--radius-pill)', border: '2px solid',
              borderColor: preset === k ? 'var(--cb-red)' : 'var(--border-subtle)',
              background: preset === k ? 'var(--cb-red)' : 'transparent',
              color: preset === k ? '#fff' : 'var(--text-body)',
            }}>{label}</button>
          ))}
        </div>
      </div>
      <p style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', marginBottom: 16 }}>
        {view.what}{projected && (measured ? ' Projected from what this run measured.'
          : ' Based on a typical storm: trigger the storm to use this run\'s own figures.')}
      </p>

      {/* Aligned at the top so the three figures share a line; the labels under them
          wrap to different heights. */}
      <div className="projection-results">
          <Big label="Serverless" value={view.serverless} warm approx={projected} />
          <Big label={view.vs} value={view.reserved} approx={projected} />
          <div>
            <div style={{ fontSize: 'var(--ui-metric)', fontWeight: 500, color: 'var(--text-strong)', lineHeight: 1.05 }}>
              {ratio >= 1.5 ? `${ratio >= 100 ? Math.round(ratio).toLocaleString() : ratio.toFixed(ratio >= 10 ? 0 : 1)}×` : '–'}
            </div>
            <div style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', fontWeight: 600 }}>
              {ratio >= 1.5 ? 'Reserved cost per serverless dollar' : 'no meaningful gap at this scale'}
            </div>
          </div>
      </div>

      {projected && (
        <div style={{ marginTop: 18, paddingTop: 14, borderTop: '2px solid var(--border-subtle)' }}>
          <div className="projection-fields">
            <Field label="Messages in a hub storm" value={stormMsgs} set={setStormMsgs} step={5000} />
            {preset === 'year' && <Field label="Storms a year" value={stormsPerYear} set={setStormsPerYear} step={1} />}
            {preset === 'year' && <Field label="Messages on a normal day" value={normalPerDay} set={setNormalPerDay} step={500} />}
            <Field label="Reserved GPU instances for the peak" value={gpus} set={setGpus} step={1} />
          </div>
          <p style={{ fontSize: 'var(--ui-label)', color: 'var(--text-muted)', marginTop: 12, marginBottom: 0 }}>
            ≈ From {measured ? 'this run' : TYPICAL.source}: ${(perMsg * 1000).toFixed(2)} per 1,000
            messages classified, {(escShare * 100).toFixed(1)}% escalated, ${perDecision.toFixed(3)} per
            decision.{' '}
            Reserved: {state?.reserved.label} at ${perHour}/hour each. Normal days are charged at the
            storm's cost per message, escalations included, so the serverless figure is on the high side.
          </p>
        </div>
      )}
    </div>
  )
}

function Big({ label, value, warm, approx }: { label: string; value: number; warm?: boolean; approx?: boolean }) {
  return (
    <div>
      <div style={{
        fontSize: 'var(--ui-metric)', fontWeight: 500, lineHeight: 1.05,
        color: warm ? 'var(--cb-red)' : 'var(--text-strong)',
      }}>{approx ? '≈' : ''}{money(value)}</div>
      <div style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', fontWeight: 600 }}>{label}</div>
    </div>
  )
}

function Field({ label, value, set, step }: { label: string; value: number; set: (v: number) => void; step: number }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontWeight: 600, color: 'var(--text-body)' }}>
      {label}
      <input type="number" min={0} step={step} value={value}
             onChange={(e) => set(Math.max(0, Number(e.target.value) || 0))}
             style={{ fontFamily: 'inherit', fontSize: 'var(--ui-body)', width: 150, padding: '6px 10px',
                      border: '2px solid var(--border-subtle)', borderRadius: 8 }} />
    </label>
  )
}

export function money(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(v >= 10_000_000 ? 0 : 1)}M`
  if (v >= 10_000) return `$${Math.round(v / 1000).toLocaleString()}k`
  if (v >= 100) return `$${Math.round(v).toLocaleString()}`
  return `$${v.toFixed(2)}`
}
