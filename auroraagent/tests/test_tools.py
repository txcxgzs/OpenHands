"""
Tool Call Test - Verify tools work correctly
"""

import asyncio
import os
from auroraagent import EmbeddedAgent, AgentConfig, tool_registry
from auroraagent.tools import file_tools, terminal_tools


async def test_registry():
    """Test tool registry"""
    print("=== Test: Tool Registry ===")

    registry = tool_registry()
    tools = registry.list_tools()

    print(f"Registered tools: {len(tools)}")
    for tool in tools:
        print(f"  - {tool.name} ({tool.toolset})")

    return len(tools) > 0


async def test_file_tools():
    """Test file tools"""
    print("\n=== Test: File Tools ===")

    registry = tool_registry()

    test_content = "Hello from AuroraAgent test!"

    write_result = await registry.execute_tool(
        "write_file",
        {"path": "/tmp/aurora_test.txt", "content": test_content}
    )
    print(f"write_file: {write_result.content}")

    read_result = await registry.execute_tool(
        "read_file",
        {"path": "/tmp/aurora_test.txt"}
    )
    print(f"read_file: {read_result.content[:50]}...")

    list_result = await registry.execute_tool(
        "list_dir",
        {"path": "/tmp"}
    )
    print(f"list_dir: {list_result.content[:100]}...")

    return "aurora_test" in read_result.content


async def test_terminal_tools():
    """Test terminal tools"""
    print("\n=== Test: Terminal Tools ===")

    registry = tool_registry()

    result = await registry.execute_tool(
        "terminal_run",
        {"command": "echo 'AuroraAgent terminal test'"}
    )
    print(f"terminal_run: {result.content[:100]}")

    return "AuroraAgent terminal test" in result.content


async def test_tool_definitions():
    """Test tool definitions format"""
    print("\n=== Test: Tool Definitions ===")

    registry = tool_registry()
    definitions = registry.get_definitions()

    print(f"Tool definitions: {len(definitions)}")

    for defn in definitions[:5]:
        print(f"  - {defn['name']}: {defn['description'][:50]}...")

    anthropic_format = any("input_schema" in str(d) for d in definitions)

    return len(definitions) > 0 and anthropic_format


async def test_agent_run():
    """Test full agent run (without API key)"""
    print("\n=== Test: Agent Run (Mock) ===")

    config = AgentConfig.load()
    agent = EmbeddedAgent(config)

    session_id = await agent.create_session()
    print(f"Session created: {session_id}")

    messages = agent.get_session(session_id)
    print(f"Session state: {messages.status.value}")

    return session_id is not None


async def main():
    print("AuroraAgent Tool Call Test Suite")
    print("=" * 50)

    results = []

    results.append(("Tool Registry", await test_registry()))
    results.append(("File Tools", await test_file_tools()))
    results.append(("Terminal Tools", await test_terminal_tools()))
    results.append(("Tool Definitions", await test_tool_definitions()))
    results.append(("Agent Session", await test_agent_run()))

    print("\n" + "=" * 50)
    print("Test Results:")
    print("-" * 50)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
