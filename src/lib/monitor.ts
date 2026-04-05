const BASE = 'http://127.0.0.1:8765/api/monitor'

export async function generatePlan(description: string, model: string, interval_seconds = 60) {
  const res = await fetch(`${BASE}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description, model, interval_seconds }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Plan generation failed')
  }
  return res.json()
}

export async function startMonitor(monitor_id: string) {
  const res = await fetch(`${BASE}/start/${monitor_id}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Start failed')
  }
  return res.json()
}

export async function stopMonitor(monitor_id: string) {
  const res = await fetch(`${BASE}/stop/${monitor_id}`, { method: 'POST' })
  return res.json()
}

export async function listMonitors() {
  const res = await fetch(`${BASE}/`)
  return res.json()
}

export async function deleteMonitor(monitor_id: string) {
  const res = await fetch(`${BASE}/${monitor_id}`, { method: 'DELETE' })
  return res.json()
}

export function streamMonitor(
  monitor_id: string,
  onEvent: (event: MonitorEvent) => void,
  signal?: AbortSignal
): () => void {
  const url = `${BASE}/stream/${monitor_id}`
  let active = true

  const connect = () => {
    fetch(url, { signal })
      .then(async (res) => {
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (active) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const evt = JSON.parse(line.slice(6))
                onEvent(evt)
              } catch { /* ignore */ }
            }
          }
        }
      })
      .catch(() => { /* stream ended */ })
  }

  connect()
  return () => { active = false }
}

export interface MonitorEvent {
  type: 'started' | 'checking' | 'check_result' | 'triggered' | 'action_done' | 'ok' | 'error' | 'stopped'
  ts: string
  monitor_id: string
  message?: string
  result?: Record<string, unknown> | string
  iteration?: number
}
