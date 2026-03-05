export interface RobotConfig {
  id: string
  name: string
  rosbridgeUrl: string
}

const ROSBRIDGE_URL = import.meta.env.VITE_ROSBRIDGE_URL || 'ws://localhost:9090'

export const ROBOTS: RobotConfig[] = [
  { id: 'go2-air-001', name: 'Go2-Air-001', rosbridgeUrl: ROSBRIDGE_URL },
  { id: 'mock-002', name: 'Mock-002', rosbridgeUrl: ROSBRIDGE_URL },
  { id: 'mock-003', name: 'Mock-003', rosbridgeUrl: ROSBRIDGE_URL },
]

export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
