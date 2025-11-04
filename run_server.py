#!/usr/bin/env python3
"""
服务器启动脚本
简化的服务器启动入口
"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from backend.main import run_server

if __name__ == "__main__":
    print("\n🚀 Starting Multi-Agent System Server")
    print("="*60)
    run_server()
