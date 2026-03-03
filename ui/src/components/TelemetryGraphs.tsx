import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { DataPoint } from '../hooks/useTimeSeries'

const RANGES = [
  { label: '5m', ms: 5 * 60 * 1000 },
  { label: '15m', ms: 15 * 60 * 1000 },
  { label: '30m', ms: 30 * 60 * 1000 },
  { label: '1h', ms: 60 * 60 * 1000 },
  { label: '3h', ms: 3 * 60 * 60 * 1000 },
]

interface GraphConfig {
  title: string
  getData: (rangeMs: number) => DataPoint[]
  color: string
  unit: string
}

interface Props {
  graphs: GraphConfig[]
}

function formatTime(epoch: number) {
  return new Date(epoch).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function TelemetryGraphs({ graphs }: Props) {
  const [rangeIdx, setRangeIdx] = useState(0)
  const range = RANGES[rangeIdx]

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Telemetry</h2>
        <div className="flex gap-1">
          {RANGES.map((r, i) => (
            <button
              key={r.label}
              onClick={() => setRangeIdx(i)}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                i === rangeIdx
                  ? 'bg-teal-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {graphs.map(g => {
          const data = g.getData(range.ms)
          return (
            <div key={g.title} className="border border-slate-100 rounded-lg p-3">
              <p className="text-xs font-medium text-slate-500 mb-2">{g.title}</p>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="time"
                    tickFormatter={formatTime}
                    tick={{ fontSize: 10 }}
                    stroke="#94a3b8"
                  />
                  <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" width={40} />
                  <Tooltip
                    labelFormatter={formatTime}
                    formatter={(v: number) => [`${v.toFixed(2)} ${g.unit}`, g.title]}
                  />
                  <Line type="monotone" dataKey="value" stroke={g.color} dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )
        })}
      </div>
    </div>
  )
}
