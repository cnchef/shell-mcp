# Shell MCP API文档

## 概述

Shell MCP Server提供基于Model Context Protocol (MCP)的安全Shell命令执行接口，支持本地和远程服务器操作。

## MCP协议基础

Shell MCP Server完全兼容MCP协议规范，支持JSON-RPC 2.0格式的消息交换。

### 连接模式

- **Stdio模式**: 标准输入输出通信，适合本地集成
- **SSE模式**: HTTP服务器端事件，适合远程访问

## 工具接口

### 1. execute_command

在本地或远程主机执行shell命令

**方法**:
```
tools/call
```

**参数**:
```json
{
  "name": "execute_command",
  "arguments": {
    "command": "string (必需)",           // 要执行的命令
    "host": "string (可选)",              // 远程主机地址
    "username": "string (可选)",          // SSH用户名
    "password": "string (可选)",          // SSH密码
    "key_file": "string (可选)",          // SSH私钥文件路径
    "port": "number (可选, 默认22)",       // SSH端口
    "session": "string (可选, 默认'default')", // 会话名称
    "env": "object (可选)",               // 环境变量字典
    "cwd": "string (可选)",               // 本地执行工作目录
    "force_execute": "boolean (可选, 默认false)" // 强制执行危险命令
  }
}
```

**请求示例**:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "ls -la /home",
      "host": "192.168.1.100",
      "username": "admin",
      "session": "my_session"
    }
  },
  "id": 1
}
```

**成功响应**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "命令执行成功\n\ntotal 12\ndrwxr-xr-x 3 admin admin 4096 Jan  1 10:00 .\ndrwxr-xr-x 3 root  root  4096 Jan  1 09:00 ..\n-rw-r--r-- 1 admin admin  220 Jan  1 08:00 .bash_logout\n"
      }
    ],
    "isError": false
  },
  "id": 1
}
```

**错误响应**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "错误: 命令被安全策略阻止: rm -rf /"
      }
    ],
    "isError": true
  },
  "id": 1
}
```

### 2. get_tools

获取服务器支持的所有工具列表

**方法**:
```
tools/list
```

**请求示例**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 2
}
```

**响应示例**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "execute_command",
        "description": "在本地或远程主机执行shell命令",
        "inputSchema": {
          "type": "object",
          "properties": {
            "command": {
              "type": "string",
              "description": "要执行的命令"
            },
            "host": {
              "type": "string",
              "description": "远程主机地址"
            },
            "username": {
              "type": "string",
              "description": "SSH用户名"
            },
            "session": {
              "type": "string",
              "description": "会话名称"
            }
          },
          "required": ["command"]
        }
      }
    ]
  },
  "id": 2
}
```

## SSE模式端点

当以SSE模式运行时，服务器提供以下HTTP端点：

### GET /message

建立SSE连接，用于接收服务器推送的消息

**示例**:
```bash
curl -N http://localhost:8000/message
```

### POST /message

发送MCP消息到服务器

**请求头**:
```
Content-Type: application/json
```

**请求体**: JSON格式的MCP消息

**示例**:
```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":1}'
```

### GET /

获取服务器信息和状态

**响应**:
```json
{
  "service": "Shell MCP Server",
  "version": "1.0.0",
  "mode": "sse",
  "status": "running"
}
```

### POST /reset

重置连接状态，清除所有会话

**示例**:
```bash
curl -X POST http://localhost:8000/reset
```

## 使用示例

### Python客户端示例

```python
import asyncio
import json
from subprocess import PIPE, Popen

async def run_stdio_command(command, cwd=None):
    """通过stdio模式执行命令"""
    process = Popen(
        ['python', 'shell_mcp_server.py'],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        cwd=cwd
    )

    # 发送初始化消息
    init_msg = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {},
        "id": 1
    }

    # 发送工具调用消息
    tool_msg = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "execute_command",
            "arguments": {
                "command": command,
                "cwd": cwd
            }
        },
        "id": 2
    }

    process.stdin.write(json.dumps(init_msg) + '\n')
    process.stdin.write(json.dumps(tool_msg) + '\n')
    process.stdin.flush()

    # 读取响应
    output = process.stdout.read()
    return output

# 使用示例
result = asyncio.run(run_stdio_command("ls -la"))
print(result)
```

### JavaScript客户端示例

```javascript
class ShellMCPClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.id = 1;
    }

    async callTool(toolName, arguments) {
        const message = {
            jsonrpc: "2.0",
            method: "tools/call",
            params: {
                name: toolName,
                arguments: arguments
            },
            id: this.id++
        };

        const response = await fetch(`${this.baseUrl}/message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(message)
        });

        return await response.json();
    }

    async executeCommand(command, options = {}) {
        return await this.callTool('execute_command', {
            command,
            ...options
        });
    }
}

// 使用示例
const client = new ShellMCPClient('http://localhost:8000');

client.executeCommand('pwd').then(result => {
    console.log('命令结果:', result.result.content[0].text);
});
```

### curl使用示例

```bash
# 1. 启动服务器
python shell_mcp_server.py --mode sse --port 8000

# 2. 测试服务器状态
curl http://localhost:8000/

# 3. 初始化MCP连接
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'

# 4. 执行本地命令
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":2}'

# 5. 执行远程命令
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"ls -la /tmp","host":"192.168.1.100","username":"admin"}},"id":3}'
```

## 错误处理

### 常见错误类型

1. **命令被阻止**
   - 错误信息: "命令被安全策略阻止"
   - 解决方案: 检查命令是否在黑名单中，或使用force_execute强制执行

2. **SSH连接失败**
   - 错误信息: "SSH连接失败: [详细错误信息]"
   - 解决方案: 检查主机地址、认证信息、网络连接

3. **会话超时**
   - 错误信息: "会话已超时"
   - 解决方案: 重新建立会话或调整会话超时时间

4. **参数错误**
   - 错误信息: "参数验证失败"
   - 解决方案: 检查必需参数是否提供，参数格式是否正确

### 错误响应格式

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "错误: [具体错误信息]"
      }
    ],
    "isError": true
  },
  "id": 1
}
```

## 安全限制

### 命令过滤

服务器内置了危险命令黑名单，包括但不限于：

- 系统破坏命令: `rm -rf /`, `mkfs`, `dd if=/dev/zero of=/dev/sda`
- 系统控制命令: `shutdown`, `reboot`, `halt`
- 用户管理命令: `userdel`, `passwd root`
- 权限修改命令: `chmod 777 /`, `chown root:root /`

### 资源限制

- 命令执行超时: 30秒
- 会话超时: 1200秒（20分钟）
- 最大SSH连接数: 10
- 最大并发命令数: 5

## 监控和日志

### 日志级别

- `DEBUG`: 详细调试信息
- `INFO`: 一般操作信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息

### 日志格式

```json
{
  "timestamp": "2025-01-01T12:00:00Z",
  "level": "INFO",
  "message": "命令执行完成",
  "command": "ls -la",
  "host": "localhost",
  "session": "default",
  "duration_ms": 150,
  "success": true
}
```

## MCP客户端集成配置

### Claude Desktop配置

在Claude Desktop的`claude_desktop_config.json`文件中添加：

```json
{
  "mcpServers": {
    "shell-mcp": {
      "command": "python",
      "args": ["/path/to/shell-mcp/shell_mcp_server.py"],
      "cwd": "/path/to/shell-mcp/"
    }
  }
}
```

### Cherry Studio配置

在Cherry Studio中配置MCP服务器：

```json
{
  "mcpServers": {
    "shell-mcp-local": {
      "command": "python",
      "args": ["shell_mcp_server.py"],
      "cwd": "/path/to/shell-mcp/",
      "description": "本地Shell命令执行"
    },
    "shell-mcp-remote": {
      "url": "http://your-server.com:8000/",
      "transport": "sse",
      "description": "远程Shell命令执行"
    }
  }
}
```

### VS Code配置

在VS Code的MCP扩展中：

```json
{
  "mcpServers": {
    "shell-mcp-local": {
      "command": "python",
      "args": ["shell_mcp_server.py", "--mode", "stdio"],
      "cwd": "./shell-mcp/",
      "description": "本地Shell命令执行"
    },
    "shell-mcp-remote": {
      "url": "http://your-server.com:8000/",
      "transport": "sse",
      "description": "远程Shell命令执行"
    }
  }
}
```

### 通用远程配置模板

所有MCP客户端都支持本地和远程两种模式：

```json
{
  "mcpServers": {
    "shell-mcp-local": {
      "command": "python",
      "args": ["/path/to/shell-mcp/shell_mcp_server.py"],
      "cwd": "/path/to/shell-mcp/",
      "description": "本地Shell命令执行"
    },
    "shell-mcp-remote": {
      "url": "http://your-server.com:8000/",
      "transport": "sse",
      "description": "远程Shell命令执行"
    }
  }
}
```

#### 支持的MCP客户端
- ✅ Claude Desktop (stdio + sse)
- ✅ Cherry Studio (SSE模式)
- ✅ VS Code with MCP扩展 (stdio + sse)
- ✅ Cursor (stdio + sse)
- ✅ Continue.dev (stdio + sse)
- ✅ Cline (stdio + sse)
- ✅ PoE自定义机器人 (stdio + sse)
- ✅ 自研Python/Node.js客户端 (stdio + sse)

#### 部署模式选择

**本地模式 (stdio)**:
- 适用于开发环境
- 直接启动Python进程
- 性能更好，延迟更低
- 适合单用户使用

**远程模式 (SSE)**:
- 适用于生产环境
- 支持多用户并发
- 易于负载均衡和扩展
- 支持HTTPS和认证

---

更多详细信息请参考：
- [MCP协议规范](https://modelcontextprotocol.io/)
- [配置指南](configuration.md)
- [项目主页](../README.md)