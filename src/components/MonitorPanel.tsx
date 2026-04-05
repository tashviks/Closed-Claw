import { useEffect, useState, useRef } from 'react'
import { useStore } from '../store'
import {
  generatePlan, startMonitor, stopMonitor, listMonitors, deleteMonitor, streamMonitor,
  type MonitorEvent,
} from '../lib/monitor'
import { X, Play, Square, Trash2, Plus, Activity, CheckCircle, AlertTriangle, Clock, Zap } from 'lucide-react'
import { cn } from '../lib/utils'

interface Monitor {
  id: string
  description: string
  status: 'pending_approval' | 'running' | 'stopped'
  plan?: Plan
  created_at: string
  last_event?: MonitorEvent
}

interface Plan {
  summary: string
  check_tool_name: string
  check_tool_description: string
  check_tool_code: string
  action_tool_name: string
  action_tool_description: string
  action_tool_code: string
  trigger_condition: string
  trigger_eval: string
  interval_seconds: number
  tools_needed: string[]
}

export default function MonitorPanel({ onClose }: { onClose: () => void }) {
  const { settings } = useStore()
  const [monitors, setMonitors] = useState<Monitor[]>([])
  const [view, setView] = useState<'list' | 'new' | 'detail'>('list')
  const [selected, setSelected] = useState<Monitor | null>(null)
  const [description, setDescription] = useState('')
  const [interval, setInterval] = useState(60)
  const [planning, setPlanning] = useState(false)
  const [pendingPlan, setPendingPlan] = useState<{ monitor_id: string; plan: Plan } | null>(null)
  const [starting, setStarting] = useState(false)
  const [events, setEvents] = useState<MonitorEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const stopStreamRef = useRef<(() => void) | null>(null)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadMonitors()
  }, [])

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  // Auto-stream running monitors when selected
  useEffect(() => {
    if (stopStreamRef.current) {
      stopStreamRef.current()
      stopStreamRef.current = null
    }
    if (selected?.status === 'running') {
      const stop = streamMonitor(selected.id, (evt) => {
        setEvents((prev) => [...prev.slice(-200), evt])
        if (evt.type === 'stopped') {
          loadMonitors()
        }
      })
      stopStreamRef.current = stop
    }
    return () => { stopStreamRef.current?.() }
  }, [selected?.id, selected?.status])

  const loadMonitors = async () => {
    const data = await listMonitors().catch(() => ({ monitors: [] }))
    setMonitors(data.monitors || [])
  }

  const handlePlan = async () => {
    if (!description.trim()) return
    setPlanning(true)
    setError(null)
    try {
      const result = await generatePlan(description, settings.defaultModel, interval)
      setPendingPlan(result)
      setView('detail')
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setPlanning(false)
    }
  }

  const handleApprove = async () => {
    if (!pendingPlan) return
    setStarting(true)
    setError(null)
    try {
      await startMonitor(pendingPlan.monitor_id)
      await loadMonitors()
      const mon = monitors.find((m) => m.id === pendingPlan.monitor_id) || {
        id: pendingPlan.monitor_id,
        description,
        status: 'running' as const,
        plan: pendingPlan.plan,
        created_at: new Date().toISOString(),
      }
      setSelected(mon as Monitor)
      setEvents([])
      setPendingPlan(null)
      setView('detail')
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async (id: string) => {
    await stopMonitor(id)
    await loadMonitors()
    if (selected?.id === id) {
      setSelected((s) => s ? { ...s, status: 'stopped' } : null)
    }
  }

  const handleDelete = async (id: string) => {
    await deleteMonitor(id)
    await loadMonitors()
    if (selected?.id === id) {
      setSelected(null)
      setView('list')
    }
  }

  const statusIcon = (status: string) => {
    if (status === 'running') return <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
    if (status === 'stopped') return <span className="w-2 h-2 rounded-full bg-muted-foreground" />
    return <span className="w-2 h-2 rounded-full bg-yellow-400" />
  }

  const eventIcon = (type: string) => {
    if (type === 'triggered') return <AlertTriangle size={12} className="text-yellow-400 shrink-0" />
    if (type === 'action_done') return <Zap size={12} className="text-primary shrink-0" />
    if (type === 'error') return <AlertTriangle size={12} className="text-destructive shrink-0" />
    if (type === 'ok') return <CheckCircle size={12} className="text-green-400 shrink-0" />
    if (type === 'checking') return <Clock size={12} className="text-muted-foreground shrink-0" />
    return <Activity size={12} className="text-muted-foreground shrink-0" />
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-2xl w-full max-w-4xl h-[85vh] shadow-2xl flex overflow-hidden">

        {/* Left sidebar */}
        <div className="w-64 border-r border-border flex flex-col">
          <div className="flex items-center justify-between px-4 py-3.5 border-b border-border">
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-primary" />
              <h2 className="font-semibold text-sm text-foreground">Monitor Mode (Beta)</h2>
            </div>
            <button onClick={onClose} className="p-1 rounded hover:bg-secondary">
              <X size={14} className="text-muted-foreground" />
            </button>
          </div>

          <div className="p-2">
            <button
              onClick={() => { setView('new'); setPendingPlan(null); setDescription(''); setError(null) }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-sm font-medium transition-colors"
            >
              <Plus size={13} /> New Monitor
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {monitors.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-6">No monitors yet</p>
            )}
            {monitors.map((m) => (
              <div
                key={m.id}
                onClick={() => { setSelected(m); setView('detail'); setEvents([]) }}
                className={cn(
                  'flex items-center gap-2 px-2 py-2.5 rounded-lg cursor-pointer transition-colors',
                  selected?.id === m.id ? 'bg-secondary' : 'hover:bg-secondary/50'
                )}
              >
                {statusIcon(m.status)}
                <span className="text-xs text-foreground truncate flex-1">{m.description.slice(0, 30)}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(m.id) }}
                  className="opacity-0 hover:opacity-100 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 size={11} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Main area */}
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* New monitor form */}
          {view === 'new' && (
            <div className="flex-1 flex flex-col p-6 gap-4">
              <div>
                <h3 className="font-semibold text-foreground mb-1">New Monitor</h3>
                <p className="text-xs text-muted-foreground">Describe what you want to monitor and what action to take.</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">What to monitor</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Monitor my Grafana dashboard at localhost:3000 and send me a WhatsApp message at +918888888888 when CPU usage exceeds 90%"
                  rows={4}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-primary/50 resize-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Check interval</label>
                <div className="flex items-center gap-3">
                  <input type="range" min="10" max="3600" step="10" value={interval}
                    onChange={(e) => setInterval(parseInt(e.target.value))}
                    className="flex-1 accent-primary" />
                  <span className="text-sm text-muted-foreground w-20">
                    {interval >= 3600 ? (interval / 3600) + 'h' : interval >= 60 ? (interval / 60) + 'm' : interval + 's'}
                  </span>
                </div>
              </div>

              {error && (
                <div className="bg-destructive/10 border border-destructive/30 rounded-lg px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={handlePlan}
                  disabled={planning || !description.trim()}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {planning ? (
                    <><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Generating plan…</>
                  ) : (
                    <><Activity size={13} /> Generate Plan</>
                  )}
                </button>
              </div>

              <div className="mt-2 space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Example monitors:</p>
                {EXAMPLES.map((ex) => (
                  <button key={ex} onClick={() => setDescription(ex)}
                    className="block w-full text-left text-xs px-3 py-2 rounded-lg border border-border hover:border-primary/40 hover:bg-primary/5 text-muted-foreground hover:text-foreground transition-all">
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Plan approval */}
          {view === 'detail' && pendingPlan && (
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div>
                <h3 className="font-semibold text-foreground">Review Plan</h3>
                <p className="text-xs text-muted-foreground mt-1">{pendingPlan.plan.summary}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <PlanCard title="Check Tool" name={pendingPlan.plan.check_tool_name}
                  desc={pendingPlan.plan.check_tool_description} code={pendingPlan.plan.check_tool_code} />
                <PlanCard title="Action Tool" name={pendingPlan.plan.action_tool_name}
                  desc={pendingPlan.plan.action_tool_description} code={pendingPlan.plan.action_tool_code} />
              </div>

              <div className="bg-secondary/30 rounded-lg px-4 py-3 space-y-2 text-sm">
                <div className="flex gap-2">
                  <span className="text-muted-foreground w-32 shrink-0">Trigger when:</span>
                  <span className="text-foreground">{pendingPlan.plan.trigger_condition}</span>
                </div>
                <div className="flex gap-2">
                  <span className="text-muted-foreground w-32 shrink-0">Interval:</span>
                  <span className="text-foreground">{pendingPlan.plan.interval_seconds}s</span>
                </div>
                {pendingPlan.plan.tools_needed?.length > 0 && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground w-32 shrink-0">Needs:</span>
                    <span className="text-foreground">{pendingPlan.plan.tools_needed.join(', ')}</span>
                  </div>
                )}
              </div>

              {error && (
                <div className="bg-destructive/10 border border-destructive/30 rounded-lg px-3 py-2 text-sm text-destructive">{error}</div>
              )}

              <div className="flex gap-2">
                <button onClick={handleApprove} disabled={starting}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/20 text-green-400 border border-green-500/30 text-sm font-medium hover:bg-green-500/30 disabled:opacity-50 transition-colors">
                  {starting ? <><span className="w-3 h-3 border-2 border-green-400/30 border-t-green-400 rounded-full animate-spin" /> Starting…</> : <><Play size={13} /> Approve & Start</>}
                </button>
                <button onClick={() => { setPendingPlan(null); setView('new') }}
                  className="px-4 py-2 rounded-lg bg-secondary text-muted-foreground text-sm hover:text-foreground transition-colors">
                  Regenerate
                </button>
              </div>
            </div>
          )}

          {/* Running monitor detail */}
          {view === 'detail' && !pendingPlan && selected && (
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
                <div>
                  <div className="flex items-center gap-2">
                    {statusIcon(selected.status)}
                    <h3 className="font-medium text-sm text-foreground">{selected.description.slice(0, 60)}</h3>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {selected.status === 'running' ? 'Running' : 'Stopped'} · {selected.plan?.interval_seconds ?? 60}s interval
                  </p>
                </div>
                <div className="flex gap-2">
                  {selected.status === 'running' ? (
                    <button onClick={() => handleStop(selected.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-destructive/20 text-destructive text-xs hover:bg-destructive/30 transition-colors">
                      <Square size={11} /> Stop
                    </button>
                  ) : (
                    <button onClick={async () => { await startMonitor(selected.id); await loadMonitors(); setSelected({ ...selected, status: 'running' }); setEvents([]) }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-xs hover:bg-green-500/30 transition-colors">
                      <Play size={11} /> Restart
                    </button>
                  )}
                </div>
              </div>

              {/* Event log */}
              <div className="flex-1 overflow-y-auto p-4 space-y-1.5 font-mono text-xs">
                {events.length === 0 && (
                  <p className="text-muted-foreground text-center py-8">Waiting for events…</p>
                )}
                {events.map((evt, i) => (
                  <div key={i} className={cn(
                    'flex items-start gap-2 px-3 py-2 rounded-lg',
                    evt.type === 'triggered' ? 'bg-yellow-400/10 border border-yellow-400/20' :
                    evt.type === 'action_done' ? 'bg-primary/10 border border-primary/20' :
                    evt.type === 'error' ? 'bg-destructive/10 border border-destructive/20' :
                    'bg-secondary/30'
                  )}>
                    {eventIcon(evt.type)}
                    <div className="flex-1 min-w-0">
                      <span className="text-muted-foreground">{new Date(evt.ts).toLocaleTimeString()} </span>
                      <span className={cn(
                        evt.type === 'triggered' ? 'text-yellow-400' :
                        evt.type === 'action_done' ? 'text-primary' :
                        evt.type === 'error' ? 'text-destructive' :
                        'text-foreground'
                      )}>
                        {String(evt.message || evt.type)}
                      </span>
                      {evt.result && evt.type !== 'ok' && (
                        <pre className="text-muted-foreground mt-1 overflow-x-auto whitespace-pre-wrap">
                          {typeof evt.result === 'string' ? evt.result : JSON.stringify(evt.result, null, 2).slice(0, 300)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={eventsEndRef} />
              </div>
            </div>
          )}

          {/* Empty state */}
          {view === 'list' && (
            <div className="flex-1 flex items-center justify-center text-center px-8">
              <div className="space-y-3">
                <div className="w-12 h-12 mx-auto rounded-xl bg-primary/10 flex items-center justify-center">
                  <Activity size={20} className="text-primary" />
                </div>
                <p className="text-sm font-medium text-foreground">Monitor Mode</p>
                <p className="text-xs text-muted-foreground max-w-xs">
                  Set up perpetual background monitors. The agent creates tools, runs checks on a schedule, and takes action when conditions are met.
                </p>
                <button onClick={() => setView('new')}
                  className="flex items-center gap-2 mx-auto px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors">
                  <Plus size={13} /> Create Monitor
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function PlanCard({ title, name, desc, code }: { title: string; name: string; desc: string; code: string }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="bg-secondary/30 rounded-lg border border-border overflow-hidden">
      <div className="px-3 py-2.5 border-b border-border">
        <p className="text-xs text-muted-foreground">{title}</p>
        <p className="text-sm font-mono font-medium text-primary">{name}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
      </div>
      <div className="px-3 py-2">
        <button onClick={() => setExpanded(!expanded)} className="text-xs text-muted-foreground hover:text-foreground">
          {expanded ? 'Hide code' : 'Show code'}
        </button>
        {expanded && (
          <pre className="mt-2 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap bg-background rounded p-2 max-h-32">
            {code}
          </pre>
        )}
      </div>
    </div>
  )
}

const EXAMPLES = [
  'Monitor my localhost:3000 dashboard and send a WhatsApp message when it goes down',
  'Check my CPU usage every 30s and notify me via macOS notification when it exceeds 80%',
  'Watch ~/Downloads for new files and move PDFs to ~/Documents/PDFs automatically',
  'Monitor a URL for changes and alert me when the content changes',
]
