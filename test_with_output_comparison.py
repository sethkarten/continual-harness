#!/usr/bin/env python3
"""
Test with detailed output saving for visual comparison
Saves all map outputs to compare with ground truth step by step
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from pokemon_env.emulator import EmeraldEmulator
from tests.test_memory_map import format_map_data
from datetime import datetime


class OutputComparisonTest:
    """Test with detailed output saving for comparison"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.rom_path = str(self.project_root / "Emerald-GBAdvance" / "rom.gba")
        
        # Create timestamped output folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(f"test_outputs/{timestamp}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Saving all outputs to: {self.output_dir}")
        
        # Create subfolders
        (self.output_dir / "direct_emulator").mkdir(exist_ok=True)
        (self.output_dir / "server").mkdir(exist_ok=True)
        (self.output_dir / "comparison").mkdir(exist_ok=True)
    
    def save_map_output(self, map_data, filename, title=""):
        """Save formatted map output to file"""
        if map_data:
            formatted_map = format_map_data(map_data, title)
            with open(filename, 'w') as f:
                f.write(formatted_map)
            print(f"   💾 Saved: {filename}")
            return True
        else:
            with open(filename, 'w') as f:
                f.write(f"=== {title} ===\nERROR: No map data available\n")
            print(f"   ❌ No data: {filename}")
            return False
    
    def save_analysis_summary(self, data, filename):
        """Save analysis data to file"""
        with open(filename, 'w') as f:
            f.write("=== TEST ANALYSIS SUMMARY ===\n\n")
            for key, value in data.items():
                f.write(f"{key}: {value}\n")
        print(f"   📊 Analysis saved: {filename}")
    
    def kill_servers(self):
        """Kill all servers"""
        print("🔄 Killing all servers...")
        os.system("pkill -f 'server.app' 2>/dev/null")
        time.sleep(2)
    
    def test_direct_emulator(self):
        """Test direct emulator with output saving"""
        print("\n" + "=" * 60)
        print("TESTING DIRECT EMULATOR (should work perfectly)")
        print("=" * 60)
        
        emu = EmeraldEmulator(self.rom_path, headless=True, sound=False)
        emu.initialize()
        
        results = {"approach": "direct_emulator"}
        
        try:
            # Load house state
            print("\n📍 Phase 1: House state")
            emu.load_state("tests/states/house.state")
            
            house_location = emu.memory_reader.read_location()
            house_position = emu.memory_reader.read_coordinates()
            house_map = emu.memory_reader.read_map_around_player(radius=7)
            
            print(f"   Location: {house_location}")
            print(f"   Position: {house_position}")
            print(f"   Map size: {len(house_map)}x{len(house_map[0]) if house_map else 0}")
            
            # Save house map
            house_file = self.output_dir / "direct_emulator" / "01_house_initial.txt"
            self.save_map_output(house_map, house_file, f"Direct Emulator House - {house_location}")
            
            results["house_location"] = house_location
            results["house_position"] = house_position
            results["house_map_size"] = f"{len(house_map)}x{len(house_map[0])}" if house_map else "0x0"
            
            # Transition outside
            print("\n🚶 Phase 2: Transitioning outside")
            for step in range(4):  # 4 steps should be enough to exit and move around
                print(f"   Step {step+1}: Moving down...")
                emu.press_buttons(['down'], hold_frames=25, release_frames=25)  # Longer button press
                time.sleep(0.1)
                
                # Save intermediate position
                intermediate_pos = emu.memory_reader.read_coordinates()
                intermediate_loc = emu.memory_reader.read_location()
                print(f"      After step {step+1}: {intermediate_loc} at {intermediate_pos}")
            
            # Get final outside state
            outside_location = emu.memory_reader.read_location()
            outside_position = emu.memory_reader.read_coordinates()
            outside_map = emu.memory_reader.read_map_around_player(radius=7)
            
            print(f"   Final location: {outside_location}")
            print(f"   Final position: {outside_position}")
            print(f"   Map size: {len(outside_map)}x{len(outside_map[0]) if outside_map else 0}")
            
            # Save outside map
            outside_file = self.output_dir / "direct_emulator" / "02_outside_final.txt"
            self.save_map_output(outside_map, outside_file, f"Direct Emulator Outside - {outside_location}")
            
            # Analyze quality
            if outside_map:
                total_tiles = sum(len(row) for row in outside_map)
                unknown_tiles = sum(1 for row in outside_map for tile in row 
                                   if len(tile) >= 2 and hasattr(tile[1], 'name') and tile[1].name == 'UNKNOWN')
                unknown_ratio = unknown_tiles / total_tiles if total_tiles > 0 else 0
                
                print(f"   Unknown tiles: {unknown_ratio:.1%}")
                
                results["outside_location"] = outside_location
                results["outside_position"] = outside_position
                results["outside_map_size"] = f"{len(outside_map)}x{len(outside_map[0])}"
                results["unknown_ratio"] = f"{unknown_ratio:.1%}"
                results["success"] = unknown_ratio < 0.1
                
                if unknown_ratio < 0.1:
                    print("   ✅ Direct emulator SUCCESS")
                else:
                    print(f"   ❌ Direct emulator has issues: {unknown_ratio:.1%} unknown")
            else:
                print("   ❌ No outside map data")
                results["success"] = False
                
        except Exception as e:
            print(f"   ❌ Direct emulator error: {e}")
            results["error"] = str(e)
            results["success"] = False
            
        finally:
            emu.stop()
        
        # Save analysis
        analysis_file = self.output_dir / "direct_emulator" / "analysis.txt"
        self.save_analysis_summary(results, analysis_file)
        
        return results
    
    def test_server(self):
        """Test server with output saving"""
        print("\n" + "=" * 60)
        print("TESTING SERVER (expected to have corruption)")
        print("=" * 60)
        
        self.kill_servers()
        
        # Start server
        server_cmd = [
            "python", "-m", "server.app",
            "--load-state", "tests/states/house.state",
            "--port", "8070",
            "--manual"
        ]
        
        server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        server_url = "http://127.0.0.1:8070"
        results = {"approach": "server"}
        
        try:
            # Wait for server
            for i in range(30):
                try:
                    response = requests.get(f"{server_url}/status", timeout=2)
                    if response.status_code == 200:
                        print(f"   Server started after {i+1} seconds")
                        break
                except requests.exceptions.RequestException:
                    time.sleep(1)
            else:
                raise Exception("Server failed to start")
            
            # Get house state
            print("\n📍 Phase 1: House state via server")
            response = requests.get(f"{server_url}/state", timeout=10)
            house_state = response.json()
            
            house_location = house_state['player']['location']
            house_position = house_state['player']['position']
            house_tiles = house_state['map']['tiles']
            
            print(f"   Location: {house_location}")
            print(f"   Position: ({house_position['x']}, {house_position['y']})")
            print(f"   Map size: {len(house_tiles)}x{len(house_tiles[0]) if house_tiles else 0}")
            
            # Save house map
            house_file = self.output_dir / "server" / "01_house_initial.txt"
            self.save_map_output(house_tiles, house_file, f"Server House - {house_location}")
            
            # Analyze house quality
            house_total = sum(len(row) for row in house_tiles)
            house_unknown = sum(1 for row in house_tiles for tile in row 
                               if len(tile) >= 2 and tile[1] == 0)
            house_unknown_ratio = house_unknown / house_total if house_total > 0 else 0
            print(f"   House unknown tiles: {house_unknown_ratio:.1%}")
            
            results["house_location"] = house_location
            results["house_position"] = f"({house_position['x']}, {house_position['y']})"
            results["house_map_size"] = f"{len(house_tiles)}x{len(house_tiles[0])}"
            results["house_unknown_ratio"] = f"{house_unknown_ratio:.1%}"
            
            # Transition outside
            print("\n🚶 Phase 2: Transitioning outside via server")
            for step in range(4):  # 4 steps should be enough to exit and move around
                print(f"   Step {step+1}: Sending DOWN action...")
                response = requests.post(f"{server_url}/action", json={"buttons": ["down"]}, timeout=5)
                time.sleep(0.2)  # Increased processing delay
                time.sleep(0.5)  # Longer delay between actions
                
                # Check intermediate state
                response = requests.get(f"{server_url}/state", timeout=5)
                if response.status_code == 200:
                    state = response.json()
                    pos = state['player']['position']
                    loc = state['player']['location']
                    print(f"      After step {step+1}: {loc} at ({pos['x']}, {pos['y']})")
                    
                    # Save intermediate map for step-by-step analysis
                    if step == 2:  # Save final step
                        intermediate_file = self.output_dir / "server" / f"01.{step+1}_step_{step+1}.txt"
                        tiles = state['map']['tiles']
                        self.save_map_output(tiles, intermediate_file, f"Server Step {step+1} - {loc}")
            
            # Get final outside state
            response = requests.get(f"{server_url}/state", timeout=10)
            outside_state = response.json()
            
            outside_location = outside_state['player']['location']
            outside_position = outside_state['player']['position']
            outside_tiles = outside_state['map']['tiles']
            
            print(f"   Final location: {outside_location}")
            print(f"   Final position: ({outside_position['x']}, {outside_position['y']})")
            print(f"   Map size: {len(outside_tiles)}x{len(outside_tiles[0]) if outside_tiles else 0}")
            
            # Save outside map
            outside_file = self.output_dir / "server" / "02_outside_final.txt"
            self.save_map_output(outside_tiles, outside_file, f"Server Outside - {outside_location}")
            
            # Analyze outside quality
            outside_total = sum(len(row) for row in outside_tiles)
            outside_unknown = sum(1 for row in outside_tiles for tile in row 
                                 if len(tile) >= 2 and tile[1] == 0)
            outside_unknown_ratio = outside_unknown / outside_total if outside_total > 0 else 0
            print(f"   Outside unknown tiles: {outside_unknown_ratio:.1%}")
            
            results["outside_location"] = outside_location
            results["outside_position"] = f"({outside_position['x']}, {outside_position['y']})"
            results["outside_map_size"] = f"{len(outside_tiles)}x{len(outside_tiles[0])}"
            results["outside_unknown_ratio"] = f"{outside_unknown_ratio:.1%}"
            results["success"] = outside_unknown_ratio < 0.1
            
            if outside_unknown_ratio < 0.1:
                print("   ✅ Server SUCCESS")
            else:
                print(f"   ❌ Server corruption detected: {outside_unknown_ratio:.1%} unknown")
                
                # Check for specific corruption patterns
                indoor_behaviors = [133, 134, 181, 195]
                indoor_found = []
                for row in outside_tiles:
                    for tile in row:
                        if len(tile) >= 2 and tile[1] in indoor_behaviors:
                            indoor_found.append(tile[1])
                
                if indoor_found:
                    print(f"   🏠 Indoor elements in outdoor map: {set(indoor_found)}")
                    results["corruption_type"] = f"Indoor elements found: {set(indoor_found)}"
            
        except Exception as e:
            print(f"   ❌ Server error: {e}")
            results["error"] = str(e)
            results["success"] = False
            
        finally:
            server_process.terminate()
            server_process.wait()
        
        # Save analysis
        analysis_file = self.output_dir / "server" / "analysis.txt"
        self.save_analysis_summary(results, analysis_file)
        
        return results
    
    def create_comparison_report(self, direct_results, server_results):
        """Create detailed comparison report"""
        print("\n" + "=" * 60)
        print("CREATING COMPARISON REPORT")
        print("=" * 60)
        
        comparison_file = self.output_dir / "comparison" / "detailed_comparison.txt"
        
        with open(comparison_file, 'w') as f:
            f.write("=== DETAILED COMPARISON REPORT ===\n\n")
            f.write(f"Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("DIRECT EMULATOR RESULTS:\n")
            f.write("-" * 30 + "\n")
            for key, value in direct_results.items():
                f.write(f"  {key}: {value}\n")
            
            f.write("\nSERVER RESULTS:\n")
            f.write("-" * 30 + "\n")
            for key, value in server_results.items():
                f.write(f"  {key}: {value}\n")
            
            f.write("\nCOMPARISON ANALYSIS:\n")
            f.write("-" * 30 + "\n")
            
            # Compare success
            direct_success = direct_results.get('success', False)
            server_success = server_results.get('success', False)
            
            f.write(f"Direct emulator success: {direct_success}\n")
            f.write(f"Server success: {server_success}\n")
            
            if direct_success and not server_success:
                f.write("CONCLUSION: Server-specific map corruption issue confirmed\n")
            elif not direct_success and not server_success:
                f.write("CONCLUSION: Fundamental map reading issue affecting both\n")
            elif direct_success and server_success:
                f.write("CONCLUSION: Both approaches working correctly\n")
            
            # Compare unknown ratios
            if 'unknown_ratio' in direct_results and 'outside_unknown_ratio' in server_results:
                f.write(f"\nMap quality comparison:\n")
                f.write(f"  Direct emulator unknown tiles: {direct_results['unknown_ratio']}\n")
                f.write(f"  Server unknown tiles: {server_results['outside_unknown_ratio']}\n")
            
            f.write(f"\nFILES SAVED:\n")
            f.write(f"  Direct emulator maps: {self.output_dir}/direct_emulator/\n")
            f.write(f"  Server maps: {self.output_dir}/server/\n")
            f.write(f"  Ground truth comparison: tests/ground_truth/\n")
        
        print(f"   📋 Comparison report: {comparison_file}")
        
        # Create simple summary for console
        print(f"\n📊 QUICK COMPARISON:")
        print(f"   Direct emulator: {'✅ SUCCESS' if direct_results.get('success') else '❌ FAILED'}")
        print(f"   Server:          {'✅ SUCCESS' if server_results.get('success') else '❌ FAILED'}")
        
        if 'unknown_ratio' in direct_results and 'outside_unknown_ratio' in server_results:
            print(f"   Quality comparison:")
            print(f"     Direct: {direct_results['unknown_ratio']} unknown")
            print(f"     Server: {server_results['outside_unknown_ratio']} unknown")
    
    def run_full_test(self):
        """Run complete test with output saving"""
        print("=" * 80)
        print("COMPREHENSIVE TEST WITH OUTPUT COMPARISON")
        print("=" * 80)
        print(f"All outputs will be saved to: {self.output_dir}")
        print(f"Compare with ground truth in: tests/ground_truth/")
        
        # Run tests
        direct_results = self.test_direct_emulator()
        server_results = self.test_server()
        
        # Create comparison
        self.create_comparison_report(direct_results, server_results)
        
        print(f"\n🎯 NEXT STEPS:")
        print(f"   1. Check outputs in: {self.output_dir}")
        print(f"   2. Compare server maps with ground truth")
        print(f"   3. Identify specific corruption patterns")
        print(f"   4. Focus debugging on server map cache invalidation")


if __name__ == "__main__":
    test = OutputComparisonTest()
    test.run_full_test()