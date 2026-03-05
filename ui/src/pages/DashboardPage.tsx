import { useState, useCallback, useRef, useEffect } from 'react'
import { useRosbridge } from '../hooks/useRosbridge'
import { useTimeSeries } from '../hooks/useTimeSeries'
import { Header } from '../components/Header'
import { RobotHealthCard } from '../components/RobotHealthCard'
import { SystemHealthCard } from '../components/SystemHealthCard'
import { TelemetryGraphs } from '../components/TelemetryGraphs'
import { ControlsCard } from '../components/ControlsCard'
import { AlertsPanel } from '../components/AlertsPanel'
import type { Alert } from '../components/AlertsPanel'
import { TaskHistory } from '../components/TaskHistory'
import type { TaskRecord } from '../components/TaskHistory'
import { ROBOTS, API } from '../config'
import type { RobotConfig } from '../config'

interface DashboardPageProps {
  user: { username: string; display_name: string }
  token: string
  onLogout: () => void
}

export function DashboardPage({ user, token, onLogout }: DashboardPageProps) {
  const [selectedRobot, setSelectedRobot] = useState<RobotConfig>(ROBOTS[0])
  const { connected: rosConnected, subscribe, publish } = useRosbridge(selectedRobot.rosbridgeUrl)
  const [piConnected, setPiConnected] = useState(false)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [tasks, setTasks] = useState<TaskRecord[]>([])

  // Time series for graphs
  const batterySeries = useTimeSeries()
  const tempSeries = useTimeSeries()
  const imuSeries = useTimeSeries()
  const cpuSeries = useTimeSeries()

  // Alert management
  const alertIdRef = useRef(0)
  const lastAlertRef = useRef<Record<string, number>>({})

  const addAlert = useCallback((message: string, severity: Alert['severity']) => {
    alertIdRef.current++
    setAlerts(prev => [{
      id: alertIdRef.current,
      time: new Date().toLocaleTimeString(),
      message,
      severity,
    }, ...prev].slice(0, 100))
  }, [])

  const checkThreshold = useCallback((key: string, value: number, threshold: number, above: boolean, message: string, severity: Alert['severity']) => {
    const now = Date.now()
    const last = lastAlertRef.current[key] || 0
    if (now - last < 30000) return
    const triggered = above ? value > threshold : value < threshold
    if (triggered) {
      lastAlertRef.current[key] = now
      addAlert(message, severity)
    }
  }, [addAlert])

  // Telemetry callbacks with threshold checks
  const onBatteryUpdate = useCallback((pct: number) => {
    batterySeries.push(pct)
    checkThreshold('battery-low', pct, 20, false, 'Battery below 20%', 'warning')
    checkThreshold('battery-critical', pct, 10, false, 'Battery critically low (<10%)', 'fatal')
  }, [batterySeries, checkThreshold])

  const onTempUpdate = useCallback((temp: number) => {
    tempSeries.push(temp)
    checkThreshold('temp-high', temp, 45, true, `Robot temperature high (${temp.toFixed(1)}°C)`, 'warning')
    checkThreshold('temp-critical', temp, 55, true, `Robot temperature critical (${temp.toFixed(1)}°C)`, 'fatal')
  }, [tempSeries, checkThreshold])

  const onImuUpdate = useCallback((z: number) => {
    imuSeries.push(z)
    const deviation = Math.abs(z - 9.81) / 9.81
    checkThreshold('tilt', deviation, 0.15, true, 'Robot tilt detected — IMU deviation > 15%', 'fatal')
  }, [imuSeries, checkThreshold])

  const onCpuUpdate = useCallback((cpu: number) => {
    cpuSeries.push(cpu)
    checkThreshold('cpu-high', cpu, 90, true, `CPU overload (${cpu.toFixed(0)}%)`, 'warning')
  }, [cpuSeries, checkThreshold])

  // Pi health check polling
  const prevPiConnectedRef = useRef(false)
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API}/health`)
        const isConnected = res.ok
        if (prevPiConnectedRef.current && !isConnected) {
          addAlert('Pi connection lost', 'fatal')
        }
        prevPiConnectedRef.current = isConnected
        setPiConnected(isConnected)
      } catch {
        if (prevPiConnectedRef.current) {
          addAlert('Pi connection lost', 'fatal')
        }
        prevPiConnectedRef.current = false
        setPiConnected(false)
      }
    }
    check()
    const interval = setInterval(check, 5000)
    return () => clearInterval(interval)
  }, [addAlert])

  // Task creation handler
  const onTaskCreated = useCallback((task: TaskRecord) => {
    setTasks(prev => [task, ...prev])
    addAlert(`Task #${task.id} dispatched by ${task.operator}`, 'info')
  }, [addAlert])

  // Graph configs
  const graphs = [
    { title: 'Battery', getData: batterySeries.getData, color: '#10b981', unit: '%', clampMin: 0 },
    { title: 'Temperature', getData: tempSeries.getData, color: '#f59e0b', unit: '°C', clampMin: 0 },
    { title: 'IMU Acceleration', getData: imuSeries.getData, color: '#6366f1', unit: 'm/s²' },
    { title: 'CPU Load', getData: cpuSeries.getData, color: '#0d9488', unit: '%', clampMin: 0 },
  ]

  return (
    <div className="min-h-screen bg-slate-50">
      <Header
        robots={ROBOTS}
        selectedRobot={selectedRobot}
        onSelectRobot={setSelectedRobot}
        piConnected={piConnected}
        rosConnected={rosConnected}
        userName={user.display_name}
        onLogout={onLogout}
      />
      <main className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <RobotHealthCard
            subscribe={subscribe}
            onBatteryUpdate={onBatteryUpdate}
            onTempUpdate={onTempUpdate}
            onImuUpdate={onImuUpdate}
          />
          <SystemHealthCard
            subscribe={subscribe}
            piConnected={piConnected}
            onCpuUpdate={onCpuUpdate}
          />
        </div>
        <TelemetryGraphs graphs={graphs} />
        <ControlsCard
          publish={publish}
          rosConnected={rosConnected}
          token={token}
          onTaskCreated={onTaskCreated}
          userName={user.display_name}
        />
        <AlertsPanel alerts={alerts} />
        <TaskHistory tasks={tasks} />
      </main>
    </div>
  )
}
