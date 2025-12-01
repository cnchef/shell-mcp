#!/usr/bin/env python3
"""
简单的STDIO模式测试脚本
"""

import subprocess
import json
import sys

def test_stdio_mode():
    """测试stdio模式"""
    print("🧪 启动STDIO模式测试...")

    # 启动服务器进程
    server_process = subprocess.Popen(
        [sys.executable, "shell_mcp_server.py", "--mode", "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        # 测试命令列表
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

        # 发送测试命令
        for i, command in enumerate(test_commands):
            print(f"\n📤 发送命令 {i+1}:")
            print(json.dumps(command, ensure_ascii=False, indent=2))

            # 发送JSON命令
            command_json = json.dumps(command, ensure_ascii=False) + '\n'
            server_process.stdin.write(command_json)
            server_process.stdin.flush()

            # 读取响应
            response_line = server_process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                print(f"📥 收到响应:")
                print(json.dumps(response, ensure_ascii=False, indent=2))
            else:
                print("❌ 没有收到响应")

        print("\n✅ 测试完成！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
    finally:
        # 关闭服务器
        server_process.stdin.close()
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    test_stdio_mode()