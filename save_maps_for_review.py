#!/usr/bin/env python3
"""
Standardized map output for review - saves both direct emulator and server maps
"""

import os
import time
import subprocess
import requests
from pokemon_env.emulator import EmeraldEmulator
from pathlib import Path

def format_map_for_review(tiles, title, location, position):
    """Format map tiles for easy review"""
    if not tiles:
        return f"=== {title} ===\nNo tiles available\n"
    
    output = []
    output.append(f"=== {title} ===")
    output.append(f"Format: (MetatileID, Behavior, X, Y)")
    output.append(f"Map dimensions: {len(tiles)}x{len(tiles[0]) if tiles else 0}")
    output.append(f"Player position: {position}")
    output.append(f"Location: {location}")
    output.append("")
    output.append("--- TRAVERSABILITY MAP ---")
    
    # Header with column numbers
    header = "      " + "  ".join(f"{i:2}" for i in range(len(tiles[0]) if tiles else 0))
    output.append(header)
    output.append("    " + "-" * (len(header) - 4))
    
    # Map rows with behavior analysis
    corruption_count = 0
    door_count = 0
    wall_count = 0
    
    for row_idx, row in enumerate(tiles):
        traversability_row = []
        for col_idx, tile in enumerate(row):
            if len(tile) >= 4:
                tile_id, behavior, collision, elevation = tile
                behavior_val = behavior if not hasattr(behavior, 'value') else behavior.value
                
                # Convert to traversability symbol with collision detection
                if behavior_val == 0:  # NORMAL
                    if collision == 0:
                        symbol = "."
                    else:
                        symbol = "#"
                        wall_count += 1
                elif behavior_val == 1:  # SECRET_BASE_WALL
                    symbol = "#"
                    wall_count += 1
                elif behavior_val == 51:  # IMPASSABLE_SOUTH
                    symbol = "IM"
                    corruption_count += 1
                elif behavior_val == 96:  # NON_ANIMATED_DOOR
                    symbol = "D"
                    door_count += 1
                elif behavior_val == 101:  # SOUTH_ARROW_WARP
                    symbol = "SO"
                elif behavior_val == 105:  # ANIMATED_DOOR
                    symbol = "D"
                    door_count += 1
                elif behavior_val == 134:  # TELEVISION
                    symbol = "TE"
                else:
                    symbol = "."  # Default to walkable for other behaviors
                
                # Mark player position (center of 15x15 map is 7,7)
                if row_idx == 7 and col_idx == 7:
                    symbol = "P"
                
                traversability_row.append(symbol)
            else:
                traversability_row.append("?")
        
        # Format row with row number
        row_str = f"{row_idx:2}: " + " ".join(f"{symbol:>2}" for symbol in traversability_row)
        output.append(row_str)
    
    # Add summary statistics
    output.append("")
    output.append("--- SUMMARY ---")
    output.append(f"Total tiles: {len(tiles) * len(tiles[0]) if tiles else 0}")
    output.append(f"Corruption (IM): {corruption_count}")
    output.append(f"Doors (D): {door_count}")
    output.append(f"Walls (#): {wall_count}")
    output.append(f"Walkable (.): {len(tiles) * len(tiles[0]) - corruption_count - door_count - wall_count if tiles else 0}")
    
    if corruption_count > 0:
        output.append("")
        output.append("--- CORRUPTION DETAILS ---")
        for row_idx, row in enumerate(tiles):
            for col_idx, tile in enumerate(row):
                if len(tile) >= 2:
                    behavior = tile[1] if not hasattr(tile[1], 'value') else tile[1].value
                    if behavior == 134:
                        output.append(f"Corruption at ({row_idx}, {col_idx}): tile_id={tile[0]}, behavior={behavior}")
    
    return "\n".join(output)

def save_direct_emulator_map():
    """Save direct emulator map for review"""
    print("📄 SAVING DIRECT EMULATOR MAP")
    print("=" * 40)
    
    emu = EmeraldEmulator('Emerald-GBAdvance/rom.gba', headless=True, sound=False)
    emu.initialize()
    emu.load_state('tests/states/house.state')
    
    try:
        # Move outside
        print("   🚶 Moving to outdoor area...")
        for i in range(4):
            emu.press_buttons(['down'], hold_frames=25, release_frames=25)
            time.sleep(0.1)
        
        # Wait for stabilization
        time.sleep(0.5)
        
        # Get state
        location = emu.memory_reader.read_location()
        position = emu.memory_reader.read_coordinates()
        tiles = emu.memory_reader.read_map_around_player(radius=7)
        
        # Format and save
        output_dir = Path("test_outputs/map_review")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        formatted_output = format_map_for_review(
            tiles, 
            f"DIRECT EMULATOR - {location}", 
            location, 
            position
        )
        
        output_file = output_dir / "direct_emulator_latest.txt"
        with open(output_file, 'w') as f:
            f.write(formatted_output)
        
        # Summary
        corruption_count = sum(1 for row in tiles for tile in row if len(tile) >= 2 and getattr(tile[1], 'value', tile[1]) == 134) if tiles else 0
        map_size = f"{len(tiles)}x{len(tiles[0]) if tiles else 0}" if tiles else "No tiles"
        
        print(f"   📊 Results: Position {position}, Map {map_size}, Corruption {corruption_count}")
        print(f"   💾 Saved to: {output_file}")
        
        return {
            'position': position,
            'location': location,
            'map_size': map_size,
            'corruption': corruption_count,
            'tiles': tiles
        }
        
    finally:
        emu.stop()

def save_server_map():
    """Save server map for review"""
    print("\n📄 SAVING SERVER MAP")
    print("=" * 40)
    
    # Kill any existing server
    os.system("pkill -f 'server.app' 2>/dev/null")
    time.sleep(2)
    
    # Start server
    server_cmd = ["python", "-m", "server.app", "--load-state", "tests/states/house.state", "--port", "8109", "--manual"]
    server_process = subprocess.Popen(server_cmd)
    server_url = "http://127.0.0.1:8109"
    
    try:
        # Wait for server startup
        print("   ⏳ Starting server...")
        for i in range(25):
            try:
                response = requests.get(f"{server_url}/status", timeout=8)
                if response.status_code == 200:
                    print(f"   ✅ Server ready after {i+1} attempts")
                    break
            except:
                time.sleep(1)
        else:
            print("   ❌ Server startup failed")
            return None
        
        # Enhanced movement to reach position (5,11) like direct emulator
        print("   🚶 Moving to target position (5,11)...")
        target_pos = (5, 11)
        
        max_moves = 8
        for move_num in range(max_moves):
            try:
                # Check current position
                response = requests.get(f"{server_url}/state", timeout=15)
                state = response.json()
                current_pos = (state['player']['position']['x'], state['player']['position']['y'])
                current_location = state['player']['location']
                
                print(f"     Move {move_num+1}: Current {current_pos}, Target {target_pos}")
                
                # If we've reached the target position, stop
                if current_pos == target_pos:
                    print(f"     🎯 TARGET POSITION REACHED!")
                    break
                
                # If we're in outdoor area but not at target Y, keep moving down
                if "LITTLEROOT TOWN" in current_location and "HOUSE" not in current_location:
                    if current_pos[1] < target_pos[1]:
                        print(f"     🔽 Moving down to reach Y={target_pos[1]}")
                        requests.post(f"{server_url}/action", json={"buttons": ["down"]}, timeout=15)
                        time.sleep(2.0)
                        continue
                    else:
                        print(f"     ✅ At outdoor area Y={current_pos[1]}")
                        break
                else:
                    # Still in house, keep moving down
                    print(f"     🔽 Moving down (still in house)")
                    requests.post(f"{server_url}/action", json={"buttons": ["down"]}, timeout=15)
                    time.sleep(2.0)
                
            except Exception as e:
                print(f"     Move {move_num+1}: Error - {e}")
                time.sleep(2)
        
        # Enhanced buffer synchronization
        print("   🔄 Synchronizing buffer...")
        try:
            # Multiple cache clears
            for i in range(3):
                requests.post(f"{server_url}/debug/clear_cache", json={}, timeout=8)
                time.sleep(0.3)
            
            # Force buffer re-detection
            requests.post(f"{server_url}/debug/force_buffer_redetection", json={}, timeout=10)
            time.sleep(1.0)
            
        except Exception as e:
            print(f"     Buffer sync warning: {e}")
        
        # Get final state
        response = requests.get(f"{server_url}/state", timeout=10)
        state = response.json()
        
        server_location = state['player']['location']
        server_position = (state['player']['position']['x'], state['player']['position']['y'])
        server_tiles = state['map']['tiles']
        
        # Format and save
        output_dir = Path("test_outputs/map_review")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        formatted_output = format_map_for_review(
            server_tiles,
            f"SERVER - {server_location}",
            server_location,
            server_position
        )
        
        output_file = output_dir / "server_latest.txt"
        with open(output_file, 'w') as f:
            f.write(formatted_output)
        
        # Summary
        corruption_count = sum(1 for row in server_tiles for tile in row if len(tile) >= 2 and tile[1] == 134) if server_tiles else 0
        map_size = f"{len(server_tiles)}x{len(server_tiles[0]) if server_tiles else 0}" if server_tiles else "No tiles"
        
        print(f"   📊 Results: Position {server_position}, Map {map_size}, Corruption {corruption_count}")
        print(f"   💾 Saved to: {output_file}")
        
        return {
            'position': server_position,
            'location': server_location,
            'map_size': map_size,
            'corruption': corruption_count,
            'tiles': server_tiles
        }
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None
    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()

def save_comparison_report(direct_result, server_result):
    """Save detailed comparison report"""
    print("\n📄 SAVING COMPARISON REPORT")
    print("=" * 40)
    
    output_dir = Path("test_outputs/map_review")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = []
    report.append("=== MAP COMPARISON REPORT ===")
    report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    if direct_result and server_result:
        # Position comparison
        report.append("--- POSITION COMPARISON ---")
        report.append(f"Direct Emulator: {direct_result['position']}")
        report.append(f"Server:          {server_result['position']}")
        pos_match = direct_result['position'] == server_result['position']
        report.append(f"Match: {'✅ YES' if pos_match else '❌ NO'}")
        if not pos_match:
            pos_diff = (
                server_result['position'][0] - direct_result['position'][0],
                server_result['position'][1] - direct_result['position'][1]
            )
            report.append(f"Difference: {pos_diff}")
        report.append("")
        
        # Map size comparison
        report.append("--- MAP SIZE COMPARISON ---")
        report.append(f"Direct Emulator: {direct_result['map_size']}")
        report.append(f"Server:          {server_result['map_size']}")
        size_match = direct_result['map_size'] == server_result['map_size']
        report.append(f"Match: {'✅ YES' if size_match else '❌ NO'}")
        report.append("")
        
        # Corruption comparison
        report.append("--- CORRUPTION COMPARISON ---")
        report.append(f"Direct Emulator: {direct_result['corruption']} corrupted tiles")
        report.append(f"Server:          {server_result['corruption']} corrupted tiles")
        corruption_match = direct_result['corruption'] == server_result['corruption']
        report.append(f"Match: {'✅ YES' if corruption_match else '❌ NO'}")
        report.append("")
        
        # Overall assessment
        report.append("--- OVERALL ASSESSMENT ---")
        all_match = pos_match and size_match and corruption_match
        if all_match:
            report.append("🎉 PERFECT MATCH: Server and direct emulator produce identical results!")
        else:
            issues = []
            if not pos_match:
                issues.append("Position mismatch")
            if not size_match:
                issues.append("Map size mismatch")
            if not corruption_match:
                issues.append("Corruption count mismatch")
            
            report.append(f"❌ ISSUES FOUND: {', '.join(issues)}")
            report.append("")
            report.append("NEXT STEPS:")
            if not pos_match:
                report.append("- Fix movement synchronization between server and direct emulator")
            if not size_match:
                report.append("- Fix map boundary calculation differences")
            if not corruption_match:
                report.append("- Fix buffer reading/detection differences")
        
        report.append("")
        report.append("--- PROGRESS TRACKING ---")
        if server_result['corruption'] == 0:
            report.append("✅ Server corruption eliminated!")
        elif server_result['corruption'] == 1:
            report.append("⚠️  Server has 1 remaining corrupted tile")
        else:
            report.append(f"❌ Server has {server_result['corruption']} corrupted tiles")
        
        if pos_match:
            report.append("✅ Position synchronization working!")
        else:
            report.append("❌ Position synchronization needs work")
        
    else:
        report.append("❌ INCOMPLETE DATA: Could not generate comparison")
        if not direct_result:
            report.append("- Direct emulator data missing")
        if not server_result:
            report.append("- Server data missing")
    
    # Save report
    report_file = output_dir / "comparison_latest.txt"
    with open(report_file, 'w') as f:
        f.write('\n'.join(report))
    
    print(f"   💾 Saved to: {report_file}")

def main():
    """Main function to save all maps for review"""
    print("🗺️  SAVING MAPS FOR REVIEW")
    print("=" * 50)
    print("This will overwrite the latest map files for easy review")
    print()
    
    # Save direct emulator map
    direct_result = save_direct_emulator_map()
    
    # Save server map
    server_result = save_server_map()
    
    # Save comparison report
    save_comparison_report(direct_result, server_result)
    
    # Summary
    print(f"\n📋 REVIEW FILES READY:")
    review_dir = Path("test_outputs/map_review")
    print(f"   📁 Directory: {review_dir}")
    print(f"   📄 direct_emulator_latest.txt - Direct emulator map")
    print(f"   📄 server_latest.txt - Server map")
    print(f"   📄 comparison_latest.txt - Detailed comparison")
    print()
    print(f"💡 TIP: Use 'cat test_outputs/map_review/comparison_latest.txt' for quick status")

if __name__ == "__main__":
    main()