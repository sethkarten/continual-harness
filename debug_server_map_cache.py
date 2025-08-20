#!/usr/bin/env python3
"""
Deep dive into server map cache behavior during area transitions
Investigates buffer detection, cache invalidation, and memory reading
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator


def kill_all_servers():
    """Kill all server processes"""
    print("🔄 Killing all servers...")
    os.system("pkill -f 'server.app' 2>/dev/null")
    time.sleep(2)


def start_debug_server(port=8060):
    """Start server with debug logging"""
    print(f"🚀 Starting debug server on port {port}...")
    
    server_cmd = [
        "python", "-m", "server.app",
        "--load-state", "tests/states/house.state",
        "--port", str(port),
        "--manual"
    ]
    
    process = subprocess.Popen(
        server_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    server_url = f"http://127.0.0.1:{port}"
    for i in range(30):
        try:
            response = requests.get(f"{server_url}/status", timeout=2)
            if response.status_code == 200:
                print(f"✅ Server started after {i+1} seconds")
                return process, server_url
        except requests.exceptions.RequestException:
            time.sleep(1)
    
    process.terminate()
    raise Exception("Server failed to start")


def analyze_map_data_detailed(tiles, location_name):
    """Detailed analysis of map data"""
    if not tiles or len(tiles) == 0:
        return {"status": "empty", "details": "No map data"}
    
    total_tiles = sum(len(row) for row in tiles)
    
    # Count different behavior types
    behavior_counts = {}
    tile_id_counts = {}
    collision_counts = {}
    elevation_counts = {}
    
    for row in tiles:
        for tile in row:
            if len(tile) >= 4:
                tile_id, behavior, collision, elevation = tile
                
                behavior_counts[behavior] = behavior_counts.get(behavior, 0) + 1
                tile_id_counts[tile_id] = tile_id_counts.get(tile_id, 0) + 1
                collision_counts[collision] = collision_counts.get(collision, 0) + 1
                elevation_counts[elevation] = elevation_counts.get(elevation, 0) + 1
    
    # Analyze for corruption patterns
    unknown_count = behavior_counts.get(0, 0)  # UNKNOWN = 0
    unknown_ratio = unknown_count / total_tiles if total_tiles > 0 else 0
    
    # Check for indoor elements in outdoor areas
    indoor_behaviors = [133, 134, 181, 195]  # TV, sound mat, etc.
    indoor_elements = {b: behavior_counts.get(b, 0) for b in indoor_behaviors if behavior_counts.get(b, 0) > 0}
    
    # Check for impossible combinations
    dominant_behavior = max(behavior_counts.items(), key=lambda x: x[1]) if behavior_counts else (None, 0)
    behavior_diversity = len(behavior_counts)
    
    analysis = {
        "status": "analyzed",
        "total_tiles": total_tiles,
        "unknown_ratio": unknown_ratio,
        "behavior_diversity": behavior_diversity,
        "dominant_behavior": dominant_behavior,
        "indoor_elements": indoor_elements,
        "behavior_counts": dict(sorted(behavior_counts.items())),
        "tile_id_range": (min(tile_id_counts.keys()), max(tile_id_counts.keys())) if tile_id_counts else (None, None)
    }
    
    # Detect corruption patterns
    corruption_indicators = []
    
    if unknown_ratio > 0.3:
        corruption_indicators.append(f"High unknown tiles: {unknown_ratio:.1%}")
    
    if indoor_elements and "TOWN" in location_name.upper():
        corruption_indicators.append(f"Indoor elements in outdoor area: {indoor_elements}")
    
    if behavior_diversity < 3:
        corruption_indicators.append(f"Low behavior diversity: {behavior_diversity} types")
    
    if dominant_behavior[1] / total_tiles > 0.8:
        corruption_indicators.append(f"Single behavior dominance: {dominant_behavior[0]} ({dominant_behavior[1]/total_tiles:.1%})")
    
    analysis["corruption_indicators"] = corruption_indicators
    analysis["likely_corrupted"] = len(corruption_indicators) > 0
    
    return analysis


def compare_direct_vs_server_buffers():
    """Compare map buffer behavior between direct emulator and server"""
    print("=" * 80)
    print("COMPARING DIRECT EMULATOR VS SERVER MAP BUFFER BEHAVIOR")
    print("=" * 80)
    
    # Test direct emulator
    print("\n📍 PHASE 1: Direct Emulator Buffer Analysis")
    print("-" * 50)
    
    project_root = Path.cwd()
    rom_path = str(project_root / "Emerald-GBAdvance" / "rom.gba")
    
    emu = EmeraldEmulator(rom_path, headless=True, sound=False)
    emu.initialize()
    
    direct_results = {}
    
    try:
        # Load house state
        emu.load_state("tests/states/house.state")
        reader = emu.memory_reader
        
        # House buffer info
        house_location = reader.read_location()
        house_position = reader.read_coordinates()
        house_map = reader.read_map_around_player(radius=7)
        
        print(f"House - Location: {house_location}")
        print(f"House - Position: {house_position}")
        print(f"House - Buffer addr: {hex(reader._map_buffer_addr) if reader._map_buffer_addr else 'None'}")
        print(f"House - Map bank/number: {reader._last_map_bank}/{reader._last_map_number}")
        
        house_analysis = analyze_map_data_detailed(house_map, house_location)
        print(f"House - Map analysis: {house_analysis['unknown_ratio']:.1%} unknown, {house_analysis['behavior_diversity']} behaviors")
        
        direct_results['house'] = {
            'location': house_location,
            'position': house_position,
            'buffer_addr': reader._map_buffer_addr,
            'map_bank': reader._last_map_bank,
            'map_number': reader._last_map_number,
            'analysis': house_analysis
        }
        
        # Transition outside
        print(f"\nTransitioning outside...")
        for i in range(3):
            emu.press_buttons(['down'], hold_frames=15, release_frames=15)
            time.sleep(0.1)
        
        # Outside buffer info
        outside_location = reader.read_location()
        outside_position = reader.read_coordinates()
        outside_map = reader.read_map_around_player(radius=7)
        
        print(f"Outside - Location: {outside_location}")
        print(f"Outside - Position: {outside_position}")
        print(f"Outside - Buffer addr: {hex(reader._map_buffer_addr) if reader._map_buffer_addr else 'None'}")
        print(f"Outside - Map bank/number: {reader._last_map_bank}/{reader._last_map_number}")
        
        outside_analysis = analyze_map_data_detailed(outside_map, outside_location)
        print(f"Outside - Map analysis: {outside_analysis['unknown_ratio']:.1%} unknown, {outside_analysis['behavior_diversity']} behaviors")
        
        direct_results['outside'] = {
            'location': outside_location,
            'position': outside_position,
            'buffer_addr': reader._map_buffer_addr,
            'map_bank': reader._last_map_bank,
            'map_number': reader._last_map_number,
            'analysis': outside_analysis
        }
        
        # Check if buffer changed
        buffer_changed = direct_results['house']['buffer_addr'] != direct_results['outside']['buffer_addr']
        bank_changed = direct_results['house']['map_bank'] != direct_results['outside']['map_bank']
        number_changed = direct_results['house']['map_number'] != direct_results['outside']['map_number']
        
        print(f"\nDirect Emulator Transition Analysis:")
        print(f"  Buffer address changed: {buffer_changed}")
        print(f"  Map bank changed: {bank_changed} ({direct_results['house']['map_bank']} → {direct_results['outside']['map_bank']})")
        print(f"  Map number changed: {number_changed} ({direct_results['house']['map_number']} → {direct_results['outside']['map_number']})")
        
    finally:
        emu.stop()
    
    # Test server
    print(f"\n📍 PHASE 2: Server Buffer Analysis")
    print("-" * 50)
    
    server_process = None
    server_results = {}
    
    try:
        kill_all_servers()
        server_process, server_url = start_debug_server()
        
        # House state
        response = requests.get(f"{server_url}/state", timeout=10)
        house_state = response.json()
        
        house_location = house_state['player']['location']
        house_position = house_state['player']['position']
        house_tiles = house_state['map']['tiles']
        
        print(f"House - Location: {house_location}")
        print(f"House - Position: ({house_position['x']}, {house_position['y']})")
        
        house_analysis = analyze_map_data_detailed(house_tiles, house_location)
        print(f"House - Map analysis: {house_analysis['unknown_ratio']:.1%} unknown, {house_analysis['behavior_diversity']} behaviors")
        if house_analysis['corruption_indicators']:
            print(f"House - Corruption indicators: {house_analysis['corruption_indicators']}")
        
        server_results['house'] = {
            'location': house_location,
            'position': house_position,
            'analysis': house_analysis
        }
        
        # Transition outside
        print(f"\nTransitioning outside...")
        for i in range(3):
            response = requests.post(f"{server_url}/action", json={"buttons": ["down"]}, timeout=5)
            time.sleep(0.4)
        
        # Outside state
        response = requests.get(f"{server_url}/state", timeout=10)
        outside_state = response.json()
        
        outside_location = outside_state['player']['location']
        outside_position = outside_state['player']['position']
        outside_tiles = outside_state['map']['tiles']
        
        print(f"Outside - Location: {outside_location}")
        print(f"Outside - Position: ({outside_position['x']}, {outside_position['y']})")
        
        outside_analysis = analyze_map_data_detailed(outside_tiles, outside_location)
        print(f"Outside - Map analysis: {outside_analysis['unknown_ratio']:.1%} unknown, {outside_analysis['behavior_diversity']} behaviors")
        if outside_analysis['corruption_indicators']:
            print(f"Outside - Corruption indicators: {outside_analysis['corruption_indicators']}")
        
        server_results['outside'] = {
            'location': outside_location,
            'position': outside_position,
            'analysis': outside_analysis
        }
        
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait()
    
    # Compare results
    print(f"\n📊 PHASE 3: Comparison Analysis")
    print("-" * 50)
    
    print(f"\nHouse Map Quality:")
    print(f"  Direct emulator: {direct_results['house']['analysis']['unknown_ratio']:.1%} unknown tiles")
    print(f"  Server:          {server_results['house']['analysis']['unknown_ratio']:.1%} unknown tiles")
    
    print(f"\nOutside Map Quality:")
    print(f"  Direct emulator: {direct_results['outside']['analysis']['unknown_ratio']:.1%} unknown tiles")
    print(f"  Server:          {server_results['outside']['analysis']['unknown_ratio']:.1%} unknown tiles")
    
    print(f"\nCorruption Analysis:")
    direct_house_ok = not direct_results['house']['analysis']['likely_corrupted']
    direct_outside_ok = not direct_results['outside']['analysis']['likely_corrupted']
    server_house_ok = not server_results['house']['analysis']['likely_corrupted']
    server_outside_ok = not server_results['outside']['analysis']['likely_corrupted']
    
    print(f"  Direct emulator house:  {'✅ Clean' if direct_house_ok else '❌ Corrupted'}")
    print(f"  Direct emulator outside: {'✅ Clean' if direct_outside_ok else '❌ Corrupted'}")
    print(f"  Server house:           {'✅ Clean' if server_house_ok else '❌ Corrupted'}")
    print(f"  Server outside:         {'✅ Clean' if server_outside_ok else '❌ Corrupted'}")
    
    # Identify the issue pattern
    print(f"\n💡 Issue Pattern Analysis:")
    if direct_house_ok and direct_outside_ok and not server_house_ok:
        print("   🎯 SERVER HAS FUNDAMENTAL MAP READING ISSUES (even in house)")
        print("   This suggests the problem is in server's memory access, not just transitions")
    elif direct_house_ok and direct_outside_ok and server_house_ok and not server_outside_ok:
        print("   🎯 SERVER SPECIFIC AREA TRANSITION BUG")
        print("   House works but outside fails - cache invalidation issue")
    else:
        print("   🎯 COMPLEX ISSUE PATTERN")
        print("   Multiple failure modes detected")
    
    # Specific recommendations
    print(f"\n🔧 Debugging Recommendations:")
    
    if not server_house_ok:
        print("   1. Investigate basic server memory reading - even house map is corrupted")
        print("   2. Check JSON serialization of behavior enums")
        print("   3. Verify server memory access patterns")
    
    if server_house_ok and not server_outside_ok:
        print("   1. Focus on area transition cache invalidation")
        print("   2. Check map buffer re-detection after transitions")
        print("   3. Verify area change detection logic")
    
    print("   4. Add detailed logging to memory_reader.py during server operations")
    print("   5. Compare memory addresses and buffer detection between modes")
    
    return direct_results, server_results


if __name__ == "__main__":
    compare_direct_vs_server_buffers()