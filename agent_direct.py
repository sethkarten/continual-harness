#!/usr/bin/env python3
"""
Direct agent implementation that runs agent and emulator in the same process
with visualization and real-time server interface like server.app
"""

import os
import pygame
import numpy as np
import time
import base64
import io
import signal
import sys
import threading
from PIL import Image
import argparse
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from pokemon_env.emulator import EmeraldEmulator
from pokemon_env.enums import MetatileBehavior
from agent.perception import perception_step
from agent.planning import planning_step
from agent.memory import memory_step
from agent.action import action_step
from utils.vlm import VLM
from utils.state_formatter import format_state_for_llm
from utils.map_formatter import format_map_for_display

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
emulator = None
agent_modules = None
running = True
step_count = 0
current_obs = None
fps = 60
agent_thinking = False
last_agent_action = None

# Pygame display
screen_width = 480  # 240 * 2 (upscaled)
screen_height = 320  # 160 * 2 (upscaled)
screen = None
font = None
clock = None

# Threading locks
obs_lock = threading.Lock()
step_lock = threading.Lock()
agent_lock = threading.Lock()

# Button mapping for manual control
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

# FastAPI app for web interface
app = FastAPI(
    title="Direct Agent Pokemon Emerald",
    description="Agent and emulator running in same process with real-time interface",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Models
class AgentActionRequest(BaseModel):
    buttons: list = []
    manual: bool = False

class AgentStateResponse(BaseModel):
    visual: dict
    player: dict
    game: dict
    map: dict
    agent: dict
    step_number: int
    status: str

class AgentModules:
    """Container for agent modules using function-based approach"""
    def __init__(self, backend="openai", model_name="gpt-4o"):
        self.vlm = VLM(backend=backend, model_name=model_name)
        self.backend = backend
        self.model_name = model_name
        
        # Agent state
        self.memory_context = []
        self.observation_buffer = []
        self.current_plan = None
        self.recent_actions = []
        self.last_observation = None
        self.last_plan = None
        self.last_action = None
        self.thinking = False
    
    def process_game_state(self, game_state):
        """Process game state through agent modules"""
        try:
            with agent_lock:
                self.thinking = True
                
                # Get screenshot from game state
                frame = game_state["visual"]["screenshot"] if game_state["visual"]["screenshot"] else None
                
                # 1. Perception - analyze current game state
                observation, slow_thinking_needed = perception_step(frame, game_state, self.vlm)
                self.last_observation = observation
                self.observation_buffer.append(observation)
                
                # Keep observation buffer reasonable size
                if len(self.observation_buffer) > 10:
                    self.observation_buffer = self.observation_buffer[-10:]
                
                # 2. Memory - update with new observations
                self.memory_context = memory_step(
                    self.memory_context, 
                    self.current_plan, 
                    self.recent_actions,
                    self.observation_buffer,
                    self.vlm
                )
                
                # 3. Planning - create high-level plan
                plan_result = planning_step(
                    self.memory_context,
                    self.current_plan,
                    slow_thinking_needed,
                    game_state,
                    self.vlm
                )
                self.current_plan = plan_result
                self.last_plan = plan_result
                
                # 4. Action - select specific button input
                action_result = action_step(
                    self.memory_context,
                    self.current_plan,
                    observation,
                    frame,
                    game_state,
                    self.recent_actions,
                    self.vlm
                )
                
                # Store action result
                self.last_action = action_result
                self.recent_actions.append(action_result)
                
                # Keep recent actions reasonable size
                if len(self.recent_actions) > 20:
                    self.recent_actions = self.recent_actions[-20:]
                
                self.thinking = False
                
                return action_result
                
        except Exception as e:
            logger.error(f"Error in agent processing: {e}")
            self.thinking = False
            return {"action": "A", "reasoning": f"Error: {e}"}  # Default safe action
    
    def get_agent_status(self):
        """Get current agent status for API"""
        return {
            "thinking": self.thinking,
            "last_observation": str(self.last_observation)[:200] + "..." if self.last_observation else "",
            "last_plan": str(self.last_plan)[:200] + "..." if self.last_plan else "",
            "last_action": str(self.last_action) if self.last_action else "",
            "reasoning": self.last_action.get("reasoning", "") if isinstance(self.last_action, dict) else "",
            "memory_size": len(self.memory_context),
            "backend": self.backend,
            "model": self.model_name
        }

def signal_handler(signum, _frame):
    """Handle shutdown signals gracefully"""
    global running
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    running = False
    if emulator:
        emulator.stop()
    pygame.quit()
    sys.exit(0)

def setup_emulator(rom_path="Emerald-GBAdvance/rom.gba", load_state=None):
    """Initialize the emulator"""
    global emulator, current_obs
    
    try:
        if not os.path.exists(rom_path):
            raise RuntimeError(f"ROM not found at {rom_path}")
        
        # Suppress debug logging
        logging.getLogger('pokemon_env.memory_reader').setLevel(logging.WARNING)
        
        emulator = EmeraldEmulator(rom_path=rom_path, headless=False, sound=False)
        emulator.initialize()
        
        if load_state and os.path.exists(load_state):
            emulator.load_state(load_state)
            print(f"✅ Loaded state from: {load_state}")
            
            # Verify state loaded correctly
            state = emulator.get_comprehensive_state()
            player_info = state.get("player", {})
            print(f"📍 Player: {player_info.get('name', 'Unknown')} at ({player_info.get('map_x', '?')}, {player_info.get('map_y', '?')})")
            print(f"🗺️  Map: {state.get('map', {}).get('current_location', 'Unknown')}")
        
        screenshot = emulator.get_screenshot()
        if screenshot:
            with obs_lock:
                current_obs = np.array(screenshot)
        else:
            with obs_lock:
                current_obs = np.zeros((emulator.height, emulator.width, 3), dtype=np.uint8)

        print("✅ Emulator initialized successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize emulator: {e}")
        return False

def setup_agent(backend="openai", model_name="gpt-4o"):
    """Initialize agent modules"""
    global agent_modules
    
    try:
        agent_modules = AgentModules(backend=backend, model_name=model_name)
        print(f"Agent initialized with {backend} backend using {model_name}")
        return True
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        return False

def handle_input(manual_mode=True):
    """Handle keyboard input"""
    global running
    actions_pressed = []
    
    if not manual_mode:
        return True, []
    
    keys = pygame.key.get_pressed()
    for key, button in button_map.items():
        if keys[key]:
            actions_pressed.append(button)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False, []
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False, []
            elif event.key == pygame.K_s:
                save_screenshot()
            elif event.key == pygame.K_m:
                display_map()
            elif event.key == pygame.K_SPACE:  # Spacebar to trigger agent action
                return True, ["AGENT_STEP"]
            elif event.key == pygame.K_1:
                if emulator:
                    save_file = "agent_direct_save.state"
                    emulator.save_state(save_file)
                    print(f"State saved to: {save_file}")
            elif event.key == pygame.K_2:
                if emulator:
                    load_file = "agent_direct_save.state"
                    if os.path.exists(load_file):
                        emulator.load_state(load_file)
                        print(f"State loaded from: {load_file}")
    
    return True, actions_pressed

# Global action queue for 60 FPS background loop
current_actions = []
action_lock = threading.Lock()
pending_agent_action = False

def queue_action(actions):
    """Queue actions to be processed by background loop"""
    global current_actions
    with action_lock:
        current_actions = actions.copy() if actions else []

def queue_agent_step():
    """Queue an agent decision step"""
    global pending_agent_action
    with action_lock:
        pending_agent_action = True

def background_emulator_loop():
    """Background 60 FPS emulator loop"""
    global current_obs, last_agent_action, pending_agent_action, running, current_actions
    
    print("🎮 Starting 60 FPS background emulator loop...")
    
    while running:
        if not emulator:
            time.sleep(0.01)
            continue
        
        actions_to_execute = []
        agent_step_needed = False
        
        # Get queued actions
        with action_lock:
            actions_to_execute = current_actions.copy() if current_actions else []
            agent_step_needed = pending_agent_action
            current_actions = []
            pending_agent_action = False
        
        # Handle agent step
        if agent_step_needed:
            if agent_modules:
                print("🤖 Agent thinking...")
                try:
                    # Clear cache to ensure fresh map data for agent
                    if hasattr(emulator, '_cached_state'):
                        delattr(emulator, '_cached_state')
                    if hasattr(emulator, '_cached_state_time'):
                        delattr(emulator, '_cached_state_time')
                    
                    game_state = emulator.get_comprehensive_state()
                    agent_action = agent_modules.process_game_state(game_state)
                    
                    if agent_action and "action" in agent_action:
                        button_action = agent_action["action"]
                        print(f"🎮 Agent chose: {button_action}")
                        last_agent_action = agent_action
                        actions_to_execute = [button_action]
                    else:
                        print("❌ Agent failed to choose action")
                except Exception as e:
                    print(f"❌ Agent error: {e}")
            else:
                print("❌ Agent not initialized")
        
        # Run frame with actions (or no actions)
        emulator.run_frame_with_buttons(actions_to_execute)
        
        # Update screenshot
        screenshot = emulator.get_screenshot()
        if screenshot:
            with obs_lock:
                current_obs = np.array(screenshot)
        
        # Run at 60 FPS (16.67ms per frame)
        time.sleep(1.0 / 60.0)

def step_emulator(actions_pressed):
    """Queue actions for the background emulator loop"""
    if "AGENT_STEP" in actions_pressed:
        queue_agent_step()
    else:
        queue_action(actions_pressed)

def update_display():
    """Update the pygame display"""
    global current_obs, screen, step_count, font
    
    if not screen:
        return
    
    with obs_lock:
        obs_copy = current_obs.copy() if current_obs is not None else None
    
    if obs_copy is not None:
        obs_surface = pygame.surfarray.make_surface(obs_copy.swapaxes(0, 1))
        scaled_surface = pygame.transform.scale(obs_surface, (screen_width, screen_height))
        screen.blit(scaled_surface, (0, 0))
        
        # Draw info overlay
        if font:
            info_lines = [
                f"Step: {step_count}",
                f"Controls: WASD/Arrows=Move, Z=A, X=B, Space=Agent Step",
                f"Special: S=Screenshot, M=Map, 1=Save, 2=Load, Esc=Quit"
            ]
            
            if agent_modules:
                agent_status = agent_modules.get_agent_status()
                if agent_status["thinking"]:
                    info_lines.append("🤖 Agent: THINKING...")
                elif agent_status["last_action"]:
                    info_lines.append(f"🤖 Last: {agent_status['last_action']} - {agent_status['reasoning'][:50]}...")
            
            y_offset = 10
            for line in info_lines:
                text_surface = font.render(line, True, (255, 255, 255))
                # Add background for readability
                text_rect = text_surface.get_rect()
                bg_rect = pygame.Rect(10, y_offset-2, text_rect.width+4, text_rect.height+4)
                pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect)
                screen.blit(text_surface, (10, y_offset))
                y_offset += 25
    
    pygame.display.flip()

def save_screenshot():
    """Save current screenshot"""
    global current_obs
    
    with obs_lock:
        obs_copy = current_obs.copy() if current_obs is not None else None
    
    if obs_copy is not None:
        timestamp = int(time.time())
        filename = f"agent_direct_screenshot_{timestamp}.png"
        img = Image.fromarray(obs_copy)
        img.save(filename)
        print(f"Screenshot saved: {filename}")

def display_map():
    """Display current map in terminal - showing both raw and agent views"""
    global emulator
    
    if not emulator:
        print("❌ Emulator not initialized")
        return
    
    try:
        # Suppress debug logs temporarily
        original_level = logging.getLogger('pokemon_env.memory_reader').level
        logging.getLogger('pokemon_env.memory_reader').setLevel(logging.WARNING)
        
        # Clear any cached state to ensure fresh data
        # if hasattr(emulator, '_cached_state'):
        #     delattr(emulator, '_cached_state')
        # if hasattr(emulator, '_cached_state_time'):
        #     delattr(emulator, '_cached_state_time')
        
        # Get raw map data FIRST (this should be clean)
        raw_map_data = emulator.memory_reader.read_map_around_player(radius=7)
        
        # Get comprehensive state - this is what the agent receives
        state = emulator.get_comprehensive_state()
        
        # Get the formatted state that the agent receives
        agent_view = format_state_for_llm(state)
        
        player_data = state.get("player", {})
        
        # Restore logging level
        logging.getLogger('pokemon_env.memory_reader').setLevel(original_level)
        
        print("\n" + "="*70)
        print("🎮 RAW MAP DATA (Direct from memory)")
        print("="*70)
        
        # Use unified formatter for raw map display
        if raw_map_data:
            facing = player_data.get('facing', 'South')
            npcs = state.get('map', {}).get('object_events', [])
            player_coords = state.get('map', {}).get('player_coords')
            formatted_map = format_map_for_display(raw_map_data, facing, "15x15 Map", npcs, player_coords)
            print(formatted_map)
        else:
            print("No raw map data available")
        
        print("\n" + "="*70)
        print("🤖 AGENT'S FORMATTED VIEW (What LLM sees)")
        print("="*70)
        
        # Show what the agent sees (which might be corrupted)
        if "=== LOCATION & MAP INFO ===" in agent_view:
            map_section_start = agent_view.index("=== LOCATION & MAP INFO ===")
            map_section = agent_view[map_section_start:]
            
            # Find the end of the map section (next === or end of string)
            next_section = map_section.find("\n===", 10)
            if next_section > 0:
                map_section = map_section[:next_section]
            
            # Print the exact map view the agent sees
            print(map_section)
        else:
            print("No map data in agent view")
        
        
        # Also show debug info
        print("\n" + "-"*70)
        print("📊 DEBUG: Additional State Info")
        print("-"*70)
        print(f"Player Name: {player_data.get('name', 'Unknown')}")
        print(f"Position: {player_data.get('position', 'Unknown')}")
        print(f"Facing: {player_data.get('facing', 'Unknown')}")
        print(f"Location: {player_data.get('location', 'Unknown')}")
        
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"❌ Error displaying map: {e}")

def init_pygame():
    """Initialize pygame"""
    global screen, font, clock
    
    pygame.init()
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Direct Agent Pokemon Emerald")
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

def game_loop(manual_mode=True, agent_auto=False):
    """Main game loop - handles input and display while background loop runs emulator at 60 FPS"""
    global running, step_count
    
    print("Starting Direct Agent game loop...")
    print("Controls: WASD/Arrows=Move, Z=A, X=B, Space=Agent Step")
    print("Special: S=Screenshot, M=Show Map, 1=Save State, 2=Load State, Esc=Quit")
    
    if agent_auto:
        print("Agent auto mode: Agent will act automatically every few seconds")
    
    # Start background 60 FPS emulator loop
    emulator_thread = threading.Thread(target=background_emulator_loop, daemon=True)
    emulator_thread.start()
    
    last_agent_time = time.time()
    agent_interval = 3.0  # Agent acts every 3 seconds in auto mode
    display_fps = 30  # Display updates at 30 FPS (emulator runs at 60 FPS in background)
    
    while running:
        # Handle input
        should_continue, actions_pressed = handle_input(manual_mode)
        if not should_continue:
            break
        
        # Auto agent mode
        if agent_auto and agent_modules and time.time() - last_agent_time > agent_interval:
            if not agent_modules.thinking:  # Don't interrupt if agent is thinking
                actions_pressed.append("AGENT_STEP")
                last_agent_time = time.time()
        
        # Queue actions for background emulator loop
        if actions_pressed:
            step_emulator(actions_pressed)
        
        # Update display (independent of emulator speed)
        update_display()
        
        # Update step count (this is now just for display purposes)
        with step_lock:
            step_count += 1
        
        # Display loop runs at 30 FPS while emulator runs at 60 FPS in background
        clock.tick(display_fps)

def run_fastapi_server(port):
    """Run FastAPI server in background thread"""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

# FastAPI endpoints
@app.get("/status")
async def get_status():
    """Get server status"""
    with step_lock:
        current_step = step_count
    
    agent_status = agent_modules.get_agent_status() if agent_modules else {"thinking": False}
    
    return {
        "status": "running",
        "step_count": current_step,
        "fps": fps,
        "agent_initialized": agent_modules is not None,
        "agent_thinking": agent_status["thinking"]
    }

@app.get("/state")
async def get_comprehensive_state():
    """Get comprehensive game state"""
    if emulator is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        # Get game state
        state = emulator.get_comprehensive_state()
        
        # Add agent information
        agent_status = agent_modules.get_agent_status() if agent_modules else {
            "thinking": False,
            "last_observation": "",
            "last_plan": "",
            "last_action": "",
            "reasoning": "",
            "memory_size": 0
        }
        
        state["agent"] = agent_status
        
        # Convert screenshot to base64
        if state["visual"]["screenshot"]:
            buffer = io.BytesIO()
            state["visual"]["screenshot"].save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            state["visual"]["screenshot_base64"] = img_str
            del state["visual"]["screenshot"]
        
        with step_lock:
            current_step = step_count
        
        return AgentStateResponse(
            visual=state["visual"],
            player=state["player"],
            game=state["game"],
            map=state["map"],
            agent=state["agent"],
            step_number=current_step,
            status="running"
        )
        
    except Exception as e:
        logger.error(f"Error getting comprehensive state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/action")
async def take_action(request: AgentActionRequest):
    """Take an action (manual or agent)"""
    if emulator is None:
        raise HTTPException(status_code=400, detail="Emulator not initialized")
    
    try:
        if request.manual:
            # Manual action
            step_emulator(request.buttons)
        else:
            # Agent action
            if agent_modules:
                step_emulator(["AGENT_STEP"])
            else:
                raise HTTPException(status_code=400, detail="Agent not initialized")
        
        with step_lock:
            step_count += 1
        
        # Return updated state
        state = await get_comprehensive_state()
        return state
        
    except Exception as e:
        logger.error(f"Error taking action: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent")
async def get_agent_status():
    """Get agent status"""
    if agent_modules is None:
        return {"status": "not_initialized", "message": "Agent not initialized"}
    
    return {
        "status": "initialized",
        **agent_modules.get_agent_status()
    }

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Direct Agent Pokemon Emerald")
    parser.add_argument("--rom", type=str, default="Emerald-GBAdvance/rom.gba", help="Path to ROM file")
    parser.add_argument("--load-state", type=str, help="Load a saved state file on startup")
    parser.add_argument("--backend", type=str, default="openai", help="VLM backend (openai, gemini, local)")
    parser.add_argument("--model-name", type=str, default="gpt-4o", help="Model name to use")
    parser.add_argument("--port", type=int, default=8000, help="Port for web interface")
    parser.add_argument("--no-display", action="store_true", help="Run without pygame display")
    parser.add_argument("--agent-auto", action="store_true", help="Agent acts automatically")
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 Starting Direct Agent Pokemon Emerald")
    print(f"ROM: {args.rom}")
    print(f"Backend: {args.backend} ({args.model_name})")
    print(f"Web interface: http://127.0.0.1:{args.port}")
    
    # Initialize pygame (unless disabled)
    if not args.no_display:
        init_pygame()
    
    # Initialize emulator
    if not setup_emulator(args.rom, args.load_state):
        print("Failed to initialize emulator")
        return 1
    
    # Initialize agent
    if not setup_agent(args.backend, args.model_name):
        print("Failed to initialize agent")
        return 1
    
    # Start web server in background thread
    server_thread = threading.Thread(
        target=run_fastapi_server, 
        args=(args.port,), 
        daemon=True
    )
    server_thread.start()
    
    try:
        # Run main game loop
        game_loop(
            manual_mode=not args.no_display, 
            agent_auto=args.agent_auto
        )
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        global running
        running = False
        if emulator:
            emulator.stop()
        if not args.no_display:
            pygame.quit()
        print("Direct Agent stopped")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())