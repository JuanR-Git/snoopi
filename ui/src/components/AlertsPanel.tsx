export interface Alert {
  id: number
  time: string
  message: string
  severity: 'fatal' | 'warning' | 'info'
}

interface Props {
  alerts: Alert[]
}

const COLORS = {
  fatal: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

const LABELS = {
  fatal: 'FATAL',
  warning: 'WARNING',
  info: 'INFO',
}

export function AlertsPanel({ alerts }: Props) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Alerts & Warnings</h2>
      <div className="space-y-2 max-h-48 overflow-y-auto">
        {alerts.length === 0 && <p className="text-sm text-slate-400">No alerts</p>}
        {alerts.map(a => (
          <div key={a.id} className={`flex items-center justify-between px-3 py-2 rounded-lg border text-sm ${COLORS[a.severity]}`}>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">{a.time}</span>
              <span>{a.message}</span>
            </div>
            <span className="text-xs font-semibold">{LABELS[a.severity]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
