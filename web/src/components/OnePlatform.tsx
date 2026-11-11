import { useEffect, useRef, useState } from 'react'
import PlatformStack from './PlatformStack'

/*
  Context for everything else on this screen.

  Two jobs. It says where the AI Data Plane sits - one layer of one platform,
  not a separate product bolted on - and it names the Mobile layer, which is
  how the same data reaches a device with no network at all.

  The mobile components are explicitly marked as NOT wired into this demo. The
  honesty discipline that governs the component list below has to hold here
  too: we are not running Couchbase Lite, and a reader should not have to
  guess which parts are claims about the platform and which are claims about
  what is on screen.
*/

const LAYERS = [
  ['AI Data Plane', 'Models, agent memory, AI functions, cache and governed data access. This demo.'],
  ['Operational Insights', 'Real-time analytics over the same operational data.'],
  ['Mobile', 'Cloud to edge to device, with on-device vector search.'],
  ['Transactional', 'The operational JSON database underneath all of it.'],
]


export default function OnePlatform() {
  const row = useRef<HTMLDivElement>(null)
  const [stackH, setStackH] = useState(352)

  // Match the stack to the height of the layer list beside it.
  useEffect(() => {
    const measure = () => {
      const text = row.current?.children[1] as HTMLElement | undefined
      if (text) setStackH(Math.max(240, Math.round(text.getBoundingClientRect().height)))
    }
    measure()
    const ro = new ResizeObserver(measure)
    if (row.current?.children[1]) ro.observe(row.current.children[1])
    return () => ro.disconnect()
  }, [])

  return (
    <div style={{ marginTop: 44 }}>
      <h2 style={{ marginBottom: 6 }}>Where this sits</h2>
      <p className="lede" style={{ fontSize: 19, color: 'var(--text-muted)' }}>
        The AI Data Plane is one layer of one platform. It is not a separate product bolted on to
        the side of it.
      </p>

      <div
        ref={row}
        style={{
          display: 'flex', gap: 44, alignItems: 'flex-start', marginTop: 24, flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '0 0 300px' }}>
          {/* Measured against the text beside it rather than guessed, so the two
              columns stay the same height if the copy changes. */}
          <PlatformStack height={stackH} />
        </div>

        <div style={{ flex: '1 1 420px', minWidth: 380 }}>
          {LAYERS.map(([name, what]) => (
            <div key={name} style={{
              paddingBottom: 14, marginBottom: 14,
              borderBottom: '2px solid var(--border-subtle)',
            }}>
              <div style={{ fontSize: 19, fontWeight: 700, color: 'var(--text-strong)' }}>
                {name}
              </div>
              <div style={{ fontSize: 17, color: 'var(--text-body)', marginTop: 2 }}>{what}</div>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
