import { useEffect, useState } from 'react'

interface BatteryState {
  percentage: number
  voltage: number
  temperature: number
}

interface Imu {
  linear_acceleration: { x: number; y: number; z: number }
}

interface Props {
  subscribe: <T>(topic: string, msgType: string, callback: (msg: T) => void) => () => void
  onBatteryUpdate?: (pct: number) => void
  onTempUpdate?: (temp: number) => void
  onImuUpdate?: (z: number) => void
}

export function RobotHealthCard({ subscribe, onBatteryUpdate, onTempUpdate, onImuUpdate }: Props) {
  const [battery, setBattery] = useState<BatteryState | null>(null)
  const [imu, setImu] = useState<Imu | null>(null)

  useEffect(() => {
    const unsubBattery = subscribe<BatteryState>('/utlidar/battery', 'sensor_msgs/msg/BatteryState', (msg) => {
      setBattery(msg)
      onBatteryUpdate?.(msg.percentage * 100)
      onTempUpdate?.(msg.temperature)
    })
    const unsubImu = subscribe<Imu>('/imu/data', 'sensor_msgs/msg/Imu', (msg) => {
      setImu(msg)
      onImuUpdate?.(msg.linear_acceleration.z)
    })
    return () => { unsubBattery(); unsubImu() }
  }, [subscribe, onBatteryUpdate, onTempUpdate, onImuUpdate])

  const batteryPct = battery ? Math.round(battery.percentage * 100) : null
  const temp = battery ? battery.temperature : null
  const imuZ = imu ? imu.linear_acceleration.z : null

  const batteryColor = batteryPct === null ? 'bg-slate-200'
    : batteryPct > 50 ? 'bg-emerald-500'
    : batteryPct > 20 ? 'bg-amber-500'
    : 'bg-red-500'

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Robot Health</h2>
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-slate-600">Battery</span>
            <span className="font-medium">{batteryPct !== null ? `${batteryPct}%` : '—'}</span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${batteryColor}`} style={{ width: `${batteryPct ?? 0}%` }} />
          </div>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">Temperature</span>
          <span className="font-medium">{temp !== null ? `${temp.toFixed(1)}°C` : '—'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">IMU z-accel</span>
          <span className="font-medium">{imuZ !== null ? `${imuZ.toFixed(2)} m/s²` : '—'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">Joint Status</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="font-medium text-emerald-700">Normal</span>
          </span>
        </div>
      </div>
    </div>
  )
}
