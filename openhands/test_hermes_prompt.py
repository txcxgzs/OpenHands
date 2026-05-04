#!/usr/bin/env python3
"""测试 Hermes 提示词构建器"""

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

def test_basic_build():
    """测试基本构建"""
    print("=" * 80)
    print("测试 1: 基本构建")
    print("=" * 80)
    
    config = PromptConfig(
        workspace=Path("/workspace/openhands-workspace"),
        mode=PromptMode.FULL,
        model_family=ModelFamily.OPENAI,
        platform="cli",
        include_timestamp=True,
        session_id="test-session-123",
        model_name="gpt-4",
        provider_name="openai"
    )
    
    builder = PromptBuilder(config)
    prompt = builder.build()
    
    print(f"提示词长度: {len(prompt)} 字符")
    print("\n提示词内容:")
    print("-" * 80)
    print(prompt[:2000] + ("..." if len(prompt) > 2000 else ""))
    print("-" * 80)
    print("\n")

def test_factory_function():
    """测试工厂函数"""
    print("=" * 80)
    print("测试 2: 工厂函数")
    print("=" * 80)
    
    prompt = build_system_prompt(
        mode=PromptMode.FULL,
        workspace=Path("/workspace/openhands-workspace"),
        model_family=ModelFamily.GOOGLE,
        platform="telegram",
        include_nous_subscription=True
    )
    
    print(f"提示词长度: {len(prompt)} 字符")
    print("\n")

def test_minimal_mode():
    """测试 Minimal 模式"""
    print("=" * 80)
    print("测试 3: Minimal 模式")
    print("=" * 80)
    
    prompt = build_system_prompt(
        mode=PromptMode.MINIMAL,
        workspace=Path("/workspace/openhands-workspace")
    )
    
    print(f"提示词长度: {len(prompt)} 字符")
    print("\n提示词内容:")
    print("-" * 80)
    print(prompt)
    print("-" * 80)
    print("\n")

def test_alibaba_model():
    """测试阿里巴巴模型身份覆盖"""
    print("=" * 80)
    print("测试 4: 阿里巴巴模型身份覆盖")
    print("=" * 80)
    
    prompt = build_system_prompt(
        workspace=Path("/workspace/openhands-workspace"),
        model_name="qwen-max",
        alibaba_model_short="Qwen Max"
    )
    
    print(f"提示词长度: {len(prompt)} 字符")
    print("\n")

def main():
    """主函数"""
    print("开始测试 Hermes 提示词构建器...\n")
    
    test_basic_build()
    test_factory_function()
    test_minimal_mode()
    test_alibaba_model()
    
    print("=" * 80)
    print("所有测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
