import { useEffect, useRef, useState, useCallback } from 'react'
import ROSLIB from 'roslib'

interface RosbridgeHook {
  connected: boolean
  subscribe: <T>(topic: string, msgType: string, callback: (msg: T) => void) => () => void
  publish: (topic: string, msgType: string, msg: object) => void
}

export function useRosbridge(url: string): RosbridgeHook {
  const rosRef = useRef<ROSLIB.Ros | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const ros = new ROSLIB.Ros({ url })
    rosRef.current = ros

    ros.on('connection', () => setConnected(true))
    ros.on('error', () => setConnected(false))
    ros.on('close', () => setConnected(false))

    return () => {
      ros.close()
      setConnected(false)
    }
  }, [url])

  const subscribe = useCallback(<T,>(
    topic: string,
    msgType: string,
    callback: (msg: T) => void,
  ) => {
    if (!rosRef.current) return () => {}
    const t = new ROSLIB.Topic({ ros: rosRef.current, name: topic, messageType: msgType })
    t.subscribe((msg) => callback(msg as T))
    return () => t.unsubscribe()
  }, [])

  const publish = useCallback((topic: string, msgType: string, msg: object) => {
    if (!rosRef.current) return
    const t = new ROSLIB.Topic({ ros: rosRef.current, name: topic, messageType: msgType })
    t.publish(new ROSLIB.Message(msg))
  }, [])

  return { connected, subscribe, publish }
}
