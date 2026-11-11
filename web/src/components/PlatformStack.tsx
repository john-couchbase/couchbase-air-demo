/*
  The four layers of one Couchbase platform.

  Drawn from the design system's approved stacked-disc motif rather than
  hotlinking the marketing PNG: couchbase.com sits behind a WAF that refuses
  non-browser fetches, and a broken image on the customer's network mid-demo
  would be worse than no image. The link to the original is still offered for
  anyone who wants the full asset in its own window.

  Colours and labels match the published diagram, and all four are inside the
  closed palette.
*/

const LAYERS = [
  { label: 'AI Data Plane', fill: 'var(--cb-black)', ink: '#FFFFFF' },
  { label: 'Operational Insights', fill: 'var(--cb-orange)', ink: '#FFFFFF' },
  { label: 'Mobile', fill: 'var(--cb-red)', ink: '#FFFFFF' },
  { label: 'Transactional', fill: 'var(--cb-burgundy)', ink: '#FFFFFF' },
]

/*
  Geometry is derived from a target height so the stack can be matched to the
  column of text beside it. Scaling the old proportions down would have
  narrowed it to ~140px, where "Transactional" no longer fits at 16px - so the
  discs get flatter instead, which is closer to the published diagram anyway.

  Width stays at 300: that is what the longest label needs.
*/
const W = 300
const RX = W / 2
const PAD = 12

export default function PlatformStack({
  highlight = 'AI Data Plane', height = 352,
}: { highlight?: string; height?: number }) {
  const H = height
  const RY = Math.min(40, Math.max(18, Math.round(H * 0.085)))
  const GAP = (H - RY * 2 - PAD) / LAYERS.length

  return (
    <svg
      viewBox={`0 0 ${W + 4} ${H}`}
      role="img"
      aria-label={
        'One Couchbase platform in four stacked layers, from the top: AI Data Plane, ' +
        'Operational Insights, Mobile, and Transactional.'
      }
      style={{ width: '100%', maxWidth: W, height: 'auto', display: 'block' }}
    >
      {/* bottom-up, so upper discs overlap the ones beneath */}
      {[...LAYERS].reverse().map((l, ri) => {
        const i = LAYERS.length - 1 - ri
        const top = RY + PAD / 2 + i * GAP
        const dim = l.label !== highlight
        return (
          <g key={l.label} opacity={dim ? 0.85 : 1}>
            <rect x="2" y={top} width={RX * 2} height={GAP} fill={l.fill} />
            <ellipse cx={RX + 2} cy={top + GAP} rx={RX} ry={RY} fill={l.fill} />
            <ellipse cx={RX + 2} cy={top} rx={RX} ry={RY} fill={l.fill} />
            {l.label === 'AI Data Plane' && (
              <>
                <ellipse cx={RX + 2} cy={top} rx={RX * 0.78} ry={RY * 0.7}
                         fill="var(--cb-peach)" opacity="0.92" />
                {[-52, -18, 16, 50].map((dx, k) => (
                  <ellipse key={k} cx={RX + 2 + dx} cy={top + (k % 2 ? RY * 0.24 : -RY * 0.2)}
                           rx={RY * 0.5} ry={RY * 0.2} fill="var(--cb-black)" />
                ))}
              </>
            )}
            {/*
              Centred in the VISIBLE layer, not in the band rectangle.

              Each layer's band runs top -> top+GAP, but its top RY is hidden
              under the disc of the layer above, and its own disc bulges RY
              below. So the visible extent is top+RY -> top+GAP+RY and the
              centre is one radius lower than the band's. The +5 is the
              baseline offset for 16px text.
            */}
            <text x={RX + 2} y={top + RY + GAP / 2 + 5} textAnchor="middle"
                  fontSize="16" fontWeight="700" fill={l.ink}>
              {l.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
