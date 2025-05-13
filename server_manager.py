#!/usr/bin/env python3
"""
Miktos Server Manager - A utility script for managing Miktos server instances.

This script provides commands for:
- Starting the server with configurable host/port
- Stopping any running server instances (with graceful shutdown)
- Checking server status
- Managing environment variables and configuration
"""
import os
import sys
import signal
import argparse
import subprocess
import atexit
from pathlib import Path
import psutil
import time
import platform
import json

# Import server configuration
from config.server_config import server_config
# Import specialized logger
from utils.server_logger import server_logger

# For backwards compatibility
DEFAULT_HOST = server_config.HOST
DEFAULT_PORT = server_config.PORT
SERVER_PID_FILE = server_config.PID_FILE


def find_running_servers(port=None):
    """Find all running Miktos server processes (uvicorn or direct Python execution)."""
    servers = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Look for either uvicorn or python processes
            if proc.info['name'] and ('python' in proc.info['name'].lower() or 'uvicorn' in proc.info['name'].lower()):
                if proc.info['cmdline'] and any(('main.py' in arg or 'main:app' in arg) for arg in proc.info['cmdline']):
                    # If port is specified, check if this process is using that port
                    if port is None or any(f"--port={port}" in arg or f"--port {port}" in arg for arg in proc.info['cmdline']):
                        servers.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return servers


def check_port_availability(host=DEFAULT_HOST, port=DEFAULT_PORT):
    """Check if the specified port is available."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


def save_server_metadata(pid, host, port, start_time=None):
    """Save server metadata to a JSON file for better process management."""
    if start_time is None:
        start_time = time.time()
        
    metadata = {
        "pid": pid,
        "host": host,
        "port": port,
        "start_time": start_time,
        "start_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
    }
    
    # Save PID and metadata
    metadata_file = f"{SERVER_PID_FILE}.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Also save plain PID file for backwards compatibility
    with open(SERVER_PID_FILE, 'w') as f:
        f.write(str(pid))
    
    return metadata


def start_server(host=DEFAULT_HOST, port=DEFAULT_PORT, debug=False, reload=False):
    """Start the Miktos server using uvicorn with improved logging and metadata."""
    # First check if port is available
    if not check_port_availability(host, port):
        server_logger.error(f"Port {port} is already in use!", {"host": host, "port": port})
        running_servers = find_running_servers(port)
        if running_servers:
            server_logger.status(f"Found {len(running_servers)} existing server(s) potentially using this port")
            for proc in running_servers:
                print(f"  - PID {proc.pid}: {' '.join(proc.info['cmdline'])}")
            
            # Ask if user wants to stop these servers
            if input("\nDo you want to stop these processes and start a fresh server? (y/n): ").lower() == 'y':
                stop_server(port)
            else:
                server_logger.status("Server startup aborted by user")
                sys.exit(1)
    
    # Build command
    cmd = ["uvicorn", "main:app", "--host", host, "--port", str(port)]
    
    # Add optional flags
    if debug:
        cmd.append("--log-level=debug")
    if reload:
        cmd.append("--reload")
        
    # Add graceful timeout
    cmd.extend(["--timeout-graceful-shutdown", str(server_config.GRACEFUL_TIMEOUT)])
    
    server_logger.start(f"Starting Miktos server on http://{host}:{port}", {
        "host": host,
        "port": port,
        "debug": debug,
        "reload": reload,
        "command": " ".join(cmd)
    })
    
    # Start server as subprocess
    server_process = subprocess.Popen(
        cmd, 
        stderr=subprocess.STDOUT
    )
    
    # We'll only register the cleanup if we're in a specific mode
    # By default, we want the server to keep running after the script exits
    if os.environ.get('MIKTOS_SERVER_CLEANUP_ON_EXIT') == 'true':
        atexit.register(lambda: _cleanup_on_exit(server_process.pid))
    
    # Save PID and metadata for better management
    metadata = save_server_metadata(server_process.pid, host, port)
    
    server_logger.start(f"Server started with PID: {server_process.pid}", {
        "pid": server_process.pid,
        "metadata_file": f"{SERVER_PID_FILE}.json" 
    })
    print(f"\n✅ Server started with PID: {server_process.pid}")
    print(f"PID and metadata saved to {SERVER_PID_FILE}.json")
    print("\n💡 To stop the server, run: python server_manager.py stop")
    
    return server_process.pid


def _cleanup_on_exit(pid):
    """Ensure server is stopped if the controlling process exits."""
    try:
        proc = psutil.Process(pid)
        if proc.is_running():
            server_logger.status(f"Cleaning up server process {pid} on manager exit")
            _send_graceful_shutdown_signal(proc)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def _send_graceful_shutdown_signal(proc):
    """Send a graceful shutdown signal to a process and wait for it to exit."""
    try:
        # First try SIGTERM for graceful shutdown
        if platform.system() == "Windows":
            proc.terminate()
        else:
            os.kill(proc.pid, signal.SIGTERM)
            
        # Wait for graceful shutdown to complete, but not indefinitely
        grace_period = server_config.GRACEFUL_TIMEOUT
        server_logger.status(f"Waiting up to {grace_period}s for graceful shutdown of PID {proc.pid}")
        
        deadline = time.time() + grace_period
        while time.time() < deadline:
            if not proc.is_running():
                return True
            time.sleep(0.5)
            
        # If still running after grace period, use SIGKILL
        server_logger.warning(f"Process {proc.pid} didn't exit gracefully, sending SIGKILL")
        if proc.is_running():
            proc.kill()
        return True
    except Exception as e:
        server_logger.error(f"Error during graceful shutdown of PID {proc.pid}: {str(e)}")
        return False


def stop_server(port=None):
    """Stop all running server instances with graceful shutdown, optionally filtered by port."""
    servers = find_running_servers(port)
    
    if not servers:
        server_logger.status("No running Miktos server instances found.")
        print("No running Miktos server instances found.")
        return False
    
    server_logger.status(f"Found {len(servers)} running Miktos server instance(s)")
    print(f"Found {len(servers)} running Miktos server instance(s):")
    for proc in servers:
        print(f"  - PID {proc.pid}: {' '.join(proc.info['cmdline'])}")
    
    success_count = 0
    for proc in servers:
        try:
            server_logger.stop(f"Stopping server with PID: {proc.pid}", {"port": port})
            if _send_graceful_shutdown_signal(proc):
                print(f"✅ Gracefully stopped server with PID: {proc.pid}")
                success_count += 1
            else:
                print(f"⚠️  Failed to stop server with PID: {proc.pid}")
        except Exception as e:
            server_logger.error(f"Error stopping server with PID {proc.pid}: {str(e)}")
            print(f"⚠️  Error stopping server with PID {proc.pid}: {str(e)}")
    
    # Clean up PID files
    if os.path.exists(SERVER_PID_FILE):
        os.remove(SERVER_PID_FILE)
    metadata_file = f"{SERVER_PID_FILE}.json"
    if os.path.exists(metadata_file):
        os.remove(metadata_file)
    
    server_logger.status(f"Stopped {success_count} of {len(servers)} server instances")
    print(f"Stopped {success_count} of {len(servers)} server instances.")
    return success_count > 0


def format_uptime(seconds):
    """Format seconds into a human-readable uptime string."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"


def get_server_metadata(proc):
    """Get detailed metadata for a server process, using saved metadata if available."""
    # Try to extract host and port from command or metadata
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    start_time = None
    metadata = {}
    
    # Check for stored metadata
    metadata_file = f"{SERVER_PID_FILE}.json"
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                stored_metadata = json.load(f)
                if stored_metadata.get('pid') == proc.pid:
                    metadata = stored_metadata
                    host = metadata.get('host', DEFAULT_HOST)
                    port = metadata.get('port', DEFAULT_PORT)
                    start_time = metadata.get('start_time')
        except Exception as e:
            server_logger.error(f"Error reading metadata file: {str(e)}")
    
    # Extract from command line if not found in metadata
    if not metadata:
        for arg in proc.info['cmdline']:
            if arg.startswith("--host="):
                host = arg.split("=")[1]
            elif arg.startswith("--port="):
                port = arg.split("=")[1]
    
    # Get detailed process info
    try:
        # Get CPU and memory percentages with a brief delay to get accurate values
        proc.cpu_percent()
        time.sleep(0.1)
        cpu_percent = proc.cpu_percent()
        memory_percent = proc.memory_percent()
        
        # Get basic process details that should be available on all platforms
        proc_info = proc.as_dict(attrs=[
            'pid', 'create_time', 'num_threads', 'cmdline'
        ])
        
        # Calculate uptime
        start_time = start_time or proc_info['create_time']
        uptime = time.time() - start_time
        uptime_str = format_uptime(uptime)
        
        # Build metadata with safely accessible attributes
        detailed_metadata = {
            'host': host,
            'port': port,
            'pid': proc.pid,
            'uptime': uptime_str,
            'uptime_seconds': uptime,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'threads': proc_info.get('num_threads', 'Unknown'),
        }
        
        # Try to get cmdline safely
        if 'cmdline' in proc_info and proc_info['cmdline']:
            detailed_metadata['cmdline'] = ' '.join(proc_info['cmdline'])
        
        # Add these attributes only if the platform supports them
        try:
            connections = proc.connections()
            detailed_metadata['connections'] = len(connections)
        except (AttributeError, psutil.AccessDenied):
            detailed_metadata['connections'] = 'Unavailable'
            
        try:
            open_files = proc.open_files()
            detailed_metadata['open_files'] = len(open_files)
        except (AttributeError, psutil.AccessDenied):
            detailed_metadata['open_files'] = 'Unavailable'
        
        return detailed_metadata
    except Exception as e:
        server_logger.error(f"Error getting detailed process info: {str(e)}")
        # Return basic info if detailed info isn't available
        return {'host': host, 'port': port, 'pid': proc.pid, 'error': str(e)}


def server_status():
    """Check server status and display detailed information with improved logging."""
    servers = find_running_servers()
    
    if not servers:
        server_logger.status("No running Miktos server instances found")
        print("No running Miktos server instances found.")
        return False
    
    server_logger.status(f"Found {len(servers)} running Miktos server instance(s)")
    print(f"Found {len(servers)} running Miktos server instance(s):")
    
    for proc in servers:
        try:
            # Get detailed server information
            details = get_server_metadata(proc)
            
            # Log server details
            server_logger.status(
                f"Server status for PID {proc.pid}", 
                details
            )
            
            # Print user-friendly output
            print(f"\nServer running at: http://{details['host']}:{details['port']}")
            print(f"PID: {details['pid']}")
            print(f"Uptime: {details.get('uptime', 'Unknown')}")
            print(f"CPU: {details.get('cpu_percent', 'Unknown')}%")
            print(f"Memory: {details.get('memory_percent', 0):.1f}%")
            print(f"Threads: {details.get('threads', 'Unknown')}")
            print(f"Network connections: {details.get('connections', 'Unknown')}")
            print(f"Command: {details.get('cmdline', 'Unknown')}")
        except Exception as e:
            server_logger.error(f"Error getting details for PID {proc.pid}: {str(e)}")
            print(f"⚠️  Error getting details for PID {proc.pid}: {str(e)}")
    
    return True


def show_config():
    """Display current server configuration."""
    config_dict = {
        key: getattr(server_config, key)
        for key in dir(server_config)
        if not key.startswith('_') and key.isupper()
    }
    
    server_logger.config("Server configuration", config_dict)
    
    print("\n📝 Current Server Configuration:")
    print("-" * 40)
    for key, value in config_dict.items():
        print(f"{key}: {value}")
    print("-" * 40)
    
    # Show where configuration is sourced from
    print("\nConfiguration sources:")
    print(f"- Environment variables (.env file)")
    print(f"- Default values in config/server_config.py")


def main():
    parser = argparse.ArgumentParser(description="Miktos Server Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the Miktos server")
    start_parser.add_argument("--host", default=server_config.HOST, 
                             help=f"Host address (default: {server_config.HOST})")
    start_parser.add_argument("--port", type=int, default=server_config.PORT, 
                             help=f"Port number (default: {server_config.PORT})")
    start_parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    start_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop all running server instances")
    stop_parser.add_argument("--port", type=int, help="Stop only instances running on specific port")
    stop_parser.add_argument("--force", action="store_true", 
                           help="Force immediate shutdown without graceful period")
    
    # Status command
    subparsers.add_parser("status", help="Check status of running server instances")
    
    # Config command
    subparsers.add_parser("config", help="Show current server configuration")
    
    args = parser.parse_args()
    
    # Default to help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute requested command
    if args.command == "start":
        start_server(args.host, args.port, args.debug, args.reload)
    elif args.command == "stop":
        # The force flag isn't actually used yet, but we're adding it for future implementation
        stop_server(args.port)
    elif args.command == "status":
        server_status()
    elif args.command == "config":
        show_config()


if __name__ == "__main__":
    main()