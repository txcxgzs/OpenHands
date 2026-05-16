#!/bin/bash
set -e

# OpenHands 一键安装脚本 v2.0
# 交互式安装体验，参考OpenClaw风格

BOLD='\033[1m'
ACCENT='\033[38;2;0;175;255m'    # 蓝色
SUCCESS='\033[38;2;0;255;136m'   # 绿色
WARN='\033[38;2;255;200;0m'      # 橙色
ERROR='\033[38;2;255;80;80m'     # 红色
INFO='\033[38;2;150;150;150m'   # 灰色
NC='\033[0m'

INSTALL_DIR="${HOME}/.openhands"
CONFIG_FILE="${INSTALL_DIR}/.env"

print_banner() {
    echo -e ""
    echo -e "${ACCENT}${BOLD}    ╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${ACCENT}${BOLD}    ║                                                          ║${NC}"
    echo -e "${ACCENT}${BOLD}    ║${NC}   ${BOLD}🤝 欢迎使用 OpenHands - AI 智能助手安装程序${NC}       ${ACCENT}${BOLD}║${NC}"
    echo -e "${ACCENT}${BOLD}    ║                                                          ║${NC}"
    echo -e "${ACCENT}${BOLD}    ╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e ""
}

print_step() {
    local step=$1
    local total=$2
    local msg=$3
    echo -e "${ACCENT}  [${step}/${total}]${NC} ${BOLD}${msg}${NC}"
}

print_success() {
    echo -e "${SUCCESS}  ✓${NC} $1"
}

print_error() {
    echo -e "${ERROR}  ✗${NC} $1"
}

print_info() {
    echo -e "${INFO}  ·${NC} $1"
}

print_warning() {
    echo -e "${WARN}  !${NC} $1"
}

detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*)    echo "windows";;
        MINGW*)     echo "windows";;
        *)          echo "unknown";;
    esac
}

check_python() {
    print_info "检测 Python..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python ${PYTHON_VERSION} 已安装"
        return 0
    elif command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        print_success "Python ${PYTHON_VERSION} 已安装"
        return 0
    else
        print_error "未找到 Python，请先安装 Python 3.8+"
        return 1
    fi
}

check_pip() {
    print_info "检测 pip..."
    if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
        print_success "pip 已安装"
        return 0
    else
        print_error "未找到 pip"
        return 1
    fi
}

create_venv() {
    print_info "创建虚拟环境..."
    
    mkdir -p "$INSTALL_DIR"
    
    if [ ! -d "$INSTALL_DIR/venv" ]; then
        python3 -m venv "$INSTALL_DIR/venv" 2>/dev/null || python -m venv "$INSTALL_DIR/venv"
        print_success "虚拟环境创建成功"
    else
        print_success "虚拟环境已存在"
    fi
}

install_openhands() {
    print_info "安装 OpenHands 及依赖..."
    
    source "$INSTALL_DIR/venv/bin/activate"
    
    pip install --upgrade pip -q
    pip install -e ".[browser,voice]" -q 2>/dev/null || pip install -e . -q
    
    print_success "OpenHands 安装完成"
}

configure_api_key() {
    echo ""
    print_info "配置 API Key"
    echo ""
    
    if [ -f "$CONFIG_FILE" ]; then
        print_info "发现已有配置文件"
        read -p "  是否重新配置 API Key？[y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "跳过 API Key 配置"
            return 0
        fi
    fi
    
    echo ""
    echo "  请选择模型提供商："
    echo ""
    echo "    1) LongCat (长上下文，支持超长对话) ⭐ 推荐"
    echo "    2) OpenAI GPT-4"
    echo "    3) Anthropic Claude"
    echo "    4) DeepSeek (国产)"
    echo "    5) OpenRouter (聚合200+模型)"
    echo "    6) 稍后手动配置"
    echo ""
    read -p "  请输入选项 [1-6]: " choice
    
    case $choice in
        1)
            PROVIDER="longcat"
            MODEL="LongCat-2.0-Preview"
            ;;
        2)
            PROVIDER="openai"
            MODEL="gpt-4o"
            ;;
        3)
            PROVIDER="anthropic"
            MODEL="claude-3-5-sonnet-20241022"
            ;;
        4)
            PROVIDER="deepseek"
            MODEL="deepseek-chat"
            ;;
        5)
            PROVIDER="openrouter"
            MODEL="openai/gpt-4o"
            ;;
        6)
            print_info "跳过 API Key 配置"
            create_default_config
            return 0
            ;;
        *)
            print_warning "无效选项，使用默认值"
            PROVIDER="longcat"
            MODEL="LongCat-2.0-Preview"
            ;;
    esac
    
    echo ""
    read -p "  请输入您的 ${PROVIDER^^} API Key: " api_key
    
    if [ -z "$api_key" ]; then
        print_warning "未输入 API Key，已跳过"
        create_default_config
        return 0
    fi
    
    case $PROVIDER in
        longcat)
            echo "LONGCAT_API_KEY=$api_key" >> "$CONFIG_FILE"
            ;;
        openai)
            echo "OPENAI_API_KEY=$api_key" >> "$CONFIG_FILE"
            ;;
        anthropic)
            echo "ANTHROPIC_API_KEY=$api_key" >> "$CONFIG_FILE"
            ;;
        deepseek)
            echo "DEEPSEEK_API_KEY=$api_key" >> "$CONFIG_FILE"
            ;;
        openrouter)
            echo "OPENROUTER_API_KEY=$api_key" >> "$CONFIG_FILE"
            ;;
    esac
    
    echo "DEFAULT_MODEL=${PROVIDER}/${MODEL}" >> "$CONFIG_FILE"
    
    print_success "API Key 配置完成"
}

create_default_config() {
    mkdir -p "$INSTALL_DIR"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        cat > "$CONFIG_FILE" << 'EOF'
# OpenHands 配置文件
# 请取消注释并填入您的 API Key

# ========== 模型配置 ==========
# LongCat (长上下文)
# LONGCAT_API_KEY=your_key_here

# OpenAI GPT
# OPENAI_API_KEY=your_key_here

# Anthropic Claude
# ANTHROPIC_API_KEY=your_key_here

# DeepSeek (国产)
# DEEPSEEK_API_KEY=your_key_here

# OpenRouter (聚合200+模型)
# OPENROUTER_API_KEY=your_key_here

# ========== 默认模型 ==========
DEFAULT_MODEL=longcat/LongCat-2.0-Preview

# ========== Agent 配置 ==========
MAX_ITERATIONS=90
ENABLE_SELF_EVOLUTION=true
MEMORY_CHAR_LIMIT=2200
ENABLE_WINDOWS_CONTROL=true
GUI_PORT=8000
EOF
    fi
}

create_launch_scripts() {
    print_info "创建启动脚本..."
    
    cat > "$INSTALL_DIR/openhands" << EOF
#!/bin/bash
source "${HOME}/.openhands/venv/bin/activate"
cd "${HOME}/.openhands"
python -c "
import os
import sys
from pathlib import Path

config_file = Path('${INSTALL_DIR}/.env')
if config_file.exists():
    with open(config_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                if value and not value.startswith('#'):
                    os.environ[key] = value

from openhands import EmbeddedAgent, AgentConfig
import asyncio

async def chat():
    config = AgentConfig()
    
    # 尝试从环境变量读取配置
    if os.getenv('LONGCAT_API_KEY'):
        config.model.provider = 'longcat'
        config.model.model = 'LongCat-2.0-Preview'
    elif os.getenv('OPENAI_API_KEY'):
        config.model.provider = 'openai'
        config.model.model = 'gpt-4o'
    elif os.getenv('ANTHROPIC_API_KEY'):
        config.model.provider = 'anthropic'
        config.model.model = 'claude-3-5-sonnet-20241022'
    elif os.getenv('DEEPSEEK_API_KEY'):
        config.model.provider = 'deepseek'
        config.model.model = 'deepseek-chat'
    elif os.getenv('OPENROUTER_API_KEY'):
        config.model.provider = 'openrouter'
        config.model.model = 'openai/gpt-4o'
    
    if len(sys.argv) > 1:
        message = ' '.join(sys.argv[1:])
    else:
        message = input('你: ')
    
    agent = EmbeddedAgent(config)
    await agent.initialize()
    session_id = await agent.create_session()
    await agent.queue_message(session_id, message)
    result = await agent.run(session_id)
    print()
    print('OpenHands: ' + (result.final_answer or '抱歉，我没有收到回复'))
    
asyncio.run(chat())
"
EOF
    chmod +x "$INSTALL_DIR/openhands"
    
    cat > "$INSTALL_DIR/openhands-gui" << 'EOF'
#!/bin/bash
source "${HOME}/.openhands/venv/bin/activate"
cd "${HOME}/.openhands"
python -m openhands.gui.server
EOF
    chmod +x "$INSTALL_DIR/openhands-gui"
    
    print_success "启动脚本创建完成"
}

print_completion() {
    echo ""
    echo -e "${SUCCESS}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${SUCCESS}${BOLD}║                                                          ║${NC}"
    echo -e "${SUCCESS}${BOLD}║${NC}        ${BOLD}🎉 安装成功！OpenHands 已准备就绪！${NC}             ${SUCCESS}${BOLD}║${NC}"
    echo -e "${SUCCESS}${BOLD}║                                                          ║${NC}"
    echo -e "${SUCCESS}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${INFO}  使用方法：${NC}"
    echo ""
    echo -e "    ${BOLD}快速聊天：${NC}"
    echo -e "      ${ACCENT}~/.openhands/openhands 你好${NC}"
    echo ""
    echo -e "    ${BOLD}交互模式：${NC}"
    echo -e "      ${ACCENT}~/.openhands/openhands${NC}"
    echo ""
    echo -e "    ${BOLD}启动 Web GUI：${NC}"
    echo -e "      ${ACCENT}~/.openhands/openhands-gui${NC}"
    echo "      然后访问 ${ACCENT}http://localhost:8000${NC}"
    echo ""
    
    if [ ! -f "$CONFIG_FILE" ] || ! grep -q "API_KEY=sk-" "$CONFIG_FILE" 2>/dev/null; then
        echo -e "${WARN}  ⚠️  请配置您的 API Key：${NC}"
        echo -e "      ${ACCENT}nano ~/.openhands/.env${NC}"
        echo ""
    fi
    
    echo -e "${INFO}  快速入门：${NC}"
    echo "    1. 编辑配置文件配置 API Key"
    echo "    2. 运行 ~/.openhands/openhands 开始聊天"
    echo ""
    echo -e "${INFO}  支持的模型：${NC}"
    echo "    · LongCat (长上下文) ⭐"
    echo "    · OpenAI GPT-4"
    echo "    · Anthropic Claude"
    echo "    · DeepSeek (国产)"
    echo "    · OpenRouter (200+模型)"
    echo ""
}

main() {
    print_banner
    
    TOTAL_STEPS=6
    
    echo ""
    print_step "1" "$TOTAL_STEPS" "检测环境"
    check_python || exit 1
    check_pip || exit 1
    
    print_step "2" "$TOTAL_STEPS" "创建虚拟环境"
    create_venv
    
    print_step "3" "$TOTAL_STEPS" "安装 OpenHands"
    install_openhands
    
    print_step "4" "$TOTAL_STEPS" "配置 API Key"
    configure_api_key
    
    print_step "5" "$TOTAL_STEPS" "创建启动脚本"
    create_launch_scripts
    
    print_step "6" "$TOTAL_STEPS" "完成"
    
    print_completion
}

main
