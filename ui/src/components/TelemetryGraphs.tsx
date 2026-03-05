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

// Tick interval per range for clock-aligned X-axis ticks
const TICK_INTERVALS: Record<string, number> = {
  '5m': 1 * 60 * 1000,
  '15m': 5 * 60 * 1000,
  '30m': 10 * 60 * 1000,
  '1h': 15 * 60 * 1000,
  '3h': 30 * 60 * 1000,
}

export interface GraphConfig {
  title: string
  getData: (rangeMs: number) => DataPoint[]
  color: string
  unit: string
  clampMin?: number
}

interface Props {
  graphs: GraphConfig[]
}

// --- Y-axis helper ---
// Finds a "nice" number >= value (snapping to 1, 2, 2.5, 5 scaled by power of 10)
function niceNum(value: number, ceil: boolean): number {
  if (value === 0) return 0
  const sign = value < 0 ? -1 : 1
  const abs = Math.abs(value)
  const exp = Math.floor(Math.log10(abs))
  const frac = abs / Math.pow(10, exp)
  const niceSteps = [1, 2, 2.5, 5, 10]

  let nice: number
  if (ceil) {
    nice = niceSteps.find(s => s >= frac) ?? 10
  } else {
    // Find largest nice step <= frac
    nice = 1
    for (const s of niceSteps) {
      if (s <= frac) nice = s
    }
  }
  return sign * nice * Math.pow(10, exp)
}

interface YAxisResult {
  domain: [number, number]
  ticks: number[]
}

function computeYAxis(data: DataPoint[], clampMin?: number): YAxisResult {
  if (data.length === 0) {
    const lo = clampMin ?? 0
    return { domain: [lo, lo + 10], ticks: [lo, lo + 5, lo + 10] }
  }

  let min = Infinity
  let max = -Infinity
  for (const d of data) {
    if (d.value < min) min = d.value
    if (d.value > max) max = d.value
  }

  // Add 10% padding
  const span = max - min || 1
  let paddedMin = min - span * 0.1
  let paddedMax = max + span * 0.1

  if (clampMin !== undefined && paddedMin < clampMin) paddedMin = clampMin

  // Compute nice step size
  const rawStep = (paddedMax - paddedMin) / 5
  const step = niceNum(rawStep, true)

  // Snap bounds to nice step
  const niceMin = Math.floor(paddedMin / step) * step
  const niceMax = Math.ceil(paddedMax / step) * step

  const finalMin = clampMin !== undefined ? Math.max(niceMin, clampMin) : niceMin
  const finalMax = niceMax

  // Generate ticks
  const ticks: number[] = []
  for (let v = finalMin; v <= finalMax + step * 0.001; v += step) {
    ticks.push(Math.round(v * 1e6) / 1e6) // avoid floating point drift
  }

  return { domain: [finalMin, finalMax], ticks }
}

// --- X-axis helper ---
function computeXTicks(windowStart: number, windowEnd: number, rangeLabel: string): number[] {
  const interval = TICK_INTERVALS[rangeLabel] ?? 60000
  // Ceiling windowStart to nearest interval (clock-aligned)
  const firstTick = Math.ceil(windowStart / interval) * interval
  const ticks: number[] = []
  for (let t = firstTick; t <= windowEnd; t += interval) {
    ticks.push(t)
  }
  return ticks
}

// --- Time formatter (range-aware) ---
function formatTime(epoch: number, rangeMs: number): string {
  const d = new Date(epoch)
  if (rangeMs <= 5 * 60 * 1000) {
    // 5m window: MM:SS
    return `${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  }
  // 15m+ windows: HH:MM
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// Concise Y-axis tick formatter
function formatYTick(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}k`
  if (Number.isInteger(value)) return String(value)
  return value.toFixed(1)
}

export function TelemetryGraphs({ graphs }: Props) {
  const [rangeIdx, setRangeIdx] = useState(0)
  const range = RANGES[rangeIdx]

  // Capture now once so all graphs share the same X window
  const now = Date.now()
  const windowStart = now - range.ms

  const xTicks = computeXTicks(windowStart, now, range.label)

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
          const { domain: yDomain, ticks: yTicks } = computeYAxis(data, g.clampMin)
          return (
            <div key={g.title} className="border border-slate-100 rounded-lg p-3">
              <p className="text-xs font-medium text-slate-500 mb-2">{g.title}</p>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={[windowStart, now]}
                    ticks={xTicks}
                    tickFormatter={(t: number) => formatTime(t, range.ms)}
                    allowDataOverflow={true}
                    tick={{ fontSize: 10 }}
                    stroke="#94a3b8"
                  />
                  <YAxis
                    domain={yDomain}
                    ticks={yTicks}
                    tickFormatter={formatYTick}
                    allowDataOverflow={true}
                    tick={{ fontSize: 10 }}
                    stroke="#94a3b8"
                    width={45}
                  />
                  <Tooltip
                    labelFormatter={(t: number) => formatTime(t, range.ms)}
                    formatter={(v: number) => [`${v.toFixed(2)} ${g.unit}`, g.title]}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={g.color}
                    dot={false}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )
        })}
      </div>
    </div>
  )
}
