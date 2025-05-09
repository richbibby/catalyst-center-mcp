from fastmcp import FastMCP
import requests
import urllib3
import json
import os
from dotenv import load_dotenv
import asyncio # Added asyncio

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global token storage and lock
_current_token = None
_token_lock = asyncio.Lock()

# Create an MCP server
mcp = FastMCP("Catalyst Center MCP")

# Configuration from environment variables
CCC_HOST = os.getenv('CCC_HOST')
CCC_USER = os.getenv('CCC_USER')
CCC_PWD = os.getenv('CCC_PWD')

# Internal function to perform authentication
async def _perform_authentication() -> str:
    """Performs authentication with Cisco Catalyst Center and returns a token."""
    url = f"{CCC_HOST}/dna/system/api/v1/auth/token"
    # In a real async environment, consider using an async HTTP client like httpx
    # For simplicity with 'requests', this will run synchronously within the async def.
    # FastMCP typically runs tools in a thread pool, mitigating some blocking.
    response = requests.post(url, auth=(CCC_USER, CCC_PWD), verify=False)
    if response.status_code == 200:
        token = response.json().get("Token")
        if not token:
            raise Exception("Authentication successful, but no token found in response.")
        return token
    else:
        raise Exception(f"Failed to authenticate with Cisco Catalyst Center. Status: {response.status_code}, Body: {response.text}")

# Helper function to get or refresh the token
async def get_or_refresh_token() -> str:
    """Gets the current token or refreshes it if necessary."""
    global _current_token
    async with _token_lock:
        if _current_token is None:
            # print("DEBUG: Token is None or invalid, performing new authentication.") # Optional for debugging
            _current_token = await _perform_authentication()
            # print(f"DEBUG: New token obtained: {_current_token[:10]}...") # Optional for debugging
        return _current_token

# Fetch devices from CCC
@mcp.tool()
async def fetch_devices() -> str:
    """Fetches a list of devices from Cisco Catalyst Center"""
    try:
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/intent/api/v1/network-device"
        headers = {"X-Auth-Token": token, "Accept": "application/json"}
        response = requests.get(url, headers=headers, verify=False)

        if response.status_code == 200:
            devices = response.json().get("response", [])
            return json.dumps(devices, indent=2)
        elif response.status_code == 401: # Token expired or invalid
            # print("DEBUG: Token expired for fetch_devices. Refreshing.") # Optional
            global _current_token
            async with _token_lock: # Ensure safe modification if multiple coroutines hit this
                _current_token = None # Invalidate token
            
            token = await get_or_refresh_token() # Get new token
            headers["X-Auth-Token"] = token # Update headers
            response = requests.get(url, headers=headers, verify=False) # Retry

            if response.status_code == 200:
                devices = response.json().get("response", [])
                return json.dumps(devices, indent=2)
            else:
                raise Exception(f"Failed to fetch devices after token refresh. Status: {response.status_code}, Body: {response.text}")
        else:
            raise Exception(f"Failed to fetch devices. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        # print(f"DEBUG: Error in fetch_devices: {str(e)}") # Optional
        raise Exception(f"Error fetching devices: {str(e)}")

# Fetch sites from CCC
@mcp.tool()
async def fetch_sites() -> str:
    """Fetches a list of sites from Cisco Catalyst Center"""
    try:
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/intent/api/v1/site"
        headers = {"X-Auth-Token": token, "Accept": "application/json"}
        response = requests.get(url, headers=headers, verify=False)

        if response.status_code == 200:
            sites = response.json().get("response", [])
            return json.dumps(sites, indent=2)
        elif response.status_code == 401: # Token expired or invalid
            # print("DEBUG: Token expired for fetch_sites. Refreshing.") # Optional
            global _current_token
            async with _token_lock:
                _current_token = None # Invalidate token
            
            token = await get_or_refresh_token() # Get new token
            headers["X-Auth-Token"] = token # Update headers
            response = requests.get(url, headers=headers, verify=False) # Retry

            if response.status_code == 200:
                sites = response.json().get("response", [])
                return json.dumps(sites, indent=2)
            else:
                raise Exception(f"Failed to fetch sites after token refresh. Status: {response.status_code}, Body: {response.text}")
        else:
            raise Exception(f"Failed to fetch sites. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        # print(f"DEBUG: Error in fetch_sites: {str(e)}") # Optional
        raise Exception(f"Error fetching sites: {str(e)}")

# Fetch interfaces from CCC
@mcp.tool()
async def fetch_interfaces(device_id: str) -> str:
    """Fetches interface information for a specific device from Cisco Catalyst Center

    Args:
        device_id: The ID of the device to fetch interfaces for
    """
    try:
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/intent/api/v1/interface/network-device/{device_id}"
        headers = {"X-Auth-Token": token, "Accept": "application/json"}
        response = requests.get(url, headers=headers, verify=False)

        if response.status_code == 200:
            interfaces = response.json().get("response", [])
            return json.dumps(interfaces, indent=2)
        elif response.status_code == 401: # Token expired or invalid
            # print(f"DEBUG: Token expired for fetch_interfaces (device: {device_id}). Refreshing.") # Optional
            global _current_token
            async with _token_lock:
                _current_token = None # Invalidate token
            
            token = await get_or_refresh_token() # Get new token
            headers["X-Auth-Token"] = token # Update headers
            response = requests.get(url, headers=headers, verify=False) # Retry

            if response.status_code == 200:
                interfaces = response.json().get("response", [])
                return json.dumps(interfaces, indent=2)
            else:
                raise Exception(f"Failed to fetch interfaces for device {device_id} after token refresh. Status: {response.status_code}, Body: {response.text}")
        else:
            raise Exception(f"Failed to fetch interfaces for device {device_id}. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        # print(f"DEBUG: Error in fetch_interfaces (device: {device_id}): {str(e)}") # Optional
        raise Exception(f"Error fetching interfaces for device {device_id}: {str(e)}")

if __name__ == "__main__":
    # Example of how to run the MCP server (if you were running this file directly)
    # For actual use, FastMCP handles running it.
    # To test locally:
    # async def main():
    #     # You'd need to set up CCC_HOST, CCC_USER, CCC_PWD in your environment
    #     # or load_dotenv() would need a .env file with these.
    #     try:
    #         print("Attempting to fetch devices...")
    #         devices_json = await fetch_devices()
    #         print("Devices:", devices_json)
    #
    #         print("\nAttempting to fetch sites...")
    #         sites_json = await fetch_sites()
    #         print("Sites:", sites_json)
    #
    #         # Assuming you have a device_id to test with, e.g., from the devices_json output
    #         # if devices_json:
    #         #     devices_data = json.loads(devices_json)
    #         #     if devices_data:
    #         #         test_device_id = devices_data[0].get('id')
    #         #         if test_device_id:
    #         #             print(f"\nAttempting to fetch interfaces for device {test_device_id}...")
    #         #             interfaces_json = await fetch_interfaces(device_id=test_device_id)
    #         #             print(f"Interfaces for {test_device_id}:", interfaces_json)
    #
    #     except Exception as e:
    #         print(f"An error occurred during testing: {e}")
    #
    # if os.getenv('CCC_HOST') and os.getenv('CCC_USER') and os.getenv('CCC_PWD'):
    #    asyncio.run(main())
    # else:
    #    print("Skipping local test run as CCC environment variables are not fully set.")
    #
    mcp.run()