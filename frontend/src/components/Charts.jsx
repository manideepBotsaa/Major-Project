import { formatMoney } from '../lib/format'

export function ChartTooltip({ active, payload, label, currency = 'INR' }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      {label && <strong>{label}</strong>}
      {payload.map((item) => (
        <span key={`${item.dataKey}-${item.name}`} style={{ color: item.color }}>
          <i style={{ background: item.color }} />
          {item.name}: {formatMoney(item.value, currency)}
        </span>
      ))}
    </div>
  )
}

export function ChartLegend({ items }) {
  return (
    <div className="chart-legend">
      {items.map((item) => (
        <span key={item.label}>
          <i style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  )
}
