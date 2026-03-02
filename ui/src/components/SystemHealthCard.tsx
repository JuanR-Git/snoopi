import { useEffect, useState } from 'react'

interface SystemStats {
  cpu_percent: number
  temperature: number
  fan_on: boolean
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
  const [uwbBase, setUwbBase] = useState(false)
  const [uwbPatient, setUwbPatient] = useState(false)

  useEffect(() => {
    const unsubStats = subscribe<any>('/snoopi/system_stats', 'std_msgs/String', (msg: any) => {
      try {
        const data = JSON.parse(msg.data)
        setStats(data)
        onCpuUpdate?.(data.cpu_percent)
      } catch {}
    })
    const unsubUwbBase = subscribe<any>('/snoopi/uwb_base_status', 'std_msgs/Bool', (msg: any) => {
      setUwbBase(msg.data)
    })
    const unsubUwbPatient = subscribe<any>('/snoopi/uwb_patient_status', 'std_msgs/Bool', (msg: any) => {
      setUwbPatient(msg.data)
    })
    return () => { unsubStats(); unsubUwbBase(); unsubUwbPatient() }
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
          <span className="text-slate-600">UWB Base</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={uwbBase} />
            <span className="font-medium">{uwbBase ? 'Online' : 'Offline'}</span>
          </span>
        </div>
        <div className="flex justify-between text-sm items-center">
          <span className="text-slate-600">UWB Patient</span>
          <span className="inline-flex items-center gap-1.5">
            <StatusDot online={uwbPatient} />
            <span className="font-medium">{uwbPatient ? 'Online' : 'Offline'}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
