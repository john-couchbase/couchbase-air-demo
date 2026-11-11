import { exampleActive } from '../lib/example'
import { useEffect, useState } from 'react'
import * as api from '../lib/api'
import type { ModelsInfo } from '../lib/types'
import Eyebrow from '../components/Eyebrow'

/*
  The catalog, and which job runs on what.

  Reference, not story: this is where the room goes when someone asks "why
  Nova for classifying?" or "what does Claude cost?". The answer to the first is on
  the same row as the answer to the second, which is the point - model choice
  is a price and quality decision made per task.

  Part 1 of the field demo (the live model swap) happens in the Capella UI.
  This screen is what that swap changes in this app.
*/

export default function Models() {
  const [m, setM] = useState<ModelsInfo | null>(null)
  useEffect(() => { api.getModels().then(setM).catch(() => {}) }, [])
  const local = m?.backend.models !== 'model_service'
  // The price gap between the two models in use, from the catalog, so it stays
  // true when either model changes.
  const small = m?.catalog.find((c) => c.used_for.includes('classify'))
  const big = m?.catalog.find((c) => c.used_for.includes('agent'))
  const ratio = small && big && small.in_per_m > 0 ? Math.round(big.in_per_m / small.in_per_m) : null

  if (exampleActive()) return <div className="fade-in learn-view">
    <Eyebrow component="Model roles" tenets={[]} />
    <h1 style={{marginTop:8,marginBottom:6}}>Model roles</h1><p className="lede">The replay illustrates two jobs. No real model is selected or called.</p>
    <div className="reference-grid">
      <section className="card"><h3>Classification</h3><p>Labels the request type, priority, and needs. Routes complex requests to Recovery.</p><div className="reference-status">Scripted classifier</div></section>
      <section className="card"><h3>Recovery decisions</h3><p>Uses the supplied tool results and passenger context to illustrate a recommendation or staff handoff.</p><div className="reference-status">Scripted recommendation</div></section>
    </div><p className="reference-note">A connected deployment will supply its model catalog and rates. The Cost screen currently uses fictional values.</p>
  </div>

  return (
    <div className="fade-in learn-view">
      <Eyebrow component="Model Service" tenets={['Model per task']} />
      <h1 style={{ marginTop: 8, marginBottom: 6 }}>Model catalog</h1>
      <p className="lede" style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)' }}>
        Compare models for classification and decisions. Prices are per million tokens.
      </p>

      <div className="card" style={{ marginTop: 24, padding: '8px 12px' }}>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Model catalog"><table className="table">
          <thead>
            <tr>
              <th>Model</th><th>Good for</th><th className="num">Input / 1M</th>
              <th className="num">Output / 1M</th><th>In this demo</th>
              {local && <th>Local stand-in</th>}
            </tr>
          </thead>
          <tbody>
            {!m?.catalog.length && <tr><td colSpan={local ? 6 : 5} className="empty-note">Awaiting model catalog</td></tr>}
            {m?.catalog.map((c) => (
              <tr key={c.id}>
                <td>
                  <div style={{ fontWeight: 700, color: 'var(--text-strong)' }}>{c.name}</div>
                  <div className="mono" style={{ fontSize: 'var(--ui-meta)', color: 'var(--text-muted)' }}>{c.id}</div>
                </td>
                <td>{c.role}</td>
                <td className="num">${c.in_per_m.toFixed(3)}</td>
                <td className="num">${c.out_per_m.toFixed(2)}</td>
                <td>
                  {c.used_for.map((u) => (
                    <span key={u} className="tag hot" style={{ fontSize: 'var(--ui-meta)', marginRight: 6 }}>
                      {u === 'classify' ? 'Classification' : 'Escalated decisions'}
                    </span>
                  ))}
                </td>
                {local && <td className="mono" style={{ fontSize: 'var(--ui-meta)', color: 'var(--cb-burgundy)' }}>{c.local_standin}</td>}
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>
      <p style={{ fontSize: 'var(--ui-body)', color: 'var(--text-muted)', marginTop: 12 }}>
        Amazon Bedrock on-demand list prices, us-east-1.
        {small && big && ratio && ratio > 1 && (
          <> {small.name.replace(/^Amazon /, '')} reads a message for about 1/{ratio}th of what{' '}
            {big.name} charges for the same input.</>
        )}
      </p>

      <div className="stat-row" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 24 }}>
        <div className="card">
          <div className="eyebrow" style={{ color: 'var(--cb-red)' }}>Swap a model</div>
          <p style={{ fontSize: 'var(--ui-body)', margin: '8px 0 0' }}>
            The classification AI Function is bound to one model. Point it at Nova Lite, Llama 4 or Claude
            Haiku and the same statement runs on the new model, with no redeploy, no capacity
            request and no second fleet.
          </p>
        </div>
        <div className="card">
          <div className="eyebrow">Provisioned, same endpoint</div>
          <p style={{ fontSize: 'var(--ui-body)', margin: '8px 0 0' }}>
            NVIDIA NIM on dedicated GPUs sits in the same catalog for steady, sensitive or
            air-gapped workloads. The application does not change when a workload moves.
          </p>
        </div>
      </div>
    </div>
  )
}
