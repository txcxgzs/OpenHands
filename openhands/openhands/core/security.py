"""
安全防注入和敏感文本清理系统 - 100%对齐Hermes

功能：
- 提示注入检测
- 越狱模式检测
- 凭证窃取检测
- SSH后门检测
- 不可见字符检测
- 敏感文本清理
- 安全的记忆写入
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Set, Pattern, Dict

logger = logging.getLogger(__name__)

# 威胁检测模式
THREAT_PATTERNS: List[Tuple[Pattern, str]] = [
    # 提示注入
    (re.compile(r'ignore\s+(previous|all|above|prior)\s+(instructions|content|conversation)', re.IGNORECASE), "prompt_injection"),
    (re.compile(r'\bdisregard\s+previous\b', re.IGNORECASE), "prompt_injection"),
    (re.compile(r'\byou\s+are\s+now\s+an?\s+', re.IGNORECASE), "role_hijack"),
    (re.compile(r'\b(you\s+are|act\s+as)\s+(not|no\s+longer)\s+', re.IGNORECASE), "role_replacement"),
    
    # 越狱
    (re.compile(r'\bdisregard\s+(your|all|any)\s+(instructions|rules|guidelines|content|content\s+filter)', re.IGNORECASE), "jailbreak"),
    (re.compile(r'\byou\s+are\s+not\s+bound\s+by\s+any\s+(rules|constraints)', re.IGNORECASE), "jailbreak"),
    (re.compile(r'\bpretend\s+you\s+have\s+(no|zero)\s+(rules|restrictions|content\s+filter)', re.IGNORECASE), "jailbreak"),
    (re.compile(r'\bforget\s+all\s+previous\s+(instructions|rules)', re.IGNORECASE), "jailbreak"),
    
    # 凭证窃取
    (re.compile(r'\bcurl\s+[^\n]*\$[a-zA-Z_]*(key|token|secret|password|credential|api)', re.IGNORECASE), "credential_exfiltration"),
    (re.compile(r'\bwget\s+[^\n]*\$[a-zA-Z_]*(key|token|secret|password|credential|api)', re.IGNORECASE), "credential_exfiltration"),
    (re.compile(r'\bcat\s+[^\n]*(\.env|\.gitconfig|credentials|\.ssh|\.netrc|\.aws|\.azure)', re.IGNORECASE), "secret_access"),
    
    # SSH后门
    (re.compile(r'authorized_keys', re.IGNORECASE), "ssh_backdoor_suspected"),
    (re.compile(r'id_rsa\s*>\s*', re.IGNORECASE), "ssh_backdoor_suspected"),
    (re.compile(r'ssh-rsa\s+A{3,}', re.IGNORECASE), "ssh_backdoor_suspected"),
]

# 不可见字符
INVISIBLE_CHARS: Set[str] = {
    '\u200b',  # Zero Width Space
    '\u200c',  # Zero Width Non-Joiner
    '\u200d',  # Zero Width Joiner
    '\u200e',  # Left-to-Right Mark
    '\u200f',  # Right-to-Left Mark
    '\u202a',  # Left-to-Right Embedding
    '\u202b',  # Right-to-Left Embedding
    '\u202c',  # Pop Directional Formatting
    '\u202d',  # Left-to-Right Override
    '\u202e',  # Right-to-Left Override
    '\u2060',  # Word Joiner
    '\u2061',  # Function Application
    '\u2062',  # Invisible Times
    '\u2063',  # Invisible Separator
    '\u2064',  # Invisible Plus
    '\ufeff',  # Byte Order Mark
    '\xad',    # Soft Hyphen
}

# 敏感文本模式
SENSITIVE_TEXT_PATTERNS: List[Pattern] = [
    # Bearer token
    re.compile(r'("?bearer"?\s*:?\s*"?[A-Za-z0-9_\-]{32,}")', re.IGNORECASE),
    # API keys
    re.compile(r'("?api_?(?:key|secret|token)?"?\s*:?\s*"?[A-Za-z0-9_\-]{16,}")', re.IGNORECASE),
    # Password
    re.compile(r'("?password"?:?\s*"?[^\s]{4,}")', re.IGNORECASE),
    # AWS keys
    re.compile(r'(AKIA[0-9A-Z]{16})'),
    re.compile(r'(ASIA[0-9A-Z]{16})'),
]

# 环境变量黑名单
ENV_BLOCKLIST: Set[str] = {
    'OPENAI_API_KEY',
    'ANTHROPIC_API_KEY',
    'API_KEY',
    'AWS_SECRET_ACCESS_KEY',
    'AWS_ACCESS_KEY_ID',
    'GITHUB_TOKEN',
    'GH_TOKEN',
    'PASSWORD',
    'SECRET',
    'TOKEN',
    'CREDENTIAL',
    'KEY',
}

# 清理后的占位符
REDACTED = "[REDACTED]"


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    is_safe: bool
    threats: List[str]
    sanitized_text: Optional[str] = None


class SecurityGuard:
    """安全防护"""
    
    def __init__(self):
        pass
    
    def scan_text_for_threats(self, text: str) -> SecurityCheckResult:
        """扫描文本威胁"""
        threats = []
        
        # 检查不可见字符
        for char in INVISIBLE_CHARS:
            if char in text:
                threats.append(f"invisible_character_{hex(ord(char))}")
        
        # 检查模式
        for pattern, name in THREAT_PATTERNS:
            if pattern.search(text):
                threats.append(name)
        
        # 清理
        sanitized = text
        if threats:
            # 移除不可见字符
            for char in INVISIBLE_CHARS:
                sanitized = sanitized.replace(char, "")
        
        return SecurityCheckResult(
            is_safe=len(threats) == 0,
            threats=threats,
            sanitized_text=sanitized
        )
    
    def redact_sensitive_text(self, text: str) -> str:
        """清理敏感文本"""
        if not text:
            return text
        
        cleaned = text
        for pattern in SENSITIVE_TEXT_PATTERNS:
            cleaned = pattern.sub(f'"{REDACTED}"', cleaned)
        
        return cleaned
    
    def is_env_var_blocked(self, var_name: str) -> bool:
        """检查环境变量是否被阻止"""
        var_name = var_name.upper()
        for blocked in ENV_BLOCKLIST:
            if blocked in var_name:
                return True
        return False
    
    def filter_env_vars(self, env_dict: Dict[str, str]) -> Dict[str, str]:
        """过滤环境变量"""
        return {
            k: v for k, v in env_dict.items()
            if not self.is_env_var_blocked(k)
        }
    
    def validate_memory_write(self, content: str) -> SecurityCheckResult:
        """验证记忆写入"""
        check = self.scan_text_for_threats(content)
        
        if check.is_safe:
            # 清理敏感信息
            sanitized = self.redact_sensitive_text(content)
            return SecurityCheckResult(
                is_safe=True,
                threats=[],
                sanitized_text=sanitized
            )
        else:
            return check
    
    def validate_tool_args(self, tool_name: str, args_dict: Dict[str, Any]) -> SecurityCheckResult:
        """验证工具参数"""
        # 序列化
        args_str = str(args_dict)
        
        check = self.scan_text_for_threats(args_str)
        
        if not check.is_safe:
            return check
        
        # 清理敏感信息
        sanitized_str = self.redact_sensitive_text(args_str)
        
        return SecurityCheckResult(
            is_safe=True,
            threats=[],
            sanitized_text=sanitized_str
        )


# 全局防护
_guard: Optional[SecurityGuard] = None


def get_security_guard() -> SecurityGuard:
    """获取安全防护"""
    global _guard
    if _guard is None:
        _guard = SecurityGuard()
    return _guard


def sanitize_text(text: str) -> str:
    """清理文本"""
    guard = get_security_guard()
    result = guard.scan_text_for_threats(text)
    return result.sanitized_text or text


def redact_sensitive(text: str) -> str:
    """清理敏感"""
    guard = get_security_guard()
    return guard.redact_sensitive_text(text)


def scan_for_threats(text: str) -> List[str]:
    """扫描威胁"""
    guard = get_security_guard()
    result = guard.scan_text_for_threats(text)
    return result.threats
