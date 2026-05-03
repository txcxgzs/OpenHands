# AuroraAgent - Windows AI Assistant

一个功能强大的 Windows AI 助手，深度结合了 OpenClaw 和 Hermes Agent 的设计理念。

## 特性

- 🖱️ **Windows 控制** - 鼠标、键盘、窗口管理
- 📸 **多模态支持** - 屏幕截图、图像理解
- ⌨️ **完整工具集** - 文件操作、终端执行、等
- 🧠 **AI 驱动** - Claude 3.5 Sonnet (默认) 等模型
- 🛡️ **安全设计** - 安全模式、权限控制

## 安装

```bash
# 克隆项目
cd auroraagent

# 安装
pip install -e .
```

或安装开发版本:
```bash
pip install -e ".[dev]"
```

### 依赖

- Python 3.11+
- anthropic
- openai
- pyautogui
- mss
- Pillow
- pynput
- pywin32 (Windows only)
- rich
- pyyaml
- python-dotenv

## 配置

### API Key

设置环境变量:
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-xxx

# or PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-xxx"
```

或使用配置文件:
```bash
aurora config --init
```

配置文件位于: `%APPDATA%\auroraagent\config.yaml`

## 使用

### 交互式聊天

```bash
aurora chat
```

### 单条消息

```bash
aurora chat -m "帮我截取当前屏幕并描述一下"
```

### 包含图像

```bash
aurora chat -m "分析这张图" --image screenshot.png
```

### 列出可用工具

```bash
aurora tools list
```

## 工具集

### 文件工具
- `read_file` - 读取文件内容
- `write_file` - 写入文件
- `list_dir` - 列出目录内容
- `delete_file` - 删除文件

### 终端工具
- `terminal` - 执行终端命令

### Windows 控制
- `mouse_position` - 获取鼠标位置
- `mouse_move` - 移动鼠标
- `mouse_click` - 点击
- `mouse_scroll` - 滚动
- `mouse_drag` - 拖拽
- `key_press` - 按键
- `key_write` - 键盘输入
- `key_hotkey` - 组合键
- `list_windows` - 列出窗口 (Windows)
- `activate_window` - 激活窗口 (Windows)
- `screen_size` - 屏幕尺寸

### 多模态
- `screenshot` - 截图
- `screenshot_region` - 区域截图
- `list_monitors` - 列出显示器
- `analyze_image` - 分析图像

## 示例

### 自动化操作

```
User: "打开记事本，输入 'Hello World!', 然后保存到 desktop"

Aurora: [会执行一系列操作...]
1. Win+R -> notepad -> Enter
2. key_write "Hello World!"
3. Ctrl+S -> ...
```

### 屏幕分析

```
User: "截图并告诉我看到了什么"

Aurora: [使用 screenshot 工具，分析并回答...]
```

### 自定义任务

```
User: "帮我创建一个 Python 脚本在 desktop"

Aurora: [使用 write_file 创建文件...]
```

## 安全

默认启用安全模式:
- 危险操作需要确认
- 文件操作受限制
- 可配置权限

在配置中调整:
```yaml
windows:
  safe_mode: true
```

## 项目结构

```
auroraagent/
├── core/
│   ├── agent.py           # Agent Loop
│   ├── config.py          # 配置
│   └── adapters/          # 模型适配器
├── tools/
│   ├── registry.py        # 工具注册表
│   ├── file_tools.py
│   └── terminal_tools.py
├── windows/
│   └── windows_tools.py   # Windows 控制
├── multimodal/
│   └── multimodal_tools.py
└── cli/
    └── main.py
```

## 架构设计

### 设计模式
- **Registry** - 工具注册和管理
- **Adapter** - 模型适配 (Anthropic, OpenAI, 等)
- **Command** - 工具执行
- **Factory** - 配置和适配器创建

### 参考项目
- [OpenClaw](https://github.com/clap-ai/clop) - TypeScript 架构
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) - Python 实现

## 开发

```bash
# 运行 lint
ruff check

# 格式化
black auroraagent
```

## 许可证

MIT License

## 贡献

欢迎 Issue 和 PR!

## 免责声明

此工具具有控制系统的能力。请谨慎使用，只在您自己的系统上运行。
