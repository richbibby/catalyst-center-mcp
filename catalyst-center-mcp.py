from fastmcp import FastMCP
import requests
import urllib3
import json
import os
from dotenv import load_dotenv
import asyncio # Added asyncio
from typing import Optional, List, Dict, Any

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Global token storage and lock
_current_token = None
_token_lock = asyncio.Lock()

# Create an MCP server
# This MCP server provides tools to interact with Cisco Catalyst Center:
# - fetch_devices: Fetches a list of devices.
# - fetch_sites: Fetches a list of sites.
# - fetch_interfaces: Fetches interface information for a specific device.
# - get_clients_list: Retrieves the list of clients with filtering and sorting.
# - get_client_details_by_mac: Retrieves specific client information by MAC address.
# - get_clients_count: Retrieves the total count of clients with filtering.
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

# ---- Client API Functions ----

@mcp.tool()
async def get_clients_list(
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 1,
    sort_by: Optional[str] = None,
    order: Optional[str] = "asc",
    client_type: Optional[str] = None, # 'type' is a reserved keyword
    os_type: Optional[List[str]] = None,
    os_version: Optional[List[str]] = None,
    site_hierarchy: Optional[List[str]] = None,
    site_hierarchy_id: Optional[List[str]] = None,
    site_id: Optional[List[str]] = None,
    ipv4_address: Optional[List[str]] = None,
    ipv6_address: Optional[List[str]] = None,
    mac_address: Optional[List[str]] = None,
    wlc_name: Optional[List[str]] = None,
    connected_network_device_name: Optional[List[str]] = None,
    ssid: Optional[List[str]] = None,
    band: Optional[List[str]] = None,
    view: Optional[List[str]] = None,
    attribute: Optional[List[str]] = None,
    x_caller_id: Optional[str] = "Roo-MCP-get_clients_list"
) -> str:
    """
    Retrieves the list of clients, with basic filtering and sorting.
    Defaults to the last 24 hours if startTime and endTime are not provided.
    API Spec: GET /dna/data/api/v1/clients
    """
    try:
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/data/api/v1/clients"
        headers = {
            "X-Auth-Token": token, 
            "Accept": "application/json",
            "X-CALLER-ID": x_caller_id
        }
        
        params: Dict[str, Any] = {}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if sort_by is not None:
            params["sortBy"] = sort_by
        if order is not None:
            params["order"] = order
        if client_type is not None:
            params["type"] = client_type
        if os_type is not None:
            params["osType"] = os_type
        if os_version is not None:
            params["osVersion"] = os_version
        if site_hierarchy is not None:
            params["siteHierarchy"] = site_hierarchy
        if site_hierarchy_id is not None:
            params["siteHierarchyId"] = site_hierarchy_id
        if site_id is not None:
            params["siteId"] = site_id
        if ipv4_address is not None:
            params["ipv4Address"] = ipv4_address
        if ipv6_address is not None:
            params["ipv6Address"] = ipv6_address
        if mac_address is not None:
            params["macAddress"] = mac_address
        if wlc_name is not None:
            params["wlcName"] = wlc_name
        if connected_network_device_name is not None:
            params["connectedNetworkDeviceName"] = connected_network_device_name
        if ssid is not None:
            params["ssid"] = ssid
        if band is not None:
            params["band"] = band
        if view is not None:
            params["view"] = view
        if attribute is not None:
            params["attribute"] = attribute

        response = requests.get(url, headers=headers, params=params, verify=False)

        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        elif response.status_code == 401:
            global _current_token
            async with _token_lock:
                _current_token = None
            token = await get_or_refresh_token()
            headers["X-Auth-Token"] = token
            response = requests.get(url, headers=headers, params=params, verify=False)
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                raise Exception(f"Failed to get clients list after token refresh. Status: {response.status_code}, Body: {response.text}")
        else:
            raise Exception(f"Failed to get clients list. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        raise Exception(f"Error in get_clients_list: {str(e)}")

@mcp.tool()
async def get_client_details_by_mac(
    client_mac_address: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    view: Optional[List[str]] = None,
    attribute: Optional[List[str]] = None,
    x_caller_id: Optional[str] = "Roo-MCP-get_client_details_by_mac"
) -> str:
    """
    Retrieves specific client information matching the MAC address.
    Defaults to the last 24 hours if startTime and endTime are not provided.
    API Spec: GET /dna/data/api/v1/clients/{id}
    
    Args:
        client_mac_address: The MAC address of the client.
        start_time: Start time in UNIX epoch ms.
        end_time: End time in UNIX epoch ms.
        view: List of views to include (e.g., ["Wireless", "WirelessHealth"]).
        attribute: List of specific attributes to include.
        x_caller_id: Optional X-CALLER-ID header value.
    """
    try:
        token = await get_or_refresh_token()
        # The API spec indicates {id} is the MAC address.
        # Ensure MAC address is URL-encoded if it contains special characters, though typically not needed for MACs.
        url = f"{CCC_HOST}/dna/data/api/v1/clients/{client_mac_address}"
        headers = {
            "X-Auth-Token": token, 
            "Accept": "application/json",
            "X-CALLER-ID": x_caller_id
        }
        
        params: Dict[str, Any] = {}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if view is not None:
            params["view"] = view
        if attribute is not None:
            params["attribute"] = attribute

        response = requests.get(url, headers=headers, params=params, verify=False)

        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        elif response.status_code == 401:
            global _current_token
            async with _token_lock:
                _current_token = None
            token = await get_or_refresh_token()
            headers["X-Auth-Token"] = token
            response = requests.get(url, headers=headers, params=params, verify=False)
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                raise Exception(f"Failed to get client details for {client_mac_address} after token refresh. Status: {response.status_code}, Body: {response.text}")
        elif response.status_code == 404:
             raise Exception(f"Client with MAC address {client_mac_address} not found. Status: 404, Body: {response.text}")
        else:
            raise Exception(f"Failed to get client details for {client_mac_address}. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        raise Exception(f"Error in get_client_details_by_mac for {client_mac_address}: {str(e)}")

@mcp.tool()
async def get_clients_count(
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    client_type: Optional[str] = None,
    os_type: Optional[List[str]] = None,
    os_version: Optional[List[str]] = None,
    site_hierarchy: Optional[List[str]] = None,
    site_hierarchy_id: Optional[List[str]] = None,
    site_id: Optional[List[str]] = None,
    ipv4_address: Optional[List[str]] = None,
    ipv6_address: Optional[List[str]] = None,
    mac_address: Optional[List[str]] = None,
    wlc_name: Optional[List[str]] = None,
    connected_network_device_name: Optional[List[str]] = None,
    ssid: Optional[List[str]] = None,
    band: Optional[List[str]] = None,
    x_caller_id: Optional[str] = "Roo-MCP-get_clients_count"
) -> str:
    """
    Retrieves the total count of clients by applying basic filtering.
    Defaults to the last 24 hours if startTime and endTime are not provided.
    API Spec: GET /dna/data/api/v1/clients/count
    """
    try:
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/data/api/v1/clients/count"
        headers = {
            "X-Auth-Token": token, 
            "Accept": "application/json",
            "X-CALLER-ID": x_caller_id
        }
        
        params: Dict[str, Any] = {}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if client_type is not None:
            params["type"] = client_type # API uses 'type'
        if os_type is not None:
            params["osType"] = os_type
        if os_version is not None:
            params["osVersion"] = os_version
        if site_hierarchy is not None:
            params["siteHierarchy"] = site_hierarchy
        if site_hierarchy_id is not None:
            params["siteHierarchyId"] = site_hierarchy_id
        if site_id is not None:
            params["siteId"] = site_id
        if ipv4_address is not None:
            params["ipv4Address"] = ipv4_address
        if ipv6_address is not None:
            params["ipv6Address"] = ipv6_address
        if mac_address is not None:
            params["macAddress"] = mac_address
        if wlc_name is not None:
            params["wlcName"] = wlc_name
        if connected_network_device_name is not None:
            params["connectedNetworkDeviceName"] = connected_network_device_name
        if ssid is not None:
            params["ssid"] = ssid
        if band is not None:
            params["band"] = band

        response = requests.get(url, headers=headers, params=params, verify=False)

        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        elif response.status_code == 401:
            global _current_token
            async with _token_lock:
                _current_token = None
            token = await get_or_refresh_token()
            headers["X-Auth-Token"] = token
            response = requests.get(url, headers=headers, params=params, verify=False)
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                raise Exception(f"Failed to get clients count after token refresh. Status: {response.status_code}, Body: {response.text}")
        else:
            raise Exception(f"Failed to get clients count. Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        raise Exception(f"Error in get_clients_count: {str(e)}")

# ---- End Client API Functions ----
if __name__ == "__main__":
    # This script defines an MCP server for Cisco Catalyst Center.
    # When run directly (e.g., `python catalyst-center-mcp.py`), it starts the FastMCP server.
    #
    # The server provides the following tools:
    # - fetch_devices: Fetches a list of devices.
    # - fetch_sites: Fetches a list of sites.
    # - fetch_interfaces: Fetches interface information for a specific device.
    # - get_clients_list: Retrieves the list of clients with filtering and sorting.
    # - get_client_details_by_mac: Retrieves specific client information by MAC address.
    # - get_clients_count: Retrieves the total count of clients with filtering.
    #
    # To test these functions locally (outside of the MCP framework, for direct script execution):
    # 1. Ensure your .env file is configured with CCC_HOST, CCC_USER, and CCC_PWD.
    # 2. Uncomment and adapt the example `async def main():` block below.
    #
    # Example for local testing (uncomment and modify as needed):
    # async def main():
    #     load_dotenv() # Ensure environment variables are loaded
    #     if not (os.getenv('CCC_HOST') and os.getenv('CCC_USER') and os.getenv('CCC_PWD')):
    #         print("CCC_HOST, CCC_USER, and CCC_PWD must be set in .env for local testing.")
    #         return
    #
    #     try:
    #         print("--- Testing fetch_devices ---")
    #         devices = await fetch_devices()
    #         print(devices)
    #
    #         print("\n--- Testing fetch_sites ---")
    #         sites = await fetch_sites()
    #         print(sites)
    #
    #         # Example: Fetch interfaces for the first device found (if any)
    #         # devices_data = json.loads(devices)
    #         # if devices_data.get("response"):
    #         #     first_device_id = devices_data["response"][0].get("id")
    #         #     if first_device_id:
    #         #         print(f"\n--- Testing fetch_interfaces for device {first_device_id} ---")
    #         #         interfaces = await fetch_interfaces(device_id=first_device_id)
    #         #         print(interfaces)
    #
    #         print("\n--- Testing get_clients_list (default last 24h) ---")
    #         clients_list = await get_clients_list(limit=5) # Limit for brevity
    #         print(clients_list)
    #
    #         # Example: Get details for a specific MAC (replace with a valid MAC from your environment)
    #         # test_mac = "AA:BB:CC:DD:EE:FF"
    #         # print(f"\n--- Testing get_client_details_by_mac for {test_mac} ---")
    #         # client_details = await get_client_details_by_mac(client_mac_address=test_mac)
    #         # print(client_details)
    #
    #         print("\n--- Testing get_clients_count (default last 24h) ---")
    #         clients_count = await get_clients_count()
    #         print(clients_count)
    #
    #     except Exception as e:
    #         print(f"An error occurred during local testing: {e}")
    #
    # if __name__ == "__main__": # This check is already present, the main() call would be inside it
    #    # asyncio.run(main()) # Call the local test main function
    #    pass # The mcp.run() below is the primary purpose when __name__ == "__main__"
    mcp.run()