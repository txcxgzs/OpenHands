#!/bin/bash
#
# OpenHands 一键安装脚本
# 支持: Linux, macOS, Windows (WSL/Git Bash)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           OpenHands - AI Assistant Installer               ║"
echo "║         The Agent That Grows With You                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*)    echo "windows";;
        MINGW*)     echo "windows";;
        *)          echo "unknown";;
    esac
}

OS=$(detect_os)
echo -e "${GREEN}[✓]${NC} 检测到操作系统: $OS"

# 检查 Python
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}[✓]${NC} Python 版本: $PYTHON_VERSION"
        return 0
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}[✓]${NC} Python 版本: $PYTHON_VERSION"
        return 0
    else
        echo -e "${RED}[✗]${NC} 未找到 Python，请先安装 Python 3.8+"
        exit 1
    fi
}

check_python

# 检查 pip
check_pip() {
    if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
        echo -e "${GREEN}[✓]${NC} pip 已安装"
        return 0
    else
        echo -e "${RED}[✗]${NC} 未找到 pip"
        exit 1
    fi
}

check_pip

# 创建虚拟环境
create_venv() {
    echo -e "${BLUE}[→]${NC} 创建虚拟环境..."
    
    INSTALL_DIR="${HOME}/.openhands"
    mkdir -p "$INSTALL_DIR"
    
    if [ ! -d "$INSTALL_DIR/venv" ]; then
        python3 -m venv "$INSTALL_DIR/venv" 2>/dev/null || python -m venv "$INSTALL_DIR/venv"
        echo -e "${GREEN}[✓]${NC} 虚拟环境创建成功: $INSTALL_DIR/venv"
    else
        echo -e "${GREEN}[✓]${NC} 虚拟环境已存在"
    fi
    
    source "$INSTALL_DIR/venv/bin/activate"
}

# 安装 OpenHands
install_openhands() {
    echo -e "${BLUE}[→]${NC} 安装 OpenHands..."
    
    # 安装依赖
    pip install --upgrade pip -q
    pip install -e . -q 2>/dev/null || pip install openhands -q
    
    # 安装可选依赖
    pip install httpx fastapi uvicorn pyautogui pillow -q 2>/dev/null || true
    
    echo -e "${GREEN}[✓]${NC} OpenHands 安装完成"
}

# 创建配置文件
create_config() {
    echo -e "${BLUE}[→]${NC} 创建配置文件..."
    
    CONFIG_DIR="${HOME}/.openhands"
    ENV_FILE="$CONFIG_DIR/.env"
    
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" << 'EOF'
# OpenHands 配置文件
# 编辑此文件配置你的 API Key

# ========== 模型配置 ==========
# 选择一个模型提供商 (取消注释并填入你的 API Key)

# Anthropic Claude (推荐)
# ANTHROPIC_API_KEY=your_anthropic_key_here

# OpenAI GPT
# OPENAI_API_KEY=your_openai_key_here

# OpenRouter (聚合 200+ 模型)
# OPENROUTER_API_KEY=your_openrouter_key_here

# LongCat (长上下文)
# LONGCAT_API_KEY=your_longcat_key_here

# DeepSeek (国产)
# DEEPSEEK_API_KEY=your_deepseek_key_here

# Ollama (本地模型，无需 API Key)
# OLLAMA_BASE_URL=http://localhost:11434

# ========== 默认模型 ==========
# 格式: provider/model
# 例如: openai/gpt-4, anthropic/claude-3-opus, openrouter/anthropic/claude-3-opus
DEFAULT_MODEL=openai/gpt-4

# ========== Agent 配置 ==========
# 最大迭代次数
MAX_ITERATIONS=90

# 启用自进化功能
ENABLE_SELF_EVOLUTION=true

# 记忆容量限制 (字符数)
MEMORY_CHAR_LIMIT=2200
USER_MEMORY_CHAR_LIMIT=1375

# ========== Windows 控制 ==========
# 启用 Windows 自动化
ENABLE_WINDOWS_CONTROL=true

# ========== Web GUI ==========
# GUI 服务端口
GUI_PORT=8000

# ========== 监控 ==========
# 启用 Prometheus 监控
ENABLE_MONITORING=false
PROMETHEUS_PORT=9090
EOF
        echo -e "${GREEN}[✓]${NC} 配置文件创建成功: $ENV_FILE"
        echo -e "${YELLOW}[!]${NC} 请编辑 $ENV_FILE 配置你的 API Key"
    else
        echo -e "${GREEN}[✓]${NC} 配置文件已存在"
    fi
}

# 创建启动脚本
create_launch_scripts() {
    echo -e "${BLUE}[→]${NC} 创建启动脚本..."
    
    INSTALL_DIR="${HOME}/.openhands"
    
    # CLI 启动脚本
    cat > "$INSTALL_DIR/openhands" << 'EOF'
#!/bin/bash
source "${HOME}/.openhands/venv/bin/activate"
cd "${HOME}/.openhands"
python -m openhands.cli "$@"
EOF
    chmod +x "$INSTALL_DIR/openhands"
    
    # GUI 启动脚本
    cat > "$INSTALL_DIR/openhands-gui" << 'EOF'
#!/bin/bash
source "${HOME}/.openhands/venv/bin/activate"
cd "${HOME}/.openhands"
python -m openhands.gui.server
EOF
    chmod +x "$INSTALL_DIR/openhands-gui"
    
    # 添加到 PATH
    if ! grep -q 'export PATH="$HOME/.openhands:$PATH"' "${HOME}/.bashrc" 2>/dev/null; then
        echo 'export PATH="$HOME/.openhands:$PATH"' >> "${HOME}/.bashrc"
    fi
    
    echo -e "${GREEN}[✓]${NC} 启动脚本创建成功"
}

# 创建桌面快捷方式
create_desktop_entry() {
    if [ "$OS" = "linux" ]; then
        DESKTOP_DIR="${HOME}/.local/share/applications"
        mkdir -p "$DESKTOP_DIR"
        
        cat > "$DESKTOP_DIR/openhands.desktop" << EOF
[Desktop Entry]
Name=OpenHands
Comment=AI Assistant That Grows With You
Exec=${HOME}/.openhands/openhands-gui
Icon=${HOME}/.openhands/icon.png
Terminal=false
Type=Application
Categories=Utility;AI;
EOF
        echo -e "${GREEN}[✓]${NC} 桌面快捷方式创建成功"
    fi
}

# 打印完成信息
print_success() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              OpenHands 安装成功！                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}下一步:${NC}"
    echo ""
    echo "  1. 配置 API Key:"
    echo "     ${BLUE}nano ~/.openhands/.env${NC}"
    echo ""
    echo "  2. 启动 CLI:"
    echo "     ${BLUE}~/.openhands/openhands${NC}"
    echo ""
    echo "  3. 启动 Web GUI:"
    echo "     ${BLUE}~/.openhands/openhands-gui${NC}"
    echo "     然后访问 ${BLUE}http://localhost:8000${NC}"
    echo ""
    echo "  4. 快速启动 (重新加载 shell 后):"
    echo "     ${BLUE}openhands${NC} - CLI 模式"
    echo "     ${BLUE}openhands-gui${NC} - GUI 模式"
    echo ""
    echo -e "${YELLOW}支持的模型:${NC}"
    echo "  - Anthropic Claude"
    echo "  - OpenAI GPT"
    echo "  - LongCat (长上下文)"
    echo "  - DeepSeek (国产)"
    echo "  - Ollama (本地模型)"
    echo "  - OpenRouter (200+ 模型聚合)"
    echo ""
}

# 主流程
main() {
    create_venv
    install_openhands
    create_config
    create_launch_scripts
    create_desktop_entry
    print_success
}

main
