export interface TaskRecord {
  id: string
  type: string
  distance_m: number
  status: string
  time: string
  operator: string
}

interface Props {
  tasks: TaskRecord[]
}

const STATUS_STYLE: Record<string, string> = {
  dispatched: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  pending: 'bg-slate-100 text-slate-600',
  failed: 'bg-red-100 text-red-700',
}

export function TaskHistory({ tasks }: Props) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Task History</h2>
      {tasks.length === 0 ? (
        <p className="text-sm text-slate-400">No tasks dispatched yet</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-100">
              <th className="pb-2 font-medium">ID</th>
              <th className="pb-2 font-medium">Type</th>
              <th className="pb-2 font-medium">Distance</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Time</th>
              <th className="pb-2 font-medium">Operator</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map(t => (
              <tr key={t.id} className="border-b border-slate-50">
                <td className="py-2 font-medium">#{t.id}</td>
                <td className="py-2">{t.type}</td>
                <td className="py-2">{t.distance_m}m</td>
                <td className="py-2">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[t.status] || STATUS_STYLE.pending}`}>
                    {t.status}
                  </span>
                </td>
                <td className="py-2 text-slate-500">{t.time}</td>
                <td className="py-2 text-slate-500">{t.operator}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
