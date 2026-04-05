import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { getTools, createTool, updateTool, deleteTool, testTool } from '../lib/api'
import { X, Plus, Play, Trash2, Edit2, Check, AlertCircle, Wrench, Code } from 'lucide-react'
import { cn } from '../lib/utils'

interface Tool {
  name: string
  description: string
  code: string
  parameters: object
  enabled: boolean
}

const EMPTY_TOOL: Tool = {
  name: '',
  description: '',
  code: '# Write your tool code here\n# Arguments are injected as variables\nresult = "Hello from tool!"\nprint(result)',
  parameters: { type: 'object', properties: {} },
  enabled: true,
}

export default function ToolsModal() {
  const { toolsOpen, setToolsOpen } = useStore()
  const [builtins, setBuiltins] = useState<Tool[]>([])
  const [userTools, setUserTools] = useState<Tool[]>([])
  const [editing, setEditing] = useState<Tool | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [testArgs, setTestArgs] = useState('{}')
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (toolsOpen) loadTools()
  }, [toolsOpen])

  const loadTools = async () => {
    const r = await getTools().catch(() => ({ builtin: [], user: [] }))
    setBuiltins(r.builtin?.map((t: { function: Tool }) => t.function) ?? [])
    setUserTools(r.user ?? [])
  }

  const save = async () => {
    if (!editing) return
    setSaving(true)
    setError(null)
    try {
      if (isNew) {
        await createTool(editing)
      } else {
        await updateTool(editing.name, editing)
      }
      await loadTools()
      setEditing(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (name: string) => {
    await deleteTool(name)
    await loadTools()
    if (editing?.name === name) setEditing(null)
  }

  const runTest = async () => {
    if (!editing) return
    setTesting(true)
    setTestResult(null)
    try {
      const args = JSON.parse(testArgs)
      const r = await testTool(editing.name || 'test', args)
      setTestResult(JSON.stringify(r.result, null, 2))
    } catch (e: unknown) {
      setTestResult(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`)
    } finally {
      setTesting(false)
    }
  }

  if (!toolsOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-2xl w-full max-w-4xl h-[80vh] shadow-2xl flex overflow-hidden">
        {/* Left panel — tool list */}
        <div className="w-64 border-r border-border flex flex-col">
          <div className="flex items-center justify-between px-4 py-3.5 border-b border-border">
            <h2 className="font-semibold text-sm text-foreground">Tools</h2>
            <button onClick={() => setToolsOpen(false)} className="p-1 rounded hover:bg-secondary">
              <X size={14} className="text-muted-foreground" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-3">
            {/* Built-in tools */}
            <div>
              <p className="text-xs text-muted-foreground px-2 py-1 font-medium">Built-in</p>
              {builtins.map((t) => (
                <div
                  key={t.name}
                  className="flex items-center gap-2 px-2 py-2 rounded-lg text-xs text-muted-foreground"
                >
                  <Wrench size={11} className="text-primary shrink-0" />
                  <span className="font-mono truncate">{t.name}</span>
                  <span className="ml-auto text-xs bg-primary/10 text-primary px-1.5 rounded">built-in</span>
                </div>
              ))}
            </div>

            {/* User tools */}
            <div>
              <div className="flex items-center justify-between px-2 py-1">
                <p className="text-xs text-muted-foreground font-medium">Custom</p>
                <button
                  onClick={() => { setEditing({ ...EMPTY_TOOL }); setIsNew(true); setTestResult(null) }}
                  className="p-0.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
                >
                  <Plus size={12} />
                </button>
              </div>
              {userTools.map((t) => (
                <div
                  key={t.name}
                  onClick={() => { setEditing(t); setIsNew(false); setTestResult(null) }}
                  className={cn(
                    'flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors',
                    editing?.name === t.name ? 'bg-secondary text-foreground' : 'hover:bg-secondary/50 text-muted-foreground'
                  )}
                >
                  <Code size={11} className="text-primary shrink-0" />
                  <span className="text-xs font-mono truncate flex-1">{t.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); remove(t.name) }}
                    className="opacity-0 group-hover:opacity-100 hover:text-destructive"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              ))}
              {userTools.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">No custom tools yet</p>
              )}
            </div>
          </div>
        </div>

        {/* Right panel — editor */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {editing ? (
            <>
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
                <h3 className="font-medium text-sm text-foreground">
                  {isNew ? 'New Tool' : `Edit: ${editing.name}`}
                </h3>
                <div className="flex gap-2">
                  <button
                    onClick={runTest}
                    disabled={testing || (!editing.name && isNew)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 text-sm text-foreground transition-colors disabled:opacity-50"
                  >
                    <Play size={12} />
                    {testing ? 'Running…' : 'Test'}
                  </button>
                  <button
                    onClick={save}
                    disabled={saving || !editing.name}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    <Check size={12} />
                    {saving ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {error && (
                  <div className="flex items-center gap-2 bg-destructive/10 border border-destructive/30 rounded-lg px-3 py-2 text-sm text-destructive">
                    <AlertCircle size={14} />
                    {error}
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">Name (snake_case)</label>
                    <input
                      value={editing.name}
                      onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                      disabled={!isNew}
                      placeholder="my_tool"
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-primary/50 disabled:opacity-50"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">Description</label>
                    <input
                      value={editing.description}
                      onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                      placeholder="What does this tool do?"
                      className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Python Code</label>
                  <textarea
                    value={editing.code}
                    onChange={(e) => setEditing({ ...editing, code: e.target.value })}
                    rows={12}
                    spellCheck={false}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-primary/50 resize-none"
                  />
                  <p className="text-xs text-muted-foreground">
                    Arguments are injected as variables. Use print() for output. No network/file access.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Test Arguments (JSON)</label>
                  <input
                    value={testArgs}
                    onChange={(e) => setTestArgs(e.target.value)}
                    placeholder='{"arg1": "value"}'
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-primary/50"
                  />
                </div>

                {testResult && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">Test Result</label>
                    <pre className="bg-background border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground overflow-x-auto max-h-40">
                      {testResult}
                    </pre>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-center px-8">
              <div className="space-y-3">
                <div className="w-12 h-12 mx-auto rounded-xl bg-primary/10 flex items-center justify-center">
                  <Wrench size={20} className="text-primary" />
                </div>
                <p className="text-sm font-medium text-foreground">Select or create a tool</p>
                <p className="text-xs text-muted-foreground">
                  Custom tools let the agent run your own Python code during conversations.
                </p>
                <button
                  onClick={() => { setEditing({ ...EMPTY_TOOL }); setIsNew(true) }}
                  className="flex items-center gap-2 mx-auto px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
                >
                  <Plus size={14} />
                  Create Tool
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
