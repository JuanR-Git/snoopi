import { useState } from 'react'
import { API } from '../config'

interface Props {
  publish: (topic: string, msgType: string, msg: object) => void
  rosConnected: boolean
  token: string
  onTaskCreated?: (task: { id: string; type: string; distance_m: number; status: string; operator: string; time: string }) => void
  userName: string
}

export function ControlsCard({ publish, rosConnected, token, onTaskCreated, userName }: Props) {
  const [distance, setDistance] = useState('')
  const [sending, setSending] = useState(false)

  const sit = () => publish('/snoopi/command', 'std_msgs/msg/String', { data: 'sit' })
  const stand = () => publish('/snoopi/command', 'std_msgs/msg/String', { data: 'stand' })

  const sendTask = async () => {
    const d = parseFloat(distance)
    if (isNaN(d) || d <= 0) return
    setSending(true)
    try {
      const res = await fetch(`${API}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ type: 'walk', distance_m: d }),
      })
      if (res.ok) {
        const task = await res.json()
        onTaskCreated?.({ ...task, operator: userName, time: new Date().toLocaleTimeString() })
        setDistance('')
      }
    } finally {
      setSending(false)
    }
  }

  const estop = async () => {
    await fetch(`${API}/estop`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Controls</h2>
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600">Walk patient</label>
          <input
            type="number"
            value={distance}
            onChange={e => setDistance(e.target.value)}
            placeholder="meters"
            className="w-24 px-2 py-1.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          />
          <button
            onClick={sendTask}
            disabled={sending || !distance}
            className="px-4 py-1.5 bg-teal-600 text-white text-sm rounded-lg font-medium hover:bg-teal-700 disabled:opacity-50 transition-colors"
          >
            {sending ? 'Sending...' : 'Send Task'}
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={sit}
            disabled={!rosConnected}
            className="px-4 py-1.5 bg-slate-100 text-slate-700 text-sm rounded-lg font-medium hover:bg-slate-200 disabled:opacity-50 transition-colors"
          >
            Sit
          </button>
          <button
            onClick={stand}
            disabled={!rosConnected}
            className="px-4 py-1.5 bg-slate-100 text-slate-700 text-sm rounded-lg font-medium hover:bg-slate-200 disabled:opacity-50 transition-colors"
          >
            Stand
          </button>
        </div>
        <button
          onClick={estop}
          className="ml-auto px-8 py-3 bg-red-600 text-white text-lg rounded-xl font-bold hover:bg-red-700 shadow-md transition-colors"
        >
          E-STOP
        </button>
      </div>
    </div>
  )
}
