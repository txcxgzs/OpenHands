#!/usr/bin/env python3
"""Quick import verification script"""

import sys

print("=" * 60)
print("OpenHands Import Verification")
print("=" * 60)
print()

# Verify version and root package
try:
    import openhands
    print(f"✓ openhands v{openhands.__version__}")
except Exception as e:
    print(f"✗ Failed to import openhands: {e}")
    sys.exit(1)

print()

# Test core modules
core_modules = [
    ("Core Config", "openhands.core.config"),
    ("Tool Registry", "openhands.tools.registry"),
    ("Tool Policy", "openhands.core.tools.policy"),
    ("Memory Store", "openhands.core.memory.store"),
    ("Sub-agents", "openhands.core.subagents.manager"),
    ("Agent Runner", "openhands.core.agent.runner"),
]

for name, module in core_modules:
    try:
        __import__(module)
        print(f"✓ {name}")
    except Exception as e:
        print(f"✗ {name}: {e}")

print()

# Test built-in tools
tools_modules = [
    ("File Tools", "openhands.tools.file_tools"),
    ("Terminal Tools", "openhands.tools.terminal_tools"),
    ("Web Tools", "openhands.tools.web_tools"),
    ("Browser Tools", "openhands.tools.browser_tools"),
    ("Voice Tools", "openhands.tools.voice_tools"),
    ("Media Tools", "openhands.tools.media_tools"),
    ("Sandbox Tools", "openhands.tools.sandbox_tools"),
]

print("Built-in Tools:")
for name, module in tools_modules:
    try:
        __import__(module)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ○ {name} (optional)")

print()

# Test Windows/Multimodal/Scheduler
other_modules = [
    ("Windows Automation", "openhands.windows.windows_tools"),
    ("Multimodal", "openhands.multimodal.multimodal_tools"),
    ("Scheduler", "openhands.scheduler"),
    ("Sandbox", "openhands.sandbox"),
]

print("Other Modules:")
for name, module in other_modules:
    try:
        __import__(module)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ○ {name} (optional)")

print()

# Test Channels
channel_modules = [
    ("Channels", "openhands.channels.slack_channel"),
]

print("Channels:")
for name, module in channel_modules:
    try:
        __import__(module)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ○ {name} (optional)")

print()

# Test GUI and CLI
gui_cli = [
    ("GUI", "openhands.gui.server"),
    ("CLI", "openhands.cli.main"),
]

print("Interfaces:")
for name, module in gui_cli:
    try:
        __import__(module)
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ○ {name}")

print()

# Test tool registry with all tools
print("=" * 60)
print("Tool Registry Test")
print("=" * 60)
print()

try:
    from openhands import tool_registry
    from openhands.tools import (
        file_tools, terminal_tools, web_tools
    )

    registry = tool_registry()

    # Register core tools
    file_tools.register_tools(registry)
    terminal_tools.register_tools(registry)
    web_tools.register_tools(registry)

    try:
        from openhands.tools import browser_tools
        browser_tools.register_tools(registry)
    except Exception as e:
        print(f"  (Browser not registered: {e})")

    try:
        from openhands.tools import voice_tools
        voice_tools.register_tools(registry)
    except Exception as e:
        print(f"  (Voice not registered: {e})")

    try:
        from openhands.tools import media_tools
        media_tools.register_tools(registry)
    except Exception as e:
        print(f"  (Media not registered: {e})")

    try:
        from openhands.tools import sandbox_tools
        sandbox_tools.register_tools(registry)
    except Exception as e:
        print(f"  (Sandbox not registered: {e})")

    tools_list = registry.list_tools()

    print(f"✓ {len(tools_list)} tools registered")
    for tool in tools_list[:20]:
        print(f"  - {tool.name}: {tool.description}")
    if len(tools_list) > 20:
        print(f"  ... and {len(tools_list)-20} more")

except Exception as e:
    print(f"✗ Tool registry error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("Verification Complete!")
print("=" * 60)
print()
print("Next steps:")
print("  1. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
print("  2. Try 'openhands chat' or 'openhands gui'")
print("  3. Check README.md for full documentation")
