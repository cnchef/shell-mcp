#!/usr/bin/env python3
"""
Shell MCP Server - 基于MCP的强大Shell接口
基于 Model Context Protocol (MCP) 的 Python 实现
支持本地和远程命令执行，带有命令黑白名单功能
支持 stdio 和 SSE/HTTP 模式
"""

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import argparse
import threading
from datetime import datetime

try:
    import paramiko

    SSH_AVAILABLE = True
except ImportError:
    libs_lst = ["bcrypt==3.2.0", "cffi==1.16.0", "cryptography==36.0.2", "paramiko>=3.4.0", "pycparser==2.21", "pynacl==1.5.0"]
    print("install %s" % (libs_lst))
    for libs_ in libs_lst:
        print(libs_)
        os.system("omsa_py -m pip install %s" % (libs_))
    import paramiko

    #
    SSH_AVAILABLE = False
    print("Warning: paramiko not installed. SSH功能将不可用。安装命令: pip install paramiko", file=sys.stderr)


##############################################################################################################
# 获取本文件完整路径名
if "__file__" in locals():
    script_path_name = os.path.realpath(__file__)
else:
    script_path_name = os.path.realpath(sys.argv[0])
##############################################################################################################
script_path = os.path.dirname(script_path_name)
script_name = os.path.basename(script_path_name)
script_pid_path = "{}.pid".format(script_path_name)
sys.path.append(os.path.dirname(script_path))


# 配置日志
def setup_logging(log_file: str = "logs.log", level: str = "INFO"):
    """设置日志配置"""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 创建日志格式
    formatter = logging.Formatter("%(levelname)-5.5s %(asctime)s - [PID:%(process)d] [code:%(lineno)d] - %(message)s")

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # 控制台处理器（仅错误信息）
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 配置根日志器
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


@dataclass
class ExecuteResult:
    """命令执行结果"""

    stdout: str
    stderr: str
    exit_code: int
    execution_time: float


class CommandFilter:
    """命令过滤器 - 支持黑白名单"""

    def __init__(self, config: Dict[str, Any]):
        self.whitelist_patterns = config.get("whitelist", [])
        self.blacklist_patterns = config.get("blacklist", [])
        self.whitelist_enabled = bool(self.whitelist_patterns)
        self.logger = logging.getLogger(__name__ + ".CommandFilter")

        # 逐个编译正则表达式，避免单个失败导致全部失效
        # 使用 (pattern, regex) 元组列表保存，确保模式与正则一一对应
        self.whitelist_rules = []
        self.blacklist_rules = []
        
        # 编译白名单正则
        for pattern in self.whitelist_patterns:
            try:
                regex = re.compile(pattern)
                self.whitelist_rules.append((pattern, regex))
            except re.error as e:
                self.logger.error(f"白名单正则表达式编译失败: {pattern}, 错误: {e}")
        
        # 编译黑名单正则
        for pattern in self.blacklist_patterns:
            try:
                regex = re.compile(pattern)
                self.blacklist_rules.append((pattern, regex))
            except re.error as e:
                self.logger.error(f"黑名单正则表达式编译失败: {pattern}, 错误: {e}")
        
        # 记录初始化状态
        self.logger.info(f"命令过滤器初始化完成 - 黑名单规则数: {len(self.blacklist_rules)}/{len(self.blacklist_patterns)}, "
                        f"白名单规则数: {len(self.whitelist_rules)}/{len(self.whitelist_patterns)}, "
                        f"白名单启用: {self.whitelist_enabled}")
        
        # 如果黑名单编译失败过多，发出警告
        if len(self.blacklist_rules) < len(self.blacklist_patterns):
            failed_count = len(self.blacklist_patterns) - len(self.blacklist_rules)
            self.logger.warning(f"警告: {failed_count} 个黑名单规则编译失败，可能导致安全风险！")

    def _extract_main_command(self, command: str) -> str:
        """
        提取命令的主要部分（去除变量赋值、注释等）
        例如: "VAR=value rm -rf /" -> "rm -rf /"
        """
        # 去除前导空白
        command = command.strip()
        
        # 如果命令以变量赋值开头，提取实际命令部分
        # 例如: "VAR=value command" -> "command"
        if '=' in command and not command.startswith('='):
            # 检查是否是变量赋值（简单判断：等号前是标识符，等号后是值）
            parts = command.split(None, 1)  # 按空白分割，最多分割1次
            if len(parts) > 1 and '=' in parts[0] and not parts[0].startswith('='):
                # 可能是变量赋值，提取后面的命令部分
                command = parts[1] if len(parts) > 1 else command
        
        # 去除注释（# 后面的内容）
        if '#' in command:
            command = command.split('#')[0].strip()
        
        return command.strip()

    def check_dangerous_command(self, command: str) -> tuple[bool, str]:
        """
        检查是否为需要确认的危险命令（如 rm 删除命令）
        返回: (是否需要确认, 危险命令类型)
        """
        main_command = self._extract_main_command(command)
        
        # 检查是否为 rm 删除命令（排除帮助、版本等非删除操作）
        # 匹配: rm 后面跟参数或路径，但排除 --help, --version, -h, -v 等
        rm_pattern = re.compile(r'^\s*rm\s+')
        if rm_pattern.match(main_command):
            # 排除帮助和版本查询
            help_patterns = ['--help', '--version', '-h', '-v', '--usage']
            command_lower = main_command.lower()
            for help_pattern in help_patterns:
                if help_pattern in command_lower:
                    return False, ""
            
            # 匹配到 rm 删除命令，需要确认
            self.logger.warning(f"检测到危险删除命令，需要用户确认: {command[:200]}")
            return True, "删除命令"
        
        return False, ""

    def is_allowed(self, command: str) -> tuple[bool, str, Optional[str]]:
        """
        检查命令是否被允许执行
        返回: (是否允许, 原因, 匹配的规则)
        """
        # 提取命令的主要部分
        main_command = self._extract_main_command(command)
        
        # 检查黑名单 - 优先检查命令开头
        for pattern, regex in self.blacklist_rules:
            try:
                # 检查模式是否以 ^ 开头（锚定命令开头）
                if pattern.startswith('^'):
                    # 模式已经锚定开头，使用 match() 检查命令开头
                    if regex.match(main_command):
                        self.logger.warning(f"命令被黑名单拦截（开头匹配）: 规则={pattern}, 命令={command[:200]}")
                        return False, f"命令被黑名单规则拒绝: {pattern}", pattern
                else:
                    # 对于不以 ^ 开头的模式，先尝试匹配命令开头（更精确）
                    # 使用 match() 检查命令开头是否匹配
                    if regex.match(main_command):
                        self.logger.warning(f"命令被黑名单拦截（开头匹配）: 规则={pattern}, 命令={command[:200]}")
                        return False, f"命令被黑名单规则拒绝: {pattern}", pattern
                    # 如果开头不匹配，检查是否在命令中（用于检查命令串联等情况，如 "; rm -rf"）
                    if regex.search(main_command):
                        self.logger.warning(f"命令被黑名单拦截（内容匹配）: 规则={pattern}, 命令={command[:200]}")
                        return False, f"命令被黑名单规则拒绝: {pattern}", pattern
            except Exception as e:
                self.logger.error(f"黑名单匹配失败: 规则={pattern}, 错误={e}, 命令={command[:200]}")

        # 如果启用了白名单，检查白名单
        if self.whitelist_enabled:
            for pattern, regex in self.whitelist_rules:
                try:
                    if regex.match(main_command) or regex.search(main_command):
                        self.logger.debug(f"命令通过白名单检查: 规则={pattern}, 命令={command[:200]}")
                        return True, "命令通过白名单检查", None
                except Exception as e:
                    self.logger.error(f"白名单匹配失败: 规则={pattern}, 错误={e}, 命令={command[:200]}")
            self.logger.warning(f"命令不在白名单中: 命令={command[:200]}")
            return False, "命令不在白名单中", None

        self.logger.debug(f"命令通过过滤检查: 命令={command[:200]}")
        return True, "命令通过过滤检查", None


class SessionManager:
    """会话管理器"""

    def __init__(self, session_timeout: int = 1200):  # 20分钟超时
        self.sessions: Dict[str, Dict] = {}
        self.session_timeout = session_timeout
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__ + ".SessionManager")

    def get_session(self, session_id: str, host: Optional[str] = None, username: Optional[str] = None):
        """获取或创建会话"""
        with self.lock:
            current_time = time.time()

            # 清理过期会话
            expired_sessions = []
            for sid, session_data in self.sessions.items():
                if current_time - session_data["last_used"] > self.session_timeout:
                    expired_sessions.append(sid)

            for sid in expired_sessions:
                self._cleanup_session(sid)

            # 获取或创建会话
            if session_id not in self.sessions:
                self.sessions[session_id] = {"host": host, "username": username, "ssh_client": None, "created": current_time, "last_used": current_time, "local_env": {}}
                self.logger.info(f"创建新会话: {session_id}")
            else:
                self.sessions[session_id]["last_used"] = current_time

            return self.sessions[session_id]

    def _cleanup_session(self, session_id: str):
        """清理会话资源"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session.get("ssh_client"):
                try:
                    session["ssh_client"].close()
                except:
                    pass
            del self.sessions[session_id]
            self.logger.info(f"会话 {session_id} 已清理")


class SSHExecutor:
    """SSH命令执行器"""

    @staticmethod
    def create_ssh_client(host: str, username: str, key_file: Optional[str] = None, password: Optional[str] = None, port: int = 22) -> paramiko.SSHClient:
        """创建SSH客户端"""
        if not SSH_AVAILABLE:
            raise Exception("SSH功能不可用，请安装paramiko: pip install paramiko")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 扩展用户路径
            if key_file:
                key_file = os.path.expanduser(key_file)

            connect_kwargs = {"hostname": host, "port": port, "username": username, "allow_agent": False, "timeout": 30}

            if key_file and os.path.exists(key_file):
                connect_kwargs["key_filename"] = key_file
            elif password:
                connect_kwargs["password"] = password
            else:
                # 尝试使用默认密钥文件
                default_keys = [os.path.expanduser("~/.ssh/id_rsa"), os.path.expanduser("~/.ssh/id_ed25519"), os.path.expanduser("~/.ssh/id_ecdsa")]

                for default_key in default_keys:
                    if os.path.exists(default_key):
                        connect_kwargs["key_filename"] = default_key
                        break

            client.connect(**connect_kwargs)
            return client
        except Exception as e:
            client.close()
            raise Exception(f"SSH连接失败: {str(e)}")

    @staticmethod
    async def execute_command(ssh_client: paramiko.SSHClient, command: str, env: Optional[Dict[str, str]] = None) -> ExecuteResult:
        """在SSH连接上执行命令"""
        start_time = time.time()

        try:
            # 准备环境变量
            env_str = ""
            if env:
                env_pairs = [f"export {k}='{v}'" for k, v in env.items()]
                env_str = "; ".join(env_pairs) + "; " if env_pairs else ""

            full_command = f"{env_str}{command}"

            # 异步执行命令
            def _execute():
                stdin, stdout, stderr = ssh_client.exec_command(full_command)
                stdout_data = stdout.read().decode("utf-8", errors="replace")
                stderr_data = stderr.read().decode("utf-8", errors="replace")
                exit_code = stdout.channel.recv_exit_status()
                return stdout_data, stderr_data, exit_code

            loop = asyncio.get_event_loop()
            stdout_data, stderr_data, exit_code = await loop.run_in_executor(None, _execute)

            execution_time = time.time() - start_time

            return ExecuteResult(stdout=stdout_data, stderr=stderr_data, exit_code=exit_code, execution_time=execution_time)

        except Exception as e:
            execution_time = time.time() - start_time
            return ExecuteResult(stdout="", stderr=f"SSH命令执行失败: {str(e)}", exit_code=1, execution_time=execution_time)


class LocalExecutor:
    """本地命令执行器"""

    @staticmethod
    async def execute_command(command: str, env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None) -> ExecuteResult:
        """本地执行命令"""
        start_time = time.time()

        try:
            # 准备环境变量
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)

            # 异步执行命令
            process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=exec_env, cwd=cwd)

            stdout_data, stderr_data = await process.communicate()

            execution_time = time.time() - start_time

            return ExecuteResult(
                stdout=stdout_data.decode("utf-8", errors="replace"),
                stderr=stderr_data.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0, 
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return ExecuteResult(stdout="", stderr=f"本地命令执行失败: {str(e)}", exit_code=1, execution_time=execution_time)


class TerminalMCPServer:
    """Shell MCP Server 主类"""

    def __init__(self, config_file: str = "config.json"):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_file)
        self.command_filter = CommandFilter(self.config.get("command_filter", {}))
        self.session_manager = SessionManager(self.config.get("session_timeout", 1200))

        # 支持的工具
        self.tools = {
            "execute_command": {
                "name": "execute_command",
                "description": "在本地或远程主机上执行命令",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要执行的命令"},
                        "host": {"type": "string", "description": "远程主机地址（可选，不提供则本地执行）"},
                        "username": {"type": "string", "description": "SSH用户名（远程执行时必需）"},
                        "password": {"type": "string", "description": "SSH密码（可选）"},
                        "key_file": {"type": "string", "description": "SSH私钥文件路径（可选）"},
                        "port": {"type": "integer", "description": "SSH端口（默认22）"},
                        "session": {"type": "string", "description": "会话名称（默认'default'）"},
                        "env": {"type": "object", "description": "环境变量"},
                        "cwd": {"type": "string", "description": "工作目录（仅本地执行）"},
                        "force_execute": {"type": "boolean", "description": "强制执行危险命令（跳过安全检查，默认false）"},
                    },
                    "required": ["command"],
                },
            },
            "get_tools": {
                "name": "get_tools",
                "description": "获取服务器支持的所有工具列表",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.logger.info(f"加载配置文件: {config_file}")
                    return config
            else:
                # 创建默认配置
                default_config = {
                    "session_timeout": 1200,
                    "command_filter": {
                        "blacklist": [
                            # 危险删除（锚定命令开头，允许前导空白）
                            "^\\s*rm\\s+-rf\\s+/(\\s|$)",
                            "^\\s*rm\\s+-rf\\s+/home",
                            "^\\s*rm\\s+-rf\\s+/etc",
                            "^\\s*rm\\s+-rf\\s+/boot",
                            "^\\s*rm\\s+-rf\\s+/var",
                            "^\\s*rm\\s+-rf\\s+/root",
                            "^\\s*rm\\s+-rf\\s+/usr",
                            "^\\s*rm\\s+-rf\\s+/lib",
                            "^\\s*rm\\s+-rf\\s+/opt",
                            "^\\s*rm\\s+-rf\\s+--no-preserve-root",
                            "^\\s*rm\\s+-fr\\s+--no-preserve-root",
                            # 格式化 / 分区 / 写盘（锚定命令开头，允许前导空白）
                            "^\\s*mkfs\\.",
                            "^\\s*dd\\s+.*of=/dev/",
                            "^\\s*parted",
                            "^\\s*fdisk",
                            "^\\s*mklabel",
                            "^\\s*mkswap",
                            "^\\s*wipefs",
                            # fork bomb（锚定命令开头，允许前导空白）
                            "^\\s*:\\(\\)\\{\\s*:\\|:\\s*;\\s*\\};:",
                            # 系统关机 / 重启（锚定命令开头，允许前导空白）
                            "^\\s*shutdown",
                            "^\\s*reboot",
                            "^\\s*halt",
                            "^\\s*poweroff",
                            "^\\s*init\\s+",
                            # 删除计划任务（锚定命令开头，允许前导空白）
                            "^\\s*crontab\\s+-r",
                            # 用户与密码（锚定命令开头，允许前导空白）
                            "^\\s*userdel",
                            "^\\s*passwd\\s+root",
                            # 权限与所有权（锚定命令开头，允许前导空白）
                            "^\\s*chmod\\s+777\\s+/",
                            "^\\s*chown\\s+.*:/",
                            # 覆盖系统文件（锚定命令开头，允许前导空白）
                            "^\\s*>\\s*/dev/",
                            "^\\s*>\\s*/etc/",
                            "^\\s*>\\s*/boot/",
                            "^\\s*>\\s*/root/",
                            # 网络下载 + 执行（锚定命令开头，允许前导空白）
                            "^\\s*curl.*\\|.*sh",
                            "^\\s*wget.*\\|.*sh",
                            # 危险进程杀掉（锚定命令开头，允许前导空白）
                            "^\\s*killall",
                            "^\\s*pkill",
                            "^\\s*kill\\s+-9\\s+1",
                            "^\\s*kill\\s+-9\\s+[0-9]+",
                            # 拼接命令防绕过（检查命令中是否包含）
                            ".*;\\s*rm\\s+-rf",
                            ".*&&\\s*rm\\s+-rf",
                            ".*\\|\\s*sh\\s*$",
                        ],
                        "whitelist": ["ifconfig", "ip", "df"],
                    },
                    "ssh": {"default_key_file": "~/.ssh/id_rsa", "timeout": 30, "max_connections": 10},
                    "logging": {"level": "INFO", "file": "terminal_mcp.log"},
                }

                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)

                self.logger.info(f"创建默认配置文件: {config_file}")
                return default_config

        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            return {}

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理MCP请求"""
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")

            self.logger.debug(f"处理请求: {method}")

            if method == "initialize":
                response = await self._handle_initialize(params)
            elif method == "tools/list":
                response = await self._handle_list_tools()
            elif method == "tools/call":
                response = await self._handle_call_tool(params)
            elif method == "ping":
                # ping 是通知方法，用于保持连接活跃
                # 根据 JSON-RPC 2.0 规范，通知请求（没有 id）不需要响应
                # 但如果有 id，应该返回响应
                if request_id is not None:
                    response = await self._handle_ping(params)
                else:
                    # 通知请求（没有 id），不返回响应
                    self.logger.debug("收到 ping 通知请求（无 id），不返回响应")
                    return None
            else:
                response = {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method}"}}

            if request_id is not None:
                response["id"] = request_id

            return response

        except Exception as e:
            self.logger.error(f"处理请求异常: {e}")
            error_response = {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
            if request.get("id") is not None:
                error_response["id"] = request["id"]
            return error_response

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理初始化请求"""
        return {
            "jsonrpc": "2.0",
            "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "shell-mcp-server", "version": "1.0.0"}},
        }

    async def _handle_list_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        return {"jsonrpc": "2.0", "result": {"tools": list(self.tools.values())}}

    async def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 ping 请求 - 用于保持连接活跃"""
        # ping 请求通常用于保持连接活跃，返回简单的成功响应
        return {
            "jsonrpc": "2.0",
            "result": {"status": "pong", "timestamp": int(time.time())}
        }

    async def _handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "execute_command" or tool_name == "execute":
            result = await self._execute_command(arguments)
            return {"jsonrpc": "2.0", "result": result}
        elif tool_name == "get_tools":
            return {"jsonrpc": "2.0", "result": {"tools": list(self.tools.values())}}
        else:
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"}}

    async def _execute_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行命令工具"""
        try:
            command = args["command"]
            host = args.get("host")
            username = args.get("username")
            password = args.get("password")
            key_file = args.get("key_file")
            port = args.get("port", 22)
            session_id = args.get("session", "default")
            env = args.get("env", {})
            cwd = args.get("cwd")

            force_execute = args.get("force_execute", False)
            self.logger.info(f"[命令执行请求] 会话ID={session_id} Host={host or 'local'} 命令={command} 强制执行={force_execute}")

            # 检查是否为需要确认的危险命令（如 rm 删除命令）
            if not force_execute:
                needs_confirmation, danger_type = self.command_filter.check_dangerous_command(command)
                if needs_confirmation:
                    self.logger.warning(f"[危险命令拦截] 会话ID={session_id} Host={host or 'local'} 类型={danger_type} 命令={command}")
                    warning_msg = f"""⚠️ **危险命令警告**

检测到危险操作：`{command}`

**命令类型**: {danger_type}
**风险说明**: 此操作可能导致数据丢失或系统损坏

**如需执行此命令，请确认后使用 `force_execute=true` 参数重新提交。**

示例：
```json
{{
  "command": "{command}",
  "force_execute": true
}}
```"""
                    return {
                        "content": [{"type": "text", "text": warning_msg}],
                        "requires_confirmation": True,
                        "dangerous_command": command,
                        "isError": False
                    }

            # 检查命令是否被允许（除非强制执行）
            if force_execute:
                self.logger.warning(f"[强制执行模式] 会话ID={session_id} Host={host or 'local'} 跳过安全检查，命令={command}")
            else:
                allowed, reason, matched_rule = self.command_filter.is_allowed(command)
                self.logger.debug(f"[命令过滤结果] 允许={allowed} 原因={reason} 匹配规则={matched_rule}")
                
                if not allowed:
                    self.logger.warning(f"[命令拒绝] 会话ID={session_id} Host={host or 'local'} 规则={matched_rule or 'N/A'} 原因={reason} 命令={command}")
                    return {
                        "content": [{"type": "text", "text": f"命令被拒绝执行: {reason}"}],
                        "isError": True
                    }

            # 获取会话
            session = self.session_manager.get_session(session_id, host, username)

            # 执行命令
            if host:
                # 远程执行 - 修复: 检查username不为None
                if not username:
                    return {
                        "content": [{"type": "text", "text": "远程执行需要提供username参数"}],
                        "isError": True
                    }
                result = await self._execute_remote_command(session, command, host, username, password, key_file, port, env)
            else:
                # 本地执行
                result = await self._execute_local_command(session, command, env, cwd)

            # 格式化输出
            output_parts = []

            # 如果是 bytes，先解码
            stdout_text = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else result.stdout
            stderr_text = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else result.stderr
            logging.info(f"stdout_text:{stdout_text} stderr_text:{stderr_text}")
            if stdout_text.strip():
                output_parts.append(f"标准输出:\n{stdout_text}")
            if stderr_text.strip():
                output_parts.append(f"标准错误:\n{stderr_text}")

            output_parts.append(f"退出码: {result.exit_code}")
            output_parts.append(f"执行时间: {result.execution_time:.2f}秒")

            # 返回符合 MCP 协议的响应格式
            return {
                "content": [{"type": "text", "text": "\n\n".join(output_parts)}],
                "isError": result.exit_code != 0
            }

        except Exception as e:
            self.logger.error(f"命令执行失败: {e}")
            return {
                "content": [{"type": "text", "text": f"命令执行失败: {str(e)}"}],
                "isError": True
            }

    async def _execute_remote_command(
        self, session: Dict, command: str, host: str, username: str, password: Optional[str], key_file: Optional[str], port: int, env: Dict[str, str]
    ) -> ExecuteResult:
        """执行远程命令"""
        try:
            # 获取或创建SSH连接
            ssh_client = session.get("ssh_client")
            if not ssh_client or not ssh_client.get_transport() or not ssh_client.get_transport().is_active():
                ssh_client = SSHExecutor.create_ssh_client(host, username, key_file, password, port)
                session["ssh_client"] = ssh_client
                self.logger.info(f"创建SSH连接: {username}@{host}:{port}")

            return await SSHExecutor.execute_command(ssh_client, command, env)

        except Exception as e:
            self.logger.error(f"远程命令执行失败: {e}")
            return ExecuteResult("", f"远程命令执行失败: {str(e)}", 1, 0)

    async def _execute_local_command(self, session: Dict, command: str, env: Dict[str, str], cwd: Optional[str]) -> ExecuteResult:
        """执行本地命令"""
        # 合并会话环境变量
        session_env = session.get("local_env", {})
        session_env.update(env)

        result = await LocalExecutor.execute_command(command, session_env, cwd)

        # 更新会话环境变量
        session["local_env"] = session_env

        return result


class MCPTransport:
    """MCP传输层基类"""

    def __init__(self, server: TerminalMCPServer):
        self.server = server
        self.logger = logging.getLogger(__name__ + ".Transport")

    async def start(self):
        """启动传输"""
        raise NotImplementedError


# 不可用
class StdioTransport(MCPTransport):
    """标准输入输出传输"""

    def __init__(self, server: TerminalMCPServer):
        super().__init__(server)
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """启动stdio传输"""
        self.logger.info("启动stdio传输模式")
        self.logger.info("按 Ctrl+C 优雅退出服务器...")
        self.logger.info("等待JSON-RPC 2.0请求 (每行一个JSON对象)...")

        # 设置stdin为非缓冲模式
        import threading
        import queue

        # 创建一个队列来接收输入
        input_queue = queue.Queue()

        def input_reader():
            """在单独线程中读取输入"""
            try:
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    input_queue.put(line)
            except Exception as e:
                self.logger.error(f"输入读取错误: {e}")

        # 启动输入读取线程
        input_thread = threading.Thread(target=input_reader, daemon=True)
        input_thread.start()

        try:
            while not self.shutdown_event.is_set():
                try:
                    # 非阻塞地检查输入队列
                    try:
                        line = input_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue

                    if not line:
                        self.logger.debug("收到空行，继续等待...")
                        continue

                    line = line.strip()
                    if not line:
                        self.logger.debug("收到空白行，继续等待...")
                        continue

                    self.logger.info(f"收到输入: {line[:100]}...")

                    # 解析JSON请求
                    try:
                        request = json.loads(line)
                        self.logger.debug(f"JSON解析成功: {request.get('method', 'unknown')}")
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON解析错误: {e}")
                        error_response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {str(e)}"}}
                        print(json.dumps(error_response, ensure_ascii=False))
                        sys.stdout.flush()
                        continue

                    # 处理请求
                    response = await self.server.handle_request(request)

                    if response:  # 只有当响应不为None时才输出
                        # 输出响应
                        response_json = json.dumps(response, ensure_ascii=False)
                        print(response_json)
                        sys.stdout.flush()
                        self.logger.info(f"发送响应: {response_json[:100]}...")

                except KeyboardInterrupt:
                    self.logger.info("收到键盘中断信号，开始关闭...")
                    break
                except Exception as e:
                    self.logger.error(f"处理请求时发生异常: {e}", exc_info=True)
                    continue

        except Exception as e:
            self.logger.error(f"Stdio传输模式异常: {e}", exc_info=True)
        finally:
            await self._cleanup()

    async def _cleanup(self):
        """清理资源"""
        self.logger.info("stdio传输模式结束")

    def shutdown(self):
        """触发关闭事件"""
        self.shutdown_event.set()


class SSETransport(MCPTransport):
    """
    MCP Streamable HTTP Transport 实现
    基于 MCP 协议 规范
    支持 HTTP POST + 可选 SSE 的标准 MCP 传输
    """

    def __init__(self, server: TerminalMCPServer, host: str = "0.0.0.0", port: int = 8000):
        super().__init__(server)
        self.host = host
        self.port = port
        self.active_streams = {}  # 存储活跃的 SSE 流
        self.runner = None
        self.site = None
        self.shutdown_event = asyncio.Event()

    async def start(self):
        try:
            from aiohttp import web
        except ImportError:
            self.logger.error("需要安装 aiohttp: pip install aiohttp")
            return

        self.logger.info(f"启动 MCP Streamable HTTP Transport: http://{self.host}:{self.port}")

        app = web.Application()

        # MCP 标准端点
        app.router.add_post("/message", self._handle_mcp_message)  # 标准 MCP 消息端点
        app.router.add_get("/message", self._handle_get_request)  # 支持 GET 请求
        app.router.add_options("/message", self._handle_options)

        # 兼容性端点
        app.router.add_post("/mcp", self._handle_mcp_message)  # 兼容旧版本
        app.router.add_get("/mcp", self._handle_get_request)
        app.router.add_post("/sse", self._handle_mcp_message)  # 兼容 Cherry Studio
        app.router.add_get("/sse", self._handle_get_request)  # Cherry Studio GET 请求
        app.router.add_options("/mcp", self._handle_options)
        app.router.add_options("/sse", self._handle_options)

        app.router.add_get("/", self._handle_server_info)

        app.router.add_post("/reset", self._handle_reset_connection)
        app.router.add_get("/reset", self._handle_reset_connection)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        self.logger.info("MCP 服务器启动完成:")
        self.logger.info(f"  标准端点: http://{self.host}:{self.port}/message")
        self.logger.info(f"  兼容端点: http://{self.host}:{self.port}/mcp")
        self.logger.info(f"  兼容端点: http://{self.host}:{self.port}/sse")
        self.logger.info("按 Ctrl+C 优雅退出服务器...")

        try:
            while not self.shutdown_event.is_set():
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=1.0)
                    break
                except asyncio.TimeoutError:
                    continue
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，开始优雅关闭...")
        finally:
            await self._cleanup()

    async def _cleanup(self):
        """清理资源"""
        self.logger.info("开始清理资源...")

        # 清理活跃流
        if self.active_streams:
            self.logger.info(f"关闭 {len(self.active_streams)} 个活跃连接...")
            for stream_id, stream in list(self.active_streams.items()):
                try:
                    if hasattr(stream, "transport") and stream.transport and not stream.transport.is_closing():
                        await stream.write_eof()
                    self.logger.debug(f"关闭连接: {stream_id}")
                except Exception as e:
                    self.logger.debug(f"关闭连接 {stream_id} 时出错: {e}")
            self.active_streams.clear()

        # 关闭服务器
        if self.site:
            try:
                await self.site.stop()
                self.logger.info("HTTP 服务器已停止")
            except Exception as e:
                self.logger.warning(f"停止 HTTP 服务器时出错: {e}")

        if self.runner:
            try:
                await self.runner.cleanup()
                self.logger.info("应用运行器已清理")
            except Exception as e:
                self.logger.warning(f"清理应用运行器时出错: {e}")

        self.logger.info("资源清理完成")

    def shutdown(self):
        """触发关闭事件"""
        self.shutdown_event.set()

    async def _handle_options(self, request):
        """处理 CORS 预检请求"""
        from aiohttp import web

        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
                "Access-Control-Max-Age": "86400",
            },
        )

    async def _handle_get_request(self, request):
        """处理 GET 请求 - 建立 SSE 连接"""
        from aiohttp import web

        self.logger.info(f"建立 SSE 连接: {request.remote}")

        # 创建 SSE 响应
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
                "Access-Control-Allow-Credentials": "true",
                "X-Accel-Buffering": "no",
            },
        )

        await response.prepare(request)

        connection_id = None
        try:
            # 存储连接
            connection_id = f"{request.remote}_{time.time()}"
            self.active_streams[connection_id] = response
            self.logger.info(f"SSE 连接已建立并存储: {connection_id}")

            # 发送连接确认事件
            try:
                await self._send_sse_event(response, "connected", {"status": "connected", "timestamp": int(time.time()), "connection_id": connection_id})
            except Exception as e:
                self.logger.warning(f"发送连接确认事件失败: {e}，但继续处理")

            # 发送 endpoint 事件（使用标准 UUID 格式）
            try:
                session_id = str(uuid.uuid4())
                endpoint_data = f"/message?sessionId={session_id}"
                await self._send_sse_event(response, "endpoint", endpoint_data)
            except Exception as e:
                self.logger.warning(f"发送 endpoint 事件失败: {e}，但继续处理")

            # 发送服务器信息
            try:
                server_info = {
                    "jsonrpc": "2.0",
                    "id": "server_info",
                    "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "shell-mcp-server", "version": "1.0.0"}},
                }
                await self._send_sse_message(response, server_info)
            except Exception as e:
                self.logger.warning(f"发送服务器信息失败: {e}，但继续处理")
                # 如果发送失败，可能是连接已关闭，但让心跳循环来处理清理
            
            # 不在这里检查连接状态，因为连接可能刚建立，状态检查可能不准确
            # 让心跳循环和实际的消息发送来判断连接是否真的关闭
            self.logger.info(f"SSE 连接 {connection_id} 初始化完成，进入心跳循环")

            # 保持连接活跃，发送心跳
            ping_count = 0
            while True:
                try:
                    # 等待一段时间后发送心跳
                    await asyncio.sleep(30)
                    ping_count += 1

                    # 尝试发送心跳，如果失败则说明连接已关闭
                    # 不预先检查连接状态，让实际的发送操作来判断
                    ping_data = {"type": "ping", "count": ping_count, "timestamp": int(time.time())}
                    await self._send_sse_event(response, "ping", ping_data)
                    self.logger.debug(f"SSE 心跳 {ping_count} 发送成功: {connection_id}")

                except asyncio.CancelledError:
                    self.logger.info(f"SSE 连接被取消: {connection_id}")
                    break
                except (ConnectionError, OSError, RuntimeError) as e:
                    error_msg = str(e).lower()
                    if "closing" in error_msg or "closed" in error_msg:
                        self.logger.info(f"SSE 连接 {connection_id} 已关闭，退出心跳循环")
                    else:
                        self.logger.warning(f"SSE 心跳发送失败（连接错误）: {e}")
                    break
                except Exception as e:
                    self.logger.warning(f"SSE 心跳发送失败: {e}")
                    break

        except Exception as e:
            self.logger.error(f"SSE 连接处理失败: {e}")
        finally:
            # 清理连接
            if connection_id in self.active_streams:
                del self.active_streams[connection_id]
            self.logger.info(f"SSE 连接断开: {request.remote}")

        return response

    async def _handle_server_info(self, request):
        """返回 MCP 服务器信息"""
        from aiohttp import web

        # 符合 MCP 协议的服务器信息
        info = {
            "jsonrpc": "2.0",
            "id": "server_info",
            "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "shell-mcp-server", "version": "1.0.0"}},
        }

        return web.json_response(info, headers={"Access-Control-Allow-Origin": "*"})

    async def _handle_reset_connection(self, request):
        """重置连接状态"""
        from aiohttp import web

        self.logger.info(f"重置连接状态: {request.remote}")

        # 清理所有活跃连接
        if self.active_streams:
            self.logger.info(f"清理 {len(self.active_streams)} 个活跃连接")
            for stream_id, stream in list(self.active_streams.items()):
                try:
                    if hasattr(stream, "transport") and stream.transport and not stream.transport.is_closing():
                        await stream.write_eof()
                except Exception as e:
                    self.logger.debug(f"关闭连接 {stream_id} 时出错: {e}")
            self.active_streams.clear()

        return web.json_response(
            {"jsonrpc": "2.0", "id": "reset", "result": {"status": "reset", "message": "连接状态已重置", "timestamp": int(time.time())}},
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def _handle_mcp_message(self, request):
        """
        处理 POST 到 SSE 端点的消息 - 广播到所有连接的客户端
        """
        from aiohttp import web

        try:
            # 解析请求
            if request.content_type and "application/json" in request.content_type:
                data = await request.json()
            else:
                text_data = await request.text()
                if not text_data.strip():
                    raise ValueError("空请求体")
                data = json.loads(text_data)

            # 验证 JSON-RPC 2.0 格式
            if not isinstance(data, dict):
                raise ValueError("请求必须是 JSON 对象")

            if data.get("jsonrpc") != "2.0":
                raise ValueError("必须指定 jsonrpc: '2.0'")

            if "method" not in data:
                raise ValueError("缺少 method 字段")

            method = data.get("method")
            request_id = data.get("id")

            self.logger.info(f"收到 MCP 请求: {method} (id: {request_id})")

            # 处理 MCP 请求
            response_data = await self.server.handle_request(data)

            # 如果返回 None，说明是通知请求（没有 id），不需要响应
            if response_data is None:
                self.logger.debug(f"通知请求 {method}（无 id），不返回响应")
                # 对于通知请求，返回 204 No Content
                return web.Response(status=204, headers={"Access-Control-Allow-Origin": "*"})

            # 确保响应格式正确
            if "jsonrpc" not in response_data:
                response_data["jsonrpc"] = "2.0"

            # 确保响应包含请求 ID（对于通知请求，id 可能为 None）
            if "id" not in response_data:
                if request_id is not None:
                    response_data["id"] = request_id
                elif method not in ["ping"]:  # ping 等通知请求可能没有 id
                    self.logger.warning(f"响应缺少 id 字段，请求 id: {request_id}")

            # 记录响应详情（用于调试）
            response_str = json.dumps(response_data, ensure_ascii=False, indent=2)
            self.logger.info(f"发送 MCP 响应 (id: {response_data.get('id', 'unknown')}, method: {method}):\n{response_str}")

            # 先广播响应到所有 SSE 连接（确保客户端能及时收到）
            if self.active_streams:
                self.logger.debug(f"广播响应到 {len(self.active_streams)} 个 SSE 连接")
                await self._broadcast_message(response_data)
            else:
                self.logger.debug("没有活跃的 SSE 连接，跳过广播")

            # 同时返回 HTTP 响应（用于非 SSE 客户端）
            return web.json_response(response_data, headers={"Access-Control-Allow-Origin": "*"})

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析错误: {e}")
            error_response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {str(e)}"}}
            return web.json_response(error_response, status=400, headers={"Access-Control-Allow-Origin": "*"})

        except ValueError as e:
            self.logger.error(f"请求格式错误: {e}")
            error_response = {"jsonrpc": "2.0", "id": data.get("id") if "data" in locals() else None, "error": {"code": -32600, "message": f"Invalid Request: {str(e)}"}}
            return web.json_response(error_response, status=400, headers={"Access-Control-Allow-Origin": "*"})

        except Exception as e:
            self.logger.error(f"MCP 请求处理失败: {e}")
            error_response = {"jsonrpc": "2.0", "id": data.get("id") if "data" in locals() else None, "error": {"code": -32603, "message": f"Internal error: {str(e)}"}}
            return web.json_response(error_response, status=500, headers={"Access-Control-Allow-Origin": "*"})

    async def _create_sse_response(self, request, response_data, request_id):
        """创建 SSE 流响应"""
        from aiohttp import web

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "X-Accel-Buffering": "no",
            },
        )

        await response.prepare(request)

        try:
            # 存储流引用
            stream_id = f"{request.remote}_{request_id}_{time.time()}"
            self.active_streams[stream_id] = response

            # 发送响应数据
            await self._send_sse_message(response, response_data)

            # 发送完成事件
            await self._send_sse_event(response, "done", {"status": "completed"})

            # 保持连接一小段时间让客户端接收完数据
            await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"SSE 流处理失败: {e}")
            await self._send_sse_event(response, "error", {"message": str(e)})
        finally:
            # 清理流引用
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]

        return response

    async def _send_sse_message(self, response, data):
        """发送 SSE 格式的 MCP 消息"""
        try:
            # 确保数据是字符串格式
            if isinstance(data, dict):
                data_str = json.dumps(data, ensure_ascii=False)
            else:
                data_str = str(data)

            # 发送 SSE 消息（使用 message 事件类型）
            # SSE 格式: event: <event_type>\ndata: <data>\n\n
            event_data = f"event: message\ndata: {data_str}\n\n"
            await response.write(event_data.encode("utf-8"))
            
            # 尝试刷新缓冲区（如果支持）
            if hasattr(response, "drain"):
                try:
                    await response.drain()
                except Exception:
                    pass  # drain 失败不影响消息发送
            
            self.logger.debug(f"SSE 消息已发送 (id: {data.get('id', 'unknown') if isinstance(data, dict) else 'N/A'})")

        except (ConnectionError, OSError, RuntimeError) as e:
            # 连接相关错误，重新抛出以便上层处理
            error_msg = str(e).lower()
            if "closing" in error_msg or "closed" in error_msg:
                self.logger.debug(f"发送 SSE 消息失败（连接已关闭）: {e}")
            else:
                self.logger.warning(f"发送 SSE 消息失败（连接错误）: {e}")
            raise
        except Exception as e:
            self.logger.error(f"发送 SSE 消息失败: {e}", exc_info=True)
            raise

    async def _send_sse_event(self, response, event_type, data):
        """发送自定义 SSE 事件"""
        try:
            # 确保数据是字符串格式
            if isinstance(data, dict):
                data_str = json.dumps(data, ensure_ascii=False)
            else:
                data_str = str(data)

            # 发送 SSE 事件
            event_data = f"event: {event_type}\ndata: {data_str}\n\n"
            await response.write(event_data.encode("utf-8"))
            
            # 尝试刷新缓冲区（如果支持）
            if hasattr(response, "drain"):
                try:
                    await response.drain()
                except Exception:
                    pass  # drain 失败不影响事件发送

        except (ConnectionError, OSError, RuntimeError) as e:
            # 连接相关错误，重新抛出以便上层处理
            error_msg = str(e).lower()
            if "closing" in error_msg or "closed" in error_msg:
                self.logger.debug(f"发送 SSE 事件失败（连接已关闭）: {e}")
            else:
                self.logger.warning(f"发送 SSE 事件失败（连接错误）: {e}")
            raise
        except Exception as e:
            self.logger.error(f"发送 SSE 事件失败: {e}")
            raise

    def _is_connection_alive(self, response) -> bool:
        """检查 SSE 连接是否还活跃"""
        try:
            # 首先检查 response 对象是否存在
            if response is None:
                return False
            
            # 检查 transport 是否存在
            if not hasattr(response, "transport") or response.transport is None:
                # transport 可能还没有初始化，这在连接刚建立时是正常的
                # 只要 response 对象存在，就认为连接可能还活跃
                return True
            
            # 检查 transport 是否正在关闭或已关闭
            if hasattr(response.transport, "is_closing"):
                if response.transport.is_closing():
                    return False
            
            # 检查 transport 是否已关闭（多种方式检查）
            if hasattr(response.transport, "_closed"):
                if response.transport._closed:
                    return False
            
            # 检查 transport 是否已关闭（aiohttp 特定）
            if hasattr(response.transport, "_conn_lost"):
                if response.transport._conn_lost:
                    return False
            
            # 不检查 _started，因为它在连接建立后可能还没有设置
            # 只要 transport 存在且没有关闭标志，就认为连接活跃
            
            return True
        except Exception as e:
            # 如果检查过程中出现异常，记录日志但不一定认为连接失效
            # 因为可能是属性访问的问题，而不是连接真的关闭了
            self.logger.debug(f"检查连接状态时出错: {e}")
            # 在异常情况下，如果 response 对象存在，仍然返回 True
            # 让实际的写入操作来判断连接是否真的关闭
            return response is not None

    async def _broadcast_message(self, message):
        """广播消息到所有活跃的 SSE 连接"""
        if not self.active_streams:
            self.logger.debug("没有活跃的 SSE 连接，跳过广播")
            return

        # 需要移除的失效连接
        dead_streams = []
        success_count = 0

        for stream_id, response in list(self.active_streams.items()):
            try:
                # 检查连接是否还活跃
                if not self._is_connection_alive(response):
                    self.logger.debug(f"连接 {stream_id} 已失效，跳过")
                    dead_streams.append(stream_id)
                    continue

                # 发送消息
                await self._send_sse_message(response, message)
                success_count += 1
                self.logger.debug(f"成功向流 {stream_id} 发送消息 (id: {message.get('id', 'unknown')})")

            except (ConnectionError, OSError, RuntimeError) as e:
                # 连接相关的错误，标记为失效
                self.logger.debug(f"向流 {stream_id} 发送消息失败（连接错误）: {e}")
                dead_streams.append(stream_id)
            except Exception as e:
                # 其他错误，记录但不一定标记为失效
                error_msg = str(e).lower()
                if "closing" in error_msg or "closed" in error_msg or "write" in error_msg:
                    self.logger.debug(f"向流 {stream_id} 发送消息失败（连接已关闭）: {e}")
                    dead_streams.append(stream_id)
                else:
                    self.logger.warning(f"向流 {stream_id} 发送消息失败: {e}")

        # 清理失效连接
        for stream_id in dead_streams:
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
                self.logger.debug(f"清理失效的 SSE 连接: {stream_id}")

        self.logger.info(f"SSE 广播完成: 成功={success_count}, 失败={len(dead_streams)}, 总连接数={len(self.active_streams)}")


class GracefulShutdown:
    """优雅关闭管理器"""

    def __init__(self):
        self.transport = None
        self.logger = logging.getLogger(__name__ + ".GracefulShutdown")
        self.shutdown_requested = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            print(f"\n收到信号 {signum}，立即退出...")
            os._exit(0)

        # 注册信号处理器
        try:
            signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
            signal.signal(signal.SIGTERM, signal_handler)  # kill
        except (OSError, ValueError) as e:
            self.logger.warning(f"无法设置信号处理器: {e}")

    def set_transport(self, transport):
        """设置传输对象"""
        self.transport = transport

    def is_shutdown_requested(self):
        """检查是否请求关闭"""
        return self.shutdown_requested


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Shell MCP Server - 基于MCP的强大Shell接口")
    parser.add_argument("--config", "-c", default="config.json", help="配置文件路径（默认: config.json）")
    parser.add_argument("--mode", "-m", choices=["stdio", "sse"], default="stdio", help="传输模式: stdio 或 sse（默认: stdio）")
    parser.add_argument("--host", default="localhost", help="SSE模式主机地址（默认: localhost）")
    parser.add_argument("--port", type=int, default=8000, help="SSE模式端口（默认: 8000）")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="日志级别")

    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(level=args.log_level)

    # 检查配置文件
    if not os.path.exists(args.config):
        logger.info(f"配置文件 {args.config} 不存在，将创建默认配置")

    shutdown_manager = GracefulShutdown()

    try:
        server = TerminalMCPServer(args.config)

        if args.mode == "stdio":
            transport = StdioTransport(server)
        elif args.mode == "sse":
            transport = SSETransport(server, args.host, args.port)
        else:
            logger.error(f"不支持的传输模式: {args.mode}")
            sys.exit(1)

        shutdown_manager.set_transport(transport)

        logger.info(f"启动 Shell MCP Server (模式: {args.mode})")
        asyncio.run(transport.start())

    except KeyboardInterrupt:
        logger.info("收到键盘中断信号")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)
    finally:
        logger.info("服务器已完全停止")


if __name__ == "__main__":
    main()
