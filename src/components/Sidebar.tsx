import { useState } from 'react'
import { useStore } from '../store'
import { cn, formatDate, truncate } from '../lib/utils'
import {
  Plus, MessageSquare, Settings, Wrench, ChevronLeft,
  ChevronRight, Trash2, Bot, Activity
} from 'lucide-react'
import MonitorPanel from './MonitorPanel'

export default function Sidebar() {
  const {
    sessions, activeSessionId, sidebarOpen,
    createSession, deleteSession, setActiveSession,
    setSidebarOpen, setSettingsOpen, setToolsOpen,
  } = useStore()

  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [monitorOpen, setMonitorOpen] = useState(false)

  // Group sessions by date
  const grouped: Record<string, typeof sessions> = {}
  for (const s of sessions) {
    const label = formatDate(s.updatedAt)
    if (!grouped[label]) grouped[label] = []
    grouped[label].push(s)
  }

  return (
    <>
      {/* Toggle button when closed */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed left-2 top-3 z-50 p-1.5 rounded-lg bg-card border border-border hover:bg-secondary transition-colors no-drag"
        >
          <ChevronRight size={16} className="text-muted-foreground" />
        </button>
      )}

      <aside
        className={cn(
          'flex flex-col bg-card border-r border-border transition-all duration-200 overflow-hidden',
          sidebarOpen ? 'w-64' : 'w-0'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-3 drag-region border-b border-border">
          <div className="flex items-center gap-2 no-drag">
            <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center">
              <Bot size={14} className="text-primary" />
            </div>
            <span className="font-semibold text-sm text-foreground">ClosedClaw</span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="no-drag p-1 rounded hover:bg-secondary transition-colors"
          >
            <ChevronLeft size={14} className="text-muted-foreground" />
          </button>
        </div>

        {/* New chat button */}
        <div className="p-2">
          <button
            onClick={() => createSession()}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-sm font-medium transition-colors"
          >
            <Plus size={15} />
            New Chat
          </button>
        </div>

        {/* Sessions list */}
        <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-3">
          {Object.entries(grouped).map(([date, items]) => (
            <div key={date}>
              <p className="text-xs text-muted-foreground px-2 py-1 font-medium">{date}</p>
              <div className="space-y-0.5">
                {items.map((session) => (
                  <div
                    key={session.id}
                    className={cn(
                      'group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors',
                      activeSessionId === session.id
                        ? 'bg-secondary text-foreground'
                        : 'hover:bg-secondary/50 text-muted-foreground hover:text-foreground'
                    )}
                    onClick={() => setActiveSession(session.id)}
                    onMouseEnter={() => setHoveredId(session.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    <MessageSquare size={13} className="shrink-0" />
                    <span className="flex-1 text-xs truncate">
                      {truncate(session.title, 28)}
                    </span>
                    {hoveredId === session.id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteSession(session.id)
                        }}
                        className="p-0.5 rounded hover:text-destructive transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-8">No chats yet</p>
          )}
        </div>

        {/* Bottom actions */}
        <div className="border-t border-border p-2 space-y-0.5">
          <button
            onClick={() => setMonitorOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground text-sm transition-colors"
          >
            <Activity size={14} />
            Monitor Mode (Beta)
          </button>
          <button
            onClick={() => setToolsOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground text-sm transition-colors"
          >
            <Wrench size={14} />
            Tools
          </button>
          <button
            onClick={() => setSettingsOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground text-sm transition-colors"
          >
            <Settings size={14} />
            Settings
          </button>
        </div>
      </aside>
      {monitorOpen && <MonitorPanel onClose={() => setMonitorOpen(false)} />}
    </>
  )
}
