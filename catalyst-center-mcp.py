from fastmcp import FastMCP
import requests
import urllib3
import json

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create an MCP server
mcp = FastMCP("Catalyst Center MCP")

# Configuration
CCC_HOST = "https://sandboxdnac.cisco.com"
CCC_USER = "devnetuser"
CCC_PWD = "Cisco123!"

# Authenticate with CCC/DNAC
@mcp.tool()
def authenticate() -> str:
    """Authenticates with Cisco Catalyst Center and returns a token"""
    url = f"{CCC_HOST}/dna/system/api/v1/auth/token"
    response = requests.post(url, auth=(CCC_USER, CCC_PWD), verify=False)
    if response.status_code == 200:
        return response.json()["Token"]
    else:
        raise Exception("Failed to authenticate with Cisco Catalyst Center")

# Fetch devices from CCC
@mcp.tool()
def fetch_devices(token: str) -> str:
    """Fetches a list of devices from Cisco Catalyst Center

    Args:
        token: Authentication token from authenticate()
    """
    url = f"{CCC_HOST}/dna/intent/api/v1/network-device"
    headers = {"X-Auth-Token": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        devices = response.json().get("response", [])
        return json.dumps(devices, indent=2)
    else:
        raise Exception("Failed to fetch devices from CCC")