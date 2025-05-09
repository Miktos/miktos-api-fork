#!/usr/bin/env python3
"""
Miktos Server Manager - A utility script for managing Miktos server instances.

This script provides commands for:
- Starting the server with configurable host/port
- Stopping any running server instances
- Checking server status
- Managing environment variables
"""
import os
import sys
import signal
import argparse
import subprocess
from pathlib import Path
import psutil
import time
import platform

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SERVER_PID_FILE = ".server_pid"


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


def start_server(host=DEFAULT_HOST, port=DEFAULT_PORT, debug=False, reload=False):
    """Start the Miktos server using uvicorn."""
    # First check if port is available
    if not check_port_availability(host, port):
        print(f"⚠️  Port {port} is already in use!")
        running_servers = find_running_servers(port)
        if running_servers:
            print(f"Found {len(running_servers)} existing server(s) potentially using this port:")
            for proc in running_servers:
                print(f"  - PID {proc.pid}: {' '.join(proc.info['cmdline'])}")
            
            # Ask if user wants to stop these servers
            if input("\nDo you want to stop these processes and start a fresh server? (y/n): ").lower() == 'y':
                stop_server(port)
            else:
                print("Server startup aborted.")
                sys.exit(1)
    
    # Build command
    cmd = ["uvicorn", "main:app", "--host", host, "--port", str(port)]
    
    # Add optional flags
    if debug:
        cmd.append("--log-level=debug")
    if reload:
        cmd.append("--reload")
    
    print(f"\n🚀 Starting Miktos server on http://{host}:{port}")
    print(f"Command: {' '.join(cmd)}")
    
    # Start server as subprocess
    server_process = subprocess.Popen(
        cmd, 
        stderr=subprocess.STDOUT
    )
    
    # Save PID for later management
    with open(SERVER_PID_FILE, 'w') as f:
        f.write(str(server_process.pid))
    
    print(f"✅ Server started with PID: {server_process.pid}")
    print(f"PID saved to {SERVER_PID_FILE}")
    print("\n💡 To stop the server, run: python server_manager.py stop")
    
    return server_process.pid


def stop_server(port=None):
    """Stop all running server instances, optionally filtered by port."""
    servers = find_running_servers(port)
    
    if not servers:
        print("No running Miktos server instances found.")
        return False
    
    print(f"Found {len(servers)} running Miktos server instance(s):")
    for proc in servers:
        print(f"  - PID {proc.pid}: {' '.join(proc.info['cmdline'])}")
    
    for proc in servers:
        try:
            if platform.system() == "Windows":
                proc.terminate()
            else:
                os.kill(proc.pid, signal.SIGTERM)
            print(f"✅ Stopped server with PID: {proc.pid}")
        except Exception as e:
            print(f"⚠️  Error stopping server with PID {proc.pid}: {str(e)}")
    
    # Clean up PID file
    if os.path.exists(SERVER_PID_FILE):
        os.remove(SERVER_PID_FILE)
    
    print("All server instances stopped.")
    return True


def server_status():
    """Check server status and display information."""
    servers = find_running_servers()
    
    if not servers:
        print("No running Miktos server instances found.")
        return False
    
    print(f"Found {len(servers)} running Miktos server instance(s):")
    for proc in servers:
        try:
            # Extract host and port from command
            host = DEFAULT_HOST
            port = DEFAULT_PORT
            
            for arg in proc.info['cmdline']:
                if arg.startswith("--host="):
                    host = arg.split("=")[1]
                elif arg.startswith("--port="):
                    port = arg.split("=")[1]
            
            # Get process info
            proc_info = proc.as_dict(attrs=['pid', 'cpu_percent', 'memory_percent', 'create_time'])
            uptime = time.time() - proc_info['create_time']
            
            # Format uptime
            days, remainder = divmod(uptime, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
            
            print(f"\nServer running at: http://{host}:{port}")
            print(f"PID: {proc.pid}")
            print(f"Uptime: {uptime_str}")
            print(f"CPU: {proc_info['cpu_percent']}%")
            print(f"Memory: {proc_info['memory_percent']:.1f}%")
            print(f"Command: {' '.join(proc.info['cmdline'])}")
        except Exception as e:
            print(f"⚠️  Error getting details for PID {proc.pid}: {str(e)}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Miktos Server Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the Miktos server")
    start_parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host address (default: {DEFAULT_HOST})")
    start_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port number (default: {DEFAULT_PORT})")
    start_parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    start_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop all running server instances")
    stop_parser.add_argument("--port", type=int, help="Stop only instances running on specific port")
    
    # Status command
    subparsers.add_parser("status", help="Check status of running server instances")
    
    args = parser.parse_args()
    
    # Default to status if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute requested command
    if args.command == "start":
        start_server(args.host, args.port, args.debug, args.reload)
    elif args.command == "stop":
        stop_server(args.port)
    elif args.command == "status":
        server_status()


if __name__ == "__main__":
    main()