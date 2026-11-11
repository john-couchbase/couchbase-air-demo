/*
  Before and after, as two columns of the same five questions.

  Rows rather than two free-form lists so the eye can go straight across: for
  each thing a team has to decide about inference, what it looks like with a
  provisioned fleet and what it looks like with serverless models. The left
  column is grey on purpose. It is not wrong, it is the cost of doing it that
  way, and the NIM option on this page is still the right answer for some of
  it.
*/

const ROWS: [string, string, string][] = [
  ['Capacity', 'Sized for the peak you forecast, reserved in advance',
   'None to size. A 10x burst is absorbed as it happens'],
  ['Cost when idle', 'The full hourly rate, around the clock',
   'Zero. You pay for tokens, and no tokens cost nothing'],
  ['Model choice', 'One model per fleet, because each fleet costs money',
   'A different model per task: small for volume, frontier for judgment'],
  ['Where inference runs', 'An app tier that pulls data out to reach the model',
   'Inside the data workflow: a SQL++ statement calls the model'],
  ['Time to first result', 'Weeks: a capacity request, drivers, patching',
   'Minutes: pick a model, deploy an endpoint, call it'],
]

export default function ReplacesDiagram() {
  return (
    <figure style={{ margin: '20px 0 0' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: '200px 1fr 1fr',
        border: '2px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
      }}>
        <div style={head} />
        <div style={{ ...head, color: 'var(--text-muted)' }}>Provisioned GPU fleet</div>
        <div style={{ ...head, color: 'var(--cb-red)' }}>Serverless models in the Model Service</div>
        {ROWS.map(([q, before, after], i) => (
          <Row key={q} q={q} before={before} after={after} last={i === ROWS.length - 1} />
        ))}
      </div>
      <figcaption style={{ fontSize: 16, color: 'var(--text-muted)', marginTop: 12 }}>
        The provisioned option has not gone anywhere. It is still the cheaper answer for load that
        is steady and high, and the only answer when data must stay on your own hardware.
      </figcaption>
    </figure>
  )
}

function Row({ q, before, after, last }: { q: string; before: string; after: string; last: boolean }) {
  const border = last ? 'none' : '2px solid var(--surface-subtle)'
  return (
    <>
      <div style={{ ...cell, borderBottom: border, fontWeight: 700, color: 'var(--text-strong)' }}>
        {q}
      </div>
      <div style={{ ...cell, borderBottom: border, color: 'var(--text-muted)' }}>{before}</div>
      <div style={{ ...cell, borderBottom: border, color: 'var(--text-strong)', fontWeight: 600 }}>
        {after}
      </div>
    </>
  )
}

const head: React.CSSProperties = {
  padding: '14px 16px', fontSize: 14, fontWeight: 700, textTransform: 'uppercase',
  letterSpacing: '0.07em', background: 'var(--surface-subtle)',
}
const cell: React.CSSProperties = { padding: '14px 16px', fontSize: 17, lineHeight: 1.4 }
