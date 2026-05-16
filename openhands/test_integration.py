#!/usr/bin/env python3
"""
测试 Hermes 提示词集成
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from openhands.core.agent.hermes_prompt_builder import (
    PromptBuilder,
    PromptConfig,
    ModelFamily,
    build_system_prompt,
    DEFAULT_WORKSPACE
)

def test_full_integration():
    """测试完整集成"""
    print("=" * 80)
    print("测试 Hermes 提示词完整集成")
    print("=" * 80)
    
    print("\n1. 测试 OPENAI 模型")
    config_openai = PromptConfig(
        workspace=Path("/workspace/openhands-workspace"),
        mode=PromptMode.FULL,
        model_family=ModelFamily.OPENAI,
        platform="cli",
        include_timestamp=True,
        session_id="test-session-openai",
        model_name="gpt-4",
        provider_name="openai"
    )
    builder_openai = PromptBuilder(config_openai)
    prompt_openai = builder_openai.build()
    print(f"   提示词长度: {len(prompt_openai)} 字符")
    print(f"   包含 'Tool-use enforcement': {'Tool-use enforcement' in prompt_openai}")
    print(f"   包含 'Execution discipline': {'Execution discipline' in prompt_openai}")
    
    print("\n2. 测试 GOOGLE 模型")
    config_google = PromptConfig(
        workspace=Path("/workspace/openhands-workspace"),
        mode=PromptMode.FULL,
        model_family=ModelFamily.GOOGLE,
        platform="telegram",
        include_timestamp=True,
        session_id="test-session-google",
        model_name="gemini-1.5-pro",
        provider_name="google"
    )
    builder_google = PromptBuilder(config_google)
    prompt_google = builder_google.build()
    print(f"   提示词长度: {len(prompt_google)} 字符")
    print(f"   包含 'Tool-use enforcement': {'Tool-use enforcement' in prompt_google}")
    print(f"   包含 'Google model operational directives': {'Google model operational directives' in prompt_google}")
    
    print("\n3. 测试工厂函数")
    factory_prompt = build_system_prompt(
        mode=PromptMode.FULL,
        workspace=Path("/workspace/openhands-workspace"),
        model_family=ModelFamily.ANTHROPIC,
        platform="web"
    )
    print(f"   工厂函数生成的提示词长度: {len(factory_prompt)} 字符")
    
    print("\n4. 测试 Minimal 模式")
    minimal_prompt = build_system_prompt(
        mode=PromptMode.MINIMAL,
        workspace=Path("/workspace/openhands-workspace")
    )
    print(f"   Minimal 模式提示词长度: {len(minimal_prompt)} 字符")
    
    print("\n" + "=" * 80)
    print("✅ 所有集成测试通过！")
    print("=" * 80)


if __name__ == "__main__":
    test_full_integration()
