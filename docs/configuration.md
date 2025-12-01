# Shell MCP 配置指南

## 概述

Shell MCP Server使用JSON格式的配置文件来管理服务器行为、安全策略和连接参数。本指南详细说明各项配置的含义和使用方法。

## 配置文件位置

默认配置文件位于项目根目录：
```
config.json
```

可以通过命令行参数指定自定义配置文件：
```bash
python shell_mcp_server.py --config /path/to/custom_config.json
```

## 完整配置示例

```json
{
  "session_timeout": 1200,
  "command_filter": {
    "blacklist": [
      "^\\s*rm\\s+-rf\\s+/(\\s|$)",
      "^\\s*shutdown",
      "^\\s*reboot"
    ],
    "whitelist": []
  },
  "ssh": {
    "default_key_file": "~/.ssh/id_rsa",
    "timeout": 30,
    "max_connections": 10
  },
  "servers": {
    "localhost": {
      "executor": "local"
    },
    "web01": {
      "executor": "ssh",
      "host": "192.168.10.15",
      "username": "root",
      "auth_method": "ssh_key",
      "password": "123456",
      "port": 22
    }
  },
  "logging": {
    "level": "INFO",
    "file": "../llm-logs/shell-mcp.log"
  }
}
```

## 配置参数详解

### 1. 会话配置 (session_timeout)

控制会话的超时时间，单位为秒。

```json
{
  "session_timeout": 1200
}
```

- **类型**: `number`
- **默认值**: `1200` (20分钟)
- **说明**: 会话空闲超过指定时间后自动清理
- **建议**: 生产环境可设置为 `600-1800` 秒

### 2. 命令过滤配置 (command_filter)

控制允许执行的命令，支持黑名单和白名单两种模式。

```json
{
  "command_filter": {
    "blacklist": [
      "危险命令正则表达式列表"
    ],
    "whitelist": [
      "允许的命令列表"
    ]
  }
}
```

#### 黑名单模式 (blacklist)

使用正则表达式匹配禁止执行的命令：

```json
{
  "blacklist": [
    "^\\s*rm\\s+-rf\\s+/(\\s|$)",      // 禁止删除根目录
    "^\\s*shutdown",                   // 禁止关机
    "^\\s*reboot",                     // 禁止重启
    "^\\s*mkfs\\.",                    // 禁止格式化
    "^\\s*dd\\s+.*of=/dev/",           // 禁止直接写设备
    "^\\s*>\\s*/dev/",                 // 禁止重定向到设备
    ".*;\\s*rm\\s+-rf",                // 禁止组合危险命令
    ".*&&\\s*rm\\s+-rf",               // 禁止组合危险命令
    ".*\\|\\s*sh\\s*$"                 // 禁止管道执行shell
  ]
}
```

**默认危险命令列表**：
- 系统删除: `rm -rf /`, `rm -rf --no-preserve-root`
- 系统控制: `shutdown`, `reboot`, `halt`, `poweroff`
- 磁盘操作: `mkfs`, `fdisk`, `parted`, `dd if=/dev/zero of=/dev/`
- 用户管理: `userdel`, `passwd root`
- 权限修改: `chmod 777 /`, `chown` 系统目录
- 进程管理: `killall`, `pkill`, `kill -9 1`

#### 白名单模式 (whitelist)

仅允许执行指定的命令：

```json
{
  "whitelist": [
    "ls", "pwd", "cd", "echo", "cat", "grep",
    "ps", "top", "df", "du", "free", "uptime",
    "ping", "curl", "wget", "git", "docker"
  ]
}
```

**使用建议**：
- 生产环境推荐使用白名单模式
- 开发环境可以使用黑名单模式
- 两种模式可以同时启用（黑名单优先检查）

### 3. SSH配置 (ssh)

配置SSH连接的默认参数。

```json
{
  "ssh": {
    "default_key_file": "~/.ssh/id_rsa",
    "timeout": 30,
    "max_connections": 10,
    "compression": true,
    "known_hosts_policy": "auto_add"
  }
}
```

#### 参数说明

- `default_key_file`: 默认SSH私钥文件路径
  - 类型: `string`
  - 默认值: `"~/.ssh/id_rsa"`
  - 支持相对路径和绝对路径

- `timeout`: SSH连接超时时间
  - 类型: `number`
  - 默认值: `30` (秒)
  - 建议: 网络环境较差时适当增加

- `max_connections`: 最大并发SSH连接数
  - 类型: `number`
  - 默认值: `10`
  - 说明: 防止连接数过多导致资源耗尽

- `compression`: 是否启用压缩
  - 类型: `boolean`
  - 默认值: `true`
  - 说明: 网络传输较慢时启用可提高性能

- `known_hosts_policy`: 主机密钥策略
  - 类型: `string`
  - 可选值: `"auto_add"`, `"strict"`, `"ignore"`
  - 默认值: `"auto_add"`

### 4. 服务器配置 (servers)

定义可连接的服务器列表，包括本地和远程服务器。

```json
{
  "servers": {
    "server_name": {
      "executor": "local|ssh",
      "host": "主机地址",
      "username": "用户名",
      "auth_method": "password|ssh_key",
      "password": "密码",
      "key_file": "私钥文件",
      "port": 22,
      "timeout": 30
    }
  }
}
```

#### 本地服务器配置

```json
{
  "localhost": {
    "executor": "local"
  }
}
```

#### SSH服务器配置

```json
{
  "web01": {
    "executor": "ssh",
    "host": "192.168.10.15",
    "username": "root",
    "auth_method": "ssh_key",
    "password": "123456",
    "key_file": "~/.ssh/web01_key",
    "port": 22,
    "timeout": 30
  }
}
```

#### 参数说明

- `executor`: 执行器类型
  - `local`: 本地执行
  - `ssh`: SSH远程执行

- `host`: 远程主机地址
  - 必需参数 (SSH模式)
  - 支持IP地址和域名

- `username`: SSH用户名
  - 必需参数 (SSH模式)

- `auth_method`: 认证方式
  - `password`: 密码认证
  - `ssh_key`: SSH密钥认证

- `password`: SSH密码
  - password认证时必需

- `key_file`: SSH私钥文件路径
  - ssh_key认证时可选，默认使用全局配置

- `port`: SSH端口
  - 类型: `number`
  - 默认值: `22`

- `timeout`: 连接超时时间
  - 类型: `number`
  - 默认值: `30` (秒)

### 5. 日志配置 (logging)

配置日志记录的级别和输出。

```json
{
  "logging": {
    "level": "INFO",
    "file": "../llm-logs/shell-mcp.log",
    "format": "json",
    "rotation": {
      "max_size": "100MB",
      "max_files": 5,
      "when": "midnight"
    }
  }
}
```

#### 参数说明

- `level`: 日志级别
  - 可选值: `DEBUG`, `INFO`, `WARNING`, `ERROR`
  - 默认值: `INFO`

- `file`: 日志文件路径
  - 类型: `string`
  - 默认值: `"shell-mcp.log"`
  - 相对路径相对于启动目录

- `format`: 日志格式
  - 可选值: `"json"`, `"text"`
  - 默认值: `"text"`

- `rotation`: 日志轮转配置
  - `max_size`: 单个文件最大大小
  - `max_files`: 保留的日志文件数量
  - `when`: 轮转时机 (`"midnight"`, `"weekly"`)

## 环境变量配置

可以通过环境变量覆盖配置文件中的参数：

```bash
# 导出环境变量
export SHELL_MCP_SESSION_TIMEOUT=1800
export SHELL_MCP_LOG_LEVEL=DEBUG
export SHELL_MCP_SSH_TIMEOUT=45

# 启动服务器
python shell_mcp_server.py
```

### 支持的环境变量

| 环境变量 | 配置路径 | 说明 |
|---------|----------|------|
| `SHELL_MCP_SESSION_TIMEOUT` | `session_timeout` | 会话超时时间 |
| `SHELL_MCP_LOG_LEVEL` | `logging.level` | 日志级别 |
| `SHELL_MCP_LOG_FILE` | `logging.file` | 日志文件路径 |
| `SHELL_MCP_SSH_TIMEOUT` | `ssh.timeout` | SSH超时时间 |
| `SHELL_MCP_SSH_MAX_CONNECTIONS` | `ssh.max_connections` | 最大SSH连接数 |

## 配置验证

启动服务器时会自动验证配置文件的正确性：

### 语法验证

```json
// 正确的JSON格式
{
  "session_timeout": 1200,
  "command_filter": {
    "blacklist": ["^\\s*rm\\s+-rf"]
  }
}
```

### 参数验证

- 检查必需参数是否存在
- 验证参数类型是否正确
- 检查参数值是否在合理范围内

### 连接测试

对于SSH服务器配置，启动时会测试连接性：

```
[INFO] 测试SSH连接: web01@192.168.10.15:22
[INFO] SSH连接成功: web01
[ERROR] SSH连接失败: test-server - Connection refused
```

## 安全配置建议

### 1. 生产环境配置

```json
{
  "session_timeout": 600,
  "command_filter": {
    "whitelist": ["ls", "pwd", "cat", "grep", "ps", "df"],
    "blacklist": ["^\\s*rm\\s+", "^\\s*shutdown", "^\\s*reboot"]
  },
  "ssh": {
    "timeout": 30,
    "max_connections": 5,
    "known_hosts_policy": "strict"
  },
  "logging": {
    "level": "WARNING",
    "file": "/var/log/shell-mcp/app.log"
  }
}
```

### 2. 开发环境配置

```json
{
  "session_timeout": 3600,
  "command_filter": {
    "blacklist": ["^\\s*rm\\s+-rf\\s+/", "^\\s*shutdown"]
  },
  "ssh": {
    "timeout": 15,
    "known_hosts_policy": "auto_add"
  },
  "logging": {
    "level": "DEBUG"
  }
}
```

### 3. 高安全配置

```json
{
  "session_timeout": 300,
  "command_filter": {
    "whitelist": ["ls", "pwd", "echo"],
    "blacklist": []
  },
  "ssh": {
    "timeout": 10,
    "max_connections": 3,
    "known_hosts_policy": "strict"
  },
  "logging": {
    "level": "INFO",
    "file": "/var/log/shell-mcp/secure.log"
  }
}
```

## 配置最佳实践

### 1. 安全第一

- 优先使用白名单模式控制命令执行
- 定期审查和更新安全规则
- 监控异常命令执行日志
- 限制SSH连接数和超时时间

### 2. 性能优化

- 合理设置连接池大小
- 启用SSH压缩提高传输效率
- 配置适当的日志级别避免性能影响
- 定期清理过期会话和日志文件

### 3. 运维友好

- 使用有意义的服务器名称
- 添加配置文件注释说明
- 建立配置变更审计流程
- 定期备份重要配置

### 4. 环境隔离

- 不同环境使用独立配置文件
- 通过环境变量管理敏感信息
- 使用配置模板确保一致性
- 建立配置版本控制

## 故障排除

### 常见配置问题

1. **JSON语法错误**
   ```bash
   # 验证JSON格式
   python -m json.tool config.json
   ```

2. **SSH连接失败**
   ```bash
   # 测试SSH连接
   ssh -i ~/.ssh/id_rsa root@192.168.10.15
   ```

3. **权限问题**
   ```bash
   # 检查文件权限
   ls -la ~/.ssh/id_rsa
   chmod 600 ~/.ssh/id_rsa
   ```

4. **路径问题**
   ```bash
   # 检查文件路径
   ls -la ~/shell-mcp/config.json
   ls -la ../llm-logs/
   ```

### 调试模式

启用详细日志进行问题诊断：

```json
{
  "logging": {
    "level": "DEBUG",
    "file": "debug.log"
  }
}
```

或使用环境变量：

```bash
export SHELL_MCP_LOG_LEVEL=DEBUG
python shell_mcp_server.py
```

## MCP客户端集成配置

### Claude Desktop配置

在Claude Desktop的`claude_desktop_config.json`文件中添加shell-mcp服务器：

```json
{
  "mcpServers": {
    "shell-mcp": {
      "command": "python",
      "args": [
        "/path/to/shell-mcp/shell_mcp_server.py",
        "--config",
        "/path/to/shell-mcp/config.json"
      ],
      "cwd": "/path/to/shell-mcp/"
    }
  }
}
```

### Cherry Studio配置

Cherry Studio支持SSE模式连接，配置方式：

```json
{
  "mcpServers": {
    "shell-mcp": {
      "url": "http://localhost:8000/",
      "transport": "sse",
      "description": "Shell MCP服务器 (SSE模式)"
    }
  }
}
```

### VS Code配置

在VS Code的MCP扩展配置中：

```json
{
  "mcp.servers": {
    "shell-mcp": {
      "command": "python",
      "args": [
        "shell_mcp_server.py",
        "--mode", "stdio",
        "--log-level", "INFO"
      ],
      "cwd": "${workspaceFolder}/shell-mcp",
      "description": "本地Shell命令执行"
    }
  }
}
```

### 配置参数说明

#### command
- `python`: Python解释器路径，可以是绝对路径
- 也可以使用虚拟环境中的python路径

#### args
- `shell_mcp_server.py`: 主脚本文件路径
- `--config`: 指定配置文件路径（可选）
- `--mode`: 运行模式，可选值：`stdio`, `sse`
- `--port`: SSE模式端口号（默认8000）
- `--host`: SSE模式监听地址（默认localhost）
- `--log-level`: 日志级别（默认INFO）

#### cwd
- 工作目录，建议设置为shell-mcp项目根目录
- 相对路径会基于此目录解析

#### 环境变量（可选）

```json
{
  "mcpServers": {
    "shell-mcp": {
      "command": "python",
      "args": ["shell_mcp_server.py"],
      "env": {
        "SHELL_MCP_LOG_LEVEL": "DEBUG",
        "SHELL_MCP_CONFIG_PATH": "/custom/path/config.json",
        "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock"
      }
    }
  }
}
```

### 完整配置示例

#### 生产环境配置

```json
{
  "mcpServers": {
    "shell-mcp-prod": {
      "command": "/opt/venv/bin/python",
      "args": [
        "/opt/shell-mcp/shell_mcp_server.py",
        "--config",
        "/opt/shell-mcp/production_config.json",
        "--log-level", "WARNING"
      ],
      "cwd": "/opt/shell-mcp/",
      "env": {
        "SHELL_MCP_SESSION_TIMEOUT": "300",
        "SHELL_MCP_SSH_MAX_CONNECTIONS": "5"
      },
      "description": "生产环境Shell命令执行（安全模式）"
    }
  }
}
```

#### 开发环境配置

```json
{
  "mcpServers": {
    "shell-mcp-local": {
      "command": "python",
      "args": [
        "shell_mcp_server.py",
        "--mode", "stdio",
        "--log-level", "DEBUG"
      ],
      "cwd": "./shell-mcp/",
      "description": "开发环境Shell命令执行（调试模式）"
    },
    "shell-mcp-remote": {
      "url": "http://remote-server:8000/",
      "transport": "sse",
      "description": "远程Shell MCP服务器"
    },
    "shell-mcp-docker": {
      "url": "http://localhost:8000/",
      "transport": "sse",
      "description": "Docker容器Shell MCP服务器"
    }
  }
}
```

### 其他MCP客户端配置

#### Cursor配置

在Cursor的设置中添加：

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

#### Continue.dev配置

在`.continue/config.json`中：

```json
{
  "mcpServers": {
    "shell-mcp-local": {
      "command": "python",
      "args": [
        "/absolute/path/to/shell-mcp/shell_mcp_server.py",
        "--config",
        "/absolute/path/to/shell-mcp/config.json"
      ],
      "cwd": "/absolute/path/to/shell-mcp/",
      "description": "本地系统Shell访问"
    },
    "shell-mcp-remote": {
      "url": "http://continue-server:8000/",
      "transport": "sse",
      "description": "远程系统Shell访问"
    }
  }
}
```

#### Cline配置

在Cline的MCP服务器设置中：

```json
{
  "mcpServers": {
    "shell-mcp-local": {
      "command": "python",
      "args": ["shell_mcp_server.py", "--mode", "stdio"],
      "cwd": "./shell-mcp/",
      "description": "本地Shell命令执行"
    },
    "shell-mcp-docker": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/shell-mcp:/app",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "python:3.9-slim",
        "python", "/app/shell_mcp_server.py"
      ],
      "description": "Docker容器内Shell执行"
    }
  }
}
```

#### PoE配置

在PoE (Poe.com) 的自定义机器人配置中：

```json
{
  "mcp_servers": {
    "shell_mcp": {
      "command": "python",
      "args": ["shell_mcp_server.py"],
      "cwd": "/absolute/path/to/shell-mcp/",
      "description": "Secure shell command execution"
    }
  }
}
```

#### OpenAI ChatGPT配置

通过第三方MCP代理服务：

```json
{
  "mcpServers": {
    "shell-mcp-proxy": {
      "url": "http://localhost:8000/",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer your-api-key"
      },
      "description": "Shell MCP via proxy"
    },
    "shell-mcp-cloud": {
      "url": "https://your-shell-mcp-service.com/",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer your-cloud-api-key"
      },
      "description": "云Shell MCP服务"
    }
  }
}
```

#### Custom MCP Client配置

对于自研的MCP客户端，支持本地和远程两种方式：

```python
# Python示例 - 支持本地和远程
import asyncio
from mcp import ClientSession, StdioServerParameters
import aiohttp

class ShellMCPClient:
    def __init__(self, mode="stdio", **kwargs):
        if mode == "stdio":
            # 本地stdio模式
            self.server_params = StdioServerParameters(
                command="python",
                args=[f"{kwargs.get('path')}/shell_mcp_server.py"],
                cwd=kwargs.get('path'),
                env={
                    "SHELL_MCP_LOG_LEVEL": "INFO",
                    "SHELL_MCP_CONFIG_PATH": f"{kwargs.get('path')}/config.json"
                }
            )
            self.session_factory = self._create_stdio_session
        elif mode == "sse":
            # 远程SSE模式
            self.url = kwargs.get('url', 'http://localhost:8000/')
            self.headers = kwargs.get('headers', {})
            self.session_factory = self._create_sse_session

    async def _create_stdio_session(self):
        return ClientSession(self.server_params)

    async def _create_sse_session(self):
        # 使用aiohttp创建SSE客户端会话
        return aiohttp.ClientSession()

    async def execute_command(self, command: str, **kwargs):
        if hasattr(self, 'server_params'):
            # stdio模式
            async with await self.session_factory() as session:
                await session.initialize()
                result = await session.call_tool("execute_command", {
                    "command": command,
                    **kwargs
                })
                return result.content[0].text
        else:
            # SSE模式
            async with await self.session_factory() as session:
                message = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "execute_command",
                        "arguments": {"command": command, **kwargs}
                    },
                    "id": 1
                }

                async with session.post(
                    f"{self.url}message",
                    json=message,
                    headers=self.headers
                ) as response:
                    result = await response.json()
                    return result["result"]["content"][0]["text"]

# 使用示例
# 本地模式
local_client = ShellMCPClient(mode="stdio", path="/path/to/shell-mcp")
local_result = await local_client.execute_command("ls -la /tmp")

# 远程模式
remote_client = ShellMCPClient(
    mode="sse",
    url="https://your-shell-mcp-service.com/",
    headers={"Authorization": "Bearer your-api-key"}
)
remote_result = await remote_client.execute_command("ls -la /tmp")
```

### Docker容器集成配置

#### Docker Compose配置

```yaml
version: '3.8'
services:
  shell-mcp:
    build:
      context: ./shell-mcp
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./shell-mcp:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - SHELL_MCP_MODE=sse
      - SHELL_MCP_PORT=8000
      - SHELL_MCP_LOG_LEVEL=INFO
    restart: unless-stopped

  mcp-client:
    image: your-mcp-client:latest
    depends_on:
      - shell-mcp
    environment:
      - MCP_SERVER_URL=http://shell-mcp:8000/message
```

#### Dockerfile示例

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建非root用户
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

EXPOSE 8000

CMD ["python", "shell_mcp_server.py", "--mode", "sse", "--port", "8000"]
```

### Kubernetes配置

#### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shell-mcp
  labels:
    app: shell-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: shell-mcp
  template:
    metadata:
      labels:
        app: shell-mcp
    spec:
      containers:
      - name: shell-mcp
        image: your-registry/shell-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: SHELL_MCP_MODE
          value: "sse"
        - name: SHELL_MCP_PORT
          value: "8000"
        - name: SHELL_MCP_LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: shell-mcp-service
spec:
  selector:
    app: shell-mcp
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### 网络代理配置

#### Nginx反向代理

```nginx
upstream shell_mcp {
    server localhost:8000;
    # 多个实例负载均衡
    # server localhost:8001;
    # server localhost:8002;
}

server {
    listen 80;
    server_name shell-mcp.example.com;

    # SSE需要特殊处理
    location /message {
        proxy_pass http://shell_mcp;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # 其他API端点
    location / {
        proxy_pass http://shell_mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 监控和可观测性

#### Prometheus监控配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'shell-mcp'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### 日志聚合配置

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/shell-mcp/*.log
  fields:
    service: shell-mcp
    environment: production
  fields_under_root: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "shell-mcp-%{+yyyy.MM.dd}"
```

---

更多详细信息请参考：
- [API文档](api.md)
- [MCP协议规范](https://modelcontextprotocol.io/)
- [项目主页](../README.md)