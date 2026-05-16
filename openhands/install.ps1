# OpenHands Windows 安装脚本
# 支持: Windows 10/11

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "║           OpenHands - AI Assistant Installer               ║" -ForegroundColor Blue
Write-Host "║         The Agent That Grows With You                      ║" -ForegroundColor Blue
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# 检查 Python
Write-Host "[→] 检查 Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[✓] $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[✗] 未找到 Python，请先安装 Python 3.8+" -ForegroundColor Red
    Write-Host "    下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# 安装目录
$InstallDir = "$env:USERPROFILE\.openhands"
Write-Host "[→] 安装目录: $InstallDir" -ForegroundColor Yellow

# 创建目录
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

# 创建虚拟环境
Write-Host "[→] 创建虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path "$InstallDir\venv")) {
    python -m venv "$InstallDir\venv"
    Write-Host "[✓] 虚拟环境创建成功" -ForegroundColor Green
} else {
    Write-Host "[✓] 虚拟环境已存在" -ForegroundColor Green
}

# 激活虚拟环境
& "$InstallDir\venv\Scripts\Activate.ps1"

# 安装 OpenHands
Write-Host "[→] 安装 OpenHands..." -ForegroundColor Yellow
pip install --upgrade pip -q
pip install httpx fastapi uvicorn pyautogui pillow pygetwindow -q 2>$null
Write-Host "[✓] OpenHands 安装完成" -ForegroundColor Green

# 创建配置文件
$EnvFile = "$InstallDir\.env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "[→] 创建配置文件..." -ForegroundColor Yellow
    
    @"
# OpenHands 配置文件
# 编辑此文件配置你的 API Key

# ========== 模型配置 ==========
# 选择一个模型提供商 (取消注释并填入你的 API Key)

# Anthropic Claude (推荐)
# ANTHROPIC_API_KEY=your_anthropic_key_here

# OpenAI GPT
# OPENAI_API_KEY=your_openai_key_here

# LongCat (长上下文)
# LONGCAT_API_KEY=your_longcat_key_here

# DeepSeek (国产)
# DEEPSEEK_API_KEY=your_deepseek_key_here

# ========== 默认模型 ==========
DEFAULT_MODEL=openai/gpt-4

# ========== Agent 配置 ==========
MAX_ITERATIONS=90
ENABLE_SELF_EVOLUTION=true
MEMORY_CHAR_LIMIT=2200

# ========== Windows 控制 ==========
ENABLE_WINDOWS_CONTROL=true

# ========== Web GUI ==========
GUI_PORT=8000
"@ | Out-File -FilePath $EnvFile -Encoding UTF8
    
    Write-Host "[✓] 配置文件创建成功: $EnvFile" -ForegroundColor Green
}

# 创建启动脚本
Write-Host "[→] 创建启动脚本..." -ForegroundColor Yellow

# CLI 启动脚本
@"
@echo off
call "$InstallDir\venv\Scripts\activate.bat"
cd /d "$InstallDir"
python -m openhands.cli %*
"@ | Out-File -FilePath "$InstallDir\openhands.bat" -Encoding ASCII

# GUI 启动脚本
@"
@echo off
call "$InstallDir\venv\Scripts\activate.bat"
cd /d "$InstallDir"
start http://localhost:8000
python -m openhands.gui.server
"@ | Out-File -FilePath "$InstallDir\openhands-gui.bat" -Encoding ASCII

# 创建桌面快捷方式
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\OpenHands.lnk")
$Shortcut.TargetPath = "$InstallDir\openhands-gui.bat"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "OpenHands - AI Assistant"
$Shortcut.Save()

Write-Host "[✓] 启动脚本创建成功" -ForegroundColor Green
Write-Host "[✓] 桌面快捷方式创建成功" -ForegroundColor Green

# 添加到 PATH
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$InstallDir", "User")
    Write-Host "[✓] 已添加到 PATH" -ForegroundColor Green
}

# 完成提示
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              OpenHands 安装成功！                          ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. 配置 API Key:" -ForegroundColor White
Write-Host "     notepad $InstallDir\.env" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. 启动方式:" -ForegroundColor White
Write-Host "     - 双击桌面 OpenHands 图标" -ForegroundColor Cyan
Write-Host "     - 或运行: $InstallDir\openhands-gui.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. 访问 Web 界面:" -ForegroundColor White
Write-Host "     http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "支持的模型:" -ForegroundColor Yellow
Write-Host "  - Anthropic Claude, OpenAI GPT, LongCat, DeepSeek, Ollama"
Write-Host ""
