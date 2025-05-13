#!/usr/bin/env python3
"""
Miktos Simple Runner - User-friendly script for common Miktos server operations

This script provides simplified commands for:
- Starting the server (with automatic port conflict resolution)
- Stopping all running server instances (with graceful shutdown)
- Checking server status

For advanced options, use server_manager.py directly.
"""
import os
import sys
import argparse
from server_manager import (
    start_server, stop_server, server_status, check_port_availability, 
    show_config, DEFAULT_HOST, DEFAULT_PORT
)
from utils.server_logger import server_logger
from config.server_config import server_config

def find_available_port(start_port=DEFAULT_PORT):
    """Find an available port starting from start_port."""
    port = start_port
    while not check_port_availability(DEFAULT_HOST, port):
        port += 1
        if port > start_port + 10:  # Don't search forever, limit to 10 ports
            return None
    return port

def main():
    parser = argparse.ArgumentParser(
        description="Miktos Simple Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simple_run.py              # Start the server with automatic port selection
  python simple_run.py --port 9000  # Start on a specific port
  python simple_run.py stop         # Stop all running server instances
  python simple_run.py status       # Check status of running servers
  python simple_run.py config       # Show current server configuration
        """
    )
    
    # Optional command argument (defaults to 'start' if not provided)
    parser.add_argument('command', nargs='?', default='start', choices=['start', 'stop', 'status', 'config'],
                        help='Command to execute (default: start)')
    
    # Port argument for start command
    parser.add_argument('--port', type=int, default=server_config.PORT,
                        help=f'Port number (default: {server_config.PORT}, auto-selects if occupied)')
    
    # Host argument for start command
    parser.add_argument('--host', default=server_config.HOST,
                        help=f'Host address (default: {server_config.HOST})')
    
    # Development mode flag
    parser.add_argument('--dev', action='store_true',
                        help='Enable development mode (auto-reload and debug logging)')
    
    args = parser.parse_args()
    
    # Execute the requested command
    if args.command == 'start':
        port = args.port
        host = args.host
        
        server_logger.start("Starting server with simple_run", {
            "requested_port": port,
            "host": host,
            "dev_mode": args.dev
        })
        
        # Check if requested port is available, if not find one that is
        if not check_port_availability(host, port):
            server_logger.status(f"Port {port} is already in use!")
            print(f"⚠️  Port {port} is already in use!")
            new_port = find_available_port(port + 1)
            if new_port:
                server_logger.status(f"Automatically switching to available port: {new_port}")
                print(f"🔄 Automatically switching to available port: {new_port}")
                port = new_port
            else:
                server_logger.error("Could not find an available port")
                print("❌ Could not find an available port! Please free up some ports and try again.")
                return 1
                
        # Start the server with selected configuration
        start_server(
            host=host,
            port=port,
            debug=args.dev,
            reload=args.dev
        )
        
    elif args.command == 'stop':
        server_logger.stop("Stopping server with simple_run")
        stop_server()
        
    elif args.command == 'status':
        server_logger.status("Checking server status with simple_run")
        server_status()
        
    elif args.command == 'config':
        server_logger.status("Showing server configuration with simple_run")
        show_config()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())