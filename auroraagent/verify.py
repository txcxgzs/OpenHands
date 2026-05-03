#!/usr/bin/env python3
"""Quick import verification script"""

import sys

print("=" * 60)
print("AuroraAgent Import Verification")
print("=" * 60)
print()

# Verify version and root package
try:
    import auroraagent
    print(f"✓ auroraagent v{auroraagent.__version__}")
except Exception as e:
    print(f"✗ Failed to import auroraagent: {e}")
    sys.exit(1)

print()

# Test core modules
core_modules = [
    ("Core Config", "auroraagent.core.config"),
    ("Tool Registry", "auroraagent.tools.registry"),
    ("Tool Policy", "auroraagent.core.tools.policy"),
    ("Memory Store", "auroraagent.core.memory.store"),
]

for name, module in core_modules:
    try:
        __import__(module)
        print(f"✓ {name}")
    except Exception as e:
        print(f"✗ {name}: {e}")

print()

# Test basic tools (no heavy deps)
toolsets = [
    ("File Tools", "auroraagent.tools.file_tools"),
    ("Terminal Tools", "auroraagent.tools.terminal_tools"),
    ("Web Tools", "auroraagent.tools.web_tools"),
]

print("Built-in Tools:")
for name, module in toolsets:
    try:
        __import__(module)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ○ {name} (optional, skip)")

print()

# Test CLI works
print("CLI Commands:")
try:
    from auroraagent.cli.main import main
    print("  ✓ CLI available")
except Exception as e:
    print(f"  ✗ CLI: {e}")

print()

# Verify tool registry has tools
print()
print("=" * 60)
print("Tool Registry Test")
print("=" * 60)
print()

try:
    from auroraagent import tool_registry
    from auroraagent.tools import file_tools, terminal_tools

    registry = tool_registry()

    # Register test tools
    file_tools.register_tools(registry)
    terminal_tools.register_tools(registry)

    tools_list = registry.list_tools()

    print(f"✓ {len(tools_list)} tools registered")
    for tool in tools_list[:10]:
        print(f"  - {tool.name}: {tool.description}")

except Exception as e:
    print(f"✗ Tool registry error: {e}")

print()
print("=" * 60)
print("Verification Complete!")
print("=" * 60)
print()
print("Next steps:")
print("  1. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
print("  2. Try 'aurora chat' or 'aurora gui'")
print("  3. Check README.md for full documentation")
