# Shell MCP Server

A powerful shell interface based on Model Context Protocol (MCP) that supports local and remote command execution with comprehensive security mechanisms and session management.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-2024--11--05-orange.svg)](https://modelcontextprotocol.io)

## ✨ Key Features

- 🖥️ **Local Command Execution**: Execute shell commands in your local environment
- 🔗 **Remote SSH Execution**: Connect to remote servers via SSH and execute commands
- 🛡️ **Security Protection**: Built-in command blacklist/whitelist to prevent dangerous command execution
- 💾 **Session Management**: Intelligent session management with environment variable persistence
- 🌐 **Multiple Transport Modes**: Support for both stdio and SSE transport modes
- 📝 **Comprehensive Logging**: Detailed logging and error tracking
- ⚡ **Async Processing**: High-performance asynchronous processing based on asyncio

## 🚀 Quick Start

### Requirements

- Python 3.8+
- Supported Operating Systems: Windows, Linux, macOS

### Installation

1. **Clone Repository**

```bash
git clone https://github.com/cnchef/shell-mcp.git
cd shell-mcp
```

2. **Install Dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure Server**

```bash
# Copy configuration template
cp config.json.example config.json
# Edit configuration file
nano config.json
```

### Basic Usage

1. **Stdio Mode (Default)**

```bash
python shell_mcp_server.py
```

2. **SSE Mode**

```bash
# Local listening
python shell_mcp_server.py --mode sse --port 8000

# Listen on all interfaces
python shell_mcp_server.py --mode sse --host 0.0.0.0 --port 8000
```

3. **Custom Configuration File**

```bash
python shell_mcp_server.py --config my_config.json
```

4. **Set Log Level**

```bash
python shell_mcp_server.py --log-level DEBUG
```

## 📖 Configuration Guide

### config.json Structure

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
    "file": "shell_mcp.log"
  }
}
```

### Security Configuration

- **Blacklist Mode**: Default deny dangerous commands, recommended for production
- **Whitelist Mode**: Only allow specified commands, suitable for high-security environments
- **Mixed Mode**: Combination of blacklist and whitelist for flexible control

## 🔧 MCP Tool Interface

### execute_command

Execute commands on local or remote hosts

**Parameters:**

- `command` (required): Command to execute
- `host` (optional): Remote host address
- `username` (optional): SSH username
- `password` (optional): SSH password
- `key_file` (optional): SSH private key file path
- `port` (optional): SSH port, default 22
- `session` (optional): Session name, default 'default'
- `env` (optional): Environment variables dictionary
- `cwd` (optional): Local execution working directory
- `force_execute` (optional): Force execute dangerous commands, default false

**Example:**

```json
{
  "command": "ls -la /home",
  "host": "192.168.1.100",
  "username": "admin",
  "session": "my_session"
}
```

### get_tools

Get a list of all tools supported by the server

## 🌐 SSE Mode Endpoints

- `GET /message` - Establish SSE connection
- `POST /message` - Send MCP message
- `GET /` - Server information
- `POST /reset` - Reset connection state

## 🛡️ Security Considerations

### ⚠️ Important Security Warnings

1. **Before Production Use**:

   - Modify default SSH connection configuration
   - Set strong passwords or use SSH key authentication
   - Configure appropriate command blacklist/whitelist for your environment
   - Limit network access and port exposure
2. **Command Filtering Recommendations**:

   - Prioritize whitelist mode
   - Regularly review and update security rules
   - Monitor command execution logs
3. **Network Security**:

   - Run service behind firewall
   - Use VPN or SSH tunnel for access
   - Regularly update dependencies

### Default Protection

The system has built-in protection for the following dangerous commands:

- System deletion commands (`rm -rf /`)
- System shutdown/reboot (`shutdown`, `reboot`)
- Disk formatting (`mkfs`, `fdisk`)
- User management (`userdel`, `passwd root`)
- Permission modification (`chmod 777 /`)

## 🧪 Testing Examples

### stdio Mode Testing

#### Method 1: Using Built-in Test Scripts

```bash
# Automated testing + interactive mode
python test_stdio.py

# Simple pipe testing
python test_simple.py

# Manual file input testing
python test_manual.py
```

#### Method 2: Manual JSON Input

```bash
# Start stdio mode
python shell_mcp_server.py --mode stdio

# Then input JSON commands line by line:
# {"jsonrpc":"2.0","method":"initialize","params":{},"id":1}
# {"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}
# {"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":3}
```

### Testing SSE Mode with curl

```bash
# 1. Start server
python shell_mcp_server.py --mode sse --port 8000

# 2. Test connection
curl http://localhost:8000/message

# 3. Initialize MCP
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'

# 4. Get tool list
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}'

# 5. Execute command
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"execute_command","arguments":{"command":"pwd"}},"id":3}'
```

### Integration with Cherry Studio

1. Add MCP server in Cherry Studio
2. Configure endpoint: `http://localhost:8000/message`
3. Select transport mode: SSE
4. Save and test connection

## 📚 API Documentation

For detailed API documentation, please refer to:

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Tool Interface Documentation](docs/api.md)
- [Configuration Guide](docs/configuration.md)

## 🤝 Contributing Guide

We welcome all forms of contributions!

1. Fork this repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

### Development Environment Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black shell_mcp_server.py

# Type checking
mypy shell_mcp_server.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) - Protocol specification
- [paramiko](https://www.paramiko.org/) - SSH connection library
- [aiohttp](https://aiohttp.readthedocs.io/) - Asynchronous HTTP framework

## 📞 Support

- 🐛 [Report Bug](https://github.com/cnchef/shell-mcp/issues)
- 💡 [Feature Request](https://github.com/cnchef/shell-mcp/issues)
- 📖 [Documentation Issue](https://github.com/cnchef/shell-mcp/issues)

## 🗺️ Roadmap

- [ ] Web management interface
- [ ] More authentication methods support
- [ ] Command execution history
- [ ] Cluster deployment support
- [ ] Monitoring and metrics collection

---

**⚠️ Disclaimer**: This tool is mainly designed for development and testing purposes. Before using in production environments, please ensure you fully understand its security risks and take appropriate security measures.