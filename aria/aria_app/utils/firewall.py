"""Firewall configuration utilities for DDS streaming."""

import subprocess
import sys

# Port range for DDS communication
DDS_PORT_RANGE_START = 7000
DDS_PORT_RANGE_END = 8000


def update_iptables() -> bool:
    """
    Update firewall to permit incoming UDP connections for DDS.

    Adds an iptables rule to accept UDP traffic on ports 7000-8000.
    Requires sudo privileges. Only applicable on Linux systems.

    Returns:
        bool: True if iptables was updated successfully, False otherwise.

    Raises:
        RuntimeError: If not running on a Linux system.
    """
    if not sys.platform.startswith("linux"):
        raise RuntimeError("iptables configuration is only supported on Linux systems")

    port_range = f"{DDS_PORT_RANGE_START}:{DDS_PORT_RANGE_END}"

    update_iptables_cmd = [
        "sudo",
        "iptables",
        "-A",
        "INPUT",  # Append to INPUT chain
        "-p",
        "udp",  # Protocol: UDP
        "-m",
        "udp",  # Match module: UDP
        "--dport",
        port_range,  # Destination port range
        "-j",
        "ACCEPT",  # Jump target: ACCEPT
    ]

    print("Updating iptables to allow DDS UDP traffic...")
    print(f"Command: {' '.join(update_iptables_cmd)}")

    try:
        subprocess.run(update_iptables_cmd, check=True, capture_output=True, text=True)
        print("✓ iptables updated successfully")
        return True

    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to update iptables: {e.stderr}", file=sys.stderr)
        return False

    except PermissionError:
        print("✗ Permission denied. sudo privileges required.", file=sys.stderr)
        return False


def check_iptables_rule_exists() -> bool:
    """
    Check if the DDS iptables rule already exists.

    Returns:
        bool: True if rule exists, False otherwise.
    """
    if not sys.platform.startswith("linux"):
        raise RuntimeError("iptables configuration is only supported on Linux systems")

    port_range = f"{DDS_PORT_RANGE_START}:{DDS_PORT_RANGE_END}"

    check_cmd = [
        "sudo",
        "iptables",
        "-C",
        "INPUT",
        "-p",
        "udp",
        "-m",
        "udp",
        "--dport",
        port_range,
        "-j",
        "ACCEPT",
    ]

    try:
        subprocess.run(check_cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def safe_update_iptables() -> bool:
    """
    Safely update iptables, checking if rule already exists first.

    Returns:
        bool: True if rule exists or was added successfully.
    """
    if not sys.platform.startswith("linux"):
        raise RuntimeError("iptables configuration is only supported on Linux systems")

    if check_iptables_rule_exists():
        print("✓ iptables rule already exists")
        return True

    return update_iptables()
