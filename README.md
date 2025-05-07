# Catalyst Center MCP

A Python-based MCP (Model-Controller-Provider) server for Cisco Catalyst Center (formerly DNA Center) that provides tools for device management and monitoring.

## Features

- Authentication with Catalyst Center
- Device discovery and listing
- Simple and extensible MCP server implementation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/catalyst-center-mcp.git
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

## Usage

1. Start the MCP server:
```bash
python catalyst-center-mcp.py
```

2. Use the test client to interact with the server:
```bash
python test_client.py
```

## Available Tools

- `authenticate`: Authenticates with Cisco Catalyst Center and returns a token
- `fetch_devices`: Fetches a list of devices from Cisco Catalyst Center

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 