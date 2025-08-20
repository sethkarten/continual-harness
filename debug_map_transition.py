#!/usr/bin/env python3
"""
Single debugging script for house-to-outside map transition issue
Tests both direct emulator and server approaches with proper action format
"""

import requests
import time
import subprocess
import os
from pathlib import Path

SERVER_PORT = 8005
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"

def kill_existing_servers():
    """Kill any existing servers"""
    os.system("pkill -f 'server.app'")
    time.sleep(1)

def start_server():
    """Start server with house.state"""
    kill_existing_servers()
    
    print(f"🚀 Starting server on port {SERVER_PORT}...")
    
    server_cmd = [
        "python", "-m", "server.app", 
        "--load-state", "tests/states/house.state",
        "--port", str(SERVER_PORT),
        "--manual"
    ]
    
    process = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Wait for server to start
    for i in range(30):
        try:
            response = requests.get(f"{SERVER_URL}/status", timeout=2)
            if response.status_code == 200:
                print(f"✅ Server started after {i+1} seconds")
                return process
        except requests.exceptions.RequestException:
            time.sleep(1)
    
    process.terminate()
    raise Exception("Server failed to start")

def test_server_approach():
    """Test the server approach with correct action format"""
    print("\n" + "="*60)
    print("TESTING SERVER APPROACH")
    print("="*60)
    
    server_process = None
    try:
        server_process = start_server()
        
        # Get initial state
        print("\n📍 Phase 1: Initial house state")
        response = requests.get(f"{SERVER_URL}/state", timeout=10)
        state = response.json()
        
        location = state['player']['location']
        position = state['player']['position']
        tiles = state['map']['tiles']
        
        print(f"   Location: {location}")
        print(f"   Position: ({position['x']}, {position['y']})")
        print(f"   Map: {len(tiles)}x{len(tiles[0])} tiles")
        
        # Walk outside using AGENT.PY FORMAT
        print("\n🚶 Phase 2: Walking outside (using agent.py action format)")
        for step in range(10):
            print(f"   Step {step+1}: Sending DOWN action...")
            
            # Use the same format as agent.py: {"buttons": ["down"]}
            action_data = {"buttons": ["down"]}
            response = requests.post(f"{SERVER_URL}/action", json=action_data, timeout=5)
            
            if response.status_code != 200:
                print(f"   ❌ Action failed: {response.status_code}")
                break
                
            time.sleep(0.3)  # Wait for action to process
            
            # Check new state
            response = requests.get(f"{SERVER_URL}/state", timeout=10)
            if response.status_code != 200:
                print(f"   ❌ State request failed: {response.status_code}")
                break
                
            state = response.json()
            new_location = state['player']['location']
            new_position = state['player']['position']
            
            print(f"      Result: {new_location} at ({new_position['x']}, {new_position['y']})")
            
            # Check if we exited
            if 'HOUSE' not in new_location.upper():
                print(f"   ✅ Exited house after {step+1} steps!")
                
                # Test outside map
                print("\n🗺️  Phase 3: Testing outside map")
                outside_tiles = state['map']['tiles']
                print(f"   Outside map: {len(outside_tiles)}x{len(outside_tiles[0])} tiles")
                
                # Quick validation
                valid_tiles = 0
                total_tiles = len(outside_tiles) * len(outside_tiles[0])
                
                for row in outside_tiles:
                    for tile in row:
                        if len(tile) >= 4 and all(isinstance(x, int) for x in tile):
                            valid_tiles += 1
                
                validation = valid_tiles / total_tiles
                print(f"   Validation: {valid_tiles}/{total_tiles} valid tiles ({validation:.1%})")
                
                if validation > 0.8:
                    print("   ✅ Outside map looks good!")
                    return True
                else:
                    print("   ❌ Outside map has issues")
                    return False
        
        print("   ❌ Could not exit house")
        return False
        
    except Exception as e:
        print(f"   ❌ Server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait()

def test_direct_emulator():
    """Test direct emulator approach (known to work)"""
    print("\n" + "="*60)
    print("TESTING DIRECT EMULATOR APPROACH")
    print("="*60)
    
    try:
        from pokemon_env.emulator import EmeraldEmulator
        from tests.test_memory_map import format_map_data
        
        # Initialize emulator
        project_root = Path.cwd()
        rom_path = str(project_root / "Emerald-GBAdvance" / "rom.gba")
        
        emu = EmeraldEmulator(rom_path, headless=True, sound=False)
        emu.initialize()
        
        # Load house state
        emu.load_state("tests/states/house.state")
        
        # Get initial state
        initial_location = emu.memory_reader.read_location()
        initial_position = emu.memory_reader.read_coordinates()
        
        print(f"📍 Initial: {initial_location} at {initial_position}")
        
        # Walk outside
        print("\n🚶 Walking outside...")
        for step in range(10):
            emu.press_buttons(['down'], hold_frames=15, release_frames=15)
            time.sleep(0.1)
            
            new_location = emu.memory_reader.read_location()
            new_position = emu.memory_reader.read_coordinates()
            
            if 'HOUSE' not in new_location.upper():
                print(f"   ✅ Exited after {step+1} steps: {new_location} at {new_position}")
                
                # Test map
                print("\n🗺️  Testing outside map...")
                outside_map = emu.memory_reader.read_map_around_player(radius=7)
                
                if outside_map and len(outside_map) > 0:
                    print(f"   Map size: {len(outside_map)}x{len(outside_map[0])}")
                    formatted_map = format_map_data(outside_map, f"Direct Emulator - {new_location}")
                    print(f"   ✅ Direct emulator map reading works!")
                    # print(f"\n{formatted_map}")  # Uncomment to see full map
                    return True
                else:
                    print("   ❌ Direct emulator map reading failed")
                    return False
        
        print("   ❌ Could not exit house with direct emulator")
        return False
        
    except Exception as e:
        print(f"   ❌ Direct emulator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'emu' in locals():
            emu.stop()

def main():
    """Run both tests and compare results"""
    print("DEBUGGING MAP TRANSITION ISSUE")
    print("Testing both server and direct emulator approaches")
    
    # Test direct emulator first (should work)
    direct_works = test_direct_emulator()
    
    # Test server approach
    server_works = test_server_approach()
    
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    print(f"Direct emulator approach: {'✅ WORKS' if direct_works else '❌ FAILED'}")
    print(f"Server approach:          {'✅ WORKS' if server_works else '❌ FAILED'}")
    
    if direct_works and not server_works:
        print("\n💡 CONCLUSION: The core fix works, but there's a server-specific issue")
        print("   - Direct emulator properly handles area transitions")
        print("   - Server has additional complexity causing problems")
    elif direct_works and server_works:
        print("\n🎉 SUCCESS: Both approaches work!")
    else:
        print("\n❌ PROBLEM: Neither approach is working correctly")

if __name__ == "__main__":
    main()