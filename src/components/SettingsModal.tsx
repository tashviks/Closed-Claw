import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { getSettings, saveProviderKey, deleteProviderKey, updateAppSettings } from '../lib/api'
import { X, Eye, EyeOff, Check, Trash2, ExternalLink } from 'lucide-react'
import { cn } from '../lib/utils'

const PROVIDERS = [
  { id: 'openrouter', name: 'OpenRouter', url: 'https://openrouter.ai/keys', note: 'Access 100+ models including free ones' },
  { id: 'openai', name: 'OpenAI', url: 'https://platform.openai.com/api-keys', note: 'GPT-4o, o3-mini, o4-mini' },
  { id: 'anthropic', name: 'Anthropic', url: 'https://console.anthropic.com/', note: 'Claude Opus 4.5, Sonnet 4.5' },
  { id: 'google', name: 'Google AI', url: 'https://aistudio.google.com/app/apikey', note: 'Gemini 2.5 Flash & Pro' },
  { id: 'groq', name: 'Groq', url: 'https://console.groq.com/keys', note: 'Ultra-fast inference — Llama, Mixtral' },
  { id: 'perplexity', name: 'Perplexity', url: 'https://www.perplexity.ai/settings/api', note: 'Sonar — web search built-in' },
  { id: 'mistral', name: 'Mistral AI', url: 'https://console.mistral.ai/', note: 'Mistral Large, Codestral' },
]

export default function SettingsModal() {
  const { settingsOpen, setSettingsOpen, settings, updateSettings } = useStore()
  const [tab, setTab] = useState<'keys' | 'general' | 'integrations'>('keys')
  const [keys, setKeys] = useState<Record<string, string>>({})
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [show, setShow] = useState<Record<string, boolean>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (settingsOpen) {
      getSettings().then((r) => setKeys(r.providers || {})).catch(() => {})
    }
  }, [settingsOpen])

  if (!settingsOpen) return null

  const saveKey = async (provider: string) => {
    const key = inputs[provider]?.trim()
    if (!key) return
    await saveProviderKey(provider, key)
    setKeys((k) => ({ ...k, [provider]: '***' + key.slice(-4) }))
    setInputs((i) => ({ ...i, [provider]: '' }))
    setSaved((s) => ({ ...s, [provider]: true }))
    setTimeout(() => setSaved((s) => ({ ...s, [provider]: false })), 2000)
  }

  const removeKey = async (provider: string) => {
    await deleteProviderKey(provider)
    setKeys((k) => { const n = { ...k }; delete n[provider]; return n })
  }

  const saveGeneral = async () => {
    await updateAppSettings({
      theme: settings.theme,
      default_model: settings.defaultModel,
      temperature: settings.temperature,
      max_tokens: settings.maxTokens,
      stream_responses: settings.streamResponses,
      sandbox_tools: settings.sandboxTools,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-semibold text-foreground">Settings</h2>
          <button onClick={() => setSettingsOpen(false)} className="p-1 rounded-lg hover:bg-secondary transition-colors">
            <X size={16} className="text-muted-foreground" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border px-5">
          {(['keys', 'general', 'integrations'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'px-3 py-3 text-sm font-medium border-b-2 transition-colors capitalize',
                tab === t
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              {t === 'keys' ? 'API Keys' : t === 'integrations' ? 'Integrations' : 'General'}
            </button>
          ))}
        </div>

        <div className="p-5 max-h-[60vh] overflow-y-auto">
          {tab === 'keys' && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                API keys are encrypted and stored locally on your machine. They never leave your device.
              </p>
              {PROVIDERS.map((p) => (
                <div key={p.id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-foreground">{p.name}</p>
                      <p className="text-xs text-muted-foreground">{p.note}</p>
                    </div>
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary flex items-center gap-1 hover:underline"
                      onClick={(e) => {
                        e.preventDefault()
                        window.electronAPI?.openExternal(p.url)
                      }}
                    >
                      Get key <ExternalLink size={10} />
                    </a>
                  </div>
                  {keys[p.id] ? (
                    <div className="flex items-center gap-2 bg-secondary/50 rounded-lg px-3 py-2">
                      <span className="flex-1 text-sm font-mono text-muted-foreground">{keys[p.id]}</span>
                      <button onClick={() => removeKey(p.id)} className="text-destructive hover:text-destructive/80">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <input
                          type={show[p.id] ? 'text' : 'password'}
                          placeholder={`Enter ${p.name} API key`}
                          value={inputs[p.id] || ''}
                          onChange={(e) => setInputs((i) => ({ ...i, [p.id]: e.target.value }))}
                          onKeyDown={(e) => e.key === 'Enter' && saveKey(p.id)}
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-primary/50 pr-9"
                        />
                        <button
                          onClick={() => setShow((s) => ({ ...s, [p.id]: !s[p.id] }))}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                        >
                          {show[p.id] ? <EyeOff size={13} /> : <Eye size={13} />}
                        </button>
                      </div>
                      <button
                        onClick={() => saveKey(p.id)}
                        disabled={!inputs[p.id]?.trim()}
                        className={cn(
                          'px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                          saved[p.id]
                            ? 'bg-green-500/20 text-green-400'
                            : inputs[p.id]?.trim()
                            ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                            : 'bg-secondary text-muted-foreground cursor-not-allowed'
                        )}
                      >
                        {saved[p.id] ? <Check size={14} /> : 'Save'}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {tab === 'general' && (
            <div className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Temperature</label>
                <div className="flex items-center gap-3">
                  <input
                    type="range" min="0" max="2" step="0.1"
                    value={settings.temperature}
                    onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
                    className="flex-1 accent-primary"
                  />
                  <span className="text-sm text-muted-foreground w-8">{settings.temperature}</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Max Tokens</label>
                <select
                  value={settings.maxTokens}
                  onChange={(e) => updateSettings({ maxTokens: parseInt(e.target.value) })}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50"
                >
                  {[1024, 2048, 4096, 8192, 16384].map((v) => (
                    <option key={v} value={v}>{v.toLocaleString()} tokens</option>
                  ))}
                </select>
              </div>

              <div className="space-y-3">
                {[
                  { key: 'useTools', label: 'Enable Tools', desc: 'Allow agent to use web search, code execution, etc.' },
                  { key: 'sandboxTools', label: 'Sandbox Tool Execution', desc: 'Run code in isolated environment (recommended)' },
                  { key: 'streamResponses', label: 'Stream Responses', desc: 'Show responses as they are generated' },
                ] .map(({ key, label, desc }) => (
                  <div key={key} className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-foreground">{label}</p>
                      <p className="text-xs text-muted-foreground">{desc}</p>
                    </div>
                    <button
                      onClick={() => updateSettings({ [key]: !settings[key as keyof typeof settings] })}
                      className={cn(
                        'w-10 h-5.5 rounded-full transition-colors relative',
                        settings[key as keyof typeof settings] ? 'bg-primary' : 'bg-secondary'
                      )}
                    >
                      <span className={cn(
                        'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                        settings[key as keyof typeof settings] ? 'translate-x-5' : 'translate-x-0.5'
                      )} />
                    </button>
                  </div>
                ))}
              </div>

              <button
                onClick={saveGeneral}
                className="w-full bg-primary text-primary-foreground rounded-lg py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Save Settings
              </button>
            </div>
          )}
          {tab === 'integrations' && <IntegrationsTab />}
        </div>
      </div>
    </div>
  )
}

function IntegrationsTab() {
  const [smtpHost, setSmtpHost] = useState('smtp.gmail.com')
  const [smtpPort, setSmtpPort] = useState('587')
  const [smtpUser, setSmtpUser] = useState('')
  const [smtpPass, setSmtpPass] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  const saveSmtp = async () => {
    const base = 'http://127.0.0.1:8765/api/integrations'
    await Promise.all([
      fetch(base, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ service: 'smtp', key: 'host', value: smtpHost }) }),
      fetch(base, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ service: 'smtp', key: 'port', value: smtpPort }) }),
      fetch(base, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ service: 'smtp', key: 'user', value: smtpUser }) }),
      fetch(base, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ service: 'smtp', key: 'password', value: smtpPass }) }),
    ])
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const testSmtp = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch('http://127.0.0.1:8765/api/integrations/smtp/test')
      const data = await res.json()
      setTestResult(data.configured ? `✓ Configured: ${data.user}` : '✗ Not configured')
    } catch {
      setTestResult('✗ Could not connect to backend')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-foreground mb-1">Email (SMTP)</p>
        <p className="text-xs text-muted-foreground mb-3">
          Used by the agent to send emails. For Gmail, create an{' '}
          <a href="#" onClick={(e) => { e.preventDefault(); window.electronAPI?.openExternal('https://myaccount.google.com/apppasswords') }}
            className="text-primary underline">App Password</a>{' '}
          (requires 2FA enabled).
        </p>
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2 space-y-1">
              <label className="text-xs text-muted-foreground">SMTP Host</label>
              <input value={smtpHost} onChange={e => setSmtpHost(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Port</label>
              <input value={smtpPort} onChange={e => setSmtpPort(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50" />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Email Address</label>
            <input value={smtpUser} onChange={e => setSmtpUser(e.target.value)}
              placeholder="you@gmail.com"
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">App Password</label>
            <div className="relative">
              <input type={showPass ? 'text' : 'password'} value={smtpPass} onChange={e => setSmtpPass(e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx"
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50 pr-9" />
              <button onClick={() => setShowPass(!showPass)} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                {showPass ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={saveSmtp} disabled={!smtpUser || !smtpPass}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 disabled:opacity-50 transition-colors">
              {saved ? <><Check size={13} /> Saved</> : 'Save SMTP'}
            </button>
            <button onClick={testSmtp} disabled={testing}
              className="px-3 py-2 rounded-lg bg-secondary text-muted-foreground text-sm hover:text-foreground transition-colors">
              {testing ? 'Testing…' : 'Test'}
            </button>
          </div>
          {testResult && <p className="text-xs text-muted-foreground">{testResult}</p>}
        </div>
      </div>

      <div className="border-t border-border pt-4">
        <p className="text-sm font-medium text-foreground mb-1">Available Built-in Tools</p>
        <p className="text-xs text-muted-foreground mb-2">The agent can use these without writing any code:</p>
        <div className="grid grid-cols-2 gap-1">
          {['send_email', 'send_notification', 'http_request', 'take_screenshot', 'get_clipboard', 'set_clipboard', 'run_applescript', 'run_shell', 'open_app', 'open_url', 'web_search', 'fetch_url', 'read_file', 'write_file', 'list_directory'].map(t => (
            <span key={t} className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded">{t}</span>
          ))}
        </div>
      </div>
    </div>
  )
}
