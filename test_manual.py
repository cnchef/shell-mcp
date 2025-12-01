#!/usr/bin/env python3
"""
手动STDIO测试 - 使用文件管道方式
"""

import subprocess
import sys
import os
import json
import tempfile

def create_test_commands():
    """创建测试命令文件"""
    test_commands = [
        # 初始化
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 1
        },
        # 获取工具列表
        {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        },
        # 执行pwd命令
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "execute_command",
                "arguments": {
                    "command": "pwd"
                }
            },
            "id": 3
        },
        # 执行ls命令
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "execute_command",
                "arguments": {
                    "command": "ls -la"
                }
            },
            "id": 4
        }
    ]

    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        for cmd in test_commands:
            f.write(json.dumps(cmd, ensure_ascii=False) + '\n')
        temp_file = f.name

    return temp_file

def main():
    print("🧪 手动STDIO模式测试")
    print("=" * 40)

    # 创建测试命令文件
    test_file = create_test_commands()
    print(f"📝 创建测试文件: {test_file}")

    try:
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        print("\n🚀 启动服务器并发送测试命令...")

        # 启动服务器并管道输入
        with open(test_file, 'r') as input_file:
            process = subprocess.run(
                [sys.executable, "shell_mcp_server.py", "--mode", "stdio", "--log-level", "INFO"],
                stdin=input_file,
                capture_output=True,
                text=True,
                env=env
            )

        print("\n📤 服务器输出:")
        print("-" * 40)
        if process.stdout:
            print(process.stdout)
        print("-" * 40)

        if process.stderr:
            print("\n⚠️ 服务器错误信息:")
            print("-" * 40)
            print(process.stderr)
            print("-" * 40)

        print(f"\n📊 退出码: {process.returncode}")

        # 解析并显示响应
        if process.stdout:
            print("\n📋 解析响应:")
            print("-" * 40)
            lines = process.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                if line.strip():
                    try:
                        response = json.loads(line)
                        print(f"响应 {i+1}: {json.dumps(response, ensure_ascii=False, indent=2)}")
                    except json.JSONDecodeError:
                        print(f"原始输出 {i+1}: {line}")
            print("-" * 40)

    except Exception as e:
        print(f"❌ 测试失败: {e}")
    finally:
        # 清理临时文件
        try:
            os.unlink(test_file)
            print(f"\n🗑️  清理临时文件: {test_file}")
        except:
            pass

if __name__ == "__main__":
    main()