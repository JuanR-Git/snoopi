import { useCallback, useRef, useState } from 'react'

export interface DataPoint {
  time: number
  value: number
}

const MAX_POINTS = 10800

export function useTimeSeries() {
  const bufferRef = useRef<DataPoint[]>([])
  const [, setTick] = useState(0)

  const push = useCallback((value: number) => {
    const buf = bufferRef.current
    buf.push({ time: Date.now(), value })
    if (buf.length > MAX_POINTS) buf.shift()
    setTick(t => t + 1)
  }, [])

  const getData = useCallback((rangeMs: number): DataPoint[] => {
    const cutoff = Date.now() - rangeMs
    return bufferRef.current.filter(p => p.time >= cutoff)
  }, [])

  return { push, getData }
}
