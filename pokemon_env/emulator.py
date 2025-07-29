import logging
import time
import threading
import queue
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from PIL import Image

import mgba.core
import mgba.log
import mgba.image
from mgba._pylib import ffi, lib

from .memory_reader import PokemonEmeraldReader

logger = logging.getLogger(__name__)


class EmeraldEmulator:
    """emulator wrapper for Pokémon Emerald with headless frame capture and scripted inputs."""

    def __init__(self, rom_path: str, headless: bool = True, sound: bool = False):
        self.rom_path = rom_path
        self.headless = headless
        self.sound = sound

        self.gba = None
        self.core = None
        self.width = 240
        self.height = 160
        self.running = False

        self.frame_queue = queue.Queue(maxsize=10)
        self.current_frame = None
        self.frame_thread = None
        
        # Memory reader for accessing game state
        self.memory_reader = None

        # Memory cache for efficient reading
        self._mem_cache = {}

        # Define key mapping for mgba
        self.KEY_MAP = {
            "a": lib.GBA_KEY_A,
            "b": lib.GBA_KEY_B,
            "start": lib.GBA_KEY_START,
            "select": lib.GBA_KEY_SELECT,
            "up": lib.GBA_KEY_UP,
            "down": lib.GBA_KEY_DOWN,
            "left": lib.GBA_KEY_LEFT,
            "right": lib.GBA_KEY_RIGHT,
            "l": lib.GBA_KEY_L,
            "r": lib.GBA_KEY_R
        }

    def initialize(self):
        """Load ROM and set up emulator"""
        try:
            # Prevents relentless spamming to stdout by libmgba.
            mgba.log.silence()
            
            # Create a temporary directory and copy the gba file into it
            # this is necessary to prevent mgba from overwriting the save file (and to prevent crashes)
            tmp_dir = Path(tempfile.mkdtemp())
            tmp_gba = tmp_dir / "rom.gba"
            tmp_gba.write_bytes(Path(self.rom_path).read_bytes())
            
            # Load the core
            self.core = mgba.core.load_path(str(tmp_gba))
            if self.core is None:
                raise ValueError(f"Failed to load GBA file: {self.rom_path}")
            
            # Auto-load save if it exists
            self.core.autoload_save()
            self.core.reset()
            
            # Get dimensions from the core
            self.width, self.height = self.core.desired_video_dimensions()
            
            # Set up video buffer for frame capture using mgba.image.Image
            self.video_buffer = mgba.image.Image(self.width, self.height)
            self.core.set_video_buffer(self.video_buffer)
            self.core.reset()  # Reset after setting video buffer
            
            # Initialize memory reader
            self.memory_reader = PokemonEmeraldReader(self.core.memory)
            
            # Set up frame callback to invalidate memory cache
            self.core.add_frame_callback(self._invalidate_mem_cache)
            
            logger.info(f"mgba initialized with ROM: {self.rom_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize mgba: {e}")

    def _invalidate_mem_cache(self):
        """Invalidate memory cache when frame changes"""
        self._mem_cache = {}

    def _get_memory_region(self, region_id: int):
        """Get memory region for efficient reading"""
        if region_id not in self._mem_cache:
            mem_core = self.core.memory.u8._core
            size = ffi.new("size_t *")
            ptr = ffi.cast("uint8_t *", mem_core.getMemoryBlock(mem_core, region_id, size))
            self._mem_cache[region_id] = ffi.buffer(ptr, size[0])[:]
        return self._mem_cache[region_id]

    def read_memory(self, address: int, size: int = 1):
        """Read memory at given address"""
        region_id = address >> lib.BASE_OFFSET
        mem_region = self._get_memory_region(region_id)
        mask = len(mem_region) - 1
        address &= mask
        return mem_region[address:address + size]

    def read_u8(self, address: int):
        """Read unsigned 8-bit value"""
        return int.from_bytes(self.read_memory(address, 1), byteorder='little', signed=False)

    def read_u16(self, address: int):
        """Read unsigned 16-bit value"""
        return int.from_bytes(self.read_memory(address, 2), byteorder='little', signed=False)

    def read_u32(self, address: int):
        """Read unsigned 32-bit value"""
        return int.from_bytes(self.read_memory(address, 4), byteorder='little', signed=False)

    def tick(self, frames: int = 1):
        """Advance emulator by given number of frames"""
        if self.core:
            for _ in range(frames):
                self.core.run_frame()

    def press_key(self, key: str, frames: int = 2):
        """Press a key for specified number of frames"""
        if key not in self.KEY_MAP:
            raise ValueError(f"Invalid key: {key}")
        if frames < 2:
            raise ValueError("Cannot press a key for less than 2 frames.")
        
        key_code = self.KEY_MAP[key]
        self.core.add_keys(key_code)
        self.tick(frames - 1)
        self.core.clear_keys(key_code)
        self.tick(1)

    def press_buttons(self, buttons: List[str], hold_frames: int = 10, release_frames: int = 10):
        """Press a sequence of buttons"""
        if not self.core:
            return "Emulator not initialized"

        for button in buttons:
            if button.lower() not in self.KEY_MAP:
                logger.warning(f"Unknown button: {button}")
                continue
            
            self.press_key(button.lower(), hold_frames)

        self.tick(release_frames)
        return f"Pressed: {'+'.join(buttons)}"

    def run_frame_with_buttons(self, buttons: List[str]):
        """Set buttons and advance one frame."""
        if not self.core:
            return

        # Set all buttons for one frame
        for button in buttons:
            if button.lower() in self.KEY_MAP:
                key_code = self.KEY_MAP[button.lower()]
                self.core.add_keys(key_code)
        
        self.core.run_frame()
        
        # Clear all buttons
        for button in buttons:
            if button.lower() in self.KEY_MAP:
                key_code = self.KEY_MAP[button.lower()]
                self.core.clear_keys(key_code)

    def get_screenshot(self) -> Optional[Image.Image]:
        """Return the current frame as a PIL image"""
        if not self.core or not self.video_buffer:
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
        if not self.core:
            return None
        
        try:
            # Get the raw state data
            raw_data = self.core.save_raw_state()
            
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
        if not self.core:
            return
        
        try:
            if path:
                with open(path, 'rb') as f:
                    state_bytes = f.read()
            if state_bytes:
                # Ensure state_bytes is actually bytes
                if not isinstance(state_bytes, bytes):
                    state_bytes = bytes(state_bytes)
                self.core.load_raw_state(state_bytes)
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
        if self.core:
            self.core = None
        logger.info("Emulator stopped.")

    def get_info(self) -> Dict[str, Any]:
        """Return metadata about emulator state"""
        return {
            "rom_path": self.rom_path,
            "dimensions": (self.width, self.height),
            "initialized": self.core is not None,
            "headless": self.headless,
            "sound": self.sound,
        }

    def get_comprehensive_state(self) -> Dict[str, Any]:
        """Get comprehensive game state including visual and memory data using enhanced memory reader"""
        # Use the enhanced memory reader's comprehensive state method
        if self.memory_reader:
            state = self.memory_reader.get_comprehensive_state()
        else:
            # Fallback to basic state
            state = {
                "visual": {
                    "screenshot": None,
                    "resolution": [self.width, self.height]
                },
                "player": {
                    "position": None,
                    "location": None,
                    "name": None
                },
                "game": {
                    "money": None,
                    "party": None,
                    "game_state": None,
                    "is_in_battle": None,
                    "time": None,
                    "badges": None,
                    "items": None,
                    "item_count": None,
                    "pokedex_caught": None,
                    "pokedex_seen": None
                },
                "map": {
                    "tiles": None,
                    "tile_names": None,
                    "metatile_behaviors": None,
                    "metatile_info": None,
                    "traversability": None
                }
            }
        
        # Get visual observation
        screenshot = self.get_screenshot()
        if screenshot:
            state["visual"]["screenshot"] = screenshot
        
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
