export default function MetricCard({ value, label, warm }: { value: string; label: string; warm?: boolean }) {
  const pending = value === '–'
  return <div className="card stat">
    <span className={`value${warm && !pending ? ' warm' : ''}${pending ? ' pending' : ''}`}>{pending ? 'Awaiting data' : value}</span>
    <span className="label">{label}</span>
  </div>
}
