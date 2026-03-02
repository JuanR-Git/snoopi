import { useState } from 'react'
import { useRosbridge } from '../hooks/useRosbridge'
import { Header } from '../components/Header'
import { ROBOTS, RobotConfig } from '../config'

interface DashboardPageProps {
  user: { username: string; display_name: string }
  token: string
  onLogout: () => void
}

export function DashboardPage({ user, token, onLogout }: DashboardPageProps) {
  const [selectedRobot, setSelectedRobot] = useState<RobotConfig>(ROBOTS[0])
  const { connected: rosConnected, subscribe, publish } = useRosbridge(selectedRobot.rosbridgeUrl)
  const [piConnected, setPiConnected] = useState(false)

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
        <p className="text-slate-500">Components will be added in following tasks.</p>
      </main>
    </div>
  )
}
