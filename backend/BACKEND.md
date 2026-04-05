# OpenClaw Backend — Technical Documentation

## Overview

The backend is a **Python FastAPI** application running locally on `127.0.0.1:8765`.
Spawned as a child process by Electron, it serves the React frontend via HTTP + SSE.

```
Electron → spawns uvicorn → FastAPI :8765
  ├── /api/chat         streaming agent loop
  ├── /api/tools        tool CRUD + execution
  ├── /api/settings     encrypted API key storage
  ├── /api/sessions     conversation history
  ├── /api/monitor      background monitor jobs
  ├── /api/commands     slash command handling
  ├── /api/integrations SMTP + webhook credentials
  └── /api/research     multi-step web research
```

All data persists to `~/.openclaw/` as JSON files with `chmod 600`.

---

## Directory Structure

```
backend/
├── main.py                   FastAPI app, middleware, router registration
├── agents/
│   ├── loop.py               Core agent loop (native + ReAct modes)
│   ├── parser.py             Multi-format tool call parser
│   ├── prompts.py            System prompt builders
│   ├── sse.py                SSE event helpers (single source of truth)
│   ├── skills.py             Persona injection (SOUL.md, AGENTS.md)
│   ├── tool_runner.py        Tool creation + execution helpers
│   └── usage.py              Token counting + cost estimation
├── core/
│   ├── config.py             App settings (pydantic-settings, .env support)
│   ├── security.py           AES-256 encryption, input sanitization, code validation
│   ├── storage.py            JSON persistence layer
│   └── credentials.py       Encrypted credentials store (SMTP etc.)
├── providers/
│   ├── base.py               Abstract base class + model registry (40+ models)
│   ├── factory.py            Provider factory — model ID → provider instance
│   ├── openai_provider.py    OpenAI-compatible (OpenAI, OpenRouter, Google, Groq, Mistral, Perplexity, Ollama)
│   └── anthropic_provider.py Anthropic Claude native API
├── routers/
│   ├── chat.py               POST /api/chat/stream — main entry point
│   ├── tools.py              CRUD for user-defined tools
│   ├── settings.py           API key management
│   ├── sessions.py           Conversation history
│   ├── monitor.py            Background monitor jobs
│   ├── commands.py           Slash commands (/compact, /status, /export...)
│   ├── integrations.py       SMTP + webhook credentials
│   └── research.py           Multi-step web research
└── tools/
    ├── registry.py           Built-in + user tool definitions (OpenAI format)
    ├── executor.py           Tool dispatch, sandboxed execution, builtin shim
    └── builtin_actions.py    Email, notifications, HTTP, shell, clipboard, screenshot
```

---

## Request Lifecycle

```
POST /api/chat/stream  {model, messages, use_tools, session_id, thinking}
  │
  ├─ Slash command? → routers/commands.py → SSE response → done
  │
  ├─ Resolve provider + API key (with failover chain)
  ├─ Sanitize user messages (XSS only, not Python keywords)
  │
  └─ agents/loop.run()
       ├─ native  (OpenAI/Anthropic/Mistral) → run_native()
       ├─ react   (all other models)         → run_react()
       └─ plain   (use_tools=false)          → direct LLM call

SSE stream:
  data: {"type":"thinking","message":"..."}
  data: {"type":"tool_call","name":"...","args":{}}
  data: {"type":"tool_result","name":"...","result":{}}
  data: {"type":"token","content":"..."}
  data: {"type":"usage","tokens":123,"cost":0.0001}
  data: {"type":"done"}
```

---

## Agent Loop (`agents/loop.py`)

### Native Function Calling — OpenAI / Anthropic / Mistral

```
1. Build messages + system prompt
2. Send to LLM with tools list (OpenAI function calling format)
3. Stream response; accumulate tool_call deltas
4. Execute each tool → append results to messages → loop
5. No tool calls → break
Max iterations: 6
```

### ReAct Loop — Gemini, OpenRouter, all others

```
1. Build messages + ReAct system prompt (includes tool format instructions)
2. Send to LLM, buffer full response (no streaming during tool detection)
3. If truncated (finish_reason=length) → ask model to continue → concat
4. Parse with 4-priority fallback:
   P1: <create_tool>{json}</create_tool>  → validate + save + run new tool
   P2: <tool_call>{json}</tool_call>      → call existing built-in tool
   P3: Intent detection (subprocess.Popen, open -a, macappstore:// in text)
   P4: Plain text → stream as tokens
5. After tool result → ask model to summarize → stream final answer
```

---

## Response Parser (`agents/parser.py`)

Handles every format models actually emit:

| Format | Example |
|--------|---------|
| Tagged JSON | `<tool_call>{"name":"x","arguments":{}}</tool_call>` |
| Create tool tag | `<create_tool>{"name":"x","code":"..."}</create_tool>` |
| Function XML | `<function=name><parameter=x>val</parameter></function>` |
| Bare JSON | `{"name":"x","code":"..."}` (no wrapping tags) |
| Code block | ` ```python\nsubprocess...``` ` |
| Intent pattern | `subprocess.Popen(...)` in plain text |

Uses brace-depth matching (not regex) for JSON extraction to handle embedded newlines in code strings. Includes newline-repair fallback for invalid JSON.

---

## Tool System

### Built-in Tools (16)

| Tool | Description |
|------|-------------|
| `web_search(query)` | DuckDuckGo search, no API key |
| `fetch_url(url)` | Fetch + parse webpage (BeautifulSoup, 8KB) |
| `run_python(code)` | Sandboxed Python (no network/fs, 128MB, 15s) |
| `read_file(path)` | Read local file (home dir only, 50KB) |
| `write_file(path, content)` | Write local file (home dir only) |
| `list_directory(path)` | List folder (home dir only) |
| `send_email(to, subject, body)` | SMTP email using stored credentials |
| `send_notification(title, message)` | macOS notification via osascript |
| `http_request(url, method, headers, body)` | HTTP/webhook calls via httpx |
| `take_screenshot(save_path)` | Screen capture via screencapture |
| `get_clipboard()` | Read clipboard via pbpaste |
| `set_clipboard(text)` | Write clipboard via pbcopy |
| `run_applescript(script)` | Mac automation via osascript |
| `run_shell(command)` | Any shell command, full system access |
| `open_app(app_name)` | Open Mac app via `open -a` |
| `open_url(url)` | Open URL via `open` |

### User-Defined Tools

Stored in `~/.openclaw/tools.json`. Created via UI or auto-created by agent.

When agent creates a tool via `<create_tool>`:
1. `validate_agent_tool_code()` — blocks `__import__`, `eval`, fork bombs
2. Saved to `tools.json` (persists across sessions)
3. Executed immediately with result returned to agent

### Builtin Shim

Every user tool subprocess gets a Python shim injected at the top. This lets agent-generated code call `open_url(...)`, `send_email(...)`, `send_notification(...)` etc. as plain Python functions without imports. The shim also injects SMTP credentials from environment variables.

```python
# Agent writes:
result = open_url("https://example.com")
print(result)

# Executor prepends the shim, so open_url() is defined and works
```

---

## Provider System

### Model Registry (`providers/base.py`)

40+ models with metadata: `provider`, `context`, `free`, `supports_thinking`.

### Provider Factory (`providers/factory.py`)

| Provider | Base URL | Auth |
|----------|----------|------|
| `openai` | `api.openai.com/v1` | API key |
| `anthropic` | `api.anthropic.com/v1` | API key (native) |
| `openrouter` | `openrouter.ai/api/v1` | API key |
| `google` | `generativelanguage.googleapis.com/v1beta/openai` | API key |
| `groq` | `api.groq.com/openai/v1` | API key |
| `perplexity` | `api.perplexity.ai` | API key |
| `mistral` | `api.mistral.ai/v1` | API key |
| `ollama` | `localhost:11434/v1` | None (local) |

### Model Failover

`routers/chat.py` defines failover chains. If the primary model fails (any exception), the next model in the chain is tried automatically:

```python
FAILOVER_CHAINS = {
    "google/gemini-2.5-flash": ["google/gemini-2.0-flash", "openrouter/stepfun/step-3.5-flash:free"],
    "openai/gpt-4o": ["openai/gpt-4o-mini"],
    "anthropic/claude-opus-4-5": ["anthropic/claude-sonnet-4-5", "anthropic/claude-3-5-sonnet"],
}
```

---

## Security Model

### API Key Encryption

```
User enters key → PBKDF2-HMAC-SHA256 (480k iterations) → AES-256 Fernet
→ stored in ~/.openclaw/settings.json (chmod 600)
→ never returned to frontend (masked as "***xxxx")
```

Salt in `~/.openclaw/.keystore` (chmod 600). Machine-local — not portable.

### Input Sanitization

`sanitize_input()` strips only XSS patterns (`<script>`, `javascript:`, event handlers).
Does NOT strip Python keywords — `subprocess`, `os`, `eval` are needed for tool code.

### Code Validation (two tiers)

**`validate_tool_code()`** — strict sandbox for `run_python`:
- Blocks: `__import__`, `eval(`, `exec(`, `socket`, `shutil.rmtree`
- 128MB RAM, 15s timeout, no network/fs env

**`validate_agent_tool_code()`** — relaxed for agent-created tools:
- Blocks only: `__import__`, `eval(`, `exec(`, `shutil.rmtree /`, fork bomb
- Allows: `subprocess`, `os`, `sys`, `smtplib`, `urllib`, `httpx`
- Full env, 30s timeout

### Network Security

- `TrustedHostMiddleware` — only `localhost`/`127.0.0.1`
- `CORSMiddleware` — only `localhost:5173`
- File access — home directory only
- URL fetching — `http://` and `https://` only

---

## Monitor Mode (`routers/monitor.py`)

Background jobs that check a condition on a schedule and act when triggered.

```
POST /api/monitor/plan        LLM generates check + action tools + trigger expression
POST /api/monitor/start/{id}  Save tools, start asyncio background task
GET  /api/monitor/stream/{id} SSE stream of events
POST /api/monitor/stop/{id}   Cancel the task
GET  /api/monitor/            List all monitors
```

### Monitor Loop

```python
while True:
    result = execute_tool(check_tool, {})
    should_fire = eval(trigger_eval, {"result": result})
    if should_fire:
        execute_tool(action_tool, {"check_result": json.dumps(result)})
    await asyncio.sleep(interval_seconds)
```

SMTP credentials are injected as `SMTP_USER`/`SMTP_PASS`/`SMTP_HOST` env vars before the loop starts.

---

## Session Commands (`routers/commands.py`)

Intercepted before the agent loop when the last user message starts with `/`:

| Command | Effect |
|---------|--------|
| `/new` or `/reset` | Clear all messages in session |
| `/compact` | LLM summarizes history → replaces with summary (saves tokens) |
| `/status` | Returns model, message count, estimated token count |
| `/think <level>` | Sets thinking mode preference |
| `/usage <mode>` | Sets usage display mode |
| `/export` | Returns full session as Markdown |

---

## Skills & Persona (`agents/skills.py`)

Read from `~/.openclaw/workspace/` on every request and prepended to system prompt:

| File | Purpose |
|------|---------|
| `SOUL.md` | Agent personality |
| `AGENTS.md` | Behavioral instructions |
| `TOOLS.md` | Tool usage notes |
| `skills/<name>/SKILL.md` | Installed skill descriptions |

---

## SSE Event Reference

| Type | Fields | Description |
|------|--------|-------------|
| `thinking` | `message` | Agent processing step |
| `token` | `content` | Text chunk to append |
| `tool_call` | `name`, `args` | Tool being called |
| `tool_result` | `name`, `result` | Tool execution result |
| `tool_created` | `name`, `description` | New tool saved |
| `error` | `message` | Error |
| `done` | — | Stream complete |
| `usage` | `tokens`, `cost` | Token usage estimate |
| `failover` | `from_model`, `to_model` | Model failover occurred |
| `export` | `content`, `filename` | Session export |
| `compact_summary` | `summary` | Context was compacted |

---

## Data Files (`~/.openclaw/`)

| File | Contents |
|------|----------|
| `settings.json` | Encrypted API keys + app preferences |
| `credentials.json` | Encrypted SMTP + integration credentials |
| `tools.json` | User-defined and agent-created tools |
| `sessions.json` | Conversation history |
| `monitors.json` | Monitor job definitions and state |
| `usage.json` | Token usage and cost tracking |
| `.keystore` | 16-byte random salt for key derivation |
| `workspace/SOUL.md` | Agent persona |
| `workspace/AGENTS.md` | Agent instructions |

All JSON files: `chmod 600` (owner read/write only).

---

## Running

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8765 --reload --http h11 --loop asyncio
```

`--http h11 --loop asyncio` are required for correct SSE streaming in Electron's Chromium renderer.

`DEBUG=true` enables the Swagger UI at `/docs`.
