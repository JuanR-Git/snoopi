import { RobotConfig } from '../config'

interface HeaderProps {
  robots: RobotConfig[]
  selectedRobot: RobotConfig
  onSelectRobot: (robot: RobotConfig) => void
  piConnected: boolean
  rosConnected: boolean
  userName: string
  onLogout: () => void
}

export function Header({ robots, selectedRobot, onSelectRobot, piConnected, rosConnected, userName, onLogout }: HeaderProps) {
  return (
    <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <h1 className="text-xl font-bold text-teal-600">Snoopi</h1>
        <select
          value={selectedRobot.id}
          onChange={e => {
            const r = robots.find(r => r.id === e.target.value)
            if (r) onSelectRobot(r)
          }}
          className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        >
          {robots.map(r => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${rosConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
          <span className="text-sm text-slate-600">{rosConnected ? 'ROS2 Connected' : 'ROS2 Disconnected'}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${piConnected ? 'bg-emerald-500' : 'bg-red-500'}`} />
          <span className="text-sm text-slate-600">Pi</span>
        </div>
        <span className="text-sm text-slate-600">{userName}</span>
        <button onClick={onLogout} className="text-sm text-slate-500 hover:text-slate-700">Logout</button>
      </div>
    </header>
  )
}
