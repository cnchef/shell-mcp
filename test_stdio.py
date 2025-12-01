#!/usr/bin/env python3
"""
修复版的STDIO模式测试脚本
专门解决缓冲区和输入问题
"""

import asyncio
import json
import subprocess
import sys
import time
import os

class StdioTesterFixed:
    def __init__(self, server_command):
        self.server_process = None
        self.server_command = server_command

    def start_server(self):
        """启动MCP服务器"""
        try:
            # 确保stdin是非缓冲的
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            self.server_process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                env=env,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            print(f"✅ MCP服务器已启动 (PID: {self.server_process.pid})")

            # 等待服务器启动
            time.sleep(1)
            return True
        except Exception as e:
            print(f"❌ 启动服务器失败: {e}")
            return False

    def send_request(self, request, timeout=10):
        """发送JSON-RPC请求并获取响应"""
        if not self.server_process:
            raise Exception("服务器未启动")

        try:
            # 发送请求
            request_json = json.dumps(request, ensure_ascii=False) + '\n'
            print(f"📤 发送请求: {request_json.strip()[:100]}...")

            # 写入stdin并立即刷新
            self.server_process.stdin.write(request_json)
            self.server_process.stdin.flush()

            # 读取响应，带超时
            response_line = self._read_line_with_timeout(timeout)
            if not response_line:
                raise Exception("读取响应超时")

            response = json.loads(response_line.strip())
            print(f"📥 收到响应: {json.dumps(response, ensure_ascii=False, indent=2)[:200]}...")

            return response

        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return {"error": str(e)}

    def _read_line_with_timeout(self, timeout=10):
        """带超时的行读取"""
        start_time = time.time()
        response_line = ""

        while time.time() - start_time < timeout:
            if self.server_process.stdout.readable():
                char = self.server_process.stdout.read(1)
                if char:
                    response_line += char
                    if char == '\n':
                        return response_line
                else:
                    break
            time.sleep(0.01)  # 短暂休眠避免CPU占用过高

        return response_line if response_line else None

    def test_basic_sequence(self):
        """基本测试序列"""
        print("\n🚀 开始基本测试序列...")

        test_requests = [
            # 1. 初始化
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 1
            },
            # 2. 获取工具列表
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            },
            # 3. 执行简单命令
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
            # 4. 执行ls命令
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

        for i, request in enumerate(test_requests):
            print(f"\n📋 测试 {i+1}/{len(test_requests)}")
            response = self.send_request(request)
            if "error" in response:
                print(f"❌ 测试 {i+1} 失败")
            else:
                print(f"✅ 测试 {i+1} 成功")

    def interactive_mode(self):
        """交互模式"""
        print("\n🎮 进入交互模式")
        print("输入命令将作为参数传递给execute_command工具")
        print("输入 'quit' 退出")
        print("-" * 50)

        request_id = 100

        while True:
            try:
                command = input("\n请输入命令: ").strip()
                if command.lower() == 'quit':
                    break
                if not command:
                    continue

                request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "execute_command",
                        "arguments": {
                            "command": command
                        }
                    },
                    "id": request_id
                }

                request_id += 1
                self.send_request(request)

            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")

    def cleanup(self):
        """清理资源"""
        if self.server_process:
            print("\n🧹 清理资源...")
            try:
                self.server_process.stdin.close()
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                    print("✅ 服务器正常关闭")
                except subprocess.TimeoutExpired:
                    print("⚠️ 服务器未响应，强制关闭")
                    self.server_process.kill()
                    self.server_process.wait()
            except Exception as e:
                print(f"⚠️ 关闭服务器时出错: {e}")

def main():
    print("🧪 Shell MCP Server - STDIO模式测试")
    print("=" * 60)

    # 检查服务器文件是否存在
    if not os.path.exists("shell_mcp_server.py"):
        print("❌ 找不到 shell_mcp_server.py 文件")
        print("请在包含 shell_mcp_server.py 的目录中运行此脚本")
        return

    # 服务器命令
    server_command = [
        sys.executable,
        "shell_mcp_server.py",
        "--mode", "stdio",
        "--log-level", "INFO"
    ]

    tester = StdioTesterFixed(server_command)

    try:
        # 启动服务器
        if not tester.start_server():
            print("❌ 无法启动服务器，退出")
            return

        # 选择测试模式
        print("\n" + "=" * 40)
        print("选择测试模式:")
        print("1. 自动测试序列")
        print("2. 交互模式")
        print("3. 两者都运行")
        print("=" * 40)

        choice = input("请选择 (1-3): ").strip()

        if choice == "1":
            tester.test_basic_sequence()
        elif choice == "2":
            tester.interactive_mode()
        elif choice == "3":
            tester.test_basic_sequence()
            tester.interactive_mode()
        else:
            print("❌ 无效选择，运行自动测试")
            tester.test_basic_sequence()

    except KeyboardInterrupt:
        print("\n👋 用户中断")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main()