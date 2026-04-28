# 🦀 ClosedClaw

A local AI agent platform with multi-provider support, tool creation, web research, and sandboxed code execution. Runs entirely on your machine.

https://github.com/user-attachments/assets/1147037f-540d-43e8-949b-debe75a3e2b9

## Features

- **Multi-provider**: OpenAI, Anthropic, Google, Mistral, OpenRouter (100+ models including free ones)
- **Agentic tool loop**: Web search, URL fetching, Python execution, file I/O
- **Custom tools**: Write and test your own Python tools in the UI
- **Web research**: Multi-step research with source synthesis
- **Secure**: API keys encrypted locally, sandboxed code execution, input sanitization
- **Cross-platform**: Mac, Windows, Linux via Electron

## Requirements

- Node.js 18+
- Python 3.10+
- npm

## Quick Start

```bash
# Mac/Linux
chmod +x setup.sh && ./setup.sh

# Windows
setup.bat
```

Then run:
```bash
npm run dev
```

## Build for Distribution

```bash
npm run build:mac    # macOS DMG
npm run build:win    # Windows NSIS installer
npm run build:linux  # Linux AppImage
```

## Architecture

```
Electron (main process)
  └── Spawns Python FastAPI backend on port 8765
  └── React frontend (Vite) served via Electron

Backend (Python/FastAPI)
  ├── /api/chat/stream   — Streaming chat with tool loop
  ├── /api/tools         — Tool CRUD + test execution
  ├── /api/settings      — Encrypted API key storage
  ├── /api/research      — Multi-step web research
  └── /api/sessions      — Conversation history

Security
  ├── API keys: AES-256 encrypted via PBKDF2 key derivation
  ├── Code execution: subprocess isolation + static analysis
  ├── File access: restricted to home directory
  └── Network: localhost-only backend, CSP headers
```

## Adding API Keys

1. Open Settings (bottom of sidebar)
2. Enter your API key for any provider
3. Keys are encrypted and stored in `~/.openclaw/`

## Free Models (No API Key Needed)

Via OpenRouter (free tier, requires OpenRouter API key — free to create):
- Llama 3.1 8B
- Mistral 7B
- Gemma 2 9B
- Qwen 2 7B
- Phi-3 Mini 128K
