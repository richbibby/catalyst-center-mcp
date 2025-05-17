from fastmcp import FastMCP
import requests
import urllib3
import json
import os
from dotenv import load_dotenv
import asyncio # Added asyncio
from typing import Optional, List, Dict, Any
from pydantic import Json # Added Json for type hinting
from datetime import datetime, timedelta, timezone # Added for time conversion tool

# Determine the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the .env file relative to the script's directory
dotenv_path = os.path.join(script_dir, '.env')

# Load environment variables from .env file
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    # This print statement is for debugging; you can remove or comment it out later.
    print(f"Warning: .env file not found at {dotenv_path}. Environment variables may not be loaded as expected.")
    # If the .env file is critical, you might want to raise an error instead:
    # raise FileNotFoundError(f"Critical: .env file not found at {dotenv_path}. Cannot proceed.")
    # For now, we'll just load from environment if .env is not found, which is default load_dotenv behavior
    # if no path is specified and file doesn't exist.
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
mcp: FastMCP = FastMCP("Catalyst Center MCP")

# Configuration from environment variables
CCC_HOST = os.getenv('CCC_HOST')
CCC_USER = os.getenv('CCC_USER')
CCC_PWD = os.getenv('CCC_PWD')

# Internal function to perform authentication
async def _perform_authentication() -> str:
    """Performs authentication with Cisco Catalyst Center and returns a token."""
    # Assign to local variables for type checking clarity and to help Mypy
    host = CCC_HOST
    user = CCC_USER
    pwd = CCC_PWD

    if not host or not user or not pwd:
        missing_vars = []
        if not host: missing_vars.append("CCC_HOST")
        if not user: missing_vars.append("CCC_USER")
        if not pwd: missing_vars.append("CCC_PWD")
        # Ensure the error message clearly indicates which variables are missing
        raise ValueError(
            f"{', '.join(missing_vars)} environment variable(s) must be set "
            "for authentication with Cisco Catalyst Center."
        )
    
    # At this point, Mypy should infer host, user, and pwd as str
    # because the check above would have raised ValueError if they were None or empty.
    
    url = f"{host}/dna/system/api/v1/auth/token"
    
    # Explicitly create the auth tuple with types Mypy can verify
    auth_credentials: tuple[str, str] = (user, pwd)
    
    # In a real async environment, consider using an async HTTP client like httpx
    # For simplicity with 'requests', this will run synchronously within the async def.
    # FastMCP typically runs tools in a thread pool, mitigating some blocking.
    response = requests.post(url, auth=auth_credentials, verify=False)
    if response.status_code == 200:
        token_data = response.json() # Store intermediate json
        token_val = token_data.get("Token") # Use a different variable name
        if not token_val:
            raise Exception("Authentication successful, but no token found in response.")
        # Ensure token is a string, as expected by the return type
        if not isinstance(token_val, str):
            raise Exception(f"Expected token to be a string, but got {type(token_val)}.")
        return token_val
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
async def fetch_devices(filters: Optional[Json[Dict[str, Any]]] = None) -> str:
    """
    Fetches a list of devices from Cisco Catalyst Center using the `/dna/intent/api/v1/network-device` endpoint.
    Supports extensive filtering capabilities.  Never use this tool without a filter.

    Args:
        filters (Optional[Json[Dict[str, Any]]]): A JSON string or dictionary of filter parameters to apply. 
            If a JSON string is provided, it will be parsed into a dictionary.
            Most filter values should be provided as a list of strings, e.g., `{"hostname": ["router1"]}`.
            Refer to the Cisco Catalyst Center API documentation for a complete list of filterable attributes.

            Common Filter Parameters:
            - id (List[str]): List of device UUIDs.
            - hostname (List[str]): List of device hostnames.
            - managementIpAddress (List[str]): List of management IP addresses.
            - macAddress (List[str]): List of MAC addresses.
            - serialNumber (List[str]): List of device serial numbers.
            - softwareVersion (List[str]): List of software versions (e.g., ["17.3.4a"]).
            - platformId (List[str]): List of platform IDs (e.g., ["C9300-48UXM"]).
            - family (List[str]): List of device families (e.g., ["Switches and Hubs"]).
            - type (List[str]): List of device types (e.g., ["Cisco Catalyst 9300 Switch"]).
            - role (List[str]): List of device roles (e.g., ["CORE", "ACCESS", "DISTRIBUTION"]).
            - roleSource (List[str]): Source of the role (e.g., ["MANUAL"]).
            - reachabilityStatus (List[str]): E.g., ["Reachable", "Unreachable"].
            - collectionStatus (List[str]): E.g., ["Managed", "Partial Collection Failure"].
            - locationName (List[str]): Full path of location (e.g., ["Global/USA/Building1/Floor1"]).
            - associatedWlcIp (List[str]): For APs, the IP of their WLC.
            - softwareType (List[str]): E.g., ["IOS-XE"].
            - series (List[str]): E.g., ["Cisco Catalyst 9300 Series Switches"].
            
            Pagination and Sorting (values are typically strings, not lists):
            - offset (str): Starting record index for pagination (e.g., "0").
            - limit (str): Maximum number of records to return (e.g., "10").
            - sortBy (str): Attribute to sort by (e.g., "hostname").
            - sortOrder (str): "asc" or "desc".

            Example: 
            `{"role": ["ACCESS"], "softwareVersion": ["17.03.04a"], "limit": "50"}`
    """
    try:
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/intent/api/v1/network-device"
        headers = {"X-Auth-Token": token, "Accept": "application/json"}
        
        # With Json[Dict[str, Any]], 'filters' will be a dict if provided, or None.
        # Pydantic handles the parsing of the JSON string.
        params: Dict[str, Any] = filters if filters is not None else {}

        response = requests.get(url, headers=headers, params=params, verify=False)

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
            response = requests.get(url, headers=headers, params=params, verify=False) # Retry

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
            original_sites = response.json().get("response", [])
            compact_sites = []
            for site in original_sites:
                location_info = {}
                if isinstance(site.get("additionalInfo"), list):
                    for info in site["additionalInfo"]:
                        if isinstance(info, dict) and info.get("nameSpace") == "Location" and isinstance(info.get("attributes"), dict):
                            location_info["type"] = info["attributes"].get("type")
                            location_info["address"] = info["attributes"].get("address")
                            location_info["latitude"] = info["attributes"].get("latitude")
                            location_info["longitude"] = info["attributes"].get("longitude")
                            break 
                
                compact_site = {
                    "id": site.get("id"),
                    "name": site.get("name"),
                    "parentId": site.get("parentId"),
                    "siteNameHierarchy": site.get("siteNameHierarchy"),
                    "type": location_info.get("type"),
                    "address": location_info.get("address"),
                    "latitude": location_info.get("latitude"),
                    "longitude": location_info.get("longitude"),
                }
                compact_sites.append(compact_site)
            return json.dumps(compact_sites, indent=2)
        elif response.status_code == 401: # Token expired or invalid
            # print("DEBUG: Token expired for fetch_sites. Refreshing.") # Optional
            global _current_token
            async with _token_lock:
                _current_token = None # Invalidate token
            
            token = await get_or_refresh_token() # Get new token
            headers["X-Auth-Token"] = token # Update headers
            response = requests.get(url, headers=headers, verify=False) # Retry

            if response.status_code == 200:
                original_sites = response.json().get("response", [])
                compact_sites = []
                for site in original_sites:
                    location_info = {}
                    if isinstance(site.get("additionalInfo"), list):
                        for info in site["additionalInfo"]:
                            if isinstance(info, dict) and info.get("nameSpace") == "Location" and isinstance(info.get("attributes"), dict):
                                location_info["type"] = info["attributes"].get("type")
                                location_info["address"] = info["attributes"].get("address")
                                location_info["latitude"] = info["attributes"].get("latitude")
                                location_info["longitude"] = info["attributes"].get("longitude")
                                break
                    
                    compact_site = {
                        "id": site.get("id"),
                        "name": site.get("name"),
                        "parentId": site.get("parentId"),
                        "siteNameHierarchy": site.get("siteNameHierarchy"),
                        "type": location_info.get("type"),
                        "address": location_info.get("address"),
                        "latitude": location_info.get("latitude"),
                        "longitude": location_info.get("longitude"),
                    }
                    compact_sites.append(compact_site)
                return json.dumps(compact_sites, indent=2)
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

# ---- Helper Time Conversion Tool ----
@mcp.tool()
async def get_api_compatible_time_range(
    time_window: Optional[str] = None,
    start_datetime_iso: Optional[str] = None,
    end_datetime_iso: Optional[str] = None
) -> str:
    """
    Converts various time inputs into a valid startTime and endTime epoch millisecond pair,
    respecting the Catalyst Center API's 30-day limit for startTime.

    Args:
        time_window (Optional[str]): A user-friendly relative time string.
            Supported examples: "last X minutes/hours/days" (e.g., "last 2 hours", "last 7 days"),
            "today", "yesterday", "last 30 days".
            If provided, this takes precedence over specific start/end ISO times.
        start_datetime_iso (Optional[str]): A specific start date/time in ISO 8601 format
            (e.g., "2023-05-15T10:00:00Z" or "2023-05-15T10:00:00-07:00").
            Used if time_window is not provided.
        end_datetime_iso (Optional[str]): A specific end date/time in ISO 8601 format.
            Used if time_window is not provided. Defaults to current time if only start_datetime_iso is given.

    Returns:
        str: A JSON string containing:
             - startTime (int): Calculated start epoch milliseconds.
             - endTime (int): Calculated end epoch milliseconds.
             - adjusted_for_30_day_limit (bool): True if startTime was adjusted.
             - original_request_info (str): Describes the input time parameters.
    """
    now_utc = datetime.now(timezone.utc)
    start_dt_utc: Optional[datetime] = None
    end_dt_utc: Optional[datetime] = None
    adjusted = False
    original_request_info = ""

    if time_window:
        original_request_info = f"time_window='{time_window}'"
        time_window_lower = time_window.lower()
        num_str, unit = "", ""
        parts = time_window_lower.split() # e.g. ["last", "2", "hours"]

        if "last" in parts and len(parts) == 3:
            try:
                num_val = int(parts[1])
                unit = parts[2]
                if unit.startswith("minute"): delta = timedelta(minutes=num_val)
                elif unit.startswith("hour"): delta = timedelta(hours=num_val)
                elif unit.startswith("day"): delta = timedelta(days=num_val)
                else: raise ValueError(f"Unsupported time unit in time_window: {unit}")
                
                end_dt_utc = now_utc
                start_dt_utc = end_dt_utc - delta
            except ValueError:
                raise ValueError(f"Invalid format for 'last X unit' in time_window: '{time_window}'. Expected e.g., 'last 2 hours'.")

        elif time_window_lower == "today":
            end_dt_utc = now_utc
            start_dt_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_window_lower == "yesterday":
            yesterday_dt = now_utc - timedelta(days=1)
            start_dt_utc = yesterday_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt_utc = yesterday_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_window_lower == "last 30 days": # Explicitly handle this common case
            end_dt_utc = now_utc
            start_dt_utc = end_dt_utc - timedelta(days=30)
        else:
            raise ValueError(f"Unsupported time_window format: '{time_window}'. Supported: 'last X minutes/hours/days', 'today', 'yesterday', 'last 30 days'.")

    elif start_datetime_iso:
        original_request_info = f"start_datetime_iso='{start_datetime_iso}'"
        try:
            start_dt_utc = datetime.fromisoformat(start_datetime_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            raise ValueError(f"Invalid start_datetime_iso format: '{start_datetime_iso}'. Expected ISO 8601 format.")
        
        if end_datetime_iso:
            original_request_info += f", end_datetime_iso='{end_datetime_iso}'"
            try:
                end_dt_utc = datetime.fromisoformat(end_datetime_iso.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                raise ValueError(f"Invalid end_datetime_iso format: '{end_datetime_iso}'. Expected ISO 8601 format.")
        else:
            end_dt_utc = now_utc # Default end to now if only start is given
            original_request_info += ", end_datetime_iso=None (defaulted to current time)"
        
        if start_dt_utc > end_dt_utc:
            raise ValueError("start_datetime_iso cannot be after end_datetime_iso.")
    else:
        # Default to last 24 hours if no time input is provided
        original_request_info = "No time parameters provided, defaulting to last 24 hours."
        end_dt_utc = now_utc
        start_dt_utc = end_dt_utc - timedelta(days=1)

    if start_dt_utc is None or end_dt_utc is None: # Should not happen with current logic, but as a safeguard
        raise ValueError("Could not determine start or end time from inputs.")

    # Enforce Catalyst Center API's 30-day limit for startTime
    thirty_days_ago_from_now = now_utc - timedelta(days=30)
    # Ensure we compare against the actual 'now' for the 30-day window, not a potentially user-supplied 'end_dt_utc'
    # that might be in the past.
    
    if start_dt_utc < thirty_days_ago_from_now:
        start_dt_utc = thirty_days_ago_from_now
        adjusted = True
        original_request_info += " (Note: startTime was adjusted to meet the 30-day API limit)"


    start_epoch_ms = int(start_dt_utc.timestamp() * 1000)
    end_epoch_ms = int(end_dt_utc.timestamp() * 1000)

    return json.dumps({
        "startTime": start_epoch_ms,
        "endTime": end_epoch_ms,
        "adjusted_for_30_day_limit": adjusted,
        "original_request_info": original_request_info,
        "start_datetime_utc_iso": start_dt_utc.isoformat(), # For clarity/debugging
        "end_datetime_utc_iso": end_dt_utc.isoformat()      # For clarity/debugging
    }, indent=2)

# ---- Client API Functions ----

@mcp.tool()
async def get_clients_list(
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: Optional[int] = 100, # Default and max cap is 100
    offset: Optional[int] = 1,
    sort_by: Optional[str] = None,
    order: Optional[str] = "asc",
    client_type: Optional[str] = None, 
    os_type: Optional[Json[List[str]]] = None,
    os_version: Optional[Json[List[str]]] = None,
    site_hierarchy: Optional[Json[List[str]]] = None,
    site_hierarchy_id: Optional[Json[List[str]]] = None,
    site_id: Optional[Json[List[str]]] = None,
    ipv4_address: Optional[Json[List[str]]] = None,
    ipv6_address: Optional[Json[List[str]]] = None,
    mac_address: Optional[Json[List[str]]] = None,
    wlc_name: Optional[Json[List[str]]] = None,
    connected_network_device_name: Optional[Json[List[str]]] = None,
    ssid: Optional[Json[List[str]]] = None,
    band: Optional[Json[List[str]]] = None,
    view: Optional[Json[List[str]]] = None,
    attribute: Optional[Json[List[str]]] = None,
    x_caller_id: Optional[str] = "Roo-MCP-get_clients_list"
) -> str:
    """
    Retrieves a list of clients from Cisco Catalyst Center, with comprehensive filtering options.
    This function will not return more than 100 clients. If the query matches more than 100 clients,
    it will return a message suggesting more specific filters, along with the total count of matching clients.
    If `startTime` is not provided, the API defaults to the current time. If `endTime` is not provided,
    it typically implies up to the current time or is unbounded, depending on API behavior.
    Note: If the API indicates data is not ready for the requested endTime, this tool
    will attempt to leverage the `get_clients_count` call's retry logic which handles this.

    Filter Parameters:
    - start_time (Optional[int]): UNIX epoch milliseconds. Filters clients active at or after this time.
                                  Note: The API restricts this to be no more than 30 days before the current time.
                                  Consider using `get_api_compatible_time_range` to generate compliant timestamps.
    - end_time (Optional[int]): UNIX epoch milliseconds. Filters clients active at or before this time.
    - limit (Optional[int]): Maximum number of clients to return. Defaults to 100. If a value greater than 100
                             is provided, it will be capped at 100. The actual number of returned clients
                             may also be limited by the total number of matching clients if less than this value.
    - offset (Optional[int]): Starting record index for pagination. Defaults to 1.
    - sort_by (Optional[str]): Attribute to sort clients by (e.g., "clientConnectionTime", "clientHealthScore").
                               Refer to Cisco DNA Center API documentation for available sortable attributes.
    - order (Optional[str]): Sort order, "asc" (ascending) or "desc" (descending). Defaults to "asc".
    - client_type (Optional[str]): Type of client (e.g., "wired", "wireless"). Internally converted to "Wired" or "Wireless" for the API. API parameter name is 'type'.
    - os_type (Optional[List[str]]): List of client operating systems (e.g., ["Windows", "macOS"]).
    - os_version (Optional[List[str]]): List of client OS versions.
    - site_hierarchy (Optional[List[str]]): Full site hierarchy path (e.g., ["Global/USA/California/SanFrancisco"]).
    - site_hierarchy_id (Optional[List[str]]): List of site hierarchy UUIDs.
    - site_id (Optional[List[str]]): List of site UUIDs.
    - ipv4_address (Optional[List[str]]): List of client IPv4 addresses.
    - ipv6_address (Optional[List[str]]): List of client IPv6 addresses.
    - mac_address (Optional[List[str]]): List of client MAC addresses.
    - wlc_name (Optional[List[str]]): List of Wireless LAN Controller names.
    - connected_network_device_name (Optional[List[str]]): List of names of network devices clients are connected to.
    - ssid (Optional[List[str]]): List of SSIDs clients are connected to.
    - band (Optional[List[str]]): List of wireless bands (e.g., ["2.4GHz", "5GHz"]).
    - view (Optional[List[str]]): List of additional data views to include (e.g., ["Wireless", "WirelessHealth"]).
                                  Refer to API documentation for available views.
    - attribute (Optional[List[str]]): List of specific client attributes to retrieve.
                                       Refer to API documentation for available attributes.
    - x_caller_id (Optional[str]): Custom X-CALLER-ID header value for API requests.
                                   Defaults to "Roo-MCP-get_clients_list".

    Returns:
        str: A JSON string containing the list of clients if count <= 100,
             or a message suggesting more specific filters if count > 100.
             Includes error details if the operation fails.
    API Spec: GET /dna/data/api/v1/clients
    """
    try:
        # First, get the total count of clients matching the filters
        count_response_str = await get_clients_count(
            start_time=start_time,
            end_time=end_time,
            client_type=client_type,
            os_type=os_type,
            os_version=os_version,
            site_hierarchy=site_hierarchy,
            site_hierarchy_id=site_hierarchy_id,
            site_id=site_id,
            ipv4_address=ipv4_address,
            ipv6_address=ipv6_address,
            mac_address=mac_address,
            wlc_name=wlc_name,
            connected_network_device_name=connected_network_device_name,
            ssid=ssid,
            band=band,
            x_caller_id="Roo-MCP-get_clients_list_internal_count" # Internal call ID
        )
        count_data = json.loads(count_response_str)
        response_field_from_count = count_data.get("response")

        extracted_count_value = None
        if isinstance(response_field_from_count, int):
            # Case 1: The 'response' field is directly the integer count (as per some API docs)
            extracted_count_value = response_field_from_count
        elif isinstance(response_field_from_count, dict):
            # Case 2: The 'response' field is a dictionary, hopefully containing a 'count' key
            # (as observed in the traceback: {'response': {'count': 7506}, ...})
            extracted_count_value = response_field_from_count.get("count")
        
        if not isinstance(extracted_count_value, int):
            # If after the above checks, we still don't have an integer, the structure is unexpected.
            error_detail = (
                f"Expected an integer count, but failed to extract it. "
                f"'response' field from count API was: {response_field_from_count} (type: {type(response_field_from_count)}). "
                f"Attempted extraction resulted in: {extracted_count_value} (type: {type(extracted_count_value)})."
            )
            raise Exception(f"Invalid or unexpected data structure for client count. {error_detail}. Full count_data: {count_data}")

        total_matching_clients = extracted_count_value # This should now be the correct integer count

        if total_matching_clients > 100:
            return json.dumps({
                "message": f"Query matches {total_matching_clients} clients, which is more than the allowed 100. Please provide more specific filters.",
                "total_matching_clients": total_matching_clients,
                "response": [] # Keep structure similar to API response
            }, indent=2)

        if total_matching_clients == 0:
            return json.dumps({
                "response": [],
                "version": count_data.get("version", "1.0"), # Use version from count_data if available
                "message": "No clients match the provided filters."
            }, indent=2)

        # Proceed to fetch the client list if 0 < total_matching_clients <= 100
        token = await get_or_refresh_token()
        url = f"{CCC_HOST}/dna/data/api/v1/clients"
        headers = {
            "X-Auth-Token": token, 
            "Accept": "application/json",
            "X-CALLER-ID": x_caller_id # Use original x_caller_id for the list request
        }
        
        params: Dict[str, Any] = {}
        if start_time is not None: params["startTime"] = start_time
        if end_time is not None: params["endTime"] = end_time
        
        # Determine effective limit for the API call
        # User's 'limit' parameter defaults to 100. Cap it at 100 if they provide more.
        user_capped_limit = min(limit, 100) if limit is not None else 100
        # Request at most total_matching_clients, and at least 1 (since total_matching_clients > 0 here)
        effective_api_limit = max(1, min(user_capped_limit, total_matching_clients))
        params["limit"] = effective_api_limit
        
        if offset is not None: params["offset"] = offset
        if sort_by is not None: params["sortBy"] = sort_by
        if order is not None: params["order"] = order
        
        processed_client_type = client_type
        if client_type is not None:
            if client_type.lower() == "wired":
                processed_client_type = "Wired"
            elif client_type.lower() == "wireless":
                processed_client_type = "Wireless"
            # If it's something else, pass it as is, API will validate
        if processed_client_type is not None: params["type"] = processed_client_type
        
        if os_type is not None: params["osType"] = os_type
        if os_version is not None: params["osVersion"] = os_version
        if site_hierarchy is not None: params["siteHierarchy"] = site_hierarchy
        if site_hierarchy_id is not None: params["siteHierarchyId"] = site_hierarchy_id
        if site_id is not None: params["siteId"] = site_id
        if ipv4_address is not None: params["ipv4Address"] = ipv4_address
        if ipv6_address is not None: params["ipv6Address"] = ipv6_address
        if mac_address is not None: params["macAddress"] = mac_address
        if wlc_name is not None: params["wlcName"] = wlc_name
        if connected_network_device_name is not None: params["connectedNetworkDeviceName"] = connected_network_device_name
        if ssid is not None: params["ssid"] = ssid
        if band is not None: params["band"] = band
        if view is not None: params["view"] = view
        if attribute is not None: params["attribute"] = attribute

        response = requests.get(url, headers=headers, params=params, verify=False)

        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        elif response.status_code == 401: # Token expired
            global _current_token
            async with _token_lock:
                _current_token = None # Invalidate token
            token = await get_or_refresh_token() # Get new token
            headers["X-Auth-Token"] = token # Update headers
            response = requests.get(url, headers=headers, params=params, verify=False) # Retry
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            else:
                raise Exception(f"Failed to get clients list after token refresh. Status: {response.status_code}, Body: {response.text}")
        elif response.status_code == 400:
            try:
                error_data = response.json()
                if error_data.get("response") and isinstance(error_data["response"], list) and error_data["response"]:
                    api_error = error_data["response"][0]
                    if api_error.get("errorCode") == 14013:
                        raise ValueError(f"API Error (14013) in get_clients_list: {api_error.get('message', 'Start time cannot be more than 30 days before current time.')}")
                    # Note: errorCode 14006 (data not ready for endTime) is handled by the get_clients_count call.
                    # If get_clients_count succeeds with a retry, get_clients_list will use the (potentially adjusted) original endTime.
                    # If get_clients_count fails due to 14006 even after its retry, that error will propagate up.
            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as parse_or_value_error:
                if isinstance(parse_or_value_error, ValueError) and "14013" in str(parse_or_value_error):
                    raise parse_or_value_error
                pass # Fall through to generic exception
            raise Exception(f"Failed to get clients list. Status: 400, Body: {response.text}")
        else:
            raise Exception(f"Failed to get clients list. Status: {response.status_code}, Body: {response.text}")
    except ValueError as ve: # Catch our specific ValueError (e.g. 14013) first
        raise ve
    except Exception as e:
        # This will catch errors from get_clients_count or the main logic of get_clients_list
        raise Exception(f"Error in get_clients_list: {str(e)}")

@mcp.tool()
async def get_client_details_by_mac(
    client_mac_address: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    view: Optional[Json[List[str]]] = None,
    attribute: Optional[Json[List[str]]] = None,
    x_caller_id: Optional[str] = "Roo-MCP-get_client_details_by_mac"
) -> str:
    """
    Retrieves specific client information matching the MAC address.
    Defaults to the last 24 hours if startTime and endTime are not provided.
    API Spec: GET /dna/data/api/v1/clients/{id}
    Note: If the API indicates data is not ready for the requested endTime, this tool
    will automatically retry once with the API-suggested endTime.
    
    Args:
        client_mac_address (str): The MAC address of the client.
        start_time (Optional[int]): Start time in UNIX epoch ms.
                                  Note: The API restricts this to be no more than 30 days before the current time.
                                  Consider using `get_api_compatible_time_range` to generate compliant timestamps.
        end_time (Optional[int]): End time in UNIX epoch ms.
        view (Optional[List[str]]): List of views to include (e.g., ["Wireless", "WirelessHealth"]). Must be a list of strings.
        attribute (Optional[List[str]]): List of specific attributes to include. Must be a list of strings.
        x_caller_id (Optional[str]): Optional X-CALLER-ID header value.
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
        elif response.status_code == 400:
            try:
                error_data = response.json()
                if error_data.get("response") and isinstance(error_data["response"], list) and error_data["response"]:
                    api_error = error_data["response"][0]
                    if api_error.get("errorCode") == 14013:
                        raise ValueError(f"API Error (14013) in get_client_details_by_mac: {api_error.get('message', 'Start time cannot be more than 30 days before current time.')}")
                    elif api_error.get("errorCode") == 14006: # Data not ready for endTime
                        message = api_error.get("message", "")
                        import re
                        match = re.search(r"query with endTime=(\d+)", message)
                        if match:
                            suggested_end_time = int(match.group(1))
                            params["endTime"] = suggested_end_time
                            # print(f"DEBUG: API suggested new endTime: {suggested_end_time}. Retrying get_client_details_by_mac.")
                            retry_response = requests.get(url, headers=headers, params=params, verify=False)
                            if retry_response.status_code == 200:
                                return json.dumps(retry_response.json(), indent=2)
                            elif retry_response.status_code == 404:
                                raise Exception(f"Client with MAC address {client_mac_address} not found on retry with suggested endTime. Status: 404, Body: {retry_response.text}")
                            else:
                                raise Exception(f"Failed to get client details for {client_mac_address} on retry with suggested endTime. Status: {retry_response.status_code}, Body: {retry_response.text}")
                        else:
                            raise Exception(f"API Error (14006) in get_client_details_by_mac: {message}. Could not parse suggested endTime for retry.")
            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as parse_or_value_error:
                if isinstance(parse_or_value_error, ValueError) and "14013" in str(parse_or_value_error): # Re-raise specific 14013 error
                    raise parse_or_value_error
                # For other parsing errors or if it's not a 14013 ValueError, fall through to the generic 400 below
                pass 
            # Generic 400 error if not handled above
            raise Exception(f"Failed to get client details for {client_mac_address}. Status: 400, Body: {response.text}")
        elif response.status_code == 404: # Initial 404, not on retry
             raise Exception(f"Client with MAC address {client_mac_address} not found. Status: 404, Body: {response.text}")
        else:
            raise Exception(f"Failed to get client details for {client_mac_address}. Status: {response.status_code}, Body: {response.text}")
    except ValueError as ve: # Catch our specific ValueError (e.g. 14013) first
        raise ve
    except Exception as e:
        raise Exception(f"Error in get_client_details_by_mac for {client_mac_address}: {str(e)}")

@mcp.tool()
async def get_clients_count(
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    client_type: Optional[str] = None,
    os_type: Optional[Json[List[str]]] = None,
    os_version: Optional[Json[List[str]]] = None,
    site_hierarchy: Optional[Json[List[str]]] = None,
    site_hierarchy_id: Optional[Json[List[str]]] = None,
    site_id: Optional[Json[List[str]]] = None,
    ipv4_address: Optional[Json[List[str]]] = None,
    ipv6_address: Optional[Json[List[str]]] = None,
    mac_address: Optional[Json[List[str]]] = None,
    wlc_name: Optional[Json[List[str]]] = None,
    connected_network_device_name: Optional[Json[List[str]]] = None,
    ssid: Optional[Json[List[str]]] = None,
    band: Optional[Json[List[str]]] = None,
    x_caller_id: Optional[str] = "Roo-MCP-get_clients_count"
) -> str:
    """
    Retrieves the total count of clients by applying basic filtering.
    Defaults to the last 24 hours if startTime and endTime are not provided.
    API Spec: GET /dna/data/api/v1/clients/count
    Note: If the API indicates data is not ready for the requested endTime, this tool
    will automatically retry once with the API-suggested endTime.

    Filter Parameters:
    - start_time (Optional[int]): UNIX epoch milliseconds. Filters clients active at or after this time.
                                  Note: The API restricts this to be no more than 30 days before the current time.
                                  Consider using `get_api_compatible_time_range` to generate compliant timestamps.
    - end_time (Optional[int]): UNIX epoch milliseconds. Filters clients active at or before this time.
    - client_type (Optional[str]): Type of client (e.g., "wired", "wireless"). Internally converted to "Wired" or "Wireless" for the API. API parameter name is 'type'.
    - os_type (Optional[List[str]]): List of client operating systems (e.g., ["Windows", "macOS"]). Must be a list of strings.
    - os_version (Optional[List[str]]): List of client OS versions. Must be a list of strings.
    - site_hierarchy (Optional[List[str]]): Full site hierarchy path (e.g., ["Global/USA/California/SanFrancisco"]). Must be a list of strings.
    - site_hierarchy_id (Optional[List[str]]): List of site hierarchy UUIDs. Must be a list of strings.
    - site_id (Optional[List[str]]): List of site UUIDs. Must be a list of strings.
    - ipv4_address (Optional[List[str]]): List of client IPv4 addresses. Must be a list of strings.
    - ipv6_address (Optional[List[str]]): List of client IPv6 addresses. Must be a list of strings.
    - mac_address (Optional[List[str]]): List of client MAC addresses. Must be a list of strings.
    - wlc_name (Optional[List[str]]): List of Wireless LAN Controller names. Must be a list of strings.
    - connected_network_device_name (Optional[List[str]]): List of names of network devices clients are connected to. Must be a list of strings.
    - ssid (Optional[List[str]]): List of SSIDs clients are connected to. Must be a list of strings.
    - band (Optional[List[str]]): List of wireless bands (e.g., ["2.4GHz", "5GHz"]). Must be a list of strings.
    - x_caller_id (Optional[str]): Custom X-CALLER-ID header value for API requests. Defaults to "Roo-MCP-get_clients_count".
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
        
        processed_client_type = client_type
        if client_type is not None:
            if client_type.lower() == "wired":
                processed_client_type = "Wired"
            elif client_type.lower() == "wireless":
                processed_client_type = "Wireless"
            # If it's something else, pass it as is, API will validate
        if processed_client_type is not None: 
            params["type"] = processed_client_type # API uses 'type'
            
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
        elif response.status_code == 400:
            try:
                error_data = response.json()
                if error_data.get("response") and isinstance(error_data["response"], list) and error_data["response"]:
                    api_error = error_data["response"][0]
                    if api_error.get("errorCode") == 14013: # Specific error code for time range
                        raise ValueError(f"API Error (14013) in get_clients_count: {api_error.get('message', 'Start time cannot be more than 30 days before current time.')}")
                    elif api_error.get("errorCode") == 14006: # Data not ready for endTime
                        message = api_error.get("message", "")
                        # Attempt to parse suggested endTime. Example: "Data is not complete/ready for endTime=1747407537569. Please query with endTime=1747407420000 instead."
                        import re
                        match = re.search(r"query with endTime=(\d+)", message)
                        if match:
                            suggested_end_time = int(match.group(1))
                            # print(f"DEBUG: API suggested new endTime: {suggested_end_time}. Retrying get_clients_count.")
                            # Retry ONCE with the suggested endTime
                            params["endTime"] = suggested_end_time
                            # Need to re-fetch token in case it was the cause of the initial attempt's 401 that led to a retry that then got a 400
                            # However, if we are here, it means the first call was not 401, or the retry after 401 was not 200.
                            # For simplicity, just re-use existing token for this specific retry.
                            # If token was an issue, it would likely fail again and not hit this 14006 logic.
                            retry_response = requests.get(url, headers=headers, params=params, verify=False)
                            if retry_response.status_code == 200:
                                return json.dumps(retry_response.json(), indent=2)
                            else:
                                raise Exception(f"Failed to get clients count on retry with suggested endTime. Status: {retry_response.status_code}, Body: {retry_response.text}")
                        else: # Could not parse suggested endTime
                            raise Exception(f"API Error (14006) in get_clients_count: {message}. Could not parse suggested endTime for retry.")
            except (json.JSONDecodeError, KeyError, IndexError, ValueError) as parse_or_value_error:
                # If parsing the error or the ValueError from 14013 occurs
                if isinstance(parse_or_value_error, ValueError) and "14013" in str(parse_or_value_error):
                    raise parse_or_value_error # Re-raise the specific ValueError for 30-day limit
                # Fallback if error parsing doesn't work as expected or other ValueErrors
                pass # Will fall through to the generic exception below for other 400s
            raise Exception(f"Failed to get clients count. Status: 400, Body: {response.text}")
        else:
            raise Exception(f"Failed to get clients count. Status: {response.status_code}, Body: {response.text}")
    except ValueError as ve: # Catch our specific ValueError (e.g. 14013) first
        raise ve
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
