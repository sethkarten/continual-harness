#!/usr/bin/env python3
"""
Test server movement with proper restart and action verification
Ensures each DOWN action is successfully executed and tracked
"""

import os
import time
import subprocess
import requests
import signal


def kill_all_servers():
    """Kill all server.app processes"""
    print("🔄 Killing all existing server processes...")
    os.system("pkill -f 'server.app' 2>/dev/null")
    time.sleep(2)  # Give time for cleanup
    
    # Verify no servers are running
    result = os.popen("ps aux | grep server.app | grep -v grep").read()
    if result.strip():
        print(f"⚠️  Still running: {result.strip()}")
        print("   Force killing...")
        os.system("pkill -9 -f 'server.app' 2>/dev/null")
        time.sleep(1)
    else:
        print("✅ All servers killed")


def start_fresh_server(port=8050):
    """Start a fresh server and verify it's running"""
    print(f"\n🚀 Starting fresh server on port {port}...")
    
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
    
    # Wait for server to start with verification
    server_url = f"http://127.0.0.1:{port}"
    for i in range(30):
        try:
            response = requests.get(f"{server_url}/status", timeout=2)
            if response.status_code == 200:
                print(f"✅ Server started successfully after {i+1} seconds")
                
                # Verify initial state
                response = requests.get(f"{server_url}/state", timeout=5)
                if response.status_code == 200:
                    state = response.json()
                    location = state['player']['location']
                    position = state['player']['position']
                    print(f"   Initial state: {location} at ({position['x']}, {position['y']})")
                    return process, server_url
                else:
                    print(f"❌ Failed to get initial state: {response.status_code}")
                    break
        except requests.exceptions.RequestException:
            time.sleep(1)
    
    # Failed to start
    process.terminate()
    process.wait()
    raise Exception(f"Server failed to start properly on port {port}")


def execute_and_verify_action(server_url, action, step_num):
    """Execute an action and verify it was processed correctly"""
    print(f"   Step {step_num}: Sending {action.upper()} action...")
    
    # Get position before action
    response = requests.get(f"{server_url}/state", timeout=5)
    if response.status_code != 200:
        print(f"   ❌ Failed to get state before action: {response.status_code}")
        return False
    
    before_state = response.json()
    before_pos = before_state['player']['position']
    before_loc = before_state['player']['location']
    
    # Send action (matching agent.py format exactly)
    action_data = {"buttons": [action]}
    response = requests.post(f"{server_url}/action", json=action_data, timeout=5)
    
    if response.status_code != 200:
        print(f"   ❌ Action request failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    print(f"      Action sent successfully (status: {response.status_code})")
    
    # Wait for processing (like agent.py does)
    time.sleep(0.1)  # Between-action delay
    time.sleep(0.3)  # Action processing delay
    
    # Get position after action
    response = requests.get(f"{server_url}/state", timeout=5)
    if response.status_code != 200:
        print(f"   ❌ Failed to get state after action: {response.status_code}")
        return False
    
    after_state = response.json()
    after_pos = after_state['player']['position']
    after_loc = after_state['player']['location']
    
    # Report changes
    pos_changed = (before_pos['x'] != after_pos['x'] or before_pos['y'] != after_pos['y'])
    loc_changed = (before_loc != after_loc)
    
    print(f"      Before: {before_loc} at ({before_pos['x']}, {before_pos['y']})")
    print(f"      After:  {after_loc} at ({after_pos['x']}, {after_pos['y']})")
    
    if pos_changed:
        print(f"      ✅ Position changed: moved from ({before_pos['x']}, {before_pos['y']}) to ({after_pos['x']}, {after_pos['y']})")
    else:
        print(f"      ⚠️  Position unchanged")
    
    if loc_changed:
        print(f"      🎯 Location changed: {before_loc} → {after_loc}")
    
    return True


def test_movement_sequence():
    """Test the complete movement sequence with verification"""
    print("=" * 70)
    print("TESTING SERVER MOVEMENT WITH PROPER RESTART AND VERIFICATION")
    print("=" * 70)
    
    server_process = None
    
    try:
        # Step 1: Clean restart
        kill_all_servers()
        server_process, server_url = start_fresh_server()
        
        # Step 2: Execute 3 DOWN actions with verification
        print(f"\n🚶 Executing 3 DOWN actions with verification...")
        
        success_count = 0
        for i in range(3):
            if execute_and_verify_action(server_url, "down", i + 1):
                success_count += 1
            else:
                print(f"   ❌ Action {i + 1} failed")
                break
            print()  # Spacing
        
        # Step 3: Final state check
        print(f"📊 Final state after {success_count}/3 actions:")
        response = requests.get(f"{server_url}/state", timeout=5)
        if response.status_code == 200:
            final_state = response.json()
            final_location = final_state['player']['location']
            final_position = final_state['player']['position']
            
            print(f"   Location: {final_location}")
            print(f"   Position: ({final_position['x']}, {final_position['y']})")
            
            # Check if we successfully exited
            if "HOUSE" not in final_location.upper():
                print(f"   ✅ SUCCESS: Player exited house!")
                
                # Test map quality
                map_tiles = final_state['map']['tiles']
                total_tiles = sum(len(row) for row in map_tiles)
                unknown_tiles = sum(1 for row in map_tiles for tile in row 
                                   if len(tile) >= 2 and tile[1] == 0)
                unknown_ratio = unknown_tiles / total_tiles if total_tiles > 0 else 0
                
                print(f"   Map quality: {unknown_ratio:.1%} unknown tiles")
                
                if unknown_ratio < 0.1:
                    print(f"   ✅ Map quality is good!")
                    return True
                else:
                    print(f"   ⚠️  Map has quality issues: {unknown_ratio:.1%} unknown tiles")
                    return False
            else:
                print(f"   ❌ FAILED: Player still in house after {success_count} actions")
                
                # Check if player moved at all
                if final_position['x'] != 8 or final_position['y'] != 7:
                    print(f"   Player did move within house: (8,7) → ({final_position['x']}, {final_position['y']})")
                else:
                    print(f"   Player didn't move at all!")
                
                return False
        else:
            print(f"   ❌ Failed to get final state: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if server_process:
            print(f"\n🛑 Cleaning up server...")
            server_process.terminate()
            server_process.wait()


if __name__ == "__main__":
    success = test_movement_sequence()
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    if success:
        print("🎉 TEST PASSED: Server movement and map reading work correctly!")
    else:
        print("💥 TEST FAILED: Issues with server movement or map reading")
        print("\nPossible issues to investigate:")
        print("- Action format not matching agent.py")
        print("- Timing/delays insufficient")
        print("- Server collision detection differences")
        print("- Map reading corruption during transitions")