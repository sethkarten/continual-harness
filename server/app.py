#!/usr/bin/env python3
"""
Fixed Simple Pokemon Emerald server - handles FastAPI and pygame properly
"""

import os
import pygame
import numpy as np
import time
import base64
import io
import signal
import sys
import asyncio
import threading
from PIL import Image

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from pokemon_env.emulator import EmeraldEmulator

# Set up logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
env = None
running = True
step_count = 0
current_obs = None
fps = 60

# Pygame display
screen_width = 480  # 240 * 2 (upscaled)
screen_height = 320  # 160 * 2 (upscaled)
screen = None
font = None
clock = None

# Threading locks for thread safety
obs_lock = threading.Lock()
step_lock = threading.Lock()

# Button mapping
button_map = {
    pygame.K_z: 'A',
    pygame.K_x: 'B', 
    pygame.K_RETURN: 'START',
    pygame.K_RSHIFT: 'SELECT',
    pygame.K_UP: 'UP',
    pygame.K_DOWN: 'DOWN',
    pygame.K_LEFT: 'LEFT',
    pygame.K_RIGHT: 'RIGHT',
}

# FastAPI app
app = FastAPI(
    title="Pokemon Emerald Simple Server",
    description="Simple server with pygame display and FastAPI endpoints",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for API requests and responses
class ActionRequest(BaseModel):
    buttons: list = []  # List of button names: A, B, SELECT, START, UP, DOWN, LEFT, RIGHT

class GameStateResponse(BaseModel):
    screenshot_base64: str
    step_number: int
    resolution: list  # [width, height]
    status: str

class ComprehensiveStateResponse(BaseModel):
    visual: dict
    player: dict
    game: dict
    map: dict
    step_number: int
    status: str

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    running = False
    if env:
        env.stop()
    pygame.quit()
    sys.exit(0)

def setup_environment():
    """Initialize the emulator"""
    global env, current_obs
    
    try:
        rom_path = "Emerald-GBAdvance/rom.gba"
        if not os.path.exists(rom_path):
            raise RuntimeError(f"ROM not found at {rom_path}")
        
        env = EmeraldEmulator(rom_path=rom_path)
        env.initialize()
        
        screenshot = env.get_screenshot()
        if screenshot:
            with obs_lock:
                current_obs = np.array(screenshot)
        else:
            with obs_lock:
                current_obs = np.zeros((env.height, env.width, 3), dtype=np.uint8)

        print("Emulator initialized successfully!")
        return True
        
    except Exception as e:
        print(f"Failed to initialize emulator: {e}")
        return False

def handle_input(manual_mode=False):
    """Handle keyboard input and convert to game actions"""
    actions_pressed = []
    
    if not manual_mode:
        # Server mode - no keyboard input
        return True, []
    
    # Manual mode - handle keyboard input
    # This handles continuous key presses
    keys = pygame.key.get_pressed()
    for key, button in button_map.items():
        if keys[key]:
            actions_pressed.append(button)

    # This handles single key events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False, []
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False, []
            elif event.key == pygame.K_s:
                save_screenshot()
            elif event.key == pygame.K_r:
                reset_game()
            elif event.key == pygame.K_1:
                env.save_state("server/simple_test.state")
            elif event.key == pygame.K_2:
                env.load_state("server/simple_test.state")
    
    return True, actions_pressed

def step_environment(actions_pressed):
    """Take a step in the environment"""
    global current_obs
    
    with step_lock:
        env.run_frame_with_buttons(actions_pressed)

        screenshot = env.get_screenshot()
        if screenshot:
            with obs_lock:
                current_obs = np.array(screenshot)

def update_display(manual_mode=False):
    """Update the display with current game state"""
    global current_obs, screen, step_count
    
    with obs_lock:
        obs_copy = current_obs.copy() if current_obs is not None else None
    
    if obs_copy is not None and screen:
        obs_surface = pygame.surfarray.make_surface(obs_copy.swapaxes(0, 1))
        scaled_surface = pygame.transform.scale(obs_surface, (screen_width, screen_height))
        screen.blit(scaled_surface, (0, 0))
    
    # if manual_mode:
    #     draw_info_overlay()
    pygame.display.flip()

def draw_info_overlay():
    """Draw information overlay on the screen"""
    global screen, step_count, font
    
    if not screen or not font:
        return
        
    overlay_height = 80
    overlay = pygame.Surface((screen_width, overlay_height))
    overlay.set_alpha(200)
    overlay.fill((0, 0, 0))
    
    # Position overlay at the bottom of the screen
    overlay_y = screen_height - overlay_height
    screen.blit(overlay, (0, overlay_y))
    
    info_lines = [
        f"Step: {step_count}",
        f"Controls: Z=A, X=B, Enter=Start, RShift=Select, Arrows=Move",
        f"Special: S=Screenshot, R=Reset, 1=Save State, 2=Load State, Esc=Quit"
    ]
    
    y_offset = overlay_y + 8
    for line in info_lines:
        text_surface = font.render(line, True, (255, 255, 255))
        screen.blit(text_surface, (10, y_offset))
        y_offset += 22

def save_screenshot():
    """Save current screenshot"""
    global current_obs
    
    with obs_lock:
        obs_copy = current_obs.copy() if current_obs is not None else None
    
    if obs_copy is not None:
        timestamp = int(time.time())
        filename = f"simple_test_screenshot_{timestamp}.png"
        img = Image.fromarray(obs_copy)
        img.save(filename)
        print(f"Screenshot saved: {filename}")

def reset_game():
    """Reset the game"""
    global env, step_count
    
    print("Resetting game...")
    with step_lock:
        env.initialize()
        step_count = 0
    print("Game reset complete")

def game_loop(manual_mode=False):
    """Main game loop - runs in main thread"""
    global running, step_count, clock
    
    if manual_mode:
        print("Starting game loop in manual mode...")
        print("Controls: Z=A, X=B, Enter=Start, RShift=Select, Arrows=Move")
        print("Special: S=Screenshot, R=Reset, 1=Save State, 2=Load State, Esc=Quit")
    else:
        print("Starting game loop in server mode...")
    
    while running:
        # Handle input
        should_continue, actions_pressed = handle_input(manual_mode)
        if not should_continue:
            break
            
        # Step environment
        step_environment(actions_pressed)
        
        # Update display
        update_display(manual_mode)
        
        with step_lock:
            step_count += 1
        
        clock.tick(fps)

def init_pygame():
    """Initialize pygame"""
    global screen, font, clock
    
    pygame.init()
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Pokemon Emerald Simple Server")
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

def run_fastapi_server(port):
    """Run FastAPI server in background thread"""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

# FastAPI endpoints
@app.get("/status")
async def get_status():
    """Get server status"""
    with step_lock:
        current_step = step_count
    return {
        "status": "running",
        "step_count": current_step,
        "fps": fps
    }

@app.get("/screenshot")
async def get_screenshot():
    """Get current screenshot"""
    global current_obs, step_count
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    with obs_lock:
        obs_copy = current_obs.copy() if current_obs is not None else None
    
    if obs_copy is None:
        raise HTTPException(status_code=500, detail="No screenshot available")
    
    try:
        # Convert numpy array to PIL image
        pil_image = Image.fromarray(obs_copy)
        
        # Convert to base64
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        with step_lock:
            current_step = step_count
        
        return GameStateResponse(
            screenshot_base64=img_str,
            step_number=current_step,
            resolution=[obs_copy.shape[1], obs_copy.shape[0]],
            status="running"
        )
        
    except Exception as e:
        logger.error(f"Error getting screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/action")
async def take_action(request: ActionRequest):
    """Take an action"""
    global current_obs, step_count
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Execute action
        step_environment(request.buttons)
        
        with step_lock:
            step_count += 1
            current_step = step_count
        
        # Get updated screenshot
        with obs_lock:
            obs_copy = current_obs.copy() if current_obs is not None else None
        
        if obs_copy is not None:
            pil_image = Image.fromarray(obs_copy)
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return GameStateResponse(
                screenshot_base64=img_str,
                step_number=current_step,
                resolution=[obs_copy.shape[1], obs_copy.shape[0]],
                status="running"
            )
        else:
            raise HTTPException(status_code=500, detail="No screenshot available")
            
    except Exception as e:
        logger.error(f"Error taking action: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/state")
async def get_comprehensive_state():
    """Get comprehensive game state including visual and memory data"""
    global step_count
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Get comprehensive state from emulator
        state = env.get_comprehensive_state()
        
        # The battle information already contains all necessary data
        # No additional analysis needed - keep it clean
        
        # Convert screenshot to base64 if available
        if state["visual"]["screenshot"]:
            buffer = io.BytesIO()
            state["visual"]["screenshot"].save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            state["visual"]["screenshot_base64"] = img_str
            # Remove the PIL image object to avoid serialization issues
            del state["visual"]["screenshot"]
        
        with step_lock:
            current_step = step_count
        
        return ComprehensiveStateResponse(
            visual=state["visual"],
            player=state["player"],
            game=state["game"],
            map=state["map"],
            step_number=current_step,
            status="running"
        )
        
    except Exception as e:
        logger.error(f"Error getting comprehensive state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/memory")
async def debug_memory():
    """Debug memory reading (basic version)"""
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        if not env.memory_reader:
            return {"error": "Memory reader not initialized"}
        
        # Test basic memory access
        diagnostics = env.memory_reader.test_memory_access()
        
        # Try to read some basic data
        try:
            party_size = env.memory_reader.read_party_size()
            coordinates = env.memory_reader.read_coordinates()
            money = env.memory_reader.read_money()
            
            # Add new debugging info
            is_in_battle = env.memory_reader.is_in_battle()
            game_state = env.memory_reader.get_game_state()
            player_name = env.memory_reader.read_player_name()
            
            # Add battle detection debugging
            try:
                battle_addr = env.memory_reader.IN_BATTLE_BIT_ADDR
                battle_raw_value = env.memory_reader._read_u8(battle_addr)
                battle_mask = env.memory_reader.IN_BATTLE_BITMASK
                battle_result = (battle_raw_value & battle_mask) != 0
            except Exception as e:
                battle_raw_value = None
                battle_mask = None
                battle_result = None
            
            diagnostics.update({
                'party_size': party_size,
                'coordinates': coordinates,
                'money': money,
                'is_in_battle': is_in_battle,
                'game_state': game_state,
                'player_name': player_name,
                'battle_detection': {
                    'address': f'0x{battle_addr:08x}' if 'battle_addr' in locals() else 'unknown',
                    'raw_value': f'0x{battle_raw_value:02x}' if battle_raw_value is not None else 'error',
                    'mask': f'0x{battle_mask:02x}' if battle_mask is not None else 'unknown',
                    'result': battle_result
                },
                'working_reads': True
            })
        except Exception as read_error:
            diagnostics['read_error'] = str(read_error)
            diagnostics['working_reads'] = False
        
        return diagnostics
        
    except Exception as e:
        logger.error(f"Error debugging memory: {e}")
        return {"error": str(e)}

@app.get("/debug/memory/comprehensive")
async def debug_memory_comprehensive():
    """Comprehensive memory reading test with detailed diagnostics"""
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Use the comprehensive memory testing method
        test_results = env.test_memory_reading()
        return test_results
        
    except Exception as e:
        logger.error(f"Error running comprehensive memory test: {e}")
        return {"error": str(e)}

@app.post("/save_state")
async def save_state():
    """Save current game state"""
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        timestamp = int(time.time())
        filename = f"save_state_{timestamp}.sav"
        data = env.save_state(filename)
        if data:
            return {"status": "saved", "filename": filename, "size": len(data)}
        else:
            raise HTTPException(status_code=500, detail="Failed to save state")
    except Exception as e:
        logger.error(f"Error saving state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/load_state")
async def load_state(filename: str):
    """Load game state from file"""
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        env.load_state(filename)
        return {"status": "loaded", "filename": filename}
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_server():
    """Stop the server"""
    global running
    running = False
    return {"status": "stopping"}

def main():
    """Main function"""
    import argparse
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parser = argparse.ArgumentParser(description="Simple Pokemon Emerald Server")
    parser.add_argument("--port", type=int, default=8000, help="Port for FastAPI server")
    parser.add_argument("--manual", action="store_true", help="Enable manual mode with keyboard input and overlay")
    parser.add_argument("--load-state", type=str, help="Load a saved state file on startup")
    
    args = parser.parse_args()
    
    print("Starting Fixed Simple Pokemon Emerald Server")
    if args.manual:
        print("Manual mode enabled - keyboard input and overlay active")
    else:
        print("Server mode - no keyboard input, no overlay")
    print("Press Ctrl+C to stop")
    
    # Initialize pygame
    init_pygame()
    
    # Initialize emulator
    if not setup_environment():
        print("Failed to initialize emulator")
        return
    
    # Load state if specified
    if args.load_state:
        try:
            env.load_state(args.load_state)
            print(f"Loaded state from: {args.load_state}")
        except Exception as e:
            print(f"Failed to load state from {args.load_state}: {e}")
            print("Continuing with fresh game state...")
    
    # Start FastAPI server in background thread
    server_thread = threading.Thread(target=run_fastapi_server, args=(args.port,), daemon=True)
    server_thread.start()
    
    print(f"FastAPI server running on http://127.0.0.1:{args.port}")
    print("Available endpoints:")
    print("  /status - Server status")
    print("  /screenshot - Current screenshot")
    print("  /action - Take action (POST)")
    print("  /state - Comprehensive game state (visual + memory data)")
    print("  /debug/memory - Debug memory reading (basic)")
    print("  /debug/memory/comprehensive - Comprehensive memory diagnostics")
    print("  /save_state - Save game state (POST)")
    print("  /load_state - Load game state (POST)")
    print("  /stop - Stop server")
    
    try:
        # Run pygame loop in main thread
        game_loop(manual_mode=args.manual)
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        global running
        running = False
        if env:
            env.stop()
        pygame.quit()
        print("Server stopped")

if __name__ == "__main__":
    main() 