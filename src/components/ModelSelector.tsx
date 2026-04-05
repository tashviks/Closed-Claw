import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { getModels } from '../lib/api'
import { ChevronDown, Zap, Lock } from 'lucide-react'
import { cn } from '../lib/utils'

interface Props {
  sessionId: string
  currentModel: string
}

interface ModelInfo {
  provider: string
  context: number
  free: boolean
}

export default function ModelSelector({ sessionId, currentModel }: Props) {
  const { sessions, updateSettings, settings } = useStore()
  const [open, setOpen] = useState(false)
  const [models, setModels] = useState<Record<string, ModelInfo>>({})

  useEffect(() => {
    // Only fetch once — models list doesn't change at runtime
    if (Object.keys(models).length === 0) {
      getModels().then((r) => setModels(r.models)).catch(() => {})
    }
  }, [])

  const updateModel = (model: string) => {
    // Update the session model in store
    useStore.setState((s) => ({
      sessions: s.sessions.map((sess) =>
        sess.id === sessionId ? { ...sess, model } : sess
      ),
    }))
    updateSettings({ defaultModel: model })
    setOpen(false)
  }

  const displayName = currentModel.split('/').slice(-1)[0].replace(':free', '')
  const isFree = models[currentModel]?.free

  const grouped: Record<string, [string, ModelInfo][]> = {}
  for (const [id, info] of Object.entries(models)) {
    const group = info.free ? 'Free Models' : info.provider.charAt(0).toUpperCase() + info.provider.slice(1)
    if (!grouped[group]) grouped[group] = []
    grouped[group].push([id, info])
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-sm text-foreground hover:text-primary transition-colors"
      >
        {isFree && <Zap size={12} className="text-yellow-400" />}
        <span className="font-medium truncate max-w-48">{displayName}</span>
        <ChevronDown size={13} className="text-muted-foreground" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 z-50 w-80 bg-card border border-border rounded-xl shadow-xl overflow-hidden">
            <div className="max-h-96 overflow-y-auto">
              {Object.entries(grouped).map(([group, items]) => (
                <div key={group}>
                  <p className="text-xs text-muted-foreground px-3 py-2 font-medium bg-secondary/30 sticky top-0">
                    {group}
                  </p>
                  {items.map(([id, info]) => (
                    <button
                      key={id}
                      onClick={() => updateModel(id)}
                      className={cn(
                        'w-full flex items-center justify-between px-3 py-2.5 hover:bg-secondary/50 transition-colors text-left',
                        currentModel === id && 'bg-primary/10'
                      )}
                    >
                      <div>
                        <p className="text-sm text-foreground font-medium">
                          {id.split('/').slice(-1)[0].replace(':free', '')}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {(info.context / 1000).toFixed(0)}K context
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        {info.free ? (
                          <span className="text-xs bg-yellow-400/10 text-yellow-400 px-1.5 py-0.5 rounded-full flex items-center gap-1">
                            <Zap size={9} /> Free
                          </span>
                        ) : (
                          <span className="text-xs bg-secondary text-muted-foreground px-1.5 py-0.5 rounded-full flex items-center gap-1">
                            <Lock size={9} /> API Key
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
