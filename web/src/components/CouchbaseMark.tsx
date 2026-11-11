/*
  The Couchbase logomark, inlined.

  The shipped SVG uses fill="currentColor", which cannot inherit anything when
  loaded through an <img> - an image is an isolated document, so currentColor
  resolves to black and the only way to change it was a filter: invert(1) hack
  that could produce white and nothing else. Inlining the path gives exact
  colour control, which is what a brand mark needs.

  Recolouring is permitted: this project is the official Couchbase design
  template.
*/

export default function CouchbaseMark({
  size = 26, color = 'var(--cb-red)',
}: { size?: number; color?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Couchbase"
      style={{ display: 'block', flex: '0 0 auto' }}
    >
      <path
        fill={color}
        d="M83.1,58.6c0,2.9-1.7,5.5-5,6.1c-5.8,1-17.9,1.6-28.1,1.6s-22.3-0.7-28.1-1.6c-3.3-0.6-5-3.2-5-6.1V39.4c0-2.9,2.3-5.7,5-6.1c1.7-0.3,5.6-0.6,8.8-0.6c1.2,0,2.2,0.9,2.2,2.3v13.3c5.9,0,11.1-0.3,17.1-0.3s11.2,0.3,17.2,0.3V35.1c0-1.4,1-2.3,2.2-2.3c3.2,0,7.1,0.3,8.8,0.6c2.7,0.4,5,3.2,5,6.1L83.1,58.6z M50,1C22.9,1,1,22.9,1,50s21.9,49,49,49s49-21.9,49-49S77.1,1,50,1L50,1z"
      />
    </svg>
  )
}
