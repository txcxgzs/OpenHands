# Hermes Agent 深度分析报告

> **"The agent that grows with you"** — 第一个真正会自学的开源 AI Agent

---

## 1. Hermes Agent 的"牛逼"之处

Hermes Agent 由 Nous Research 开发，上线不到半年，GitHub 星标突破 10 万，OpenRouter 排行榜 Coding Agents 类目第一、Productivity 类目第二。它不是"另一个 OpenClaw"，而是一种完全不同的东西。

### 1.1 一句话定义差异

| | 定位 |
|---|---|
| **OpenClaw** | *"你写多少它会多少，你不写它就不会。"* |
| **Hermes Agent** | *"它干完活之后，会自己把踩坑经验提炼成可复用的技能。用得越久，能力越强。"* |

这不是功能差异，是**设计哲学的分野**——一个靠人喂，一个自己长。

### 1.2 六大核心优势

#### ① 唯一内置学习循环的 Agent

Hermes 是目前唯一一个内置封闭学习循环的开源 Agent。它不是"记住你说过的话"，而是"从解决问题的过程中自动提炼方法论，封装为可复用的 Skill"。每次对话结束后，Agent 会评估这次解决问题的过程，决定要不要把工作流程提炼成一个新的 Skill。

**Slogan 的真正含义**：`the agent that grows with you` 不是指它记住了你的偏好，而是指它的**能力本身在增长**。

#### ② 越用越懂你的记忆系统

Memory 系统通过 FTS5 全文搜索 + LLM 摘要实现跨会话检索，集成 Honcho 方言用户建模，能够深度构建用户画像。它知道你喜欢喝美式、你的代码风格、你的项目约定——而且这些知识会跨会话持久化。

#### ③ 200+ 模型随时切换，零锁定

支持 Nous Portal、OpenRouter（200+ 模型）、NVIDIA NIM、Xiaomi MiMo、Kimi/Moonshot、MiniMax、Hugging Face、OpenAI 等。一个命令即可切换，无需改代码。对比 OpenClaw 主要支持阿里云千问和少数国际模型。

#### ④ 极简部署，$5 VPS 即可运行

一行脚本安装，支持 Linux、macOS、WSL2、Android Termux。内置 6 种终端后端（本地、Docker、SSH、Daytona、Singularity、Modal）。Daytona 和 Modal 支持无服务器休眠——空闲时几乎零成本。

#### ⑤ 研究级能力

内置批量轨迹生成、Atropos RL 环境、轨迹压缩工具，可用于训练下一代工具调用模型。这是 OpenClaw 完全没有的能力——Hermes 不仅是工具，更是研究平台。

#### ⑥ 真正的移动端体验

支持 Android Termux 安装运行，语音备忘录转录，跨平台会话连续性。你可以在 Telegram 上和它聊天，同时它在云端 VM 上干活。

---

## 2. 自进化机制深度解析

Hermes Agent 的自进化能力建立在三个相互协作的子系统之上，共同构成一个**"经验 → 抽象 → 持久化 → 复用"**的闭环。

### 2.1 三子系统架构

| 子系统 | 角色定位 | 类比 |
|--------|---------|------|
| **Memory（记忆）** | 声明性记忆——"我知道什么" | 助理随身带的小本子，记着"老板喜欢喝美式" |
| **Skill（技能）** | 程序性记忆——"我会做什么" | 助理积累的操作手册——"部署 K8s 第 2 步一定要先推镜像" |
| **Nudge Engine（提醒引擎）** | 进化引擎——"该学习了" | 定时响的闹钟，提醒助理回头想想有没有什么值得记的 |

> 打个比方：Memory 是助理随身带的小本子，记着"老板喜欢喝美式"这些事实；Skill 是助理积累的操作手册——"部署 K8s 第 2 步一定要先推镜像"；Nudge Engine 是定时响的闹钟，提醒助理回头想想有没有什么值得记的。

---

### 2.2 Memory 系统：越用越懂你

#### 定量化存储：富有约束即特性

Hermes 的 Memory 设计非常克制——只用两个纯文本文件，用 `§` 分隔条目：

```
~/.hermes/memories/
├── MEMORY.md   # Agent 的个人笔记（环境事实、项目约定、工具怪癖）
└── USER.md     # Agent 对用户的认知（偏好、沟通风格、工作习惯）
```

**字符上限故意设得很紧**：
- MEMORY 限 **2200 chars**
- USER 限 **1375 chars**

容量有限就迫使 Agent 挑重要的记，不重要的自然被挤掉。

**对比 OpenClaw**：它的 MEMORY.md 是纯追加模式，用几个月就膨胀成几万行的怪兽文件，找几个月前的一句话只能笨拙地通读全文。Hermes 的做法反过来：容量有限就倒逼 Agent 做信息压缩，过时的自然被挤掉，留下的都是高密度事实。

#### 超限处理：让模型自己做信息整理

Hermes 不会静默丢弃旧条目，也不会自动压缩——它选择让 `add` 直接失败，然后把当前所有条目返回给模型：

```python
# tools/memory_tool.py:248-259
if new_total > limit:
    current = self._char_count(target)
    return {
        "success": False,
        "error": (
            f"Memory at {current:,}/{limit:,} chars. "
            f"Adding this entry ({len(content)} chars) would exceed the limit. "
            f"Replace or remove existing entries first."
        ),
        "current_entries": entries,
        "usage": f"{current:,}/{limit:,}",
    }
```

错误信息里一句 `"Replace or remove existing entries first"` 就把模型引导到了 `replace` 和 `remove` 操作上。同时返回 `current_entries`，让模型能看到现有的所有条目，自己决定哪些过时了该删、哪些可以合并压缩。

**模型不是被动地执行淘汰规则，而是主动做信息整理——这本身就是一次"自我反思"。**

#### 冻结快照机制：省 Token 的精妙设计

每次会话启动时，Memory 加载后立刻捕获一份快照，之后系统提示词里用的都是这份快照：

```python
# tools/memory_tool.py:124-140
def load_from_disk(self):
    mem_dir = get_memory_dir()
    self.memory_entries = self._read_file(mem_dir / "MEMORY.md")
    self.user_entries = self._read_file(mem_dir / "USER.md")
    # 会话开始时冻结快照，之后不再变动
    self._system_prompt_snapshot = {
        "memory": self._render_block("memory", self.memory_entries),
        "user": self._render_block("user", self.user_entries),
    }
```

快照注入系统提示词后，Agent 还没看到用户消息就已经知道你的环境和偏好了。为什么"冻结"而不是实时更新？因为系统提示词会话内不变就可以**共享前缀缓存（Prefix Cache）**，省掉重复计费。新写入的内容只改磁盘，下一个会话才刷新进来。

#### 提示词引导：什么该记、什么不该记

系统提示词中的 `MEMORY_GUIDANCE`：

```python
# agent/prompt_builder.py:144-162
MEMORY_GUIDANCE = (
    "You have persistent memory across sessions. Save durable facts using the memory "
    "tool: user preferences, environment details, tool quirks, and stable conventions.\n"
    "Prioritize what reduces future user steering — the most valuable memory is one "
    "that prevents the user from having to correct or remind you again.\n"
    "Write memories as declarative facts, not instructions to yourself. "
    "'User prefers concise responses' ✓ — 'Always respond concisely' ✗. "
    "'Project uses pytest with xdist' ✓ — 'Run tests with pytest -n 4' ✗."
)
```

关键区别：
- ✓ `"User prefers concise responses"` — 偏好，可被上下文覆盖
- ✗ `"Always respond concisely"` — 死命令，限制灵活性

同时明确边界：`"If you've discovered a new way to do something, save it as a skill."` —— Memory 不存操作步骤，操作步骤归 Skill 管。

---

### 2.3 Skill 系统：把做过的事变成会做的事

#### Skill 长什么样

每个 Skill 是一个目录，核心是 SKILL.md 文件：

```
~/.hermes/skills/
├── devops/
│   └── flask-k8s-deploy/
│       ├── SKILL.md          # 主指令
│       ├── references/       # 参考文档
│       └── templates/        # 模板文件
└── software-development/
    └── fix-pytest-fixtures/
        └── SKILL.md
```

一个典型的 SKILL.md：

```yaml
---
name: flask-k8s-deploy
description: Deploy a Flask app to Kubernetes with health checks
version: 1.0.0
---
# Flask K8s Deployment

## When to use
- User wants to deploy a Flask/Python app to Kubernetes
- User mentions K8s, kubectl, or container deployment

## Steps
1. Create Dockerfile with gunicorn (not dev server)
2. Build and push image to registry BEFORE creating deployment
3. Write deployment.yaml with livenessProbe pointing to /health
4. Write service.yaml with correct port mapping
5. kubectl apply both files
6. Verify with kubectl get pods and kubectl logs

## Pitfalls
- MUST push image to registry before kubectl apply, otherwise ImagePullBackOff
- Flask 默认没有 /health 端点，需要手动添加
- Django 需要额外设置 ALLOWED_HOSTS 环境变量
- livenessProbe path 必须返回 200，不能用需要认证的路径
```

> **Pitfalls 这一节不是预先写好的，而是 Agent 踩坑后追加的**——这就是 Skill 层面的"self-improving"。

#### 什么时候创建 Skill：工具调用驱动

Agent 不需要用户说"帮我创建一个 Skill"。创建的门槛由 `skill_manage` 工具的 schema 明确定义：

```python
# tools/skill_manager_tool.py:681-701
SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "description": (
        "Manage skills (create, update, delete). Skills are your procedural "
        "memory — reusable approaches for recurring task types.\n\n"
        "Create when: complex task succeeded (5+ calls), errors overcome, "
        "user-corrected approach worked, non-trivial workflow discovered, "
        "or user asks you to remember a procedure.\n"
        "Update when: instructions stale/wrong, OS-specific failures, "
        "missing steps or pitfalls found during use. "
        "If you used a skill and hit issues not covered by it, "
        "patch it immediately with skill_manage(action='patch') "
        "— don't wait to be asked.\n\n"
        "After difficult/iterative tasks, offer to save as a skill. "
        "Skip for simple one-offs."
    ),
}
```

创建门槛：
- 工具调用超过 **5 次**才值得创建（简单任务不记）
- 踩过坑再修复的经验才有价值
- 用户纠正过的做法要铭记
- 非平凡的工作流被发现时主动提议保存

**对比 OpenClaw**：也有 Skill 系统，也是 SKILL.md + YAML frontmatter，但 Skill 要么是你手写的，要么是从社区装的。手写的成本高，懒得维护；社区装的不是针对你的环境。**Agent 本身不会从工作中学到任何东西**——干了一百次部署，第一百零一次犯的错跟第一次一模一样。

#### Skill 的自我修补：踩坑当场就补

当 Agent 按照已有 Skill 执行，但中途发现步骤有遗漏或踩了新坑时，它会在完成任务后回头做精确的局部 patch：

```python
# tools/skill_manager_tool.py:397-485
def _patch_skill(name, old_string, new_string, file_path=None, replace_all=False):
    """Targeted find-and-replace within a skill file."""
    from tools.fuzzy_match import fuzzy_find_and_replace
    new_content, match_count, _, match_error = fuzzy_find_and_replace(
        content, old_string, new_string, replace_all
    )
    if match_error:
        return {"success": False, "error": match_error}

    # 修改前备份原内容
    original_content = content
    _atomic_write_text(target, new_content)

    # 修改后重新做安全扫描
    scan_error = _security_scan_skill(skill_dir)
    if scan_error:
        _atomic_write_text(target, original_content)  # 不通过就回滚
        return {"success": False, "error": scan_error}
```

关键设计：
- **模糊匹配**（fuzzy_find_and_replace）：Agent 给出的 old_string 可能跟原文有格式差异
- **安全扫描**：每次修改后跑 `_security_scan_skill()`，不通过自动回滚
- **当场修补**：Agent 在踩完坑的当场就把 Pitfalls 补上了，下次遇到同样的场景直接绕过去

系统提示词里还有一句 `"Skills that aren't maintained become liabilities"`——通过提示词给 Agent 灌输责任感，防止它只管创建不管维护。

#### 渐进式加载：动态图书馆

OpenClaw 采用"重型背包"模式，每次会话把 SOUL.md、IDENTITY.md 和各种设定一股脑塞进上下文，设定越多背包越沉，Token 浪费严重，模型注意力也被稀释。

Hermes 更像一座"动态图书馆"，默认上下文极其轻量，只放一个轻量索引——每个 Skill 的名字和一句话描述：

```
Available skills:
  devops:
    - flask-k8s-deploy: Deploy a Flask app to Kubernetes with health checks
    - nginx-reverse-proxy: Configure Nginx reverse proxy with SSL
  software-development:
    - fix-pytest-fixtures: Debug and fix pytest fixture scope issues
```

Agent 判断某个 Skill 跟当前任务相关时，才通过 `skill_view` 加载完整内容。

**三级加载策略**：
1. **元数据**（skills_list）→ 每个技能的名字和描述
2. **主文档**（skill_view）→ Agent 判断相关后按需加载
3. **附属文件**（references/templates）→ 进一步按需加载

"先看目录再翻全文"，在功能完整性与 Token 效率之间取得平衡。

---

### 2.4 Nudge Engine：谁来提醒 Agent "该学习了"

Memory 和 Skill 都是存储系统，写入需要有人触发。Nudge Engine 就是这个触发器。

#### 两个计数器，两种粒度

```python
# run_agent.py:1328-1331 — Memory 计数器
self._memory_nudge_interval = 10   # 每 10 个用户回合触发一次
self._turns_since_memory = 0

# run_agent.py:1428-1431 — Skill 计数器（从配置读取，默认 10）
self._skill_nudge_interval = int(skills_config.get("creation_nudge_interval", 10))
self._iters_since_skill = 0
```

粒度不同是有道理的：
- **Memory 计数器**：信息来自用户输入，按**回合**计
- **Skill 计数器**：经验来自工具使用过程，按**迭代**计

计数器到阈值就触发审查，Agent 主动调用了 `memory` 或 `skill_manage` 则重置——已经在做了就不用催。

#### 后台 Fork Agent：不打扰用户的静默审查

Nudge 触发后不会在主对话中插一条"让我想想有没有什么该记的"——那样太打扰用户了。而是在后台 fork 一个独立的 Agent 实例：

```python
# run_agent.py:2665-2711
def _spawn_background_review(self, messages_snapshot, review_memory=False, review_skills=False):
    def _run_review():
        with open(os.devnull, "w") as _devnull, \
             contextlib.redirect_stdout(_devnull), \
             contextlib.redirect_stderr(_devnull):
            review_agent = AIAgent(
                model=self.model,
                max_iterations=8,
                quiet_mode=True,
            )
            review_agent._memory_store = self._memory_store
            # 禁用 review agent 自身的 nudge，否则会无限递归
            review_agent._memory_nudge_interval = 0
            review_agent._skill_nudge_interval = 0
            review_agent.run_conversation(
                user_message=prompt,
                conversation_history=messages_snapshot,
            )

    thread = threading.Thread(target=_run_review, daemon=True)
    thread.start()
```

关键细节：
- 输出重定向到 `/dev/null`，用户完全无感知
- 最多 8 次工具调用，不会无限消耗 API
- Review Agent 自身的 nudge 被禁用，避免无限递归
- 和主 Agent 共享同一份 Memory，写入直接生效
- **"干活"和"反思"拆成两个实例，互不干扰**

审查在响应发送给用户之后才触发，用户收到回复后该干嘛干嘛，Agent 在后台默默复盘。

#### 类优先抽象：防止技能库膨胀

Review Agent 的提示词强制要求将具体经验抽象为可复用的任务类别：

> *"You are looking for the CLASS of task that just happened, not the exact task. Example: a successful Tauri build is in the class 'desktop app build troubleshooting', not 'fix my specific Tauri error today'."*

同时要求优先更新现有技能，而非创建新技能：

> *"PREFER GENERALIZING AN EXISTING SKILL over creating a new one."*

每个审查 prompt 都以这句话收尾：

> *"If nothing is worth saving, just say 'Nothing to save.' and stop."*

防止 Review Agent 每次都往里塞东西来"交差"。

---

### 2.5 完整学习闭环：从"不会"到"精通"的三次会话

以 K8s 部署场景为例，展示三个子系统的协同。

#### 第 1 次会话：冷启动

```
用户: 帮我把这个 Flask 应用部署到 K8s 集群
```

Memory 和 Skills 都是空的，Agent 靠基座知识摸索，**12 次工具调用**，踩了两个坑：

```
iter 1:  terminal("kubectl version")           → 确认集群版本
iter 2:  read_file("app.py")                   → 读取应用代码
iter 3:  write_file("Dockerfile")              → 创建 Dockerfile
iter 4:  terminal("docker build -t myapp .")    → 构建镜像
iter 5:  write_file("deployment.yaml")          → 编写 K8s 部署文件
iter 6:  terminal("kubectl apply -f deployment.yaml")
        → 💥 ImagePullBackOff！忘记推镜像到 registry
iter 7:  terminal("docker push myregistry...")  → 推送镜像
iter 8:  terminal("kubectl apply -f deployment.yaml") → 重新部署
iter 9:  write_file("service.yaml")            → 编写 Service
iter 10: terminal("kubectl apply -f service.yaml")
iter 11: terminal("kubectl get pods")
        → 💥 CrashLoopBackOff！livenessProbe 路径不对
iter 12: 修改 deployment.yaml → 重新部署 → ✅ 成功
```

12 次迭代触发 Skill Review，Review Agent 在后台看到两次报错和修复过程，创建了一个 Skill：

```yaml
---
name: flask-k8s-deploy
description: Deploy a Flask app to Kubernetes with health checks
---
## Steps
1. Create Dockerfile with gunicorn
2. Build and push image to registry BEFORE kubectl apply
3. Write deployment.yaml with livenessProbe → /health
...

## Pitfalls
- MUST push image to registry first, otherwise ImagePullBackOff
- Flask 默认没有 /health 端点，需手动添加
- livenessProbe path 必须返回 200
```

安全扫描通过后写入磁盘，**用户对这一切毫不知情**。

#### 第 2 次会话：Skill 复用 + 自我修补

```
用户: 帮我再部署一个 Django 应用到 K8s
```

系统提示词里多了 Skills 索引，Agent 加载 `flask-k8s-deploy` 后照着步骤做。但发现 Django 需要额外设置 `ALLOWED_HOSTS` 环境变量——这是原 Skill 里没有的。

完成部署后，Agent **自动 patch Skill**，追加了 Django 特有的注意事项。

#### 第 3 次会话：完全自动化

```
用户: 再部署一个 FastAPI 应用
```

Agent 加载已修补的 Skill，直接跳过所有已知坑点，**6 次调用零错误完成**。

> **这就是自进化的力量**：从 12 次调用踩两个坑，到 6 次调用零错误。每一次踩坑都在加固护城河。

---

## 3. 与 OpenClaw 的核心差异对比

### 3.1 自进化能力：最核心的差异

| 能力 | OpenClaw | Hermes Agent |
|------|----------|-------------|
| **自动创建 Skill** | ✘ 不支持，需手写 | ✔ 复杂任务后自动提炼 |
| **Skill 自我修补** | ✘ 无内置机制 | ✔ 踩坑后当场 patch |
| **后台审查引擎** | ✘ 无 | ✔ Nudge Engine + Review Agent |
| **记忆容量管理** | 纯追加，容易膨胀 | 定量限制 + 自主压缩 |
| **用户建模** | SOUL.md + USER.md | Honcho 方言用户建模 |
| **前缀缓存优化** | 无特殊优化 | 冻结快照 + Prefix Cache |
| **类优先抽象** | 无 | 强制抽象为任务类别 |
| **渐进式加载** | 重型背包模式 | 动态图书馆三级加载 |

### 3.2 其他关键差异

| 维度 | OpenClaw | Hermes Agent |
|------|----------|-------------|
| **技术栈** | 纯 TypeScript | Python + TypeScript 混合 |
| **模型数量** | 少量（主要千问、Claude） | 200+ 模型（OpenRouter 等） |
| **平台覆盖** | 15+ 渠道（国内优势） | 主流国际平台 + Email |
| **媒体生成** | 内置音乐/视频/图片 | 无内置（可插件扩展） |
| **研究能力** | 无 | 批量轨迹 + RL 环境 + 压缩 |
| **移动端** | Win11/Mac/Linux | Linux/Mac/WSL2/Android Termux |
| **上手难度** | 中等（配置复杂） | 低（一行脚本） |
| **Homebrew** | ✘ | ✔ |
| **Nix** | ✘ | ✔ |
| **YOLO 模式** | ✘ | ✔ (--yolo 跳过所有审批) |

---

## 4. OpenClaw 架构上做不到的事

Hermes 的自进化不是 OpenClaw 团队不想做，而是它的架构没有为"Agent 自主学习"预留通路。要补这一课，需要重写核心架构。

| 缺失能力 | 说明 |
|---------|------|
| **没有创建触发** | OpenClaw 的 Agent 没有"任务完成后复盘"的触发机制 |
| **没有 patch 机制** | Skill 是静态文件，没有运行时修补的能力 |
| **没有 Review Agent** | 缺少独立的后台审查实例来评估任务价值 |
| **没有类优先抽象** | 无法将具体经验提炼为通用方法论 |
| **没有 Nudge Engine** | 没有定时提醒 Agent 学习的机制 |
| **没有容量管理** | Memory 纯追加，无法自我压缩和淘汰 |

> **结论**：当模型智能被商品化、Agent 框架被开源，真正的护城河是 Agent 在工作中积累的领域知识。OpenClaw 的 Skill 是手写的配置文件，用了一年还是那份手写的配置文件；Hermes 的 Skill 是越用越厚的经验资产——每一次踩坑都在加固护城河。

---

## 5. 当前局限性与改进方向

### 5.1 成功判定的缺失

当前触发审查的硬性条件只有三个：最终响应存在、未被中断、工具调用次数达标。**没有"任务成功"的判定**，意味着：

| 场景 | 工具调用 | 是否合理 |
|------|---------|---------|
| 反复报错后成功解决 | 8 次 | ✔ 合理 |
| 反复报错后放弃 | 8 次 | ✘ 不应沉淀 |
| Agent 道歉说"做不到" | 8 次 | ✘ 不应沉淀 |
| 用户说"算了"（未打断） | 8 次 | ✘ 不应沉淀 |

当前依赖 LLM 的软性自我约束（`"Only act when something is genuinely worth saving"`），缺乏程序化的验证机制。

### 5.2 改进建议

| 方案 | 描述 | 复杂度 |
|------|------|--------|
| **工具成功率统计** | 失败率超过 50% 则跳过审查 | 低 |
| **用户反馈信号检测** | 检测"不对""算了""放弃"等负面信号 | 低 |
| **Agent 自我评估** | 在审查提示词中增加硬性成功判定要求 | 低 |
| **结果验证模式** | 对文件创建、代码执行等任务做后置验证 | 中 |
| **调整 nudge 间隔** | 将 creation_nudge_interval 调到 15-20 次 | 低 |
| **定期审计** | 定期审计 ~/.hermes/skills/ 目录，清理低质量技能 | 低 |

### 5.3 生产环境建议

- 调整 `creation_nudge_interval` 到更保守的值（如 15-20 次工具调用）
- 定期审计 `~/.hermes/skills/` 目录，清理低质量技能
- 在 `skill_manager_tool` 的 description 中增加更严格的成功判定提示

---

## 6. 总结

Hermes Agent 的核心价值不在于"对话"，而在于"成长"。它通过 Memory（记人）、Skill（记事）、Nudge Engine（提醒学习）三大系统闭环，让 Agent 越用越懂你、越用越强。

这不是手写配置的"人工智能"，而是从实践中自动提炼的"经验智能"。对于开发者而言，这意味着你的 Agent 会随着时间的推移变得越来越专业——它会记住你的项目约定、你踩过的坑、你纠正过的做法，并将这些经验转化为可复用的能力。

**一句话总结**：

> **OpenClaw 是一个工具，Hermes 是一个伙伴——一个会成长的伙伴。**

---

## 7. 参考资料

- [Hermes Agent GitHub](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com/docs/)
- [深入源码：Hermes Agent 如何实现 Self-Improving（阿里云）](https://developer.aliyun.com/article/1730226)
- [Hermes Agent 自进化能力原理剖析](http://m.toutiao.com/group/7634163299717743131/)
- [Hermes Agent Skills 自进化机制：AI 是怎么炼成的](http://m.toutiao.com/group/7634151240352203300/)
- [B站视频：Hermes Agent 新 OpenClaw?](https://www.bilibili.com/video/BV1nfdmBCEE8/)
- [B站视频：外网爆火的 Hermes Agent 实测](https://www.bilibili.com/video/BV1ztQ4BzECC/)
- [B站视频：Hermes Agent 深入体验](https://www.bilibili.com/video/BV1nyo1BuEd9/)
- [Hermes Agent 从入门到精通（橙皮书）](https://www.cdut.edu.cn/__local/D/6C/4E/D566CE58D375BECAF4551E7F121_723F6229_52BA50.pdf)
- [Hermes Agent v0.7.0 Deep Dive (DEV Community)](https://dev.to/_46ea277e677b888e0cd13/hermes-agent-the-self-improving-open-source-ai-agent-framework-v070-deep-dive-270j)
- [爆火出圈的 Hermes Agent 深度调研 (CSDN)](https://blog.csdn.net/weixin_41645817/article/details/160073929)
