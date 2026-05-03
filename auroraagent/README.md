# AuroraAgent

AI Assistant with Windows Control, deeply inspired by OpenClaw and Hermes Agent.

## Features

- **Agent Runtime**: Full-featured agent loop with tool calling
- **Windows Control**: Mouse, keyboard, window, screenshot automation
- **Multi-Provider**: Anthropic, OpenAI, OpenRouter support
- **Tools**: File operations, terminal, web, browser, media
- **Memory**: Vector memory store for long-term context
- **Tool Policy**: Per-profile tool permissions
- **GUI**: Modern web interface
- **CLI**: Rich command-line interface
- **SubAgents**: Task delegation
- **Scheduled Tasks**: Cron and interval jobs
- **Sandbox**: Docker isolation for code execution
- **Browser**: Playwright automation

## Quick Start

```bash
# Clone and install
cd /workspace/auroraagent
pip install -e .

# Set API key
export ANTHROPIC_API_KEY=your_key

# Start GUI
aurora gui --port 8000

# CLI chat
aurora chat --profile coding

# Single question
aurora ask "What can you do?"
```

## Configuration

Copy `config.example.yaml` and edit:

```yaml
model:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  temperature: 0.7

tools:
  default_profile: coding

# Or use .env file
cp .env.example .env
```

## Available Tools

| Toolset | Tools |
|---------|-------|
| File | `read_file`, `write_file`, `list_dir` |
| Terminal | `terminal_run` |
| Windows | `mouse_click`, `mouse_move`, `key_press`, `type_text`, `screenshot` |
| Multimodal | `capture_region`, `list_monitors` |
| Memory | `memory_add`, `memory_search`, `memory_list` |
| Web | `web_search`, `web_fetch` |
| Browser | `browser_navigate`, `browser_screenshot`, `browser_click` |
| Sandbox | `sandbox_exec`, `sandbox_check` |
| Voice | `tts_speak`, `tts_save`, `asr_transcribe`, `asr_listen` |
| Media | `generate_image`, `generate_speech`, `transcribe_audio` |

## Examples

See the [examples/](examples/) directory for:
- [Simple chat](examples/simple_chat.py)
- [Screenshot analysis](examples/screenshot_analysis.py)
- [Windows automation](examples/windows_automation.py)
- [Memory demo](examples/memory_demo.py)
- [Subagent demo](examples/subagent_demo.py)

## Tests

```bash
# Install test dependencies
pip install -e .[dev]

# Run tests
pytest tests/ -v
```

## Architecture

```
auroraagent/
├── core/
│   ├── agent/           # Agent runtime (EmbeddedAgent)
│   ├── adapters/        # Model provider adapters
│   ├── tools/           # Tool registry and policy
│   ├── memory/          # Memory store (vector search)
│   ├── subagents/       # Sub-agent manager
│   ├── mcp/             # MCP protocol
│   └── prompts.py       # System prompts
├── cli/                 # Command-line interface
├── gui/                 # Web GUI
├── tools/               # Built-in tools
├── windows/             # Windows automation
├── multimodal/          # Multimodal tools
├── scheduler/           # Scheduled tasks
├── sandbox/             # Docker sandbox
├── channels/            # Channel integrations
├── plugins/             # Plugin system
└── utils/               # Utilities
```

## Credits

- **OpenClaw**: Architecture, tool system, agent loop
- **Hermes Agent**: Memory system, tool patterns
- **Anthropic Claude**: Primary model provider

## License

MIT
