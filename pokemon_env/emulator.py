import logging
import time
import threading
import queue
from typing import Dict, Any, Optional, List
import numpy as np
from PIL import Image

import mgba.log

from .memory_reader import PokemonEmeraldReader

logger = logging.getLogger(__name__)


class EmeraldEmulator:
    """pygba emulator wrapper for Pokémon Emerald with headless frame capture and scripted inputs."""

    def __init__(self, rom_path: str, headless: bool = True, sound: bool = False):
        self.rom_path = rom_path
        self.headless = headless
        self.sound = sound

        self.gba = None
        self.width = 240
        self.height = 160
        self.running = False

        self.frame_queue = queue.Queue(maxsize=10)
        self.current_frame = None
        self.frame_thread = None
        
        # Memory reader for accessing game state
        self.memory_reader = None

        # Define key mapping for pygba
        self.BUTTON_MAP = {
            "a": "A",
            "b": "B", 
            "start": "Start",
            "select": "Select",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "l": "L",
            "r": "R"
        }

        self.PYGBA_BUTTON_ORDER = ["A", "B", "Select", "Start", "Right", "Left", "Up", "Down", "R", "L"]
        self._LOWER_TO_PYGBA_BUTTONS = {
            "a": "A", "b": "B", "select": "Select", "start": "Start",
            "right": "Right", "left": "Left", "up": "Up", "down": "Down",
            "r": "R", "l": "L"
        }

    def initialize(self):
        """Load ROM and set up emulator"""
        try:
            import pygba
            import mgba.image
            # Prevents relentless spamming to stdout by libmgba.
            mgba.log.silence()
            self.gba = pygba.PyGBA.load(self.rom_path)
            
            # Get dimensions from the core
            self.width, self.height = self.gba.core.desired_video_dimensions()
            
            # Set up video buffer for frame capture using mgba.image.Image
            self.video_buffer = mgba.image.Image(self.width, self.height)
            self.gba.core.set_video_buffer(self.video_buffer)
            self.gba.core.reset()  # Reset after setting video buffer
            
            # Initialize memory reader
            self.memory_reader = PokemonEmeraldReader(self.gba.core.memory)
            
            logger.info(f"pygba initialized with ROM: {self.rom_path}")
            # self.tick(60)  # Advance 60 frames after initializing
        except ImportError:
            raise ImportError("pygba not installed. Try: pip install pygba")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize pygba: {e}")

    def tick(self, frames: int = 1):
        """Advance emulator by given number of frames"""
        if self.gba:
            for _ in range(frames):
                self.gba.core.run_frame()

    def press_buttons(self, buttons: List[str], hold_frames: int = 10, release_frames: int = 10):
        """Press a sequence of buttons"""
        if not self.gba:
            return "Emulator not initialized"

        for button in buttons:
            mapped = self.BUTTON_MAP.get(button.lower())
            if mapped is None:
                logger.warning(f"Unknown button: {button}")
                continue
            
            # Use pygba's button press methods
            if mapped == "A":
                self.gba.press_a(hold_frames)
            elif mapped == "B":
                self.gba.press_b(hold_frames)
            elif mapped == "Start":
                self.gba.press_start(hold_frames)
            elif mapped == "Select":
                self.gba.press_select(hold_frames)
            elif mapped == "Up":
                self.gba.press_up(hold_frames)
            elif mapped == "Down":
                self.gba.press_down(hold_frames)
            elif mapped == "Left":
                self.gba.press_left(hold_frames)
            elif mapped == "Right":
                self.gba.press_right(hold_frames)
            elif mapped == "L":
                self.gba.press_l(hold_frames)
            elif mapped == "R":
                self.gba.press_r(hold_frames)

        self.tick(release_frames)
        return f"Pressed: {'+'.join(buttons)}"

    def run_frame_with_buttons(self, buttons: List[str]):
        """Set buttons and advance one frame."""
        if not self.gba:
            return

        # Try to use core.set_buttons if available
        core = getattr(self.gba, 'core', None)
        set_buttons = getattr(core, 'set_buttons', None)
        if callable(set_buttons):
            # Build a bitmask or list as required by set_buttons
            # Assume set_buttons expects a list of bools in PYGBA_BUTTON_ORDER
            action = [False] * len(self.PYGBA_BUTTON_ORDER)
            for button in buttons:
                pygba_button = self._LOWER_TO_PYGBA_BUTTONS.get(button.lower())
                if pygba_button:
                    try:
                        idx = self.PYGBA_BUTTON_ORDER.index(pygba_button)
                        action[idx] = True
                    except ValueError:
                        logger.warning(f"Button {pygba_button} not in PYGBA_BUTTON_ORDER")
            set_buttons(action)
            core.run_frame()
            return

        # Fallback: Use individual press methods for one frame
        for button in buttons:
            mapped = self.BUTTON_MAP.get(button.lower())
            if mapped is None:
                logger.warning(f"Unknown button: {button}")
                continue
            method_name = f"press_{mapped.lower()}"
            press_method = getattr(self.gba, method_name, None)
            if callable(press_method):
                press_method(2)  # Hold for 2 frames (minimum allowed)
        self.tick(1)

    def get_screenshot(self) -> Optional[Image.Image]:
        """Return the current frame as a PIL image"""
        if not self.gba or not self.video_buffer:
            return None
        
        try:
            # Use the built-in to_pil() method from mgba.image.Image
            if hasattr(self.video_buffer, 'to_pil'):
                screenshot = self.video_buffer.to_pil()
                if screenshot:
                    screenshot = screenshot.convert("RGB")
                    return screenshot
                else:
                    logger.warning("mgba.image.Image does not have to_pil method")
                    return None
            else:
                logger.warning("mgba.image.Image does not have to_pil method")
                return None
        except Exception as e:
            logger.error(f"Failed to get screenshot: {e}")
            return None

    def save_state(self, path: Optional[str] = None) -> Optional[bytes]:
        """Save current emulator state to file or return as bytes"""
        if not self.gba:
            return None
        
        try:
            # Get the raw state data
            raw_data = self.gba.core.save_raw_state()
            
            # Convert CFFI object to bytes if needed
            if hasattr(raw_data, 'buffer'):
                data = bytes(raw_data.buffer)
            elif hasattr(raw_data, '__len__'):
                data = bytes(raw_data)
            else:
                data = raw_data
            
            if path:
                with open(path, 'wb') as f:
                    f.write(data)
                logger.info(f"State saved to {path}")
            return data
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return None

    def load_state(self, path: Optional[str] = None, state_bytes: Optional[bytes] = None):
        """Load emulator state from file or memory"""
        if not self.gba:
            return
        
        try:
            if path:
                with open(path, 'rb') as f:
                    state_bytes = f.read()
            if state_bytes:
                # Ensure state_bytes is actually bytes
                if not isinstance(state_bytes, bytes):
                    state_bytes = bytes(state_bytes)
                self.gba.core.load_raw_state(state_bytes)
                logger.info("State loaded.")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def start_frame_capture(self, fps: int = 30):
        """Start asynchronous frame capture"""
        self.running = True
        self.frame_thread = threading.Thread(target=self._frame_loop, args=(fps,), daemon=True)
        self.frame_thread.start()

    def _frame_loop(self, fps: int):
        interval = 1.0 / fps
        while self.running:
            start = time.time()
            frame = self.get_screenshot()
            if frame:
                np_frame = np.array(frame)
                if self.frame_queue.full():
                    self.frame_queue.get_nowait()
                self.frame_queue.put(np_frame)
                self.current_frame = np_frame
            elapsed = time.time() - start
            time.sleep(max(0.001, interval - elapsed))

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return last captured frame"""
        return self.current_frame.copy() if self.current_frame is not None else None

    def process_input(self, input_data: Dict[str, Any]) -> str:
        """Handle JSON-style input payload"""
        try:
            input_type = input_data.get('type', 'button')
            if input_type == 'button':
                button = input_data.get('button')
                if button:
                    return self.press_buttons([button])
            elif input_type == 'sequence':
                buttons = input_data.get('buttons', [])
                return self.press_buttons(buttons)
            elif input_type == 'hold':
                button = input_data.get('button')
                duration = int(input_data.get('duration', 1.0) * 60)
                return self.press_buttons([button], hold_frames=duration)
            return "Invalid input type"
        except Exception as e:
            logger.error(f"Input error: {e}")
            return str(e)

    def stop(self):
        """Stop emulator and cleanup"""
        self.running = False
        if self.frame_thread and self.frame_thread.is_alive():
            self.frame_thread.join(timeout=1)
        if self.gba:
            self.gba = None
        logger.info("Emulator stopped.")

    def get_info(self) -> Dict[str, Any]:
        """Return metadata about emulator state"""
        return {
            "rom_path": self.rom_path,
            "dimensions": (self.width, self.height),
            "initialized": self.gba is not None,
            "headless": self.headless,
            "sound": self.sound,
        }

    def get_comprehensive_state(self) -> Dict[str, Any]:
        """Get comprehensive game state including visual and memory data"""
        state = {
            "visual": {
                "screenshot": None,
                "resolution": [self.width, self.height]
            },
            "player": {
                "position": None,
                "location": None
            },
            "game": {
                "money": None,
                "party": None
            },
            "map": {
                "tiles": None,
                "tile_names": None,
                "metatile_behaviors": None,
                "metatile_info": None
            }
        }
        
        # Get visual observation
        screenshot = self.get_screenshot()
        if screenshot:
            state["visual"]["screenshot"] = screenshot
        
        # Get memory data if available
        if self.memory_reader:
            try:
                # Player position
                coords = self.memory_reader.read_coordinates()
                if coords:
                    state["player"]["position"] = {"x": coords[0], "y": coords[1]}
                
                # Map location
                location = self.memory_reader.read_location()
                if location:
                    state["player"]["location"] = location
                
                # Enhanced player information
                player_name = self.memory_reader.read_player_name()
                game_state = self.memory_reader.get_game_state()
                is_in_battle = self.memory_reader.is_in_battle()

                state["game"] = {
                    "player_name": player_name,
                    "game_state": game_state,
                    "is_in_battle": is_in_battle,
                    "money": self.memory_reader.read_money(),
                    "party": None # Party will be added below
                }
                
                # Add battle details if in battle
                if is_in_battle:
                    battle_details = self.memory_reader.read_battle_details()
                    if battle_details:
                        state["game"]["battle"] = battle_details
                
                # Party Pokemon
                party = self.memory_reader.read_party_pokemon()
                if party:
                    state["game"]["party"] = [
                        {
                            "species": pokemon.species_name,
                            "level": pokemon.level,
                            "current_hp": pokemon.current_hp,
                            "max_hp": pokemon.max_hp,
                            "status": pokemon.status.get_status_name() if pokemon.status else "OK",
                            "types": [t.name for t in [pokemon.type1, pokemon.type2] if t],
                            "moves": pokemon.moves,
                            "move_pp": pokemon.move_pp,
                            "nickname": pokemon.nickname
                        }
                        for pokemon in party
                    ]
                
                # Map tiles around player
                tiles = self.memory_reader.read_map_around_player(radius=7)
                if tiles:
                    state["map"]["tiles"] = tiles
                    
                    # Convert tiles to readable names (existing format)
                    tile_names = []
                    metatile_behaviors = []
                    metatile_info = []
                    
                    for row in tiles:
                        row_names = []
                        row_behaviors = []
                        row_info = []
                        
                        for tile_data in row:
                            # Debug for tile ID 1
                            if len(tile_data) > 0 and tile_data[0] == 1:
                                print(f"🐛 EMULATOR DEBUG: Tile ID 1 - tile_data length: {len(tile_data)}, content: {tile_data}")
                            
                            # tile_data is now (metatile_id, behavior, collision, elevation)
                            if len(tile_data) >= 4:
                                tile_id, behavior, collision, elevation = tile_data
                                if tile_id == 1:
                                    print(f"🐛 EMULATOR DEBUG: Tile ID 1 - took 4-element path")
                            elif len(tile_data) >= 2:
                                # Backward compatibility
                                tile_id, behavior = tile_data[:2]
                                collision = 0
                                elevation = 0
                                if tile_id == 1:
                                    print(f"🐛 EMULATOR DEBUG: Tile ID 1 - took 2-element path (backward compatibility)")
                            else:
                                # Handle unexpected format
                                tile_id = tile_data[0] if tile_data else 0
                                behavior = None
                                collision = 0
                                elevation = 0
                                if tile_id == 1:
                                    print(f"🐛 EMULATOR DEBUG: Tile ID 1 - took fallback path")
                            
                            # Existing tile name format
                            tile_name = f"Tile_{tile_id:04X}"
                            if behavior is not None and hasattr(behavior, 'name'):
                                tile_name += f"({behavior.name})"
                            row_names.append(tile_name)
                            
                            # Clean behavior name for the behaviors map
                            if tile_id == 1:  # Debug for center tile
                                print(f"🐛 EMULATOR DEBUG: Tile ID 1 - behavior type: {type(behavior)}, behavior value: {behavior}")
                                if hasattr(behavior, 'name'):
                                    print(f"🐛 EMULATOR DEBUG: Tile ID 1 - behavior.name: {behavior.name}")
                                else:
                                    print(f"🐛 EMULATOR DEBUG: Tile ID 1 - behavior has no 'name' attribute")
                            
                            # Fix: behavior can be MetatileBehavior.NORMAL (value=0) which is falsy but valid
                            behavior_name = behavior.name if behavior is not None and hasattr(behavior, 'name') else "UNKNOWN"
                            row_behaviors.append(behavior_name)
                            
                            # Detailed tile info using new collision-based logic
                            tile_info = {
                                "id": tile_id,
                                "behavior": behavior_name,
                                "collision": collision,
                                "elevation": elevation,
                                "passable": self._get_tile_passability(tile_data),
                                "encounter_possible": self._get_tile_encounter_possible(tile_data),
                                "surfable": self._get_tile_surfable(tile_data)
                            }
                            row_info.append(tile_info)
                        
                        tile_names.append(row_names)
                        metatile_behaviors.append(row_behaviors)
                        metatile_info.append(row_info)
                    
                    state["map"]["tile_names"] = tile_names
                    state["map"]["metatile_behaviors"] = metatile_behaviors
                    state["map"]["metatile_info"] = metatile_info
                    
                    # Create enhanced traversability map for agent navigation
                    traversability_map = []
                    for row_info in metatile_info:
                        traversability_row = []
                        for tile_info in row_info:
                            behavior = tile_info["behavior"]
                            passable = tile_info["passable"]
                            
                            # Enhanced traversability: show actual behaviors for special tiles
                            if behavior == "NORMAL":
                                # Only NORMAL tiles show as . or 0 based on passability
                                traversability_row.append("." if passable else "0")
                            else:
                                # All non-NORMAL tiles show their behavior name regardless of passability
                                # Abbreviate long names for readability
                                short_name = behavior.replace("_", "")[:4]  # First 4 chars, no underscores
                                traversability_row.append(short_name)
                        traversability_map.append(traversability_row)
                    
                    state["map"]["traversability"] = traversability_map
                    
            except Exception as e:
                logger.warning(f"Failed to read memory data: {e}")
        
        return state

    def _get_tile_passability(self, tile_data) -> bool:
        """Determine if a tile is passable based on collision bits (like GeminiPlaysPokemonLive)"""
        if not tile_data or len(tile_data) < 3:
            return True  # Default to passable if no data
        
        # tile_data is (metatile_id, behavior, collision, elevation)
        collision = tile_data[2] if len(tile_data) > 2 else 0
        
        # Primary rule: collision == 0 means passable, non-zero means blocked
        return collision == 0

    def _get_tile_encounter_possible(self, tile_data) -> bool:
        """Determine if a tile can trigger encounters based on its behavior"""
        if not tile_data or len(tile_data) < 2:
            return False
        
        # Import here to avoid circular imports
        from .enums import MetatileBehavior
        
        behavior = tile_data[1] if len(tile_data) > 1 else None
        if not behavior:
            return False
        
        # Check for encounter tiles
        encounter_behaviors = {
            MetatileBehavior.TALL_GRASS,
            MetatileBehavior.LONG_GRASS,
            MetatileBehavior.UNUSED_05,
            MetatileBehavior.DEEP_SAND,
            MetatileBehavior.CAVE,
            MetatileBehavior.INDOOR_ENCOUNTER,
            MetatileBehavior.POND_WATER,
            MetatileBehavior.INTERIOR_DEEP_WATER,
            MetatileBehavior.DEEP_WATER,
            MetatileBehavior.OCEAN_WATER,
            MetatileBehavior.SEAWEED,
            MetatileBehavior.ASHGRASS,
            MetatileBehavior.FOOTPRINTS,
            MetatileBehavior.SEAWEED_NO_SURFACING
        }
        
        return behavior in encounter_behaviors

    def _get_tile_surfable(self, tile_data) -> bool:
        """Determine if a tile can be surfed on based on its behavior"""
        if not tile_data or len(tile_data) < 2:
            return False
        
        # Import here to avoid circular imports
        from .enums import MetatileBehavior
        
        behavior = tile_data[1] if len(tile_data) > 1 else None
        if not behavior:
            return False
        
        # Check for surfable tiles
        surfable_behaviors = {
            MetatileBehavior.POND_WATER,
            MetatileBehavior.INTERIOR_DEEP_WATER,
            MetatileBehavior.DEEP_WATER,
            MetatileBehavior.SOOTOPOLIS_DEEP_WATER,
            MetatileBehavior.OCEAN_WATER,
            MetatileBehavior.NO_SURFACING,
            MetatileBehavior.SEAWEED,
            MetatileBehavior.SEAWEED_NO_SURFACING
        }
        
        return behavior in surfable_behaviors

    def get_player_position(self) -> Optional[Dict[str, int]]:
        """Get current player position"""
        if self.memory_reader:
            try:
                coords = self.memory_reader.read_coordinates()
                if coords:
                    return {"x": coords[0], "y": coords[1]}
            except Exception as e:
                logger.warning(f"Failed to read player position: {e}")
        return None

    def get_map_location(self) -> Optional[str]:
        """Get current map location name"""
        if self.memory_reader:
            try:
                return self.memory_reader.read_location()
            except Exception as e:
                logger.warning(f"Failed to read map location: {e}")
        return None

    def get_money(self) -> Optional[int]:
        """Get current money amount"""
        if self.memory_reader:
            try:
                return self.memory_reader.read_money()
            except Exception as e:
                logger.warning(f"Failed to read money: {e}")
        return None

    def get_party_pokemon(self) -> Optional[List[Dict[str, Any]]]:
        """Get current party Pokemon"""
        if self.memory_reader:
            try:
                party = self.memory_reader.read_party_pokemon()
                if party:
                    return [
                        {
                            "species": pokemon.species_name,
                            "level": pokemon.level,
                            "current_hp": pokemon.current_hp,
                            "max_hp": pokemon.max_hp,
                            "status": pokemon.status.get_status_name() if pokemon.status else "OK",
                            "types": [t for t in [pokemon.type1.name if pokemon.type1 else None, 
                                                 pokemon.type2.name if pokemon.type2 else None] if t is not None]
                        }
                        for pokemon in party
                    ]
            except Exception as e:
                logger.warning(f"Failed to read party Pokemon: {e}")
        return None

    def get_map_tiles(self, radius: int = 7) -> Optional[List[List[tuple]]]:
        """Get map tiles around player"""
        if self.memory_reader:
            try:
                return self.memory_reader.read_map_around_player(radius=radius)
            except Exception as e:
                logger.warning(f"Failed to read map tiles: {e}")
        return None

    def test_memory_reading(self) -> Dict[str, Any]:
        """Test memory reading capabilities and return diagnostic information"""
        if not self.memory_reader:
            return {"error": "Memory reader not initialized"}
        
        try:
            # Get memory diagnostics
            diagnostics = self.memory_reader.test_memory_access()
            
            # Test some basic reads
            test_results = {
                "player_name": None,
                "money": None,
                "coordinates": None,
                "party_size": None,
                "location": None
            }
            
            try:
                test_results["player_name"] = self.memory_reader.read_player_name()
            except Exception as e:
                test_results["player_name_error"] = str(e)
            
            try:
                test_results["money"] = self.memory_reader.read_money()
            except Exception as e:
                test_results["money_error"] = str(e)
            
            try:
                test_results["coordinates"] = self.memory_reader.read_coordinates()
            except Exception as e:
                test_results["coordinates_error"] = str(e)
            
            try:
                test_results["party_size"] = self.memory_reader.read_party_size()
            except Exception as e:
                test_results["party_size_error"] = str(e)
            
            try:
                test_results["location"] = self.memory_reader.read_location()
            except Exception as e:
                test_results["location_error"] = str(e)
            
            return {
                "diagnostics": diagnostics,
                "test_results": test_results
            }
        except Exception as e:
            return {"error": f"Failed to run memory tests: {e}"}
