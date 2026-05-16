"""
Skill System - 自进化技能系统
参考 Hermes Agent 的 Skill 自我学习机制
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import json
import yaml
import re
import logging
import shutil

logger = logging.getLogger(__name__)

SKILL_TEMPLATE = '''---
name: {name}
description: {description}
version: "1.0.0"
created: {created}
updated: {updated}
---

# {name}

## When to use
{when_to_use}

## Steps
{steps}

## Pitfalls
{pitfalls}

## Examples
{examples}
'''


@dataclass
class SkillMetadata:
    name: str
    description: str
    version: str = "1.0.0"
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    category: str = "general"
    tags: List[str] = field(default_factory=list)


@dataclass
class Skill:
    metadata: SkillMetadata
    content: str
    when_to_use: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    pitfalls: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    references: Dict[str, str] = field(default_factory=dict)
    templates: Dict[str, str] = field(default_factory=dict)
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    @property
    def description(self) -> str:
        return self.metadata.description


class SkillManager:
    """
    技能管理器 - 支持自动创建、自我修补
    参考 Hermes Agent 的 skill_manager_tool
    """
    
    MEMORY_LIMIT = 2200
    USER_MEMORY_LIMIT = 1375
    
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or Path.home() / ".openhands" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, Skill] = {}
        self._skill_index: Dict[str, Dict[str, str]] = {}
        self._load_skills()
    
    def _load_skills(self):
        for category_dir in self.skills_dir.iterdir():
            if category_dir.is_dir():
                for skill_dir in category_dir.iterdir():
                    if skill_dir.is_dir():
                        skill_file = skill_dir / "SKILL.md"
                        if skill_file.exists():
                            try:
                                skill = self._parse_skill_file(skill_file)
                                self._skills[skill.name] = skill
                                if category_dir.name not in self._skill_index:
                                    self._skill_index[category_dir.name] = {}
                                self._skill_index[category_dir.name][skill.name] = skill.metadata.description
                            except Exception as e:
                                logger.warning(f"Failed to load skill {skill_dir}: {e}")
    
    def _parse_skill_file(self, file_path: Path) -> Skill:
        content = file_path.read_text(encoding="utf-8")
        
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError(f"Invalid skill file format: {file_path}")
        
        frontmatter = yaml.safe_load(frontmatter_match.group(1))
        body = frontmatter_match.group(2)
        
        metadata = SkillMetadata(
            name=frontmatter.get("name", file_path.parent.name),
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "1.0.0"),
            created=datetime.fromisoformat(frontmatter["created"]) if "created" in frontmatter else datetime.now(),
            updated=datetime.fromisoformat(frontmatter["updated"]) if "updated" in frontmatter else datetime.now(),
            category=frontmatter.get("category", "general"),
            tags=frontmatter.get("tags", []),
        )
        
        when_to_use = self._extract_section(body, "When to use")
        steps = self._extract_section(body, "Steps")
        pitfalls = self._extract_section(body, "Pitfalls")
        examples = self._extract_section(body, "Examples")
        
        return Skill(
            metadata=metadata,
            content=body,
            when_to_use=when_to_use,
            steps=steps,
            pitfalls=pitfalls,
            examples=examples,
        )
    
    def _extract_section(self, content: str, section_name: str) -> List[str]:
        pattern = rf'## {section_name}\n(.*?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return []
        
        section = match.group(1).strip()
        items = []
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                items.append(line[2:])
            elif re.match(r'^\d+\.\s', line):
                items.append(re.sub(r'^\d+\.\s', '', line))
        return items
    
    def list_skills(self, category: Optional[str] = None) -> List[Skill]:
        if category:
            return [s for s in self._skills.values() if s.metadata.category == category]
        return list(self._skills.values())
    
    def get_skill_index(self) -> Dict[str, Dict[str, str]]:
        return self._skill_index.copy()
    
    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)
    
    def create_skill(
        self,
        name: str,
        description: str,
        when_to_use: List[str],
        steps: List[str],
        pitfalls: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        category: str = "general",
    ) -> Skill:
        category_dir = self.skills_dir / category
        skill_dir = category_dir / name.lower().replace(" ", "-").replace("_", "-")
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        now = datetime.now()
        metadata = SkillMetadata(
            name=name,
            description=description,
            created=now,
            updated=now,
            category=category,
        )
        
        content = SKILL_TEMPLATE.format(
            name=name,
            description=description,
            created=now.isoformat(),
            updated=now.isoformat(),
            when_to_use="\n".join(f"- {item}" for item in when_to_use),
            steps="\n".join(f"{i+1}. {step}" for i, step in enumerate(steps)),
            pitfalls="\n".join(f"- {p}" for p in (pitfalls or [])) or "None yet",
            examples="\n".join(f"- {e}" for e in (examples or [])) or "None yet",
        )
        
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content, encoding="utf-8")
        
        skill = Skill(
            metadata=metadata,
            content=content,
            when_to_use=when_to_use,
            steps=steps,
            pitfalls=pitfalls or [],
            examples=examples or [],
        )
        
        self._skills[name] = skill
        if category not in self._skill_index:
            self._skill_index[category] = {}
        self._skill_index[category][name] = description
        
        logger.info(f"Created skill: {name}")
        return skill
    
    def patch_skill(
        self,
        name: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> bool:
        skill = self._skills.get(name)
        if not skill:
            logger.error(f"Skill not found: {name}")
            return False
        
        skill_dir = self._find_skill_dir(name)
        if not skill_dir:
            return False
        
        skill_file = skill_dir / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
        
        if new_content == content:
            logger.warning(f"No match found for patch in {name}")
            return False
        
        new_content = re.sub(
            r'updated: ".*?"',
            f'updated: "{datetime.now().isoformat()}"',
            new_content,
        )
        
        backup_file = skill_file.with_suffix(".md.bak")
        shutil.copy(skill_file, backup_file)
        
        skill_file.write_text(new_content, encoding="utf-8")
        
        try:
            updated_skill = self._parse_skill_file(skill_file)
            self._skills[name] = updated_skill
            backup_file.unlink()
            logger.info(f"Patched skill: {name}")
            return True
        except Exception as e:
            shutil.copy(backup_file, skill_file)
            backup_file.unlink()
            logger.error(f"Patch failed, rolled back: {e}")
            return False
    
    def add_pitfall(self, name: str, pitfall: str) -> bool:
        skill = self._skills.get(name)
        if not skill:
            return False
        
        if pitfall in skill.pitfalls:
            return True
        
        skill_dir = self._find_skill_dir(name)
        if not skill_dir:
            return False
        
        skill_file = skill_dir / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        
        pitfalls_section = "\n## Pitfalls\n" + "\n".join(f"- {p}" for p in skill.pitfalls + [pitfall])
        
        pattern = r'\n## Pitfalls\n.*?(?=\n## |\Z)'
        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, pitfalls_section + "\n", content, flags=re.DOTALL)
        else:
            new_content = content.rstrip() + "\n" + pitfalls_section + "\n"
        
        new_content = re.sub(
            r'updated: ".*?"',
            f'updated: "{datetime.now().isoformat()}"',
            new_content,
        )
        
        skill_file.write_text(new_content, encoding="utf-8")
        skill.pitfalls.append(pitfall)
        skill.metadata.updated = datetime.now()
        
        logger.info(f"Added pitfall to {name}: {pitfall}")
        return True
    
    def add_step(self, name: str, step: str, position: Optional[int] = None) -> bool:
        skill = self._skills.get(name)
        if not skill:
            return False
        
        skill_dir = self._find_skill_dir(name)
        if not skill_dir:
            return False
        
        if position is None:
            position = len(skill.steps)
        else:
            position = max(0, min(position, len(skill.steps)))
        
        skill.steps.insert(position, step)
        
        skill_file = skill_dir / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        
        steps_section = "\n## Steps\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(skill.steps))
        
        pattern = r'\n## Steps\n.*?(?=\n## |\Z)'
        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, steps_section + "\n", content, flags=re.DOTALL)
        else:
            new_content = content.rstrip() + "\n" + steps_section + "\n"
        
        new_content = re.sub(
            r'updated: ".*?"',
            f'updated: "{datetime.now().isoformat()}"',
            new_content,
        )
        
        skill_file.write_text(new_content, encoding="utf-8")
        skill.metadata.updated = datetime.now()
        
        logger.info(f"Added step to {name} at position {position}")
        return True
    
    def _find_skill_dir(self, name: str) -> Optional[Path]:
        for category_dir in self.skills_dir.iterdir():
            if category_dir.is_dir():
                for skill_dir in category_dir.iterdir():
                    if skill_dir.is_dir():
                        if skill_dir.name.lower() == name.lower().replace(" ", "-").replace("_", "-"):
                            return skill_dir
        return None
    
    def delete_skill(self, name: str) -> bool:
        skill_dir = self._find_skill_dir(name)
        if not skill_dir:
            return False
        
        shutil.rmtree(skill_dir)
        
        if name in self._skills:
            del self._skills[name]
        
        for category, skills in self._skill_index.items():
            if name in skills:
                del skills[name]
        
        logger.info(f"Deleted skill: {name}")
        return True
    
    def should_create_skill(
        self,
        tool_call_count: int,
        had_errors: bool,
        user_corrected: bool,
        complexity_threshold: int = 5,
    ) -> bool:
        if tool_call_count < complexity_threshold:
            return False
        if had_errors or user_corrected:
            return True
        return tool_call_count >= complexity_threshold * 2


skill_manager = SkillManager()
