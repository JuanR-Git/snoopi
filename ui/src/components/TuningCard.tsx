import { useState } from 'react'

interface Props {
  publish: (topic: string, msgType: string, msg: object) => void
  rosConnected: boolean
}

const PARAM_FIELDS: { key: string; label: string; unit: string; default: number }[] = [
  { key: 'obstacle_dist', label: 'Obstacle Dist', unit: 'm', default: 0.40 },
  { key: 'obstacle_dist_safe', label: 'Obstacle Safe', unit: 'm', default: 0.30 },
  { key: 'patient_max_dist', label: 'Patient Max', unit: 'm', default: 2.00 },
  { key: 'patient_min_dist', label: 'Patient Min', unit: 'm', default: 0.50 },
  { key: 'patient_close_dist', label: 'Patient Close', unit: 'm', default: 1.50 },
  { key: 'max_speed', label: 'Max Speed', unit: 'm/s', default: 0.25 },
  { key: 'min_speed', label: 'Min Speed', unit: 'm/s', default: 0.10 },
  { key: 'catchup_speed', label: 'Catchup Speed', unit: 'm/s', default: 0.25 },
  { key: 'max_rotation', label: 'Max Rotation', unit: 'rad/s', default: 0.70 },
  { key: 'walk_distance', label: 'Walk Distance', unit: 'm', default: 2.13 },
]

function buildDefaults(): Record<string, string> {
  const obj: Record<string, string> = {}
  for (const f of PARAM_FIELDS) obj[f.key] = String(f.default)
  return obj
}

export function TuningCard({ publish, rosConnected }: Props) {
  const [values, setValues] = useState<Record<string, string>>(buildDefaults)

  const update = (key: string, val: string) =>
    setValues(prev => ({ ...prev, [key]: val }))

  const apply = () => {
    const payload: Record<string, number> = {}
    for (const f of PARAM_FIELDS) {
      const n = parseFloat(values[f.key])
      if (isNaN(n) || n <= 0) return // block if any value invalid
      payload[f.key] = n
    }
    publish('/snoopi/params', 'std_msgs/msg/String', { data: JSON.stringify(payload) })
  }

  const allValid = PARAM_FIELDS.every(f => {
    const n = parseFloat(values[f.key])
    return !isNaN(n) && n > 0
  })

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">
        Parameter Tuning
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {PARAM_FIELDS.map(f => (
          <div key={f.key}>
            <label className="block text-xs text-slate-500 mb-1">
              {f.label} ({f.unit})
            </label>
            <input
              type="number"
              step="any"
              value={values[f.key]}
              onChange={e => update(f.key, e.target.value)}
              className="w-full px-2 py-1.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-end">
        <button
          onClick={apply}
          disabled={!rosConnected || !allValid}
          className="px-6 py-2 bg-teal-600 text-white text-sm rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50 transition-colors"
        >
          Apply Parameters
        </button>
      </div>
    </div>
  )
}
