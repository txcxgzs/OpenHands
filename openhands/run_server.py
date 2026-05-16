
"""
临时测试启动脚本 - 强制使用 LongCat
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 强制设置环境变量
os.environ['OPENHANDS_MODEL'] = 'longcat'
os.environ['OPENHANDS_MODEL_NAME'] = 'LongCat-2.0-Preview'
os.environ['OPENHANDS_MODEL_PROVIDER'] = 'longcat'
os.environ['LONGCAT_API_KEY'] = 'ak_2si0nr6tc4jx6XM4pv36f9i90dd4Z'

from openhands.gui.server import run_gui

if __name__ == '__main__':
    print()
    print('=' * 60)
    print('🚀 OpenHands - 启动中')
    print(f'   模型: LongCat-2.0-Preview')
    print(f'   访问地址: http://localhost:8000')
    print('=' * 60)
    print()
    
    run_gui()
