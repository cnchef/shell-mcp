# Shell MCP Server

一个基于 Model Context Protocol (MCP) 的强大Shell接口，支持本地和远程命令执行，带有完善的安全机制和会话管理功能。

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io)

## ✨ 主要功能

- 🖥️ **本地命令执行**: 支持在本地环境执行shell命令
- 🔗 **远程SSH执行**: 支持通过SSH连接到远程服务器执行命令
- 🛡️ **安全防护**: 内置命令黑白名单，防止危险命令执行
- 💾 **会话管理**: 智能会话管理，支持环境变量持久化
- 🌐 **多种传输模式**: 支持stdio和SSE两种传输模式
- 📝 **完整日志**: 详细的日志记录和错误追踪
- ⚡ **异步处理**: 基于asyncio的高性能异步处理

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 支持的操作系统: Windows, Linux, macOS

### 安装

1. **克隆仓库**

```bash
git clone https://github.com/cnchef/shell-mcp.git
cd shell-mcp
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置服务器**

```bash
# 复制配置模板
cp config.json.example config.json
# 编辑配置文件
nano config.json
```

### 基本使用

1. **Stdio模式 (默认)**

```bash
python terminal_mcp_server.py
```

2. **SSE模式**

```bash
# 本地监听
python terminal_mcp_server.py --mode sse --port 8000

# 监听所有接口
python terminal_mcp_server.py --mode sse --host 0.0.0.0 --port 8000
```

3. **自定义配置文件**

```bash
python terminal_mcp_server.py --config my_config.json
```

4. **设置日志级别**

```bash
python terminal_mcp_server.py --log-level DEBUG
```

## 📖 配置说明

### config.json 结构

```json
{
  "session_timeout": 1200,
  "command_filter": {
    "blacklist": [
      "^\\s*rm\\s+-rf\\s+/(\\s|$)",
      "^\\s*shutdown",
      "^\\s*reboot"
    ],
    "whitelist": ["ls", "pwd", "echo"]
  },
  "ssh": {
    "default_key_file": "~/.ssh/id_rsa",
    "timeout": 30,
    "max_connections": 10
  },
  "servers": {
    "web01": {
      "executor": "ssh",
      "host": "server.example.com",
      "username": "admin",
      "auth_method": "ssh_key",
      "port": 22
    },
    "localhost": {
      "executor": "local"
    }
  },
  "logging": {
    "level": "INFO",
    "file": "terminal_mcp.log"
  }
}
```

### 安全配置

- **黑名单模式**: 默认禁止危险命令，推荐生产环境使用
- **白名单模式**: 仅允许指定命令，适合高安全要求场景
- **混合模式**: 黑白名单结合，灵活控制

## 🔧 MCP工具接口

### execute_command

在本地或远程主机执行命令

**参数:**

- `command` (必需): 要执行的命令
- `host` (可选): 远程主机地址
- `username` (可选): SSH用户名
- `password` (可选): SSH密码
- `key_file` (可选): SSH私钥文件路径
- `port` (可选): SSH端口，默认22
- `session` (可选): 会话名称，默认'default'
- `env` (可选): 环境变量字典
- `cwd` (可选): 本地执行工作目录
- `force_execute` (可选): 强制执行危险命令，默认false

**示例:**

```json
{
  "command": "ls -la /home",
  "host": "192.168.1.100",
  "username": "admin",
  "session": "my_session"
}
```

### get_tools

获取服务器支持的所有工具列表

## 🌐 SSE模式端点

- `GET /message` - 建立SSE连接
- `POST /message` - 发送MCP消息
- `GET /` - 服务器信息
- `POST /reset` - 重置连接状态

## 🛡️ 安全注意事项

### ⚠️ 重要安全警告

1. **生产环境使用前请务必**:

   - 修改默认的SSH连接配置
   - 设置强密码或使用SSH密钥认证
   - 配置适合您环境的命令黑白名单
   - 限制网络访问和端口暴露
2. **命令过滤建议**:

   - 优先使用白名单模式
   - 定期审查和更新安全规则
   - 监控命令执行日志
3. **网络安全**:

   - 在防火墙后运行服务
   - 使用VPN或SSH隧道访问
   - 定期更新依赖包

### 默认防护

系统内置了以下危险命令防护:

- 系统删除命令 (`rm -rf /`)
- 系统关机重启 (`shutdown`, `reboot`)
- 磁盘格式化 (`mkfs`, `fdisk`)
- 用户管理 (`userdel`, `passwd root`)
- 权限修改 (`chmod 777 /`)

## 🧪 测试示例

### stdio模式测试

#### 方法1: 使用内置测试脚本

```bash
# 自动化测试 + 交互模式
python test_stdio.py

# 简单管道测试
python test_simple.py

# 手动文件输入测试
python test_manual.py
```

#### 方法2: 手动JSON输入

```bash
# 启动stdio模式
python shell_mcp_server.py --mode stdio

# 然后逐行输入JSON命令:
# {"jsonrpc":"2.0","method":"initialize","params":{},"id":1}
# {"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}
# {"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":3}
```

### 使用curl测试SSE模式

```bash
# 1. 启动服务器
python shell_mcp_server.py --mode sse --port 8000

# 2. 测试连接
curl http://localhost:8000/message

# 3. 初始化MCP
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'

# 4. 获取工具列表
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}'

# 5. 执行命令
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":3}'
```

### 与Cherry Studio集成

1. 在Cherry Studio中添加MCP服务器
2. 配置端点: `http://localhost:8000/message`
3. 选择传输模式: SSE
4. 保存并测试连接

## 📚 API文档

详细的API文档请参考:

- [MCP协议规范](https://modelcontextprotocol.io/)
- [工具接口文档](docs/api.md)
- [配置指南](docs/configuration.md)

## 🤝 贡献指南

我们欢迎所有形式的贡献！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/

# 代码格式化
black shell_mcp_server.py

# 类型检查
mypy shell_mcp_server.py
```

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Model Context Protocol](https://modelcontextprotocol.io/) - 协议规范
- [paramiko](https://www.paramiko.org/) - SSH连接库
- [aiohttp](https://aiohttp.readthedocs.io/) - 异步HTTP框架

## 📞 支持

- 🐛 [报告Bug](https://github.com/yourusername/shell-mcp/issues)
- 💡 [功能建议](https://github.com/yourusername/shell-mcp/issues)
- 📖 [文档问题](https://github.com/yourusername/shell-mcp/issues)

## 🗺️ 路线图

- [ ] Web管理界面
- [ ] 更多认证方式支持
- [ ] 命令执行历史记录
- [ ] 集群部署支持
- [ ] 监控和指标收集

---

**⚠️ 免责声明**: 本工具主要用于开发和测试目的。在生产环境中使用前，请确保充分了解其安全风险并采取适当的安全措施。
