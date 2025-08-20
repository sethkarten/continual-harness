#!/usr/bin/env python3
"""
Debug memory buffer differences between direct emulator and server
Compares map buffer addresses, detection logic, and memory state during transitions
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator


def debug_direct_emulator():
    """Debug direct emulator memory buffer detection"""
    print("=" * 60)
    print("DEBUGGING DIRECT EMULATOR MEMORY BUFFER")
    print("=" * 60)
    
    project_root = Path.cwd()
    rom_path = str(project_root / "Emerald-GBAdvance" / "rom.gba")
    
    emu = EmeraldEmulator(rom_path, headless=True, sound=False)
    emu.initialize()
    
    try:
        # Load house state
        print("\n📍 Phase 1: House state loaded")
        emu.load_state("tests/states/house.state")
        
        reader = emu.memory_reader
        location1 = reader.read_location()
        position1 = reader.read_coordinates()
        
        print(f"   Location: {location1}")
        print(f"   Position: {position1}")
        print(f"   Map buffer addr: {hex(reader._map_buffer_addr) if reader._map_buffer_addr else 'None'}")
        print(f"   Map width: {reader._map_width}")
        print(f"   Map height: {reader._map_height}")
        print(f"   Map bank: {reader._last_map_bank}")
        print(f"   Map number: {reader._last_map_number}")
        
        # Get some map data to verify
        map1 = reader.read_map_around_player(radius=3)  # Small radius for debugging
        if map1:
            print(f"   Map data: {len(map1)}x{len(map1[0])}")
            # Show center tile info
            center = map1[3][3] if len(map1) > 3 and len(map1[3]) > 3 else None
            if center:
                print(f"   Center tile: ID={center[0]}, Behavior={center[1]}, Collision={center[2]}, Elevation={center[3]}")
        
        # Transition to outside
        print("\n🚶 Phase 2: Transitioning outside")
        for step in range(3):
            emu.press_buttons(['down'], hold_frames=15, release_frames=15)
            time.sleep(0.1)
        
        # Check memory state after transition
        location2 = reader.read_location()
        position2 = reader.read_coordinates()
        
        print(f"   New location: {location2}")
        print(f"   New position: {position2}")
        print(f"   Map buffer addr: {hex(reader._map_buffer_addr) if reader._map_buffer_addr else 'None'}")
        print(f"   Map width: {reader._map_width}")
        print(f"   Map height: {reader._map_height}")
        print(f"   Map bank: {reader._last_map_bank}")
        print(f"   Map number: {reader._last_map_number}")
        
        # Check if buffer address changed
        print(f"   Buffer address changed: {reader._map_buffer_addr != reader._map_buffer_addr}")
        
        # Get outside map data
        map2 = reader.read_map_around_player(radius=3)
        if map2:
            print(f"   Outside map data: {len(map2)}x{len(map2[0])}")
            # Show center tile info
            center = map2[3][3] if len(map2) > 3 and len(map2[3]) > 3 else None
            if center:
                print(f"   Center tile: ID={center[0]}, Behavior={center[1]}, Collision={center[2]}, Elevation={center[3]}")
                
            # Check for unknown tiles
            total_tiles = sum(len(row) for row in map2)
            unknown_tiles = sum(1 for row in map2 for tile in row 
                               if len(tile) >= 2 and hasattr(tile[1], 'name') and tile[1].name == 'UNKNOWN')
            unknown_ratio = unknown_tiles / total_tiles if total_tiles > 0 else 0
            print(f"   Unknown tiles: {unknown_ratio:.1%}")
        
        return {
            'house_buffer_addr': reader._map_buffer_addr,
            'house_location': location1,
            'house_position': position1,
            'outside_buffer_addr': reader._map_buffer_addr,
            'outside_location': location2,
            'outside_position': position2,
            'unknown_ratio': unknown_ratio if 'unknown_ratio' in locals() else 0.0
        }
        
    finally:
        emu.stop()


def debug_server_approach():
    """Debug server memory buffer detection"""
    print("\n" + "=" * 60)
    print("DEBUGGING SERVER MEMORY BUFFER")
    print("=" * 60)
    
    # Kill any existing servers
    os.system("pkill -f 'server.app' 2>/dev/null")
    time.sleep(1)
    
    # Start server with debug logging
    server_cmd = [
        "python", "-m", "server.app",
        "--load-state", "tests/states/house.state",
        "--port", "8040",
        "--manual"
    ]
    
    server_process = subprocess.Popen(
        server_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    server_url = "http://127.0.0.1:8040"
    for i in range(30):
        try:
            response = requests.get(f"{server_url}/status", timeout=2)
            if response.status_code == 200:
                print(f"   Server started after {i+1} seconds")
                break
        except requests.exceptions.RequestException:
            time.sleep(1)
    else:
        server_process.terminate()
        print("   ❌ Server failed to start")
        return None
    
    try:
        # Get house state
        print("\n📍 Phase 1: House state via server")
        response = requests.get(f"{server_url}/state", timeout=10)
        house_state = response.json()
        
        house_location = house_state['player']['location']
        house_position = house_state['player']['position']
        house_tiles = house_state['map']['tiles']
        
        print(f"   Location: {house_location}")
        print(f"   Position: ({house_position['x']}, {house_position['y']})")
        print(f"   Map size: {len(house_tiles)}x{len(house_tiles[0])}")
        
        # Analyze house map
        house_total = sum(len(row) for row in house_tiles)
        house_unknown = sum(1 for row in house_tiles for tile in row 
                           if len(tile) >= 2 and tile[1] == 0)
        house_unknown_ratio = house_unknown / house_total if house_total > 0 else 0
        print(f"   House unknown tiles: {house_unknown_ratio:.1%}")
        
        # Show center tile for comparison
        if len(house_tiles) > 7 and len(house_tiles[7]) > 7:
            center_tile = house_tiles[7][7]
            print(f"   Center tile: {center_tile}")
        
        # Transition to outside
        print("\n🚶 Phase 2: Transitioning outside via server")
        for step in range(3):
            print(f"   Step {step+1}: Sending DOWN action...")
            response = requests.post(f"{server_url}/action", 
                                   json={"buttons": ["down"]}, 
                                   timeout=5)
            if response.status_code != 200:
                print(f"   ❌ Action failed: {response.status_code}")
                break
            time.sleep(0.1)  # Between actions like agent.py
            
        # Additional delay like agent.py does
        time.sleep(0.3 * 3)  # action_delay * num_actions
        print("   Waiting for transition to complete...")
        
        # Get outside state
        response = requests.get(f"{server_url}/state", timeout=10)
        outside_state = response.json()
        
        outside_location = outside_state['player']['location']
        outside_position = outside_state['player']['position']
        outside_tiles = outside_state['map']['tiles']
        
        print(f"   New location: {outside_location}")
        print(f"   New position: ({outside_position['x']}, {outside_position['y']})")
        print(f"   Map size: {len(outside_tiles)}x{len(outside_tiles[0])}")
        
        # Analyze outside map
        outside_total = sum(len(row) for row in outside_tiles)
        outside_unknown = sum(1 for row in outside_tiles for tile in row 
                             if len(tile) >= 2 and tile[1] == 0)
        outside_unknown_ratio = outside_unknown / outside_total if outside_total > 0 else 0
        print(f"   Outside unknown tiles: {outside_unknown_ratio:.1%}")
        
        # Show center tile for comparison
        if len(outside_tiles) > 7 and len(outside_tiles[7]) > 7:
            center_tile = outside_tiles[7][7]
            print(f"   Center tile: {center_tile}")
        
        # Check for signs of memory corruption
        # Look for indoor elements in outdoor location
        has_indoor_elements = False
        indoor_elements = []
        
        for row in outside_tiles:
            for tile in row:
                if len(tile) >= 2:
                    behavior = tile[1]
                    # Check for behaviors that shouldn't be in outdoor areas
                    # These are rough guesses based on common indoor behavior values
                    if behavior in [133, 134, 181, 195]:  # TV, sound mat, etc.
                        has_indoor_elements = True
                        indoor_elements.append(behavior)
        
        if has_indoor_elements:
            print(f"   ⚠️  DETECTED INDOOR ELEMENTS IN OUTDOOR MAP: {set(indoor_elements)}")
            print(f"   This suggests server is reading wrong memory buffer!")
        
        return {
            'house_location': house_location,
            'house_position': house_position,
            'house_unknown_ratio': house_unknown_ratio,
            'outside_location': outside_location,
            'outside_position': outside_position,
            'outside_unknown_ratio': outside_unknown_ratio,
            'has_memory_corruption': has_indoor_elements
        }
        
    finally:
        server_process.terminate()
        server_process.wait()


def compare_results(emulator_result, server_result):
    """Compare the debugging results"""
    print("\n" + "=" * 60)
    print("COMPARISON AND ANALYSIS")
    print("=" * 60)
    
    if not emulator_result or not server_result:
        print("❌ Could not compare - missing results")
        return
    
    print(f"\n📍 LOCATION COMPARISON:")
    print(f"   Emulator house: {emulator_result['house_location']}")
    print(f"   Server house:   {server_result['house_location']}")
    print(f"   Emulator outside: {emulator_result['outside_location']}")
    print(f"   Server outside:   {server_result['outside_location']}")
    
    print(f"\n📐 POSITION COMPARISON:")
    print(f"   Emulator outside: {emulator_result['outside_position']}")
    print(f"   Server outside:   {server_result['outside_position']}")
    
    print(f"\n🔍 MAP QUALITY COMPARISON:")
    print(f"   Emulator unknown tiles: {emulator_result['unknown_ratio']:.1%}")
    print(f"   Server unknown tiles:   {server_result['outside_unknown_ratio']:.1%}")
    
    print(f"\n🧠 MEMORY CORRUPTION ANALYSIS:")
    if server_result.get('has_memory_corruption', False):
        print("   ❌ SERVER: Indoor elements detected in outdoor map - MEMORY CORRUPTION")
    else:
        print("   ✅ SERVER: No obvious indoor elements in outdoor map")
    
    print(f"   📊 Server house unknown ratio: {server_result['house_unknown_ratio']:.1%}")
    if server_result['house_unknown_ratio'] > 0.1:
        print("   ⚠️  Even the house map has unknown tiles - fundamental server issue")
    
    # Conclusion
    print(f"\n💡 CONCLUSION:")
    if emulator_result['unknown_ratio'] < 0.1 and server_result['outside_unknown_ratio'] > 0.3:
        print("   - Direct emulator works correctly")
        print("   - Server has significant map reading issues")
        print("   - The bug is in server-specific memory handling")
        if server_result.get('has_memory_corruption', False):
            print("   - Server is likely reading from wrong memory buffer")
    else:
        print("   - Unexpected results - need further investigation")


def main():
    """Run the complete debugging analysis"""
    print("MEMORY BUFFER DEBUGGING ANALYSIS")
    print("Comparing direct emulator vs server memory handling")
    print()
    
    # Debug direct emulator
    emulator_result = debug_direct_emulator()
    
    # Debug server
    server_result = debug_server_approach()
    
    # Compare and analyze
    compare_results(emulator_result, server_result)


if __name__ == "__main__":
    main()