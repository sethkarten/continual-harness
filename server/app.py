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
import json
from PIL import Image

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import socketio     # for streamer setup

from pokemon_env.emulator import EmeraldEmulator
from pokemon_env.emerald_utils import (
    SYSTEM_FLAGS_START, FLAG_VISITED_LITTLEROOT_TOWN, FLAG_VISITED_OLDALE_TOWN,
    FLAG_VISITED_PETALBURG_CITY, FLAG_VISITED_RUSTBORO_CITY, FLAG_VISITED_DEWFORD_TOWN,
    FLAG_VISITED_SLATEPORT_CITY, FLAG_VISITED_MAUVILLE_CITY, FLAG_BADGE01_GET,
    FLAG_BADGE02_GET, FLAG_BADGE03_GET, FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET,
    FLAG_DEFEATED_RUSTBORO_GYM, FLAG_DEFEATED_DEWFORD_GYM, FLAG_DEFEATED_MAUVILLE_GYM
)

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

# Milestone tracking system
MILESTONES_FILE = "milestones_progress.json"
milestone_tracker = {}

class MilestoneTracker:
    """Persistent milestone tracking system"""
    
    def __init__(self, filename: str = MILESTONES_FILE):
        self.filename = filename
        self.milestones = {}
        self.load_from_file()
    
    def load_from_file(self):
        """Load milestone progress from file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    self.milestones = data.get('milestones', {})
                logger.info(f"Loaded {len(self.milestones)} milestone records from {self.filename}")
            else:
                logger.info(f"No existing milestone file found, starting fresh")
                self.milestones = {}
        except Exception as e:
            logger.warning(f"Error loading milestones from file: {e}")
            self.milestones = {}
    
    def save_to_file(self):
        """Save milestone progress to file"""
        try:
            data = {
                'milestones': self.milestones,
                'last_updated': time.time(),
                'version': '1.0'
            }
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved milestone progress to {self.filename}")
        except Exception as e:
            logger.warning(f"Error saving milestones to file: {e}")
    
    def mark_completed(self, milestone_id: str, timestamp: float = None):
        """Mark a milestone as completed"""
        if timestamp is None:
            timestamp = time.time()
        
        if milestone_id not in self.milestones or not self.milestones[milestone_id].get('completed', False):
            self.milestones[milestone_id] = {
                'completed': True,
                'timestamp': timestamp,
                'first_completed': timestamp
            }
            logger.info(f"Milestone completed: {milestone_id}")
            self.save_to_file()
            return True
        return False
    
    def is_completed(self, milestone_id: str) -> bool:
        """Check if a milestone is completed"""
        return self.milestones.get(milestone_id, {}).get('completed', False)
    
    def get_milestone_data(self, milestone_id: str) -> dict:
        """Get milestone data"""
        return self.milestones.get(milestone_id, {'completed': False, 'timestamp': None})
    
    def reset_milestone(self, milestone_id: str):
        """Reset a milestone (for testing)"""
        if milestone_id in self.milestones:
            del self.milestones[milestone_id]
            self.save_to_file()
            logger.info(f"Reset milestone: {milestone_id}")
    
    def reset_all(self):
        """Reset all milestones (for testing)"""
        self.milestones = {}
        self.save_to_file()
        logger.info("Reset all milestones")

# Initialize milestone tracker
milestone_tracker = MilestoneTracker()

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
    global recent_button_presses
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
    
    # Track manual button presses for the action queue display
    if actions_pressed:
        current_time = time.time()
        for button in actions_pressed:
            # Avoid duplicate consecutive buttons within 100ms
            should_add = True
            if recent_button_presses:
                last_entry = recent_button_presses[-1]
                if (last_entry["button"] == button and 
                    current_time - last_entry["timestamp"] < 0.1):  # 100ms threshold
                    should_add = False
            
            if should_add:
                recent_button_presses.append({
                    "button": button,
                    "timestamp": current_time
                })
        
        # Keep only last 50 button presses to avoid memory issues
        if len(recent_button_presses) > 50:
            recent_button_presses = recent_button_presses[-50:]
    
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

    # Create a new Socket.IO server
    sio = socketio.AsyncServer(cors_allowed_origins='*')

    # Attach the Socket.IO server to the FastAPI app
    sio_app = socketio.ASGIApp(sio, app)

    # Define event handlers for the Socket.IO server
    @sio.event
    async def connect(sid, environ):
        print('Client connected:', sid)

    @sio.event
    async def disconnect(sid):
        print('Client disconnected:', sid)

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
    global current_obs, step_count, recent_button_presses
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Track button presses for recent actions display
        if request.buttons:
            current_time = time.time()
            for button in request.buttons:
                # Avoid duplicate consecutive buttons within 100ms
                should_add = True
                if recent_button_presses:
                    last_entry = recent_button_presses[-1]
                    if (last_entry["button"] == button and 
                        current_time - last_entry["timestamp"] < 0.1):  # 100ms threshold
                        should_add = False
                
                if should_add:
                    recent_button_presses.append({
                        "button": button,
                        "timestamp": current_time
                    })
            
            # Keep only last 50 button presses to avoid memory issues
            if len(recent_button_presses) > 50:
                recent_button_presses = recent_button_presses[-50:]
        
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
    global step_count, milestone_tracker
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Get comprehensive state from emulator
        state = env.get_comprehensive_state()
        
        # Update milestones based on current state
        check_and_update_milestones(state)
        
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
    """Save current game state and milestone progress"""
    global milestone_tracker
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        timestamp = int(time.time())
        filename = f"save_state_{timestamp}.sav"
        milestone_filename = f"milestones_{timestamp}.json"
        
        # Save emulator state
        data = env.save_state(filename)
        if not data:
            raise HTTPException(status_code=500, detail="Failed to save emulator state")
        
        # Save milestone progress with the same timestamp
        milestone_backup = milestone_tracker.filename
        milestone_tracker.filename = milestone_filename
        milestone_tracker.save_to_file()
        milestone_tracker.filename = milestone_backup  # Restore original filename
        
        return {
            "status": "saved", 
            "filename": filename, 
            "milestone_file": milestone_filename,
            "size": len(data),
            "milestones_saved": len(milestone_tracker.milestones)
        }
    except Exception as e:
        logger.error(f"Error saving state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/load_state")
async def load_state(filename: str):
    """Load game state from file and corresponding milestone progress"""
    global milestone_tracker
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Load emulator state
        env.load_state(filename)
        
        # Try to load corresponding milestone file
        milestone_filename = filename.replace(".sav", ".json").replace("save_state_", "milestones_")
        if os.path.exists(milestone_filename):
            # Temporarily change filename to load the specific milestone file
            original_filename = milestone_tracker.filename
            milestone_tracker.filename = milestone_filename
            milestone_tracker.load_from_file()
            milestone_tracker.filename = original_filename  # Restore original filename
            milestone_tracker.save_to_file()  # Save loaded milestones to main file
            
            return {
                "status": "loaded", 
                "filename": filename,
                "milestone_file": milestone_filename,
                "milestones_loaded": len(milestone_tracker.milestones)
            }
        else:
            logger.warning(f"No milestone file found for {filename}")
            return {
                "status": "loaded", 
                "filename": filename,
                "milestone_file": "not_found",
                "milestones_loaded": 0
            }
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent")
async def get_agent_thinking():
    """Get current agent thinking status"""
    # This would connect to your agent system
    # For now, returning placeholder data
    return {
        "status": "thinking",
        "current_thought": "Analyzing game state and planning next actions...",
        "confidence": 0.85,
        "timestamp": time.time()
    }

def check_and_update_milestones(game_state: dict):
    """Check current game state and update milestones"""
    global milestone_tracker
    
    try:
        # Only check milestones that aren't already completed
        milestones_to_check = [
            "GAME_RUNNING", "HAS_PARTY", "LITTLEROOT_TOWN", "STARTER_CHOSEN", 
            "POKEDEX_RECEIVED", "OLDALE_TOWN", "FIRST_WILD_ENCOUNTER", 
            "FIRST_POKEMON_CAUGHT", "PETALBURG_CITY", "RUSTBORO_CITY", 
            "STONE_BADGE", "DEWFORD_TOWN", "KNUCKLE_BADGE", "SLATEPORT_CITY",
            "MAUVILLE_CITY", "DYNAMO_BADGE", "POKEDEX_5_SEEN", "POKEDEX_10_SEEN",
            "EARNED_1000_POKEDOLLARS", "PARTY_OF_TWO"
        ]
        
        for milestone_id in milestones_to_check:
            if not milestone_tracker.is_completed(milestone_id):
                if check_milestone_condition(milestone_id, game_state):
                    milestone_tracker.mark_completed(milestone_id)
    
    except Exception as e:
        logger.warning(f"Error checking milestones: {e}")

def check_milestone_condition(milestone_id: str, game_state: dict) -> bool:
    """Check if a specific milestone condition is met based on current game state"""
    try:
        # Test milestones (should always work)
        if milestone_id == "GAME_RUNNING":
            return True  # If we can execute this, game is running
        elif milestone_id == "HAS_PARTY":
            if game_state:
                party = game_state.get("player", {}).get("party", [])
                return len(party) > 0
            return False
        
        # Location-based milestones - check current location
        elif milestone_id == "LITTLEROOT_TOWN":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "LITTLEROOT" in str(location).upper()
            return False
        elif milestone_id == "OLDALE_TOWN":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "OLDALE" in str(location).upper()
            return False
        elif milestone_id == "PETALBURG_CITY":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "PETALBURG" in str(location).upper()
            return False
        elif milestone_id == "RUSTBORO_CITY":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "RUSTBORO" in str(location).upper()
            return False
        elif milestone_id == "DEWFORD_TOWN":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "DEWFORD" in str(location).upper()
            return False
        elif milestone_id == "SLATEPORT_CITY":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "SLATEPORT" in str(location).upper()
            return False
        elif milestone_id == "MAUVILLE_CITY":
            if game_state:
                location = game_state.get("player", {}).get("location", "")
                return "MAUVILLE" in str(location).upper()
            return False
            
        # Pokemon system milestones - check party/pokedex state  
        elif milestone_id == "STARTER_CHOSEN":
            if game_state:
                party = game_state.get("player", {}).get("party", [])
                return len(party) >= 1 and any(p.get("species_name", "").strip() for p in party)
            return False
        elif milestone_id == "POKEDEX_RECEIVED":
            if game_state:
                pokedex_seen = game_state.get("game", {}).get("pokedex_seen", 0)
                return (pokedex_seen if isinstance(pokedex_seen, int) else 0) >= 1
            return False
            
        # Badge milestones - check badge count/list
        elif milestone_id == "STONE_BADGE":
            if game_state:
                badges = game_state.get("game", {}).get("badges", [])
                if isinstance(badges, list):
                    return len(badges) >= 1 or any("Stone" in str(b) for b in badges)
                elif isinstance(badges, int):
                    return badges >= 1
            return False
        elif milestone_id == "KNUCKLE_BADGE":
            if game_state:
                badges = game_state.get("game", {}).get("badges", [])
                if isinstance(badges, list):
                    return len(badges) >= 2 or any("Knuckle" in str(b) for b in badges)
                elif isinstance(badges, int):
                    return badges >= 2
            return False
        elif milestone_id == "DYNAMO_BADGE":
            if game_state:
                badges = game_state.get("game", {}).get("badges", [])
                if isinstance(badges, list):
                    return len(badges) >= 3 or any("Dynamo" in str(b) for b in badges)
                elif isinstance(badges, int):
                    return badges >= 3
            return False
            
        # Progress-based milestones
        elif milestone_id == "FIRST_POKEMON_CAUGHT":
            if game_state:
                pokedex_caught = game_state.get("game", {}).get("pokedex_caught", 0)
                return (pokedex_caught if isinstance(pokedex_caught, int) else 0) >= 1
            return False
        elif milestone_id == "FIRST_WILD_ENCOUNTER":
            if game_state:
                pokedex_seen = game_state.get("game", {}).get("pokedex_seen", 0)
                return (pokedex_seen if isinstance(pokedex_seen, int) else 0) >= 2
            return False
        elif milestone_id == "PARTY_OF_TWO":
            if game_state:
                party = game_state.get("player", {}).get("party", [])
                valid_pokemon = [p for p in party if p.get("species_name", "").strip() and p.get("species_name", "").strip() != "NONE"]
                return len(valid_pokemon) >= 2
            return False
        elif milestone_id == "EARNED_1000_POKEDOLLARS":
            if game_state:
                money = game_state.get("game", {}).get("money", 0)
                return (money if isinstance(money, int) else 0) >= 1000
            return False
        elif milestone_id == "POKEDEX_5_SEEN":
            if game_state:
                pokedex_seen = game_state.get("game", {}).get("pokedex_seen", 0)
                return (pokedex_seen if isinstance(pokedex_seen, int) else 0) >= 5
            return False
        elif milestone_id == "POKEDEX_10_SEEN":
            if game_state:
                pokedex_seen = game_state.get("game", {}).get("pokedex_seen", 0)
                return (pokedex_seen if isinstance(pokedex_seen, int) else 0) >= 10
            return False
            
        return False
        
    except Exception as e:
        logger.warning(f"Error checking milestone condition {milestone_id}: {e}")
        return False

@app.get("/milestones")
async def get_milestones():
    """Get current milestones achieved based on persistent tracking"""
    global milestone_tracker
    
    if env is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Get current game state and update milestones
        game_state = env.get_comprehensive_state()
        check_and_update_milestones(game_state)
        
        # Define milestone progression in logical order  
        milestone_definitions = [
            # Test milestones
            {"id": "GAME_RUNNING", "name": "GAME_RUNNING", "category": "basic"},
            {"id": "HAS_PARTY", "name": "HAS_PARTY", "category": "pokemon"},
            
            # Location milestones  
            {"id": "LITTLEROOT_TOWN", "name": "LITTLEROOT_TOWN", "category": "location"},
            {"id": "OLDALE_TOWN", "name": "OLDALE_TOWN", "category": "location"},
            {"id": "PETALBURG_CITY", "name": "PETALBURG_CITY", "category": "location"},
            {"id": "RUSTBORO_CITY", "name": "RUSTBORO_CITY", "category": "location"},
            {"id": "DEWFORD_TOWN", "name": "DEWFORD_TOWN", "category": "location"},
            {"id": "SLATEPORT_CITY", "name": "SLATEPORT_CITY", "category": "location"},
            {"id": "MAUVILLE_CITY", "name": "MAUVILLE_CITY", "category": "location"},
            
            # Pokemon milestones
            {"id": "STARTER_CHOSEN", "name": "STARTER_CHOSEN", "category": "pokemon"},
            {"id": "POKEDEX_RECEIVED", "name": "POKEDEX_RECEIVED", "category": "pokemon"},
            {"id": "FIRST_WILD_ENCOUNTER", "name": "FIRST_WILD_ENCOUNTER", "category": "pokemon"},
            {"id": "FIRST_POKEMON_CAUGHT", "name": "FIRST_POKEMON_CAUGHT", "category": "pokemon"},
            {"id": "PARTY_OF_TWO", "name": "PARTY_OF_TWO", "category": "pokemon"},
            
            # Badge milestones
            {"id": "STONE_BADGE", "name": "STONE_BADGE", "category": "badge"},
            {"id": "KNUCKLE_BADGE", "name": "KNUCKLE_BADGE", "category": "badge"},
            {"id": "DYNAMO_BADGE", "name": "DYNAMO_BADGE", "category": "badge"},
            
            # Progress milestones
            {"id": "POKEDEX_5_SEEN", "name": "POKEDEX_5_SEEN", "category": "progress"},
            {"id": "POKEDEX_10_SEEN", "name": "POKEDEX_10_SEEN", "category": "progress"},
            {"id": "EARNED_1000_POKEDOLLARS", "name": "EARNED_1000_POKEDOLLARS", "category": "progress"},
        ]
        
        # Build milestone list with persistent data
        milestones = []
        for i, milestone_def in enumerate(milestone_definitions):
            milestone_data = milestone_tracker.get_milestone_data(milestone_def["id"])
            milestones.append({
                "id": i + 1,
                "name": milestone_def["name"],
                "category": milestone_def["category"],
                "completed": milestone_data["completed"],
                "timestamp": milestone_data.get("timestamp", None)
            })
        
        # Calculate summary stats
        completed_count = sum(1 for m in milestones if m["completed"])
        total_count = len(milestones)
        
        # Handle location data properly
        location_data = game_state.get("player", {}).get("location", "")
        if isinstance(location_data, dict):
            current_location = location_data.get("map_name", "UNKNOWN")
        else:
            current_location = str(location_data) if location_data else "UNKNOWN"
        
        # Handle badges data properly
        badges_data = game_state.get("game", {}).get("badges", 0)
        if isinstance(badges_data, list):
            badge_count = sum(1 for b in badges_data if b)
        else:
            badge_count = badges_data if isinstance(badges_data, int) else 0
        
        return {
            "milestones": milestones,
            "completed": completed_count,
            "total": total_count,
            "progress": completed_count / total_count if total_count > 0 else 0,
            "current_location": current_location,
            "badges": badge_count,
            "pokedex_seen": game_state.get("game", {}).get("pokedex_seen", 0),
            "pokedex_caught": game_state.get("game", {}).get("pokedex_caught", 0),
            "party_size": len(game_state.get("player", {}).get("party", [])),
            "tracking_system": "file_based",
            "milestone_file": milestone_tracker.filename
        }
        
    except Exception as e:
        logger.error(f"Error getting milestones: {e}")
        # Fallback to basic milestones if memory reading fails
        basic_milestones = [
            {"id": 1, "name": "GAME_STARTED", "category": "basic", "completed": True, "timestamp": time.time()},
            {"id": 2, "name": "EMULATOR_RUNNING", "category": "basic", "completed": True, "timestamp": time.time()},
        ]
        return {
            "milestones": basic_milestones,
            "completed": 2,
            "total": 2,
            "progress": 1.0,
            "tracking_system": "fallback",
            "error": str(e)
        }

# Global list to track recent button presses
recent_button_presses = []

@app.get("/recent_actions")
async def get_recent_actions():
    """Get recently pressed buttons"""
    global recent_button_presses
    return {
        "recent_buttons": recent_button_presses[-20:],  # Last 20 button presses
        "timestamp": time.time()
    }

@app.get("/debug/milestones")
async def debug_milestones():
    """Debug milestone tracking system"""
    global milestone_tracker
    
    try:
        return {
            "tracking_system": "file_based",
            "milestone_file": milestone_tracker.filename,
            "file_exists": os.path.exists(milestone_tracker.filename),
            "total_milestones": len(milestone_tracker.milestones),
            "completed_milestones": sum(1 for m in milestone_tracker.milestones.values() if m.get("completed", False)),
            "milestone_details": milestone_tracker.milestones
        }
    except Exception as e:
        logger.error(f"Error in milestone debug: {e}")
        return {"error": str(e)}

@app.post("/debug/reset_milestones")
async def reset_milestones():
    """Reset all milestones (for testing)"""
    global milestone_tracker
    
    try:
        milestone_tracker.reset_all()
        return {
            "status": "reset",
            "milestone_file": milestone_tracker.filename,
            "remaining_milestones": len(milestone_tracker.milestones)
        }
    except Exception as e:
        logger.error(f"Error resetting milestones: {e}")
        return {"error": str(e)}

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
    print("  /agent - Agent thinking status")
    print("  /milestones - Current milestones achieved")
    print("  /recent_actions - Recently pressed buttons")
    print("  /debug/memory - Debug memory reading (basic)")
    print("  /debug/memory/comprehensive - Comprehensive memory diagnostics")
    print("  /debug/milestones - Debug milestone tracking system")
    print("  /debug/reset_milestones - Reset all milestones (POST)")
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