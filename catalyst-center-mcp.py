from fastmcp import FastMCP
import requests
import urllib3
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create an MCP server
mcp = FastMCP("Catalyst Center MCP")

# Configuration from environment variables
CCC_HOST = os.getenv('CCC_HOST')
CCC_USER = os.getenv('CCC_USER')
CCC_PWD = os.getenv('CCC_PWD')

# Authenticate with CCC/DNAC
@mcp.tool()
async def authenticate() -> str:
    """Authenticates with Cisco Catalyst Center and returns a token"""
    url = f"{CCC_HOST}/dna/system/api/v1/auth/token"
    response = requests.post(url, auth=(CCC_USER, CCC_PWD), verify=False)
    if response.status_code == 200:
        return response.json()["Token"]
    else:
        raise Exception("Failed to authenticate with Cisco Catalyst Center")

# Fetch devices from CCC
@mcp.tool()
async def fetch_devices(token: str) -> str:
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

# Fetch sites from CCC
@mcp.tool()
async def fetch_sites(token: str) -> str:
    """Fetches a list of sites from Cisco Catalyst Center

    Args:
        token: Authentication token from authenticate()
    """
    url = f"{CCC_HOST}/dna/intent/api/v1/site"
    headers = {"X-Auth-Token": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        sites = response.json().get("response", [])
        return json.dumps(sites, indent=2)
    else:
        raise Exception("Failed to fetch sites from CCC")

# Fetch interfaces from CCC
@mcp.tool()
async def fetch_interfaces(token: str, device_id: str) -> str:
    """Fetches interface information for a specific device from Cisco Catalyst Center

    Args:
        token: Authentication token from authenticate()
        device_id: The ID of the device to fetch interfaces for
    """
    url = f"{CCC_HOST}/dna/intent/api/v1/interface/network-device/{device_id}"
    headers = {"X-Auth-Token": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        interfaces = response.json().get("response", [])
        return json.dumps(interfaces, indent=2)
    else:
        raise Exception(f"Failed to fetch interfaces for device {device_id} from CCC")

if __name__ == "__main__":
    mcp.run()