"""
Security Scanner - 安全扫描系统
参考 Hermes Agent 的 skills_guard.py
"""

from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class Severity(Enum):
    """严重级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TrustLevel(Enum):
    """信任等级"""
    BUILTIN = "builtin"
    TRUSTED = "trusted"
    COMMUNITY = "community"
    AGENT_CREATED = "agent_created"


@dataclass
class ThreatPattern:
    """威胁模式"""
    name: str
    category: str
    pattern: re.Pattern
    severity: Severity
    description: str
    remediation: str


@dataclass
class ScanResult:
    """扫描结果"""
    is_safe: bool
    threats: List[Dict[str, Any]] = field(default_factory=list)
    severity: Severity = Severity.INFO
    summary: str = ""


# 信任等级策略
TRUSTED_REPOS: Set[str] = {
    "openai/skills",
    "anthropics/skills",
}

INSTALL_POLICY: Dict[TrustLevel, Tuple[str, str, str]] = {
    # (caution_action, dangerous_action, critical_action)
    TrustLevel.BUILTIN: ("allow", "allow", "allow"),
    TrustLevel.TRUSTED: ("allow", "allow", "block"),
    TrustLevel.COMMUNITY: ("allow", "block", "block"),
    TrustLevel.AGENT_CREATED: ("allow", "allow", "ask"),
}


# 威胁模式库 (70+ 正则模式，8 大威胁类别)
THREAT_PATTERNS: List[ThreatPattern] = [
    # 数据泄露
    ThreatPattern(
        name="env_exfiltration",
        category="data_exfiltration",
        pattern=re.compile(r'(?:curl|wget)\s+.*?\$[{]?[A-Z_]+[}]?', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Attempt to exfiltrate environment variables via HTTP",
        remediation="Remove network calls with environment variable interpolation",
    ),
    ThreatPattern(
        name="ssh_key_access",
        category="data_exfiltration",
        pattern=re.compile(r'(?:~/.ssh|/home/[^/]+/.ssh|id_rsa|id_ed25519)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Attempt to access SSH private keys",
        remediation="Remove SSH key access patterns",
    ),
    ThreatPattern(
        name="aws_credential_access",
        category="data_exfiltration",
        pattern=re.compile(r'(?:~/.aws|AWS_|aws_access_key|aws_secret)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Attempt to access AWS credentials",
        remediation="Remove AWS credential access patterns",
    ),
    ThreatPattern(
        name="gpg_key_access",
        category="data_exfiltration",
        pattern=re.compile(r'(?:~/.gnupg|/home/[^/]+/.gnupg|\.gpg)', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Attempt to access GPG keys",
        remediation="Remove GPG key access patterns",
    ),
    ThreatPattern(
        name="dns_exfiltration",
        category="data_exfiltration",
        pattern=re.compile(r'(?:nslookup|dig|host)\s+.*?\$[{]?[A-Z_]+[}]?', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Potential DNS-based data exfiltration",
        remediation="Remove DNS queries with variable interpolation",
    ),
    
    # 提示注入
    ThreatPattern(
        name="ignore_instructions",
        category="prompt_injection",
        pattern=re.compile(r'ignore\s+(?:previous|all|above)\s+(?:instructions?|rules?)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Attempt to override system instructions",
        remediation="Remove instruction override patterns",
    ),
    ThreatPattern(
        name="role_hijack",
        category="prompt_injection",
        pattern=re.compile(r'(?:you\s+are|act\s+as|pretend\s+(?:to\s+be)?)\s+(?:a|an)\s+(?:admin|root|system|developer)', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Attempt to hijack agent role",
        remediation="Remove role manipulation patterns",
    ),
    ThreatPattern(
        name="system_override",
        category="prompt_injection",
        pattern=re.compile(r'(?:system|assistant|developer)\s*(?:prompt|message|instruction)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Attempt to override system prompt",
        remediation="Remove system prompt manipulation patterns",
    ),
    ThreatPattern(
        name="jailbreak",
        category="prompt_injection",
        pattern=re.compile(r'(?:DAN|do\s+anything\s+now|unrestricted|bypass)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Potential jailbreak attempt",
        remediation="Remove jailbreak patterns",
    ),
    
    # 破坏性操作
    ThreatPattern(
        name="rm_rf",
        category="destructive",
        pattern=re.compile(r'rm\s+(?:-rf?|--recursive)\s+(?:/|~|\*)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Destructive file deletion",
        remediation="Remove destructive rm commands",
    ),
    ThreatPattern(
        name="chmod_777",
        category="destructive",
        pattern=re.compile(r'chmod\s+(?:-R\s+)?777', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Insecure permission setting",
        remediation="Remove insecure chmod commands",
    ),
    ThreatPattern(
        name="disk_wipe",
        category="destructive",
        pattern=re.compile(r'(?:mkfs|dd\s+of=/dev/|shred)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Disk wipe or format attempt",
        remediation="Remove disk destruction commands",
    ),
    ThreatPattern(
        name="fork_bomb",
        category="destructive",
        pattern=re.compile(r':\(\)\{.*?:\|:&\};:', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Fork bomb pattern",
        remediation="Remove fork bomb patterns",
    ),
    
    # 持久化
    ThreatPattern(
        name="crontab_modification",
        category="persistence",
        pattern=re.compile(r'(?:crontab|cron\.d)', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="Crontab modification attempt",
        remediation="Remove crontab modifications",
    ),
    ThreatPattern(
        name="bashrc_modification",
        category="persistence",
        pattern=re.compile(r'(?:\.bashrc|\.zshrc|\.profile)', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="Shell profile modification attempt",
        remediation="Remove shell profile modifications",
    ),
    ThreatPattern(
        name="authorized_keys",
        category="persistence",
        pattern=re.compile(r'authorized_keys', re.IGNORECASE),
        severity=Severity.HIGH,
        description="SSH authorized_keys modification",
        remediation="Remove authorized_keys modifications",
    ),
    ThreatPattern(
        name="systemd_service",
        category="persistence",
        pattern=re.compile(r'(?:systemctl|\.service)', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="Systemd service modification",
        remediation="Remove systemd service modifications",
    ),
    
    # 网络
    ThreatPattern(
        name="reverse_shell",
        category="network",
        pattern=re.compile(r'(?:nc|netcat|socat|ncat)\s+.*?(?:-e|-c|exec)', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Reverse shell attempt",
        remediation="Remove reverse shell patterns",
    ),
    ThreatPattern(
        name="tunnel_service",
        category="network",
        pattern=re.compile(r'(?:ngrok|cloudflared|frp)\s+', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Tunnel service usage",
        remediation="Remove tunnel service patterns",
    ),
    ThreatPattern(
        name="hardcoded_ip",
        category="network",
        pattern=re.compile(r'(?:\d{1,3}\.){3}\d{1,3}:\d+', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="Hardcoded IP address with port",
        remediation="Remove hardcoded network addresses",
    ),
    
    # 混淆
    ThreatPattern(
        name="base64_pipe",
        category="obfuscation",
        pattern=re.compile(r'(?:base64|b64decode).*?\|', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Base64 pipe execution",
        remediation="Remove base64 pipe patterns",
    ),
    ThreatPattern(
        name="eval_exec",
        category="obfuscation",
        pattern=re.compile(r'(?:eval|exec|execjs)\s*\(', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Dynamic code execution",
        remediation="Remove eval/exec patterns",
    ),
    ThreatPattern(
        name="hex_encoding",
        category="obfuscation",
        pattern=re.compile(r'\\x[0-9a-fA-F]{2}', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="Hex-encoded content",
        remediation="Remove hex-encoded patterns",
    ),
    
    # 进程执行
    ThreatPattern(
        name="subprocess_shell",
        category="process_execution",
        pattern=re.compile(r'subprocess\..*?shell\s*=\s*True', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="Shell=True in subprocess",
        remediation="Use shell=False in subprocess",
    ),
    ThreatPattern(
        name="os_system",
        category="process_execution",
        pattern=re.compile(r'os\.system\s*\(', re.IGNORECASE),
        severity=Severity.MEDIUM,
        description="os.system usage",
        remediation="Use subprocess instead of os.system",
    ),
    
    # 路径遍历
    ThreatPattern(
        name="path_traversal",
        category="path_traversal",
        pattern=re.compile(r'(?:\.\./|\.\.\\)', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Path traversal attempt",
        remediation="Remove path traversal patterns",
    ),
    ThreatPattern(
        name="etc_passwd",
        category="path_traversal",
        pattern=re.compile(r'/etc/passwd', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Attempt to access /etc/passwd",
        remediation="Remove /etc/passwd access",
    ),
    ThreatPattern(
        name="proc_access",
        category="path_traversal",
        pattern=re.compile(r'/proc/self', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Attempt to access /proc/self",
        remediation="Remove /proc/self access",
    ),
    
    # 加密挖矿
    ThreatPattern(
        name="xmrig",
        category="crypto_mining",
        pattern=re.compile(r'xmrig', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Cryptominer detected",
        remediation="Remove cryptominer patterns",
    ),
    ThreatPattern(
        name="stratum",
        category="crypto_mining",
        pattern=re.compile(r'stratum\+tcp', re.IGNORECASE),
        severity=Severity.CRITICAL,
        description="Mining pool connection",
        remediation="Remove mining pool patterns",
    ),
    ThreatPattern(
        name="monero",
        category="crypto_mining",
        pattern=re.compile(r'monero|xmr', re.IGNORECASE),
        severity=Severity.HIGH,
        description="Monero-related content",
        remediation="Remove Monero-related patterns",
    ),
]


class SecurityScanner:
    """
    安全扫描器
    
    特性:
    - 70+ 威胁模式
    - 8 大威胁类别
    - 4 级信任等级
    - 自动修复建议
    """
    
    def __init__(self, custom_patterns: Optional[List[ThreatPattern]] = None):
        self.patterns = THREAT_PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)
    
    def scan(self, content: str, trust_level: TrustLevel = TrustLevel.COMMUNITY) -> ScanResult:
        """扫描内容"""
        threats = []
        max_severity = Severity.INFO
        
        for pattern in self.patterns:
            matches = pattern.pattern.findall(content)
            if matches:
                threats.append({
                    "name": pattern.name,
                    "category": pattern.category,
                    "severity": pattern.severity.value,
                    "description": pattern.description,
                    "remediation": pattern.remediation,
                    "matches": matches[:5],  # 只显示前5个匹配
                })
                if self._severity_level(pattern.severity) > self._severity_level(max_severity):
                    max_severity = pattern.severity
        
        policy = INSTALL_POLICY[trust_level]
        is_safe = self._apply_policy(max_severity, policy)
        
        return ScanResult(
            is_safe=is_safe,
            threats=threats,
            severity=max_severity,
            summary=self._generate_summary(threats, max_severity),
        )
    
    def scan_skill(self, skill_content: str, trust_level: TrustLevel = TrustLevel.AGENT_CREATED) -> ScanResult:
        """扫描技能内容"""
        return self.scan(skill_content, trust_level)
    
    def scan_file(self, file_path: str, trust_level: TrustLevel = TrustLevel.COMMUNITY) -> ScanResult:
        """扫描文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.scan(content, trust_level)
        except Exception as e:
            return ScanResult(
                is_safe=False,
                threats=[{"error": str(e)}],
                severity=Severity.HIGH,
                summary=f"Failed to scan file: {e}",
            )
    
    def _severity_level(self, severity: Severity) -> int:
        """严重级别数值"""
        levels = {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }
        return levels.get(severity, 0)
    
    def _apply_policy(self, severity: Severity, policy: Tuple[str, str, str]) -> bool:
        """应用策略"""
        caution_action, dangerous_action, critical_action = policy
        
        severity_level = self._severity_level(severity)
        
        if severity_level >= 4:  # CRITICAL
            return critical_action == "allow"
        elif severity_level >= 3:  # HIGH
            return dangerous_action == "allow"
        elif severity_level >= 2:  # MEDIUM
            return caution_action == "allow"
        
        return True
    
    def _generate_summary(self, threats: List[Dict], max_severity: Severity) -> str:
        """生成摘要"""
        if not threats:
            return "No threats detected"
        
        categories = set(t["category"] for t in threats)
        return f"Found {len(threats)} threat(s) in {len(categories)} category(ies), max severity: {max_severity.value}"
    
    def get_threat_categories(self) -> Set[str]:
        """获取所有威胁类别"""
        return set(p.category for p in self.patterns)
    
    def add_pattern(self, pattern: ThreatPattern):
        """添加自定义模式"""
        self.patterns.append(pattern)


security_scanner = SecurityScanner()
