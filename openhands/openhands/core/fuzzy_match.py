"""
Fuzzy Match - 模糊匹配算法
参考 Hermes Agent 的九策略匹配链
"""

from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass
import re
import unicodedata
import logging

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """匹配结果"""
    matched: bool
    new_content: str
    match_count: int
    strategy_used: Optional[str] = None
    error: Optional[str] = None


class FuzzyMatcher:
    """
    模糊匹配器 - 九策略匹配链
    
    策略优先级:
    1. exact - 精确匹配
    2. line_trimmed - 逐行去除首尾空白
    3. whitespace_normalized - 空白归一化
    4. indentation_flexible - 忽略缩进
    5. escape_normalized - 转义序列还原
    6. trimmed_boundary - 首尾行修剪
    7. unicode_normalized - Unicode 归一化
    8. block_anchor - 块锚点匹配
    9. context_aware - 上下文感知（50%相似度）
    """
    
    def __init__(self, similarity_threshold: float = 0.5):
        self.similarity_threshold = similarity_threshold
        self.strategies = [
            ("exact", self._strategy_exact),
            ("line_trimmed", self._strategy_line_trimmed),
            ("whitespace_normalized", self._strategy_whitespace_normalized),
            ("indentation_flexible", self._strategy_indentation_flexible),
            ("escape_normalized", self._strategy_escape_normalized),
            ("trimmed_boundary", self._strategy_trimmed_boundary),
            ("unicode_normalized", self._strategy_unicode_normalized),
            ("block_anchor", self._strategy_block_anchor),
            ("context_aware", self._strategy_context_aware),
        ]
    
    def find_and_replace(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> MatchResult:
        """查找并替换"""
        for strategy_name, strategy in self.strategies:
            try:
                result = strategy(content, old_string, new_string, replace_all)
                if result.matched:
                    result.strategy_used = strategy_name
                    return result
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
                continue
        
        return MatchResult(
            matched=False,
            new_content=content,
            match_count=0,
            error="No matching strategy found",
        )
    
    def _strategy_exact(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略1: 精确匹配"""
        if old_string not in content:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        if replace_all:
            count = content.count(old_string)
            new_content = content.replace(old_string, new_string)
        else:
            count = 1
            new_content = content.replace(old_string, new_string, 1)
        
        return MatchResult(matched=True, new_content=new_content, match_count=count)
    
    def _strategy_line_trimmed(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略2: 逐行去除首尾空白"""
        content_lines = content.split('\n')
        old_lines = old_string.split('\n')
        new_lines = new_string.split('\n')
        
        trimmed_content = '\n'.join(line.strip() for line in content_lines)
        trimmed_old = '\n'.join(line.strip() for line in old_lines)
        
        if trimmed_old not in trimmed_content:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        # 找到匹配位置并映射回原始内容
        start_idx = trimmed_content.find(trimmed_old)
        if start_idx == -1:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        # 简化处理：直接在原始内容中查找相似块
        return self._replace_by_line_count(content, old_lines, new_lines, replace_all)
    
    def _replace_by_line_count(
        self,
        content: str,
        old_lines: List[str],
        new_lines: List[str],
        replace_all: bool,
    ) -> MatchResult:
        """按行数替换"""
        content_lines = content.split('\n')
        old_line_count = len(old_lines)
        
        matches = []
        for i in range(len(content_lines) - old_line_count + 1):
            chunk = content_lines[i:i + old_line_count]
            if self._lines_similar(chunk, old_lines):
                matches.append(i)
        
        if not matches:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        if not replace_all:
            matches = matches[:1]
        
        result_lines = content_lines.copy()
        for i in reversed(matches):
            result_lines[i:i + old_line_count] = new_lines
        
        return MatchResult(
            matched=True,
            new_content='\n'.join(result_lines),
            match_count=len(matches),
        )
    
    def _lines_similar(self, lines1: List[str], lines2: List[str]) -> bool:
        """判断两组行是否相似"""
        if len(lines1) != len(lines2):
            return False
        
        for l1, l2 in zip(lines1, lines2):
            if l1.strip() != l2.strip():
                return False
        
        return True
    
    def _strategy_whitespace_normalized(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略3: 空白归一化"""
        def normalize_ws(s: str) -> str:
            return re.sub(r'\s+', ' ', s)
        
        normalized_content = normalize_ws(content)
        normalized_old = normalize_ws(old_string)
        
        if normalized_old not in normalized_content:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        # 使用正则表达式在原始内容中查找
        pattern = re.escape(old_string)
        pattern = re.sub(r'\\s\+', r'\\s\+', pattern)
        
        try:
            regex = re.compile(pattern, re.DOTALL)
            matches = list(regex.finditer(content))
            if not matches:
                return MatchResult(matched=False, new_content=content, match_count=0)
            
            if replace_all:
                new_content = regex.sub(new_string, content)
                return MatchResult(matched=True, new_content=new_content, match_count=len(matches))
            else:
                new_content = regex.sub(new_string, content, count=1)
                return MatchResult(matched=True, new_content=new_content, match_count=1)
        except re.error:
            return MatchResult(matched=False, new_content=content, match_count=0)
    
    def _strategy_indentation_flexible(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略4: 忽略缩进"""
        def strip_indent(s: str) -> str:
            lines = s.split('\n')
            return '\n'.join(line.lstrip() for line in lines)
        
        stripped_content = strip_indent(content)
        stripped_old = strip_indent(old_string)
        
        if stripped_old not in stripped_content:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        # 找到匹配并尝试替换
        content_lines = content.split('\n')
        old_lines = old_string.split('\n')
        new_lines = new_string.split('\n')
        
        for i in range(len(content_lines) - len(old_lines) + 1):
            chunk = content_lines[i:i + len(old_lines)]
            if strip_indent('\n'.join(chunk)) == stripped_old:
                result_lines = content_lines[:i] + new_lines + content_lines[i + len(old_lines):]
                return MatchResult(
                    matched=True,
                    new_content='\n'.join(result_lines),
                    match_count=1,
                )
        
        return MatchResult(matched=False, new_content=content, match_count=0)
    
    def _strategy_escape_normalized(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略5: 转义序列还原"""
        def normalize_escapes(s: str) -> str:
            s = s.replace("\\'", "'")
            s = s.replace('\\"', '"')
            s = s.replace('\\\\', '\\')
            return s
        
        normalized_content = normalize_escapes(content)
        normalized_old = normalize_escapes(old_string)
        normalized_new = normalize_escapes(new_string)
        
        if normalized_old not in normalized_content:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        count = normalized_content.count(normalized_old)
        if replace_all:
            new_content = normalized_content.replace(normalized_old, normalized_new)
        else:
            new_content = normalized_content.replace(normalized_old, normalized_new, 1)
            count = 1
        
        return MatchResult(matched=True, new_content=new_content, match_count=count)
    
    def _strategy_trimmed_boundary(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略6: 首尾行修剪"""
        old_lines = old_string.strip().split('\n')
        content_lines = content.split('\n')
        
        for i in range(len(content_lines) - len(old_lines) + 1):
            chunk = '\n'.join(content_lines[i:i + len(old_lines)]).strip()
            if chunk == old_string.strip():
                result_lines = content_lines[:i] + new_string.split('\n') + content_lines[i + len(old_lines):]
                return MatchResult(
                    matched=True,
                    new_content='\n'.join(result_lines),
                    match_count=1,
                )
        
        return MatchResult(matched=False, new_content=content, match_count=0)
    
    def _strategy_unicode_normalized(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略7: Unicode 归一化"""
        def normalize_unicode(s: str) -> str:
            # 智能引号 → 直引号
            s = s.replace('"', '"').replace('"', '"')
            s = s.replace(''', "'").replace(''', "'")
            # 破折号 → 双横线
            s = s.replace('—', '--').replace('–', '-')
            # 省略号 → 三点
            s = s.replace('…', '...')
            # 不换行空格 → 普通空格
            s = s.replace('\u00a0', ' ')
            # Unicode 归一化
            s = unicodedata.normalize('NFKC', s)
            return s
        
        normalized_content = normalize_unicode(content)
        normalized_old = normalize_unicode(old_string)
        
        if normalized_old not in normalized_content:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        # 找到匹配位置
        start = normalized_content.find(normalized_old)
        if start == -1:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        # 尝试在原始内容中找到对应位置
        # 简化处理：直接使用归一化后的内容
        count = normalized_content.count(normalized_old)
        if replace_all:
            new_content = normalized_content.replace(normalized_old, new_string)
        else:
            new_content = normalized_content.replace(normalized_old, new_string, 1)
            count = 1
        
        return MatchResult(matched=True, new_content=new_content, match_count=count)
    
    def _strategy_block_anchor(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略8: 块锚点匹配"""
        # 提取首行和尾行作为锚点
        old_lines = old_string.split('\n')
        if len(old_lines) < 2:
            return MatchResult(matched=False, new_content=content, match_count=0)
        
        first_anchor = old_lines[0].strip()
        last_anchor = old_lines[-1].strip()
        
        content_lines = content.split('\n')
        
        for i in range(len(content_lines) - len(old_lines) + 1):
            if content_lines[i].strip() == first_anchor:
                for j in range(i + len(old_lines) - 1, min(i + len(old_lines) * 2, len(content_lines))):
                    if content_lines[j].strip() == last_anchor:
                        # 找到可能的块
                        block = '\n'.join(content_lines[i:j+1])
                        if self._similarity(block, old_string) >= self.similarity_threshold:
                            result_lines = content_lines[:i] + new_string.split('\n') + content_lines[j+1:]
                            return MatchResult(
                                matched=True,
                                new_content='\n'.join(result_lines),
                                match_count=1,
                            )
        
        return MatchResult(matched=False, new_content=content, match_count=0)
    
    def _strategy_context_aware(
        self,
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> MatchResult:
        """策略9: 上下文感知"""
        # 使用滑动窗口找到最相似的块
        old_len = len(old_string)
        content_len = len(content)
        
        best_match_start = -1
        best_similarity = 0.0
        
        window_size = old_len
        step = max(1, old_len // 10)
        
        for start in range(0, content_len - window_size + 1, step):
            chunk = content[start:start + window_size]
            similarity = self._similarity(chunk, old_string)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_start = start
        
        if best_similarity >= self.similarity_threshold and best_match_start >= 0:
            new_content = content[:best_match_start] + new_string + content[best_match_start + old_len:]
            return MatchResult(
                matched=True,
                new_content=new_content,
                match_count=1,
            )
        
        return MatchResult(matched=False, new_content=content, match_count=0)
    
    def _similarity(self, s1: str, s2: str) -> float:
        """计算字符串相似度 (Jaccard)"""
        if not s1 or not s2:
            return 0.0
        
        # 使用字符集合的 Jaccard 相似度
        set1 = set(s1)
        set2 = set(s2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union


fuzzy_matcher = FuzzyMatcher()


def fuzzy_find_and_replace(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> Tuple[str, int, Optional[str], Optional[str]]:
    """
    模糊查找并替换
    
    返回: (new_content, match_count, strategy_used, error)
    """
    result = fuzzy_matcher.find_and_replace(content, old_string, new_string, replace_all)
    return result.new_content, result.match_count, result.strategy_used, result.error
