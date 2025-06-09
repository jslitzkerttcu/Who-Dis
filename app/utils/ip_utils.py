"""
Utility functions for IP address extraction and handling.
"""

from flask import request
from typing import Optional, Dict
import ipaddress


def get_client_ip() -> str:
    """
    Extract the client's IP address from the request.

    Handles X-Forwarded-For headers and falls back to remote_addr.
    Returns the first (client) IP if multiple are present.
    """
    # Check X-Forwarded-For header first (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # We want the first one (the original client)
        client_ip = forwarded_for.split(",")[0].strip()
        return client_ip

    # Fall back to direct connection IP
    return request.remote_addr or "unknown"


def get_all_ips() -> Dict[str, Optional[str]]:
    """
    Get all available IP information from the request.

    Returns a dictionary with:
    - client_ip: The original client IP
    - forwarded_for: Full X-Forwarded-For header (if present)
    - remote_addr: Direct connection IP
    """
    return {
        "client_ip": get_client_ip(),
        "forwarded_for": request.headers.get("X-Forwarded-For"),
        "remote_addr": request.remote_addr,
    }


def is_internal_ip(ip: str) -> bool:
    """
    Check if an IP address is internal/private.

    Returns True for:
    - 127.0.0.0/8 (loopback)
    - 10.0.0.0/8
    - 172.16.0.0/12
    - 192.168.0.0/16
    - fc00::/7 (IPv6 private)
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback
    except ValueError:
        return False


def format_ip_info() -> str:
    """
    Format IP information for logging purposes.

    Returns a string like:
    - "192.168.1.100" (for simple cases)
    - "192.168.1.100 (via 203.0.113.0)" (when behind proxy)
    """
    ip_info = get_all_ips()
    client_ip = ip_info["client_ip"] or "unknown"
    remote_addr = ip_info["remote_addr"]

    if not remote_addr or client_ip == remote_addr:
        return client_ip

    # If we have both and they're different, show both
    return f"{client_ip} (via {remote_addr})"
