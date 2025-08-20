#!/usr/bin/env python3
"""
Debug test for house-to-outside transition
Saves visualization ground truth and compares direct emulator vs server
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator
from tests.test_memory_map import format_map_data


class HouseToOutsideTransitionTest:
    """Test house-to-outside transition with both approaches"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.rom_path = str(self.project_root / "Emerald-GBAdvance" / "rom.gba")
        self.ground_truth_dir = Path("tests/ground_truth")
        self.ground_truth_dir.mkdir(exist_ok=True)
        
    def test_direct_emulator(self):
        """Test transition with direct emulator and save ground truth"""
        print("=" * 60)
        print("TESTING DIRECT EMULATOR APPROACH")
        print("=" * 60)
        
        emu = EmeraldEmulator(self.rom_path, headless=True, sound=False)
        emu.initialize()
        
        try:
            # Load house state
            emu.load_state("tests/states/house.state")
            
            # Get initial house map
            print("\n📍 Phase 1: House state")
            house_location = emu.memory_reader.read_location()
            house_position = emu.memory_reader.read_coordinates()
            house_map = emu.memory_reader.read_map_around_player(radius=7)
            
            print(f"   Location: {house_location}")
            print(f"   Position: {house_position}")
            print(f"   Map size: {len(house_map)}x{len(house_map[0]) if house_map else 0}")
            
            # Save house ground truth
            if house_map:
                house_viz = format_map_data(house_map, f"House - {house_location}")
                house_file = self.ground_truth_dir / "house_direct_emulator.txt"
                with open(house_file, 'w') as f:
                    f.write(house_viz)
                print(f"   ✅ Saved ground truth: {house_file}")
            
            # Transition to outside
            print("\n🚶 Phase 2: Transitioning outside")
            for step in range(3):
                print(f"   Step {step+1}: Moving down...")
                emu.press_buttons(['down'], hold_frames=15, release_frames=15)
                time.sleep(0.1)
            
            # Get outside map
            outside_location = emu.memory_reader.read_location()
            outside_position = emu.memory_reader.read_coordinates()
            outside_map = emu.memory_reader.read_map_around_player(radius=7)
            
            print(f"   New location: {outside_location}")
            print(f"   New position: {outside_position}")
            print(f"   Map size: {len(outside_map)}x{len(outside_map[0]) if outside_map else 0}")
            
            # Analyze outside map quality
            if outside_map:
                total_tiles = sum(len(row) for row in outside_map)
                unknown_tiles = sum(1 for row in outside_map for tile in row 
                                   if len(tile) >= 2 and hasattr(tile[1], 'name') and tile[1].name == 'UNKNOWN')
                unknown_ratio = unknown_tiles / total_tiles if total_tiles > 0 else 0
                
                print(f"   Unknown tiles: {unknown_ratio:.1%}")
                
                # Save outside ground truth
                outside_viz = format_map_data(outside_map, f"Outside - {outside_location}")
                outside_file = self.ground_truth_dir / "outside_direct_emulator.txt"
                with open(outside_file, 'w') as f:
                    f.write(outside_viz)
                print(f"   ✅ Saved ground truth: {outside_file}")
                
                if unknown_ratio > 0.1:
                    print(f"   ⚠️  High unknown tile ratio: {unknown_ratio:.1%}")
                    return False
                else:
                    print(f"   ✅ Direct emulator transition successful")
                    return True
            else:
                print("   ❌ Failed to read outside map")
                return False
                
        finally:
            emu.stop()
    
    def test_server_approach(self):
        """Test transition with server and compare with ground truth"""
        print("\n" + "=" * 60)
        print("TESTING SERVER APPROACH")
        print("=" * 60)
        
        # Kill any existing servers
        os.system("pkill -f 'server.app' 2>/dev/null")
        time.sleep(1)
        
        # Start server
        server_cmd = [
            "python", "-m", "server.app",
            "--load-state", "tests/states/house.state",
            "--port", "8030",
            "--manual"
        ]
        
        server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        server_url = "http://127.0.0.1:8030"
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
            return False
        
        try:
            # Get initial house map
            print("\n📍 Phase 1: House state via server")
            response = requests.get(f"{server_url}/state", timeout=10)
            if response.status_code != 200:
                print(f"   ❌ Failed to get house state: {response.status_code}")
                return False
            
            house_state = response.json()
            house_location = house_state['player']['location']
            house_position = house_state['player']['position']
            house_tiles = house_state['map']['tiles']
            
            print(f"   Location: {house_location}")
            print(f"   Position: ({house_position['x']}, {house_position['y']})")
            print(f"   Map size: {len(house_tiles)}x{len(house_tiles[0]) if house_tiles else 0}")
            
            # Analyze house map quality
            house_total = sum(len(row) for row in house_tiles)
            house_unknown = sum(1 for row in house_tiles for tile in row 
                               if len(tile) >= 2 and tile[1] == 0)  # UNKNOWN = 0
            house_unknown_ratio = house_unknown / house_total if house_total > 0 else 0
            print(f"   House unknown tiles: {house_unknown_ratio:.1%}")
            
            # Save house server visualization
            house_viz = format_map_data(house_tiles, f"House Server - {house_location}")
            house_server_file = self.ground_truth_dir / "house_server.txt"
            with open(house_server_file, 'w') as f:
                f.write(house_viz)
            print(f"   📄 Saved server visualization: {house_server_file}")
            
            # Transition to outside
            print("\n🚶 Phase 2: Transitioning outside via server")
            for step in range(3):
                print(f"   Step {step+1}: Sending DOWN action...")
                response = requests.post(f"{server_url}/action", 
                                       json={"buttons": ["down"]}, 
                                       timeout=5)
                if response.status_code != 200:
                    print(f"   ❌ Action failed: {response.status_code}")
                    return False
                time.sleep(0.3)
            
            # Get outside map
            response = requests.get(f"{server_url}/state", timeout=10)
            if response.status_code != 200:
                print(f"   ❌ Failed to get outside state: {response.status_code}")
                return False
            
            outside_state = response.json()
            outside_location = outside_state['player']['location']
            outside_position = outside_state['player']['position']
            outside_tiles = outside_state['map']['tiles']
            
            print(f"   New location: {outside_location}")
            print(f"   New position: ({outside_position['x']}, {outside_position['y']})")
            print(f"   Map size: {len(outside_tiles)}x{len(outside_tiles[0]) if outside_tiles else 0}")
            
            # Analyze outside map quality
            outside_total = sum(len(row) for row in outside_tiles)
            outside_unknown = sum(1 for row in outside_tiles for tile in row 
                                 if len(tile) >= 2 and tile[1] == 0)  # UNKNOWN = 0
            outside_unknown_ratio = outside_unknown / outside_total if outside_total > 0 else 0
            print(f"   Outside unknown tiles: {outside_unknown_ratio:.1%}")
            
            # Save outside server visualization
            outside_viz = format_map_data(outside_tiles, f"Outside Server - {outside_location}")
            outside_server_file = self.ground_truth_dir / "outside_server.txt"
            with open(outside_server_file, 'w') as f:
                f.write(outside_viz)
            print(f"   📄 Saved server visualization: {outside_server_file}")
            
            # Compare with ground truth
            ground_truth_file = self.ground_truth_dir / "outside_direct_emulator.txt"
            if ground_truth_file.exists():
                print(f"\n🔍 Comparing with ground truth...")
                print(f"   Ground truth file: {ground_truth_file}")
                print(f"   Server file: {outside_server_file}")
                
                if outside_unknown_ratio > 0.3:
                    print(f"   ❌ SERVER BUG DETECTED: {outside_unknown_ratio:.1%} unknown tiles")
                    print(f"   This confirms the area transition bug exists in server mode")
                    return False
                else:
                    print(f"   ✅ Server transition successful: {outside_unknown_ratio:.1%} unknown tiles")
                    return True
            else:
                print(f"   ⚠️  No ground truth file found - run direct emulator test first")
                return outside_unknown_ratio <= 0.1
                
        finally:
            server_process.terminate()
            server_process.wait()
    
    def run_full_test(self):
        """Run both tests and compare results"""
        print("HOUSE-TO-OUTSIDE TRANSITION DEBUG TEST")
        print("Saving visualization ground truth for comparison")
        print()
        
        # Test direct emulator (should work)
        emulator_success = self.test_direct_emulator()
        
        # Test server (likely to show bug)
        server_success = self.test_server_approach()
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"Direct emulator: {'✅ SUCCESS' if emulator_success else '❌ FAILED'}")
        print(f"Server approach:  {'✅ SUCCESS' if server_success else '❌ FAILED'}")
        
        if emulator_success and not server_success:
            print("\n💡 CONCLUSION:")
            print("   - Direct emulator handles area transitions correctly")
            print("   - Server has area transition bug causing map corruption")
            print("   - Ground truth visualizations saved for comparison")
            print(f"\n📁 Files saved in: {self.ground_truth_dir}")
            print("   - outside_direct_emulator.txt (correct)")
            print("   - outside_server.txt (shows bug)")
        elif emulator_success and server_success:
            print("\n🎉 Both approaches work correctly!")
        else:
            print("\n❌ Unexpected results - both approaches have issues")
        
        return emulator_success, server_success


if __name__ == "__main__":
    test = HouseToOutsideTransitionTest()
    test.run_full_test()