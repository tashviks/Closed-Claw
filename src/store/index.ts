import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  toolCalls?: ToolCall[]
  toolResults?: ToolResult[]
  thinkingSteps?: string[]
  timestamp: number
  isStreaming?: boolean
}

export interface ToolCall {
  name: string
  args: Record<string, unknown>
}

export interface ToolResult {
  name: string
  result: unknown
}

export interface Session {
  id: string
  title: string
  model: string
  messages: Message[]
  createdAt: number
  updatedAt: number
}

export interface AppSettings {
  theme: 'dark' | 'light'
  defaultModel: string
  temperature: number
  maxTokens: number
  streamResponses: boolean
  sandboxTools: boolean
  useTools: boolean
}

interface AppState {
  sessions: Session[]
  activeSessionId: string | null
  settings: AppSettings
  sidebarOpen: boolean
  settingsOpen: boolean
  toolsOpen: boolean

  // Actions
  createSession: (model?: string) => string
  deleteSession: (id: string) => void
  setActiveSession: (id: string) => void
  updateSessionTitle: (id: string, title: string) => void
  addMessage: (sessionId: string, message: Message) => void
  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => void
  updateSettings: (settings: Partial<AppSettings>) => void
  setSidebarOpen: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  setToolsOpen: (open: boolean) => void
  getActiveSession: () => Session | null
}

const DEFAULT_SETTINGS: AppSettings = {
  theme: 'dark',
  defaultModel: 'google/gemini-2.5-flash',
  temperature: 0.7,
  maxTokens: 4096,
  streamResponses: true,
  sandboxTools: true,
  useTools: true,
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,
      settings: DEFAULT_SETTINGS,
      sidebarOpen: true,
      settingsOpen: false,
      toolsOpen: false,

      createSession: (model) => {
        const id = crypto.randomUUID()
        const session: Session = {
          id,
          title: 'New Chat',
          model: model || get().settings.defaultModel,
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }
        set((s) => ({
          sessions: [session, ...s.sessions],
          activeSessionId: id,
        }))
        return id
      },

      deleteSession: (id) => {
        set((s) => {
          const sessions = s.sessions.filter((s) => s.id !== id)
          const activeSessionId =
            s.activeSessionId === id
              ? sessions[0]?.id ?? null
              : s.activeSessionId
          return { sessions, activeSessionId }
        })
      },

      setActiveSession: (id) => set({ activeSessionId: id }),

      updateSessionTitle: (id, title) => {
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === id ? { ...sess, title, updatedAt: Date.now() } : sess
          ),
        }))
      },

      addMessage: (sessionId, message) => {
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === sessionId
              ? {
                  ...sess,
                  messages: [...sess.messages, message],
                  updatedAt: Date.now(),
                }
              : sess
          ),
        }))
      },

      updateMessage: (sessionId, messageId, updates) => {
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === sessionId
              ? {
                  ...sess,
                  messages: sess.messages.map((m) =>
                    m.id === messageId ? { ...m, ...updates } : m
                  ),
                }
              : sess
          ),
        }))
      },

      updateSettings: (settings) => {
        set((s) => ({ settings: { ...s.settings, ...settings } }))
      },

      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setSettingsOpen: (open) => set({ settingsOpen: open }),
      setToolsOpen: (open) => set({ toolsOpen: open }),

      getActiveSession: () => {
        const { sessions, activeSessionId } = get()
        return sessions.find((s) => s.id === activeSessionId) ?? null
      },
    }),
    {
      name: 'openclaw-store',
      version: 5,
      migrate: (persisted: unknown, version: number) => {
        // Clear stale data on version bump
        if (version < 2) {
          return { sessions: [], activeSessionId: null, settings: DEFAULT_SETTINGS }
        }
        return persisted
      },
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
        settings: state.settings,
      }),
    }
  )
)
