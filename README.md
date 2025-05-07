# Catalyst Center MCP

A Python-based MCP (Model Context Protocol) server for Cisco Catalyst Center (formerly DNA Center) that provides tools for device management and monitoring.

## Features

- Authentication with Catalyst Center
- Device discovery and listing
- Simple and extensible MCP server implementation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/richbibby/catalyst-center-mcp.git
cd catalyst-center-mcp
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Update the configuration in `catalyst-center-mcp.py`:
```python
CCC_HOST = "your-catalyst-center-host"
CCC_USER = "your-username"
CCC_PWD = "your-password"
```

## Usage With Claude Desktop Client

1. Configure Claude Desktop to use this MCP server:

- Open Claude Desktop
- Go to Settings > Developer > Edit Config
- Add the following configuration file `claude_desktop_config.json`

```  
{
  "mcpServers": {
    "catalyst-center-mcp": {
      "command": "/Users/rich/dev/ccc_mcp/venv/bin/fastmcp",
      "args": [
        "run",
        "/Users/rich/dev/ccc_mcp/catalyst-center-mcp.py"
      ]
    }
  }
}
```

- Replace the path's above to reflect your local environment.

2. Restart Claude Desktop

3. Interact with Claude Desktop:

- Ask Claude to perform actions like "Show me the devices in my Cisco Catalyst Center"
- Claude will use the MCP server to authenticate and fetch device information

![Claude Desktop with Catalyst Center MCP](images/Claude_2.png)

![Claude Desktop with Catalyst Center MCP](images/Claude_1.png)


## Available Tools

- `authenticate`: Authenticates with Cisco Catalyst Center and returns a token
- `fetch_devices`: Fetches a list of devices from Cisco Catalyst Center

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 