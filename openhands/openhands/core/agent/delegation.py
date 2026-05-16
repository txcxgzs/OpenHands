"""
子代理委托系统

Hermes风格的子代理架构：
- 隔离上下文的子代理
- 独立的工具集
- 父代理阻塞等待子代理完成
- 支持单任务和批处理模式
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


@dataclass
class DelegationConfig:
    """委托配置"""
    max_concurrent: int = 3
    timeout_seconds: float = 300.0
    auto_approve: bool = False
    blocked_tools: frozenset = None
    
    def __post_init__(self):
        if self.blocked_tools is None:
            self.blocked_tools = frozenset([
                "delegate_task",  # 禁止递归委托
                "clarify",  # 禁止用户交互
                "memory_add",  # 禁止写入共享记忆
                "send_message",  # 禁止跨平台副作用
            ])


class DelegationResult:
    """委托任务结果"""
    def __init__(self, task_id: str, success: bool, result: str = "", error: str = ""):
        self.task_id = task_id
        self.success = success
        self.result = result
        self.error = error


class SubAgent:
    """子代理实例"""
    
    def __init__(
        self,
        task_id: str,
        goal: str,
        context: str = "",
        tools: List[str] = None,
        config: DelegationConfig = None
    ):
        self.task_id = task_id
        self.goal = goal
        self.context = context
        self.tools = tools or []
        self.config = config or DelegationConfig()
        
        self._future = None
        self._executor = None
    
    async def run(self, agent) -> DelegationResult:
        """运行子代理"""
        logger.info(f"启动子代理 {self.task_id}: {self.goal[:100]}...")
        
        try:
            # 构建子代理的系统提示词
            system_prompt = self._build_subagent_prompt()
            
            # 在线程池中运行（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            
            def run_sync():
                return agent.run_conversation(
                    user_message=f"任务：{self.goal}\n\n上下文：{self.context}",
                    system_message=system_prompt
                )
            
            self._future = loop.run_in_executor(
                None,
                run_sync
            )
            
            try:
                result = await asyncio.wait_for(
                    self._future,
                    timeout=self.config.timeout_seconds
                )
                
                # 提取结果
                final_response = result.get('final_response', '') if isinstance(result, dict) else str(result)
                
                logger.info(f"子代理 {self.task_id} 完成")
                return DelegationResult(
                    task_id=self.task_id,
                    success=True,
                    result=final_response
                )
            except asyncio.TimeoutError:
                logger.warning(f"子代理 {self.task_id} 超时")
                return DelegationResult(
                    task_id=self.task_id,
                    success=False,
                    error=f"任务超时（{self.config.timeout_seconds}秒）"
                )
                
        except Exception as e:
            logger.error(f"子代理 {self.task_id} 失败: {e}")
            return DelegationResult(
                task_id=self.task_id,
                success=False,
                error=str(e)
            )
    
    def _build_subagent_prompt(self) -> str:
        """构建子代理系统提示词"""
        return f"""你是一个专注的子代理，负责完成以下任务。

## 你的任务
{self.goal}

## 上下文
{self.context}

## 规则
1. 专注完成任务，不要偏离目标
2. 使用提供的工具完成工作
3. 返回简洁的结果总结
4. 不要询问用户，直接执行
5. 遇到无法解决的问题时，记录错误并返回

## 可用工具
{', '.join(self.tools) if self.tools else '所有标准工具'}

开始执行任务。"""


class DelegationManager:
    """委托管理器"""
    
    def __init__(self, agent):
        self.agent = agent
        self.config = DelegationConfig()
        self._active_subagents: Dict[str, SubAgent] = {}
        self._completed_results: Dict[str, DelegationResult] = {}
    
    async def delegate_task(
        self,
        goal: str,
        context: str = "",
        tools: List[str] = None,
        task_id: str = None
    ) -> DelegationResult:
        """委托单个任务给子代理"""
        task_id = task_id or f"subagent-{uuid.uuid4().hex[:8]}"
        
        # 过滤被阻止的工具
        available_tools = self._filter_blocked_tools(tools)
        
        # 创建子代理
        subagent = SubAgent(
            task_id=task_id,
            goal=goal,
            context=context,
            tools=available_tools,
            config=self.config
        )
        
        self._active_subagents[task_id] = subagent
        
        try:
            result = await subagent.run(self.agent)
            self._completed_results[task_id] = result
            return result
        finally:
            if task_id in self._active_subagents:
                del self._active_subagents[task_id]
    
    async def delegate_batch(
        self,
        tasks: List[Dict[str, str]],
        parallel: bool = True
    ) -> List[DelegationResult]:
        """批量委托任务
        
        Args:
            tasks: [{"goal": "...", "context": "...", "task_id": "..."}]
            parallel: 是否并行执行
        """
        if not parallel:
            # 顺序执行
            results = []
            for task in tasks:
                result = await self.delegate_task(
                    goal=task.get('goal', ''),
                    context=task.get('context', ''),
                    task_id=task.get('task_id')
                )
                results.append(result)
            return results
        
        # 并行执行
        coroutines = []
        for task in tasks:
            coro = self.delegate_task(
                goal=task.get('goal', ''),
                context=task.get('context', ''),
                task_id=task.get('task_id')
            )
            coroutines.append(coro)
        
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(DelegationResult(
                    task_id=tasks[i].get('task_id', f'task-{i}'),
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def _filter_blocked_tools(self, tools: List[str]) -> List[str]:
        """过滤被阻止的工具"""
        if not tools:
            return tools
        return [t for t in tools if t not in self.config.blocked_tools]
    
    def get_active_count(self) -> int:
        """获取活跃子代理数量"""
        return len(self._active_subagents)
    
    def get_result(self, task_id: str) -> Optional[DelegationResult]:
        """获取已完成任务的结果"""
        return self._completed_results.get(task_id)
    
    def cancel_all(self):
        """取消所有活跃子代理"""
        for task_id in list(self._active_subagents.keys()):
            logger.info(f"取消子代理 {task_id}")
            del self._active_subagents[task_id]


async def delegate_task_tool(
    goal: str,
    context: str = "",
    tools: List[str] = None,
    delegation_manager: DelegationManager = None
) -> str:
    """委托任务工具
    
    用于在智能体中调用子代理。
    
    Args:
        goal: 子代理的任务描述
        context: 额外的上下文信息
        tools: 子代理可用的工具列表（None表示所有工具）
        delegation_manager: 委托管理器实例
    
    Returns:
        委托结果的JSON字符串
    """
    if delegation_manager is None:
        return '{"error": "委托管理器未初始化"}'
    
    try:
        result = await delegation_manager.delegate_task(
            goal=goal,
            context=context,
            tools=tools
        )
        
        import json
        return json.dumps({
            'task_id': result.task_id,
            'success': result.success,
            'result': result.result,
            'error': result.error
        }, ensure_ascii=False)
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'
