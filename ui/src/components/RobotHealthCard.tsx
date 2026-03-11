import { useEffect, useState } from 'react'

// Battery: JSON String from our SDK patch on /snoopi/battery
interface BatteryData {
  soc: number
  current: number
  power_v: number
  temperature_ntc1: number
  cycle: number
}

// IMU: go2_interfaces/msg/IMU (custom type, not sensor_msgs)
interface Go2Imu {
  quaternion: number[]
  gyroscope: number[]
  accelerometer: number[]
  rpy: number[]
  temperature: number
}

interface Props {
  subscribe: <T>(topic: string, msgType: string, callback: (msg: T) => void) => () => void
  onBatteryUpdate?: (pct: number) => void
  onTempUpdate?: (temp: number) => void
  onImuUpdate?: (z: number) => void
}

export function RobotHealthCard({ subscribe, onBatteryUpdate, onTempUpdate, onImuUpdate }: Props) {
  const [battery, setBattery] = useState<BatteryData | null>(null)
  const [imu, setImu] = useState<Go2Imu | null>(null)

  useEffect(() => {
    // Battery arrives as JSON inside a std_msgs/String on /snoopi/battery
    const unsubBattery = subscribe<{ data: string }>('/snoopi/battery', 'std_msgs/msg/String', (msg) => {
      const data: BatteryData = JSON.parse(msg.data)
      setBattery(data)
      onBatteryUpdate?.(data.soc)
      onTempUpdate?.(data.temperature_ntc1)
    })
    // IMU is go2_interfaces/msg/IMU on /imu (not sensor_msgs/Imu on /imu/data)
    const unsubImu = subscribe<Go2Imu>('/imu', 'go2_interfaces/msg/IMU', (msg) => {
      setImu(msg)
      onImuUpdate?.(msg.accelerometer[2])
    })
    return () => { unsubBattery(); unsubImu() }
  }, [subscribe, onBatteryUpdate, onTempUpdate, onImuUpdate])

  const batteryPct = battery ? Math.round(battery.soc) : null
  const temp = battery ? battery.temperature_ntc1 : null
  const imuZ = imu ? imu.accelerometer[2] : null

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
