/*
  What the AI Data Plane replaces.

  One claim, drawn as a difference rather than stated as a benefit: the same
  agent either talks to six systems that have to be kept in step, or to one.
  The crossing lines on the left are the point - they are what "scattered agent
  infrastructure" actually looks like, and they disappear on the right.

  Red marks the consolidated side, since that is the element under discussion.
*/

const LEFT = [
  ['Vector database', 'embeddings'],
  ['Session store', 'agent memory'],
  ['Semantic cache', 'to cut inference cost'],
  ['GPU fleet', 'to serve the models'],
  ['Pipeline / ETL', 'to move data to them'],
  ['Operational DB', 'flights, bookings'],
]

// Shown as what lives behind the one endpoint. They are collections in this
// demo's one scope, but the claim on screen is deliberately about the endpoint:
// how many places the agent has to talk to, not how the data is partitioned
// behind it. A larger deployment may well use several buckets and the argument
// is unchanged.
const SCOPES = ['messages', 'bookings', 'memory', 'meter']
const RED = '#EC1218'

export default function ConsolidationDiagram() {
  return (
    <figure style={{ margin: '26px 0 0' }}>
      <svg
        viewBox="0 0 1180 382"
        role="img"
        aria-label={
          'A comparison. On the left, one agent connects to six separate systems - a vector ' +
          'database, session store, semantic cache, GPU fleet, data pipeline and operational ' +
          'database - with crossing connections. On the right, the same agent connects to a ' +
          'single Couchbase endpoint, with four collections inside it.'
        }
        style={{ width: '100%', height: 'auto', color: 'var(--text-strong)' }}
      >
        <defs>
          <marker id="cd-arrow" viewBox="0 0 10 10" refX="9" refY="5"
                  markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
          </marker>
        </defs>

        {/* ---------------- left: six systems ---------------- */}
        <text x="20" y="26" fontSize="16" fontWeight="700" fill="currentColor"
              opacity="0.6" letterSpacing="0.07em">TYPICALLY</text>
        <text x="20" y="50" fontSize="19" fontWeight="700" fill="currentColor">
          Six systems to keep in step
        </text>

        <rect x="180" y="72" width="160" height="46" rx="8"
              fill="var(--surface-page)" stroke="currentColor" strokeWidth="2" />
        <text x="260" y="101" fontSize="18" fontWeight="700" textAnchor="middle"
              fill="currentColor">One agent</text>

        {LEFT.map(([name, sub], i) => {
          const col = i % 3
          const row = Math.floor(i / 3)
          const x = 20 + col * 172
          const y = 196 + row * 84
          return (
            <g key={name}>
              <line x1="260" y1="120" x2={x + 76} y2={y - 4}
                    stroke="currentColor" strokeWidth="1.5" opacity="0.5"
                    markerEnd="url(#cd-arrow)" />
              <rect x={x} y={y} width="152" height="62" rx="8"
                    fill="var(--surface-page)" stroke="currentColor" strokeWidth="2" />
              <text x={x + 12} y={y + 26} fontSize="16" fontWeight="700" fill="currentColor">
                {name}
              </text>
              <text x={x + 12} y={y + 47} fontSize="14" fill="currentColor" opacity="0.66">
                {sub}
              </text>
            </g>
          )
        })}

        {/* ---------------- divider ---------------- */}
        <line x1="566" y1="20" x2="566" y2="352" stroke="currentColor"
              strokeWidth="2" opacity="0.18" />

        {/* ---------------- right: one layer ---------------- */}
        <text x="606" y="26" fontSize="16" fontWeight="700" fill={RED}
              letterSpacing="0.07em">WITH THE AI DATA PLANE</text>
        <text x="606" y="50" fontSize="19" fontWeight="700" fill="currentColor">
          One governed layer
        </text>

        {/* Box is 490 x 157 so the padding is 20 on all four sides: the chips
            end at x=1076 and the last line of text at y=333, and the title's
            ink starts 12.5px below its baseline rather than the ~19 the font
            metrics imply - so the top edge sits at 188, not 196. It was
            480 x 146, which left 10 on the right and 9 at the bottom against
            20 on the left. Centre moves 846 -> 851 to follow. */}
        <rect x="771" y="72" width="160" height="46" rx="8"
              fill="var(--surface-page)" stroke="currentColor" strokeWidth="2" />
        <text x="851" y="101" fontSize="18" fontWeight="700" textAnchor="middle"
              fill="currentColor">One agent</text>

        <line x1="851" y1="120" x2="851" y2="180" stroke={RED} strokeWidth="3"
              markerEnd="url(#cd-arrow)" />

        <rect x="606" y="188" width="490" height="165" rx="10"
              fill="var(--surface-page)" stroke={RED} strokeWidth="3" />
        <text x="626" y="228" fontSize="18" fontWeight="700" fill="currentColor">
          Couchbase, one endpoint
        </text>
        {SCOPES.map((sc, i) => (
          <g key={sc}>
            {/* 108 wide at 13px mono: agent_catalog is 13 characters and
                overflowed a 100-wide chip at 14px. */}
            <rect x={626 + i * 114} y={246} width="108" height="34" rx="6"
                  fill="var(--surface-subtle)" />
            <text x={680 + i * 114} y={268} fontSize="13" textAnchor="middle"
                  fill="currentColor" fontFamily="ui-monospace, Menlo, monospace">{sc}</text>
          </g>
        ))}
        <text x="626" y="308" fontSize="15" fill="currentColor" opacity="0.7">
          operational data, memory, vectors, cache and models
        </text>
        <text x="626" y="329" fontSize="15" fill="currentColor" opacity="0.7">
          behind one endpoint, queryable with SQL++
        </text>
      </svg>

      <figcaption style={{
        fontSize: 17, color: 'var(--text-muted)', marginTop: 14,
      }}>
        Nothing on the left is wrong. It is what most agent stacks are. The cost is that six
        systems have to agree about the same customer, the data has to travel to reach the model,
        and someone has to keep a GPU fleet sized for a peak nobody can forecast.
      </figcaption>
    </figure>
  )
}
