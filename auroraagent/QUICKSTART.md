# Quick Start

## 5-Minute Setup

```bash
cd /workspace/auroraagent

# Install
pip install -e ".[browser,voice]"

# Copy config
cp config.example.yaml config.yaml

# Set API key
export ANTHROPIC_API_KEY=your_key

# Run tests
python tests/test_tools.py
```

## Try It Now

### Start GUI

```bash
aurora gui --host 0.0.0.0 --port 8000
```

Open browser: http://localhost:8000

### CLI Chat

```bash
aurora chat --profile coding
```

### Single Question

```bash
aurora ask "List the files in /workspace"
```

### List Tools and Profiles

```bash
aurora tools
aurora profiles
```

## Example Scripts

```bash
# Run simple chat
python examples/simple_chat.py

# Memory demo
python examples/memory_demo.py
```

## Configuration Options

### Use OpenAI

```yaml
model:
  provider: openai
  model: gpt-4o
```

### Use OpenRouter (200+ models)

```yaml
model:
  provider: openrouter
  model: openai/gpt-4o
```

## Next Steps

1. Read [README.md](README.md) for full documentation
2. Check [examples/](examples/) for more code patterns
3. Explore the [auroraagent/](auroraagent/) source directory
