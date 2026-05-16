"""
心跳机制 - 定期后台任务执行

OpenClaw风格的心跳任务：
- 定期检查 HEARTBEAT.md
- 执行待处理的后台任务
- 更新心跳状态
- 维护记忆
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 默认心跳状态文件
DEFAULT_HEARTBEAT_STATE = Path("./data/heartbeat-state.json")
DEFAULT_WORKSPACE = Path("./workspace/openhands-workspace")


@dataclass
class HeartbeatState:
    """心跳状态"""
    last_heartbeat: Optional[str] = None
    consecutive_failures: int = 0
    tasks_completed: int = 0
    tasks_pending: List[str] = None
    
    def __post_init__(self):
        if self.tasks_pending is None:
            self.tasks_pending = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HeartbeatState':
        return cls(**data)


class HeartbeatManager:
    """心跳管理器"""
    
    def __init__(
        self,
        workspace: Path = None,
        state_file: Path = None,
        interval_seconds: int = 300  # 5分钟
    ):
        self._workspace = workspace or DEFAULT_WORKSPACE
        self._state_file = state_file or DEFAULT_HEARTBEAT_STATE
        self._interval = interval_seconds
        self._state: Optional[HeartbeatState] = None
        self._running = False
        self._task = None
    
    def load_state(self) -> HeartbeatState:
        """加载心跳状态"""
        if self._state is not None:
            return self._state
        
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._state = HeartbeatState.from_dict(data)
            else:
                self._state = HeartbeatState()
        except Exception as e:
            logger.warning(f"Failed to load heartbeat state: {e}")
            self._state = HeartbeatState()
        
        return self._state
    
    def save_state(self):
        """保存心跳状态"""
        if self._state is None:
            return
        
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(self._state.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save heartbeat state: {e}")
    
    def read_heartbeat_tasks(self) -> List[str]:
        """读取心跳任务"""
        heartbeat_file = self._workspace / "HEARTBEAT.md"
        
        if not heartbeat_file.exists():
            return []
        
        try:
            content = heartbeat_file.read_text()
            # 解析任务（简化版：提取非注释行）
            tasks = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    if line.startswith('- [ ]') or line.startswith('- [x]'):
                        tasks.append(line)
            return tasks
        except Exception as e:
            logger.warning(f"Failed to read heartbeat tasks: {e}")
            return []
    
    def should_run(self) -> bool:
        """检查是否应该运行"""
        state = self.load_state()
        
        if not self.read_heartbeat_tasks():
            return False
        
        if state.last_heartbeat is None:
            return True
        
        last = datetime.fromisoformat(state.last_heartbeat)
        elapsed = datetime.now() - last
        
        return elapsed >= timedelta(seconds=self._interval)
    
    async def run_heartbeat(self, agent) -> Dict[str, Any]:
        """执行心跳"""
        state = self.load_state()
        state.last_heartbeat = datetime.now().isoformat()
        
        tasks = self.read_heartbeat_tasks()
        
        if not tasks:
            return {'status': 'skipped', 'reason': 'no_tasks'}
        
        logger.info(f"Running heartbeat with {len(tasks)} tasks")
        
        results = {
            'status': 'completed',
            'tasks_found': len(tasks),
            'tasks_executed': 0,
            'errors': []
        }
        
        # 执行每个任务
        for task in tasks:
            try:
                # 这里应该调用agent执行任务
                # 简化版：仅记录
                if task.startswith('- [ ]'):
                    results['tasks_executed'] += 1
            except Exception as e:
                results['errors'].append(str(e))
                state.consecutive_failures += 1
        
        if not results['errors']:
            state.consecutive_failures = 0
            state.tasks_completed += results['tasks_executed']
        
        self.save_state()
        return results
    
    async def start(self, agent):
        """启动心跳循环"""
        if self._running:
            return
        
        self._running = True
        logger.info("Heartbeat manager started")
        
        while self._running:
            try:
                if self.should_run():
                    await self.run_heartbeat(agent)
                
                await asyncio.sleep(self._interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """停止心跳"""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Heartbeat manager stopped")


# 全局心跳管理器
_heartbeat_manager: Optional[HeartbeatManager] = None


def get_heartbeat_manager(
    workspace: Path = None,
    state_file: Path = None
) -> HeartbeatManager:
    """获取心跳管理器"""
    global _heartbeat_manager
    if _heartbeat_manager is None:
        _heartbeat_manager = HeartbeatManager(workspace, state_file)
    return _heartbeat_manager
