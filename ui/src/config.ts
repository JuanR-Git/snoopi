export interface RobotConfig {
  id: string
  name: string
  rosbridgeUrl: string
}

export const ROBOTS: RobotConfig[] = [
  { id: 'go2-air-001', name: 'Go2-Air-001', rosbridgeUrl: 'ws://localhost:9090' },
  { id: 'mock-002', name: 'Mock-002', rosbridgeUrl: 'ws://localhost:9090' },
  { id: 'mock-003', name: 'Mock-003', rosbridgeUrl: 'ws://localhost:9090' },
]

export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
