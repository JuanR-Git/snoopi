import { useEffect, useState } from 'react'

interface SystemStats {
  cpu_percent: number
  temperature: number
  fan_on: boolean
  robot_reachable: boolean
  driver_running: boolean
  robot_message: string
}

interface UwbStatus {
  anchor_1_connected: boolean
  anchor_2_connected: boolean
  anchor_1_tag_detected: boolean
  anchor_2_tag_detected: boolean
  anchor_1_distance_m: number
  anchor_2_distance_m: number
}

interface Props {
  subscribe: <T>(topic: string, msgType: string, callback: (msg: T) => void) => () => void
  piConnected: boolean
  onCpuUpdate?: (cpu: number) => void
}

function StatusDot({ online }: { online: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${online ? 'bg-emerald-500' : 'bg-red-500'}`} />
  )
}

export function SystemHealthCard({ subscribe, piConnected, onCpuUpdate }: Props) {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [uwb, setUwb] = useState<UwbStatus | null>(null)

  useEffect(() => {
    const unsubStats = subscribe<any>('/snoopi/system_stats', 'std_msgs/msg/String', (msg: any) => {
      try {
        const data = JSON.parse(msg.data)
        setStats(data)
        onCpuUpdate?.(data.cpu_percent)
      } catch {}
    })
    const unsubUwb = subscribe<any>('/snoopi/uwb_status', 'std_msgs/msg/String', (msg: any) => {
      try {
        setUwb(JSON.parse(msg.data))
      } catch {}
    })
    return () => { unsubStats(); unsubUwb() }
  }, [subscribe, onCpuUpdate])

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">System Health</h2>
      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">RPi CPU Load</span>
          <span className="font-medium">{stats ? `${stats.cpu_percent.toFixed(0)}%` : '—'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">RPi Temp</span>
          <span className="font-medium">{stats ? `${stats.temperature.toFixed(1)}°C` : '—'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-600">RPi Fan</span>
          <span className="font-medium">{stats ? (stats.fan_on ? 'ON' : 'OFF') : '—'}</span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">Pi Connection</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={piConnected} />
            <span className="font-medium">{piConnected ? 'Connected' : 'Offline'}</span>
          </span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">Robot Connection</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={!!stats?.robot_reachable && !!stats?.driver_running} />
            <span className="font-medium">
              {stats ? (stats.robot_reachable && stats.driver_running ? 'Connected' : stats.robot_message || 'Disconnected') : '—'}
            </span>
          </span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">USB Anchor 1</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={!!uwb?.anchor_1_connected} />
            <span className="font-medium">{uwb ? (uwb.anchor_1_connected ? 'Connected' : 'Disconnected') : '—'}</span>
          </span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">USB Anchor 2</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={!!uwb?.anchor_2_connected} />
            <span className="font-medium">{uwb ? (uwb.anchor_2_connected ? 'Connected' : 'Disconnected') : '—'}</span>
          </span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">Anchor 1 Tag</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={!!uwb?.anchor_1_tag_detected} />
            <span className="font-medium">
              {uwb ? (uwb.anchor_1_tag_detected ? `${uwb.anchor_1_distance_m.toFixed(2)} m` : 'Not Detected') : '—'}
            </span>
          </span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">Anchor 2 Tag</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={!!uwb?.anchor_2_tag_detected} />
            <span className="font-medium">
              {uwb ? (uwb.anchor_2_tag_detected ? `${uwb.anchor_2_distance_m.toFixed(2)} m` : 'Not Detected') : '—'}
            </span>
          </span>
        </div>
      </div>
    </div>
  )
}
