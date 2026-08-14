import { createContext, createElement, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, stationSocketUrl } from '../api'
import type { Disposition, StationSnapshot } from '../types'

export type ConnectionState = 'CONNECTING' | 'LIVE' | 'STALE' | 'DISCONNECTED'

function useStationSource(stationId = 'ST01') {
  const [data, setData] = useState<StationSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('CONNECTING')
  const lastMessage = useRef(0)
  const socket = useRef<WebSocket | null>(null)

  const applySnapshot = useCallback((snapshot: StationSnapshot) => {
    setError(null)
    setData(snapshot)
    lastMessage.current = Date.now()
  }, [])

  const load = useCallback(async () => {
    try {
      const snapshot = await api.station(stationId)
      applySnapshot(snapshot)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法加载工位')
    } finally {
      setLoading(false)
    }
  }, [applySnapshot, stationId])

  useEffect(() => {
    let active = true
    void api.station(stationId)
      .then((snapshot) => { if (active) applySnapshot(snapshot) })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : '无法加载工位')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [applySnapshot, stationId])

  useEffect(() => {
    let reconnectTimer: number | undefined
    let closed = false
    const connect = () => {
      setConnection('CONNECTING')
      const active = new WebSocket(stationSocketUrl(stationId))
      socket.current = active
      active.onopen = () => setConnection('LIVE')
      active.onmessage = (event) => {
        setData(JSON.parse(event.data) as StationSnapshot)
        lastMessage.current = Date.now()
        setConnection('LIVE')
      }
      active.onerror = () => active.close()
      active.onclose = () => {
        if (!closed) {
          setConnection('DISCONNECTED')
          reconnectTimer = window.setTimeout(connect, 2500)
        }
      }
    }
    connect()
    const healthTimer = window.setInterval(() => {
      if (!lastMessage.current) return
      const elapsed = Date.now() - lastMessage.current
      if (elapsed > 15_000) setConnection('DISCONNECTED')
      else if (elapsed > 5_000) setConnection('STALE')
    }, 1000)
    return () => {
      closed = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      window.clearInterval(healthTimer)
      socket.current?.close()
    }
  }, [stationId])

  const mutate = useCallback(async (operation: () => Promise<StationSnapshot>) => {
    setError(null)
    try {
      const snapshot = await operation()
      setData(snapshot)
      lastMessage.current = Date.now()
      return snapshot
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : '操作失败'
      setError(message)
      throw reason
    }
  }, [])

  return {
    data, loading, error, connection,
    retry: () => {
      setLoading(true)
      return load()
    },
    runScenario: (name: string) => mutate(() => api.scenario(name)),
    reset: () => mutate(api.reset),
    applyDisposition: async (disposition: Disposition, reason: string) => {
      if (!data?.cycle.cycle_id) throw new Error('当前没有 Cycle')
      await api.disposition(data.cycle.cycle_id, disposition, reason)
      return load()
    },
  }
}

type StationContextValue = ReturnType<typeof useStationSource>

const StationContext = createContext<StationContextValue | null>(null)

export function StationProvider({ children, stationId = 'ST01' }: { children: ReactNode; stationId?: string }) {
  const value = useStationSource(stationId)
  return createElement(StationContext.Provider, { value }, children)
}

export function useStation() {
  const value = useContext(StationContext)
  if (!value) throw new Error('useStation must be used inside StationProvider')
  return value
}
