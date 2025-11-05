#!/usr/bin/env python3
"""
Entry point for running the MCP server as a module
使用方式: python -m wheeltec_navigation_mcp
"""

import asyncio
from .navigation_server import main

if __name__ == "__main__":
    asyncio.run(main())
