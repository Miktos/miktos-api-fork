#!/usr/bin/env python3
"""
Miktos Simple Runner - User-friendly script for common Miktos server operations

This script provides simplified commands for:
- Starting the server (with automatic port conflict resolution)
- Stopping all running server instances
- Checking server status

For advanced options, use server_manager.py directly.
"""
import os
import sys
import argparse
from server_manager import start_server, stop_server, server_status, check_port_availability, DEFAULT_HOST, DEFAULT_PORT

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
        """
    )
    
    # Optional command argument (defaults to 'start' if not provided)
    parser.add_argument('command', nargs='?', default='start', choices=['start', 'stop', 'status'],
                        help='Command to execute (default: start)')
    
    # Port argument for start command
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'Port number (default: {DEFAULT_PORT}, auto-selects if occupied)')
    
    # Development mode flag
    parser.add_argument('--dev', action='store_true',
                        help='Enable development mode (auto-reload and debug logging)')
    
    args = parser.parse_args()
    
    # Execute the requested command
    if args.command == 'start':
        port = args.port
        
        # Check if requested port is available, if not find one that is
        if not check_port_availability(DEFAULT_HOST, port):
            print(f"⚠️  Port {port} is already in use!")
            new_port = find_available_port(port + 1)
            if new_port:
                print(f"🔄 Automatically switching to available port: {new_port}")
                port = new_port
            else:
                print("❌ Could not find an available port! Please free up some ports and try again.")
                return 1
                
        # Start the server with selected configuration
        start_server(
            host=DEFAULT_HOST,
            port=port,
            debug=args.dev,
            reload=args.dev
        )
        
    elif args.command == 'stop':
        stop_server()
        
    elif args.command == 'status':
        server_status()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())