/*
  The eyebrow, carrying the tenet this screen is evidence for.

  The Demo tab names three tenets up front. A list read at the start of a
  session is a list nobody recalls by the end of it, so each screen restates
  the ones it proves at the moment it proves them. Names must match TENETS in
  views/Demo.tsx exactly.
*/

export default function Eyebrow({ component, tenets }: { component?: string; tenets: string[] }) {
  return (
    <div className="eyebrow">
      <span>Couchbase AI Data Plane{component ? ` / ${component}` : ''}</span>
      {tenets.length > 0 && (
        <span style={{ color: 'var(--cb-red)' }}>{' / '}{tenets.join(' / ')}</span>
      )}
    </div>
  )
}
