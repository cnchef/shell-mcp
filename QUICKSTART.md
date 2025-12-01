# Shell MCP Server - 快速开始指南

## 🚀 5分钟快速上手

### 1. 环境准备

```bash
# Python 3.8+ 必需
python --version

# 安装依赖
pip install -r requirements.txt
```

### 2. 立即测试

#### stdio模式测试
```bash
# 方式1: 使用自动化测试（推荐）
python test_stdio.py

# 方式2: 手动启动
python shell_mcp_server.py --mode stdio
# 然后输入: {"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}
```

#### SSE模式测试
```bash
# 启动HTTP服务器
python shell_mcp_server.py --mode sse --port 8000

# 在另一个终端测试
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'
```

### 3. 执行第一个命令

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "echo 'Hello from Shell MCP!'"
    }
  },
  "id": 1
}
```

### 4. 远程命令执行

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "ls -la /tmp",
      "host": "192.168.1.100",
      "username": "admin",
      "password": "your_password"
    }
  },
  "id": 2
}
```

## 🧪 测试脚本使用

### test_stdio.py - 完整测试
```bash
python test_stdio.py
# 选择模式:
# 1. 自动测试序列 (测试基本功能)
# 2. 交互模式 (手动输入命令)
# 3. 两者都运行
```

### test_simple.py - 快速验证
```bash
python test_simple.py
# 自动执行基本功能测试
```

### test_manual.py - 调试专用
```bash
python test_manual.py
# 使用临时文件测试，适合调试
```

## ⚡ 常用命令示例

### 本地命令
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":1}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"whoami"}},"id":2}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"date"}},"id":3}
```

### 带环境变量的命令
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "echo $MY_VAR",
      "env": {
        "MY_VAR": "Hello World"
      }
    }
  },
  "id": 4
}
```

### 会话管理
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "export MY_SESSION_VAR='test'; echo $MY_SESSION_VAR",
      "session": "my_session"
    }
  },
  "id": 5
}
```

## 🔧 配置文件

编辑 `config.json` 自定义设置:

```json
{
  "session_timeout": 1200,
  "command_filter": {
    "blacklist": ["^\\s*rm\\s+-rf\\s+/"],
    "whitelist": []
  },
  "logging": {
    "level": "INFO",
    "file": "shell_mcp.log"
  }
}
```

## 🛡️ 安全提醒

- ⚠️ 生产使用前请修改默认配置
- 🔒 建议使用SSH密钥认证而非密码
- 📋 定期审查命令黑白名单
- 🌐 在防火墙后运行服务

## ❓ 常见问题

**Q: stdio模式没有响应怎么办？**
A: 使用测试脚本 `python test_stdio.py` 或确保输入完整的JSON

**Q: 如何查看详细日志？**
A: 启动时添加 `--log-level DEBUG`

**Q: SSH连接失败？**
A: 检查网络连接、SSH服务状态和认证信息

**Q: 命令被拦截怎么办？**
A: 检查配置文件中的黑白名单规则，或使用 `force_execute: true`

---

🎉 **恭喜！您已经掌握了Shell MCP Server的基本用法！**

详细文档请查看 [README.md](README.md) 和 [ARCHITECTURE.md](ARCHITECTURE.md)