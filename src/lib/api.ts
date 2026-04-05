const BASE = 'http://127.0.0.1:8765/api'

export async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export interface StreamCallbacks {
  onToken: (token: string) => void
  onToolCall: (name: string, args: Record<string, unknown>) => void
  onToolResult: (name: string, result: unknown) => void
  onThinking: (step: string) => void
  onDone: () => void
  onError: (err: string) => void
  onUsage?: (tokens: number, cost: number) => void
  onExport?: (content: string, filename: string) => void
  onFailover?: (from: string, to: string) => void
  signal?: AbortSignal
}

export async function streamChat(payload: object, callbacks: StreamCallbacks) {
  const { onToken, onToolCall, onToolResult, onThinking, onDone, onError,
          onUsage, onExport, onFailover, signal } = callbacks

  console.log('[OpenClaw] streamChat', JSON.stringify(payload).slice(0, 200))

  let res: Response
  try {
    res = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })
  } catch (e: unknown) {
    if ((e as Error).name === 'AbortError') return
    console.error('[OpenClaw] fetch error:', e)
    onError((e as Error).message)
    return
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    onError(err.detail || 'Stream failed')
    return
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line.startsWith(': ')) continue
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        try {
          const event = JSON.parse(raw)
          console.log('[OpenClaw]', event.type, event.type === 'token' ? `"${String(event.content).slice(0,40)}"` : '')

          switch (event.type) {
            case 'token': onToken(event.content); break
            case 'thinking': onThinking(event.message); break
            case 'tool_call': onToolCall(event.name, event.args); break
            case 'tool_result': onToolResult(event.name, event.result); break
            case 'error': console.error('[OpenClaw] error:', event.message); onError(event.message); return
            case 'done': onDone(); return
            case 'usage': onUsage?.(event.tokens, event.cost); break
            case 'export': onExport?.(event.content, event.filename); break
            case 'failover': onFailover?.(event.from_model, event.to_model); break
            case 'compact_summary': onToken(`\n\n*Context compacted. Summary: ${event.summary}*\n\n`); break
          }
        } catch (e) {
          console.warn('[OpenClaw] parse error:', line, e)
        }
      }
    }
  } catch (e: unknown) {
    if ((e as Error).name === 'AbortError') return
    console.error('[OpenClaw] read error:', e)
    onError((e as Error).message)
    return
  }

  if (buffer.startsWith('data: ')) {
    try {
      const event = JSON.parse(buffer.slice(6))
      if (event.type === 'token') onToken(event.content)
    } catch { /* ignore */ }
  }

  onDone()
}

export async function getModels() { return apiFetch('/chat/models', { method: 'POST' }) }
export async function getUsage() { return apiFetch('/chat/usage') }
export async function getSettings() { return apiFetch('/settings/') }
export async function saveProviderKey(provider: string, api_key: string) {
  return apiFetch('/settings/provider-key', { method: 'POST', body: JSON.stringify({ provider, api_key }) })
}
export async function deleteProviderKey(provider: string) {
  return apiFetch(`/settings/provider-key/${provider}`, { method: 'DELETE' })
}
export async function updateAppSettings(settings: object) {
  return apiFetch('/settings/app', { method: 'PUT', body: JSON.stringify(settings) })
}
export async function getTools() { return apiFetch('/tools/') }
export async function createTool(tool: object) {
  return apiFetch('/tools/', { method: 'POST', body: JSON.stringify(tool) })
}
export async function updateTool(name: string, tool: object) {
  return apiFetch(`/tools/${name}`, { method: 'PUT', body: JSON.stringify(tool) })
}
export async function deleteTool(name: string) {
  return apiFetch(`/tools/${name}`, { method: 'DELETE' })
}
export async function testTool(name: string, arguments_: object) {
  return apiFetch('/tools/test', { method: 'POST', body: JSON.stringify({ name, arguments: arguments_ }) })
}
export async function sendCommand(session_id: string, command: string, model: string) {
  return apiFetch('/commands/', { method: 'POST', body: JSON.stringify({ session_id, command, model }) })
}
export function modelSupportsTools(_modelId: string): boolean { return true }
export async function checkHealth() {
  try { return (await fetch('http://127.0.0.1:8765/health')).ok } catch { return false }
}
