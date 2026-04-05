import { useEffect, useState } from 'react'
import { useStore } from './store'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import SettingsModal from './components/SettingsModal'
import ToolsModal from './components/ToolsModal'
import { checkHealth } from './lib/api'
import { cn } from './lib/utils'

export default function App() {
  const { sidebarOpen, activeSessionId, createSession } = useStore()
  const [backendReady, setBackendReady] = useState(false)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    let attempts = 0
    const check = async () => {
      const ok = await checkHealth().catch(() => false)
      if (ok) {
        setBackendReady(true)
      } else {
        attempts++
        if (attempts < 20) {
          setTimeout(check, 1500)  // slower polling — 1.5s not 1s
        } else {
          setRetrying(true)
        }
      }
    }
    check()
  }, [])

  useEffect(() => {
    if (backendReady && !activeSessionId) {
      createSession()
    }
  }, [backendReady, activeSessionId, createSession])

  if (!backendReady) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 mx-auto rounded-xl bg-primary/20 flex items-center justify-center">
            <span className="text-2xl">🦀</span>
          </div>
          <p className="text-muted-foreground text-sm">
            {retrying ? 'Backend failed to start. Check Python installation.' : 'Starting backend…'}
          </p>
          {retrying && (
            <button
              onClick={() => window.location.reload()}
              className="text-primary text-sm underline"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main
        className={cn(
          'flex-1 flex flex-col min-w-0 transition-all duration-200',
          sidebarOpen ? 'ml-0' : 'ml-0'
        )}
      >
        <ChatView />
      </main>
      <SettingsModal />
      <ToolsModal />
    </div>
  )
}
