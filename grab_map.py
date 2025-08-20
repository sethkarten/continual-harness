#!/usr/bin/env python3
"""
Script to grab and display the current map data from the running Pokemon Emerald server.
Usage: python grab_map.py [--save FILENAME]
"""

import argparse
import requests
import sys
from tests.test_memory_map import print_map_data

SERVER_URL = "http://127.0.0.1:8000"

def main():
    parser = argparse.ArgumentParser(description='Grab and display current map data from running Pokemon Emerald server')
    parser.add_argument('--save', type=str, default=None,
                        help='Save the formatted map to a text file')
    parser.add_argument('--server', type=str, default=SERVER_URL,
                        help=f'Server URL (default: {SERVER_URL})')
    args = parser.parse_args()
    
    print(f"Connecting to server at {args.server}...")
    
    try:
        # Get comprehensive state from server
        response = requests.get(f"{args.server}/state", timeout=5)
        if response.status_code != 200:
            print(f"Error: Failed to get state from server (HTTP {response.status_code})")
            print("Make sure server/app.py is running!")
            sys.exit(1)
        
        state_data = response.json()
        
        # Extract map data
        if 'map' not in state_data or 'tiles' not in state_data['map']:
            print("Error: No map data in server response")
            print("The server might not have map data available yet")
            sys.exit(1)
        
        map_data = state_data['map']['tiles']
        
        # Get additional info
        location = state_data.get('player', {}).get('location', 'Unknown')
        coords = state_data.get('player', {}).get('position', {})
        
        # Format and display the map
        title = f"Current Map - {location} ({coords.get('x', '?')}, {coords.get('y', '?')})"
        formatted_map = print_map_data(map_data, title)
        
        # Save to file if requested
        if args.save:
            with open(args.save, 'w') as f:
                f.write(formatted_map)
            print(f"\nMap saved to {args.save}")
            
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to server at {args.server}")
        print("Make sure server/app.py is running!")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: Server request timed out")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()