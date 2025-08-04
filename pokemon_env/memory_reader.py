from dataclasses import dataclass
import struct
from typing import Optional, Dict, Any, List, Tuple
import logging

from mgba._pylib import ffi, lib

from pokemon_env.emerald_utils import ADDRESSES, Pokemon_format, parse_pokemon, EmeraldCharmap
from .enums import MetatileBehavior, StatusCondition, Tileset, PokemonType, PokemonSpecies, Move, Badge, MapLocation
from .types import PokemonData

logger = logging.getLogger(__name__)

@dataclass
class MemoryAddresses:
    """Centralized memory address definitions for Pokemon Emerald; many unconfirmed"""
    # Save Block 1 addresses (main save data)
    SAVE_BLOCK1_BASE = 0x02025734
    PLAYER_NAME = 0x02025734  # Start of Save Block 1
    PLAYER_GENDER = 0x0202573B
    PLAYER_TRAINER_ID = 0x0202573C
    PLAYER_SECRET_ID = 0x0202573E
    PLAYER_COINS = 0x02025744
    PLAYER_BADGES = 0x02025748
    
    # Savestate object addresses (for money and coordinates)
    SAVESTATE_OBJECT_POINTER = 0x03005d8c
    SAVESTATE_PLAYER_X_OFFSET = 0x00
    SAVESTATE_PLAYER_Y_OFFSET = 0x02
    SAVESTATE_MONEY_OFFSET = 0x490
    
    # Party Pokemon addresses (from emerald_utils.py)
    PARTY_COUNT = 0x020244E9
    PARTY_BASE = 0x020244EC
    PARTY_POKEMON_SIZE = 100
    
    # Pokemon data structure offsets
    POKEMON_PID = 0x00
    POKEMON_OTID = 0x04
    POKEMON_NICKNAME = 0x08
    POKEMON_OT_NAME = 0x14
    POKEMON_ENCRYPTED_DATA = 0x20
    POKEMON_STATUS = 0x50
    POKEMON_LEVEL = 0x54
    POKEMON_CURRENT_HP = 0x56
    POKEMON_MAX_HP = 0x58
    POKEMON_ATTACK = 0x5A
    POKEMON_DEFENSE = 0x5C
    POKEMON_SPEED = 0x5E
    POKEMON_SP_ATTACK = 0x60
    POKEMON_SP_DEFENSE = 0x62
    
    # Game state addresses
    GAME_STATE = 0x03005074
    MENU_STATE = 0x03005078
    DIALOG_STATE = 0x020370B8
    IN_BATTLE_FLAG = 0x030026F9
    IN_BATTLE_MASK = 0x02
    
    # Map and location addresses
    MAP_BANK = 0x020322E4
    MAP_NUMBER = 0x020322E5
    PLAYER_X = 0x02025734  # Relative to save block
    PLAYER_Y = 0x02025736  # Relative to save block
    
    # Item bag addresses
    BAG_ITEMS = 0x02039888
    BAG_ITEMS_COUNT = 0x0203988C
    
    # Pokedex addresses
    POKEDEX_CAUGHT = 0x0202A4B0
    POKEDEX_SEEN = 0x0202A4B4
    
    # Time addresses
    GAME_TIME = 0x0202A4C0
    
    # Security key for decryption
    SECURITY_KEY_POINTER = 0x03005D90
    SECURITY_KEY_OFFSET = 0x01F4
    
    # Save block pointers (from emerald_utils.py)
    SAVE_BLOCK1_PTR = 0x03005D8C
    SAVE_BLOCK2_PTR = 0x03005D90
    
    # Battle addresses
    BATTLE_TYPE = 0x02023E82
    BATTLE_OUTCOME = 0x02023E84
    BATTLE_FLAGS = 0x02023E8A
    BATTLE_TURN = 0x02023E8C
    
    # Battle detection addresses (for debug endpoint)
    IN_BATTLE_BIT_ADDR = 0x030026F9
    IN_BATTLE_BITMASK = 0x02
    
    # Map layout addresses
    MAP_HEADER = 0x02037318
    MAP_LAYOUT_OFFSET = 0x00
    PRIMARY_TILESET_OFFSET = 0x10
    SECONDARY_TILESET_OFFSET = 0x14
    
    # Text and dialog addresses (from Pokemon Emerald decompilation symbols)
    # https://raw.githubusercontent.com/pret/pokeemerald/symbols/pokeemerald.sym
    G_STRING_VAR1 = 0x02021cc4  # 256 bytes - Main string variable 1
    G_STRING_VAR2 = 0x02021dc4  # 256 bytes - Main string variable 2  
    G_STRING_VAR3 = 0x02021ec4  # 256 bytes - Main string variable 3
    G_STRING_VAR4 = 0x02021fc4  # 1000 bytes - Main string variable 4 (largest)
    G_DISPLAYED_STRING_BATTLE = 0x02022e2c  # 300 bytes - Battle dialog text
    G_BATTLE_TEXT_BUFF1 = 0x02022f58  # 16 bytes - Battle text buffer 1
    G_BATTLE_TEXT_BUFF2 = 0x02022f68  # 16 bytes - Battle text buffer 2
    G_BATTLE_TEXT_BUFF3 = 0x02022f78  # 16 bytes - Battle text buffer 3
    
    # Legacy text buffer addresses (keeping for compatibility)
    TEXT_BUFFER_1 = 0x02021F18
    TEXT_BUFFER_2 = 0x02021F20
    TEXT_BUFFER_3 = 0x02021F28
    TEXT_BUFFER_4 = 0x02021F30
    
    # Flag addresses (from emerald_utils.py)
    SCRIPT_FLAGS_START = 0x50
    TRAINER_FLAGS_START = 0x500
    SYSTEM_FLAGS_START = 0x860
    DAILY_FLAGS_START = 0x920
    
    # Save block addresses for flags
    SAVE_BLOCK1_FLAGS_OFFSET = 0x1270  # Approximate offset for flags in SaveBlock1

@dataclass
class PokemonDataStructure:
    """Pokemon data structure layout for proper decryption"""
    # Unencrypted data (offsets from Pokemon base address)
    PID = 0x00
    OTID = 0x04
    NICKNAME = 0x08
    OT_NAME = 0x14
    MARKINGS = 0x1C
    CHECKSUM = 0x1C
    
    # Encrypted data block (offsets from encrypted data start)
    ENCRYPTED_START = 0x20
    ENCRYPTED_SIZE = 48
    
    # Encrypted data offsets
    SPECIES = 0x00
    HELD_ITEM = 0x02
    EXPERIENCE = 0x04
    PP_BONUSES = 0x08
    FRIENDSHIP = 0x09
    UNKNOWN = 0x0A
    MOVES = 0x0C
    PP = 0x18
    HP_EV = 0x1A
    ATTACK_EV = 0x1B
    DEFENSE_EV = 0x1C
    SPEED_EV = 0x1D
    SP_ATTACK_EV = 0x1E
    SP_DEFENSE_EV = 0x1F
    COOL = 0x20
    BEAUTY = 0x21
    CUTE = 0x22
    SMART = 0x23
    TOUGH = 0x24
    SHEEN = 0x25
    POKERUS = 0x26
    MET_LOCATION = 0x27
    MET_LEVEL = 0x28
    MET_GAME = 0x29
    POKEBALL = 0x2A
    OT_GENDER = 0x2B
    IVS = 0x2C
    ABILITY = 0x30
    RIBBONS = 0x31
    UNKNOWN2 = 0x32

class PokemonEmeraldReader:
    """Systematic memory reader for Pokemon Emerald with proper data structures"""

    def __init__(self, core):
        """Initialize with a mGBA memory view object"""
        self.core = core
        self.memory = core.memory
        self.addresses = MemoryAddresses()
        self.pokemon_struct = PokemonDataStructure()
        
        # Cache for tileset behaviors
        self._cached_behaviors = None
        self._cached_behaviors_map_key = None
        
        # Map buffer cache
        self._map_buffer_addr = None
        self._map_width = None
        self._map_height = None
        
        # Add properties for battle detection (for debug endpoint compatibility)
        self.IN_BATTLE_BIT_ADDR = self.addresses.IN_BATTLE_BIT_ADDR
        self.IN_BATTLE_BITMASK = self.addresses.IN_BATTLE_BITMASK
        
        self.core.add_frame_callback(self._invalidate_mem_cache)
        self._mem_cache = {}
        
        # Dialog detection timeout for residual text
        self._dialog_text_start_time = None
        self._dialog_text_timeout = 0.5  # 0.5 seconds timeout for residual text
        
        # Dialog content tracking for FPS adjustment
        self._last_dialog_content = None
        self._dialog_fps_start_time = None
        self._dialog_fps_duration = 5.0  # Run at 120 FPS for 5 seconds when dialog detected
        
    def _invalidate_mem_cache(self):
        self._mem_cache = {}

    def _read_u8(self, address: int):
        return int.from_bytes(self.read_memory(address, 1), byteorder='little', signed=False)

    def _read_u16(self, address: int):
        return int.from_bytes(self.read_memory(address, 2), byteorder='little', signed=False)

    def _read_u32(self, address: int):
        return int.from_bytes(self.read_memory(address, 4), byteorder='little', signed=False)

    def _read_bytes(self, address: int, length: int) -> bytes:
        """Read a sequence of bytes from memory"""
        try:
            result = bytearray()
            for i in range(length):
                result.append(self._read_u8(address + i))
            return bytes(result)
        except Exception as e:
            logger.warning(f"Failed to read {length} bytes at 0x{address:08X}: {e}")
            return b'\x00' * length

    def _get_security_key(self) -> int:
        """Get the security key for decrypting encrypted data"""
        try:
            base_pointer = self._read_u32(self.addresses.SECURITY_KEY_POINTER)
            if base_pointer == 0:
                logger.warning("Security key base pointer is null")
                return 0
            
            security_key_addr = base_pointer + self.addresses.SECURITY_KEY_OFFSET
            return self._read_u32(security_key_addr)
        except Exception as e:
            logger.warning(f"Failed to read security key: {e}")
            return 0

    def _decrypt_data(self, encrypted_data: bytes, pid: int, otid: int) -> bytes:
        """Decrypt Pokemon data using PID and OTID"""
        if len(encrypted_data) != self.pokemon_struct.ENCRYPTED_SIZE:
            logger.warning(f"Invalid encrypted data size: {len(encrypted_data)}")
            return encrypted_data
        
        # Calculate decryption key
        key = pid ^ otid
        
        # Decrypt data
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_data):
            decrypted_byte = byte ^ ((key >> (8 * (i % 4))) & 0xFF)
            decrypted.append(decrypted_byte)
        
        return bytes(decrypted)

    def _decode_pokemon_text(self, byte_array: bytes) -> str:
        """Decode Pokemon text using proper character mapping"""
        if not byte_array:
            return ""
        
        # Use the proper EmeraldCharmap from emerald_utils.py
        charmap = EmeraldCharmap()
        return charmap.decode(byte_array)

    def read_player_name(self) -> str:
        """Read player name from Save Block 2"""
        try:
            # Get SaveBlock2 pointer
            save_block_2_ptr = self._read_u32(self.addresses.SAVE_BLOCK2_PTR)
            if save_block_2_ptr == 0:
                logger.warning("SaveBlock2 pointer is null")
                return "Player"
            
            # Player name is at the start of SaveBlock2 (7 bytes + 1 padding)
            name_bytes = self._read_bytes(save_block_2_ptr, 8)
            decoded_name = self._decode_pokemon_text(name_bytes)
            
            if decoded_name and len(decoded_name) >= 2:
                logger.info(f"Read player name: '{decoded_name}'")
                return decoded_name
            
            logger.warning("Could not read valid player name")
            return "Player"
            
        except Exception as e:
            logger.warning(f"Failed to read player name: {e}")
            return "Player"

    def read_money(self) -> int:
        """Read player's money with proper decryption"""
        try:
            # Read the base pointer from SAVESTATE_OBJECT_POINTER_ADDR
            base_pointer = self._read_u32(self.addresses.SAVESTATE_OBJECT_POINTER)
            if base_pointer == 0:
                logger.warning("Player object base pointer is null")
                return 0
            
            # Calculate the actual address of the encrypted money value
            encrypted_money_addr = base_pointer + self.addresses.SAVESTATE_MONEY_OFFSET
            
            # Read the 32-bit encrypted money value
            encrypted_money = self._read_u32(encrypted_money_addr)
            
            # Get the security key for decryption
            security_key = self._get_security_key()
            if security_key == 0:
                logger.warning("Could not get security key for money decryption")
                return 0
            
            # Decrypt the money value by XORing with the security key
            decrypted_money = encrypted_money ^ security_key
            
            return decrypted_money & 0xFFFFFFFF
            
        except Exception as e:
            logger.warning(f"Failed to read money: {e}")
            return 0

    def read_party_size(self) -> int:
        """Read number of Pokemon in party"""
        try:
            # Read party count directly from the dedicated address
            party_count = int(self._read_u8(self.addresses.PARTY_COUNT))
            logger.info(f"Read party count: {party_count}")
            return party_count
        except Exception as e:
            logger.warning(f"Failed to read party size: {e}")
            return 0
        
    def _get_memory_region(self, region_id: int):
        if region_id not in self._mem_cache:
            mem_core = self.core.memory.u8._core
            size = ffi.new("size_t *")
            ptr = ffi.cast("uint8_t *", mem_core.getMemoryBlock(mem_core, region_id, size))
            self._mem_cache[region_id] = ffi.buffer(ptr, size[0])[:]
        return self._mem_cache[region_id]
        
    def read_memory(self, address: int, size: int = 1):
        region_id = address >> lib.BASE_OFFSET
        mem_region = self._get_memory_region(region_id)
        mask = len(mem_region) - 1
        address &= mask
        return mem_region[address:address + size]

    def read_party_pokemon(self) -> List[PokemonData]:
        """Read all Pokemon in party with direct memory access"""
        party = []
        try:
            party_size = self.read_party_size()
            logger.info(f"Reading party with size: {party_size}")

            # Read the entire party data from memory
            party_data = self.read_memory(ADDRESSES["gPlayerParty"], party_size * struct.calcsize(Pokemon_format))

            for i in range(party_size):
                logger.info(f"Reading Pokemon at slot {i}")
                try:
                    # Calculate the offset for each Pokemon
                    offset = i * self.addresses.PARTY_POKEMON_SIZE
                    pokemon_data = party_data[offset:offset + self.addresses.PARTY_POKEMON_SIZE]

                    # Parse the Pokemon data
                    pokemon = parse_pokemon(pokemon_data)
                    party.append(pokemon)

                    logger.info(f"Slot {i}: Parsed Pokemon = {pokemon}")
                except Exception as e:
                    logger.warning(f"Failed to read Pokemon at slot {i}: {e}")
        except Exception as e:
            logger.warning(f"Failed to read party: {e}")

        return party

    def _read_pokemon_moves_from_decrypted(self, decrypted_data: bytes) -> Tuple[List[str], List[int]]:
        """Read moves and PP from decrypted Pokemon data"""
        moves = []
        move_pp = []
        
        try:
            # Read moves (4 moves, 2 bytes each)
            for i in range(4):
                move_offset = self.pokemon_struct.MOVES + (i * 2)
                move_id = self._read_u16_from_bytes(decrypted_data, move_offset)
                
                if move_id == 0:
                    moves.append("")
                    move_pp.append(0)
                else:
                    try:
                        move = Move(move_id)
                        move_name = move.name.replace('_', ' ').title()
                        moves.append(move_name)
                    except ValueError:
                        moves.append(f"Move_{move_id}")
                    
                    # Read PP
                    pp_offset = self.pokemon_struct.PP + i
                    pp = decrypted_data[pp_offset] if pp_offset < len(decrypted_data) else 0
                    move_pp.append(pp)
            
        except Exception as e:
            logger.warning(f"Failed to read moves from decrypted data: {e}")
            moves = ["", "", "", ""]
            move_pp = [0, 0, 0, 0]
        
        return moves, move_pp

    def _read_u16_from_bytes(self, data: bytes, offset: int) -> int:
        """Read u16 from bytes at offset"""
        if offset + 1 >= len(data):
            return 0
        return data[offset] | (data[offset + 1] << 8)

    def is_in_battle(self) -> bool:
        """Check if player is in battle"""
        try:
            battle_flag = self._read_u8(self.addresses.IN_BATTLE_FLAG)
            return (battle_flag & self.addresses.IN_BATTLE_MASK) != 0
        except Exception as e:
            logger.warning(f"Failed to read battle state: {e}")
            return False

    def is_in_dialog(self) -> bool:
        """Check if currently in dialog state using timeout-based approach"""
        try:
            import time
            current_time = time.time()
            
            # Special case: if we're in an after_dialog state, force return False
            # This handles cases where the state file has residual dialog content
            if hasattr(self, '_current_state_file') and self._current_state_file:
                if 'after_dialog' in self._current_state_file.lower():
                    logger.debug(f"Forcing dialog=False for after_dialog state: {self._current_state_file}")
                    return False
            
            # First check if we're in battle - if so, don't consider it dialog for FPS purposes
            if self.is_in_battle():
                return False
            
            # Check dialog state flag and overworld_freeze - either can indicate dialog
            dialog_state = self._read_u8(self.addresses.DIALOG_STATE)
            overworld_freeze = self._read_u8(0x02022B4C)
            
            # If both dialog flags are 0, we're definitely not in dialog (regardless of text)
            if dialog_state == 0 and overworld_freeze == 0:
                return False
            
            # Check for active dialog by reading dialog text
            dialog_text = self.read_dialog()
            has_meaningful_text = dialog_text and len(dialog_text.strip()) > 5
            
            if has_meaningful_text:
                # Additional check: make sure this isn't just residual battle text
                # Battle escape messages and other battle-related text shouldn't trigger dialog FPS
                cleaned_text = dialog_text.strip().lower()
                battle_indicators = [
                    "got away safely", "fled", "escape", "battle", "wild", "trainer",
                    "used", "attack", "defend", "missed", "critical", "super effective"
                ]
                
                # If the text contains battle indicators, it's likely residual battle text
                if any(indicator in cleaned_text for indicator in battle_indicators):
                    logger.debug(f"Ignoring residual battle text: {dialog_text[:50]}...")
                    return False
                
                # Check if this is new dialog content (different from last time)
                is_new_dialog = (self._last_dialog_content != dialog_text)
                
                # If we have meaningful text and dialog flags are set, this is active dialog
                if dialog_state > 0 or overworld_freeze > 0:
                    # If this is new dialog, start the FPS timer
                    if is_new_dialog:
                        self._dialog_fps_start_time = current_time
                        self._last_dialog_content = dialog_text
                        logger.debug(f"New dialog detected, starting 5s FPS boost: '{dialog_text[:50]}...'")
                    
                    # Check if we're still within the FPS boost window
                    if (self._dialog_fps_start_time is not None and 
                        current_time - self._dialog_fps_start_time < self._dialog_fps_duration):
                        logger.debug(f"Dialog FPS active ({current_time - self._dialog_fps_start_time:.1f}s remaining): '{dialog_text[:50]}...'")
                        return True
                    else:
                        # FPS boost window expired, but we still have dialog
                        logger.debug(f"Dialog FPS expired, but dialog still present: '{dialog_text[:50]}...'")
                        return False
                else:
                    # No dialog flags set - this is residual text, don't treat as dialog
                    # But cache the content so we don't treat it as "new" next time
                    if self._last_dialog_content is None:
                        self._last_dialog_content = dialog_text
                    logger.debug(f"Residual text detected (no dialog flags): dialog_state={dialog_state}, overworld_freeze={overworld_freeze}, text='{dialog_text[:50]}...'")
                    return False
            else:
                # No meaningful text, but we might have dialog flags set
                # This could be a transition state or residual flags
                if dialog_state > 0 or overworld_freeze > 0:
                    # If we have flags but no text, this might be a transition
                    # Start a shorter timeout for this case
                    if self._dialog_fps_start_time is None:
                        self._dialog_fps_start_time = current_time
                        logger.debug(f"Dialog flags set but no text - starting transition timeout")
                    
                    # Use a shorter timeout for transition states
                    transition_timeout = 1.0  # 1 second for transition states
                    if current_time - self._dialog_fps_start_time < transition_timeout:
                        logger.debug(f"Dialog transition active ({current_time - self._dialog_fps_start_time:.1f}s remaining)")
                        return True
                    else:
                        logger.debug(f"Dialog transition expired - treating as residual flags")
                        return False
                
                # No meaningful text, reset dialog tracking
                self._last_dialog_content = None
                self._dialog_fps_start_time = None
                return False
            
        except Exception as e:
            logger.warning(f"Failed to check dialog state: {e}")
            return False

    def reset_dialog_tracking(self):
        """Reset dialog tracking state (call when loading new state)"""
        self._last_dialog_content = None
        self._dialog_fps_start_time = None
        self._dialog_text_start_time = None
        logger.info("Dialog tracking reset")

    def read_coordinates(self) -> Tuple[int, int]:
        """Read player coordinates"""
        try:
            # Get the base address of the savestate object structure
            base_address = self._read_u32(self.addresses.SAVESTATE_OBJECT_POINTER)
            
            if base_address == 0:
                logger.warning("Could not read savestate object pointer")
                return (0, 0)
            
            # Read coordinates from the savestate object
            x = self._read_u16(base_address + self.addresses.SAVESTATE_PLAYER_X_OFFSET)
            y = self._read_u16(base_address + self.addresses.SAVESTATE_PLAYER_Y_OFFSET)
            return (x, y)
        except Exception as e:
            logger.warning(f"Failed to read coordinates: {e}")
            return (0, 0)

    def read_location(self) -> str:
        """Read current location"""
        try:
            map_bank = self._read_u8(self.addresses.MAP_BANK)
            map_num = self._read_u8(self.addresses.MAP_NUMBER)
            
            try:
                location = MapLocation((map_bank << 8) | map_num)
                return location.name.replace('_', ' ')
            except ValueError:
                return f"Map_{map_bank:02X}_{map_num:02X}"
        except Exception as e:
            logger.warning(f"Failed to read location: {e}")
            return "Unknown"

    def read_badges(self) -> List[str]:
        """Read obtained badges"""
        try:
            badge_byte = self._read_u8(self.addresses.PLAYER_BADGES)
            badge_names = ["Stone", "Knuckle", "Dynamo", "Heat", "Balance", "Feather", "Mind", "Rain"]
            
            obtained_badges = []
            for i, badge_name in enumerate(badge_names):
                if badge_byte & (1 << i):
                    obtained_badges.append(badge_name)
            
            return obtained_badges
        except Exception as e:
            logger.warning(f"Failed to read badges: {e}")
            return []

    def read_game_time(self) -> Tuple[int, int, int]:
        """Read game time"""
        try:
            time_addr = self._read_u32(self.addresses.GAME_TIME)
            if time_addr == 0:
                return (0, 0, 0)
            
            hours = self._read_u8(time_addr)
            minutes = self._read_u8(time_addr + 1)
            seconds = self._read_u8(time_addr + 2)
            
            return (hours, minutes, seconds)
        except Exception as e:
            logger.warning(f"Failed to read game time: {e}")
            return (0, 0, 0)

    def read_items(self) -> List[Tuple[str, int]]:
        """Read items in bag"""
        try:
            items_addr = self._read_u32(self.addresses.BAG_ITEMS)
            count_addr = self._read_u32(self.addresses.BAG_ITEMS_COUNT)
            
            if items_addr == 0 or count_addr == 0:
                return []
            
            item_count = self._read_u16(count_addr)
            items = []
            
            for i in range(min(item_count, 30)):
                item_id = self._read_u16(items_addr + i * 4)
                quantity = self._read_u16(items_addr + i * 4 + 2)
                
                if item_id > 0:
                    item_name = f"Item_{item_id:03d}"
                    items.append((item_name, quantity))
            
            return items
        except Exception as e:
            logger.warning(f"Failed to read items: {e}")
            return []

    def read_item_count(self) -> int:
        """Read number of items in bag"""
        try:
            count_addr = self._read_u32(self.addresses.BAG_ITEMS_COUNT)
            if count_addr == 0:
                return 0
            return self._read_u16(count_addr)
        except Exception as e:
            logger.warning(f"Failed to read item count: {e}")
            return 0

    def read_pokedex_caught_count(self) -> int:
        """Read number of Pokemon caught"""
        try:
            caught_addr = self._read_u32(self.addresses.POKEDEX_CAUGHT)
            if caught_addr == 0:
                return 0
            
            caught_count = 0
            for i in range(32):
                flags = self._read_u8(caught_addr + i)
                caught_count += bin(flags).count('1')
            
            return caught_count
        except Exception as e:
            logger.warning(f"Failed to read Pokedex caught count: {e}")
            return 0

    def read_pokedex_seen_count(self) -> int:
        """Read number of Pokemon seen"""
        try:
            seen_addr = self._read_u32(self.addresses.POKEDEX_SEEN)
            if seen_addr == 0:
                return 0
            
            seen_count = 0
            for i in range(32):
                flags = self._read_u8(seen_addr + i)
                seen_count += bin(flags).count('1')
            
            return seen_count
        except Exception as e:
            logger.warning(f"Failed to read Pokedex seen count: {e}")
            return 0

    def get_game_state(self) -> str:
        """Get current game state"""
        try:
            if self.is_in_battle():
                return "battle"
            
            menu_state = self._read_u32(self.addresses.MENU_STATE)
            if menu_state != 0:
                return "menu"
            
            # Check for dialog using the same timeout logic as is_in_dialog()
            if self.is_in_dialog():
                return "dialog"
            
            return "overworld"
        except Exception as e:
            logger.warning(f"Failed to determine game state: {e}")
            return "unknown"

    def read_battle_details(self) -> Dict[str, Any]:
        """Read battle-specific information"""
        try:
            if not self.is_in_battle():
                return None
            
            battle_type_value = self._read_u8(self.addresses.BATTLE_TYPE)
            battle_type = "unknown"
            
            if battle_type_value == 0:
                battle_type = "wild"
            elif 1 <= battle_type_value <= 4:
                battle_type = "trainer"
            
            return {
                "in_battle": True,
                "battle_type": battle_type,
                "battle_type_raw": battle_type_value,
                "can_escape": battle_type == "wild",
            }
            
        except Exception as e:
            logger.warning(f"Failed to read battle details: {e}")
            return {"in_battle": True, "battle_type": "unknown", "error": str(e)}

    # Map reading methods (keeping existing implementation for now)
    def _find_map_buffer_addresses(self):
        """Find map buffer addresses"""
        for offset in range(0, 0x8000 - 12, 4):
            try:
                width = self._read_u32(0x03000000 + offset)
                height = self._read_u32(0x03000000 + offset + 4)
                
                if 10 <= width <= 200 and 10 <= height <= 200:
                    map_ptr = self._read_u32(0x03000000 + offset + 8)
                    
                    if 0x02000000 <= map_ptr <= 0x02040000:
                        self._map_buffer_addr = map_ptr
                        self._map_width = width
                        self._map_height = height
                        logger.info(f"Found map buffer at 0x{map_ptr:08X} with size {width}x{height}")
                        return True
            except Exception:
                continue
        
        logger.warning("Could not find map buffer addresses")
        return False

    def read_map_around_player(self, radius: int = 7) -> List[List[Tuple[int, MetatileBehavior, int, int]]]:
        """Read map area around player"""
        if not self._map_buffer_addr:
            if not self._find_map_buffer_addresses():
                return []
        
        try:
            player_x, player_y = self.read_coordinates()
            map_x = player_x + 7
            map_y = player_y + 7
            
            x_start = max(0, map_x - radius)
            y_start = max(0, map_y - radius)
            x_end = min(self._map_width, map_x + radius + 1)
            y_end = min(self._map_height, map_y + radius + 1)
            
            width = x_end - x_start
            height = y_end - y_start
            
            return self.read_map_metatiles(x_start, y_start, width, height)
        except Exception as e:
            logger.warning(f"Failed to read map around player: {e}")
            return []

    def read_map_metatiles(self, x_start: int = 0, y_start: int = 0, width: int = None, height: int = None) -> List[List[Tuple[int, MetatileBehavior, int, int]]]:
        """Read map metatiles"""
        if not self._map_buffer_addr:
            return []
        
        if width is None:
            width = self._map_width
        if height is None:
            height = self._map_height
        
        width = min(width, self._map_width - x_start)
        height = min(height, self._map_height - y_start)
        
        try:
            metatiles = []
            for y in range(y_start, y_start + height):
                row = []
                for x in range(x_start, x_start + width):
                    index = x + y * self._map_width
                    metatile_addr = self._map_buffer_addr + (index * 2)
                    metatile_value = self._read_u16(metatile_addr)
                    
                    metatile_id = metatile_value & 0x03FF
                    collision = (metatile_value & 0x0C00) >> 10
                    elevation = (metatile_value & 0xF000) >> 12
                    
                    behavior = self.get_exact_behavior_from_id(metatile_id)
                    row.append((metatile_id, behavior, collision, elevation))
                metatiles.append(row)
            
            return metatiles
        except Exception as e:
            logger.warning(f"Failed to read map metatiles: {e}")
            return []

    # Tileset reading methods (keeping existing implementation)
    def get_map_layout_base_address(self) -> int:
        """Get map layout base address"""
        try:
            return self._read_u32(self.addresses.MAP_HEADER + self.addresses.MAP_LAYOUT_OFFSET)
        except Exception as e:
            logger.warning(f"Failed to read map layout base address: {e}")
            return 0

    def get_tileset_pointers(self, map_layout_base_address: int) -> Tuple[int, int]:
        """Get tileset pointers"""
        if not map_layout_base_address:
            return (0, 0)
        
        try:
            primary = self._read_u32(map_layout_base_address + self.addresses.PRIMARY_TILESET_OFFSET)
            secondary = self._read_u32(map_layout_base_address + self.addresses.SECONDARY_TILESET_OFFSET)
            return (primary, secondary)
        except Exception as e:
            logger.warning(f"Failed to read tileset pointers: {e}")
            return (0, 0)

    def read_metatile_behaviors_from_tileset(self, tileset_base_address: int, num_metatiles: int) -> List[int]:
        """Read metatile behaviors from tileset"""
        if not tileset_base_address or num_metatiles <= 0:
            return []

        try:
            attributes_ptr = self._read_u32(tileset_base_address + 0x10)
            if not attributes_ptr:
                return []

            bytes_to_read = num_metatiles * 2
            attribute_bytes = self._read_bytes(attributes_ptr, bytes_to_read)

            if len(attribute_bytes) != bytes_to_read:
                return []

            behaviors = []
            for i in range(num_metatiles):
                byte_offset = i * 2
                byte1 = attribute_bytes[byte_offset]
                byte2 = attribute_bytes[byte_offset + 1]
                attribute_value = (byte2 << 8) | byte1
                behavior = attribute_value & 0x00FF
                behaviors.append(behavior)

            return behaviors

        except Exception as e:
            logger.warning(f"Failed to read metatile behaviors: {e}")
            return []

    def get_all_metatile_behaviors(self) -> List[int]:
        """Get all metatile behaviors for current map"""
        try:
            map_bank = self._read_u8(self.addresses.MAP_BANK)
            map_number = self._read_u8(self.addresses.MAP_NUMBER)
            cache_key = (map_bank, map_number)
            
            if self._cached_behaviors_map_key == cache_key and self._cached_behaviors is not None:
                return self._cached_behaviors

            map_layout_base = self.get_map_layout_base_address()
            if not map_layout_base:
                return []

            primary_addr, secondary_addr = self.get_tileset_pointers(map_layout_base)
            all_behaviors = []

            if primary_addr:
                primary_behaviors = self.read_metatile_behaviors_from_tileset(primary_addr, 0x200)
                all_behaviors.extend(primary_behaviors)

            if secondary_addr:
                secondary_behaviors = self.read_metatile_behaviors_from_tileset(secondary_addr, 0x200)
                all_behaviors.extend(secondary_behaviors)

            self._cached_behaviors = all_behaviors
            self._cached_behaviors_map_key = cache_key
            
            return all_behaviors

        except Exception as e:
            logger.warning(f"Failed to get all metatile behaviors: {e}")
            return []

    def get_exact_behavior_from_id(self, metatile_id: int) -> MetatileBehavior:
        """Get exact behavior for metatile ID"""
        try:
            all_behaviors = self.get_all_metatile_behaviors()
            
            if not all_behaviors or metatile_id >= len(all_behaviors):
                return MetatileBehavior.NORMAL

            behavior_byte = all_behaviors[metatile_id]
            
            try:
                return MetatileBehavior(behavior_byte)
            except ValueError:
                return MetatileBehavior.NORMAL

        except Exception as e:
            logger.warning(f"Failed to get exact behavior for metatile {metatile_id}: {e}")
            return MetatileBehavior.NORMAL

    def get_comprehensive_state(self) -> Dict[str, Any]:
        """Get comprehensive game state"""
        logger.info("Starting comprehensive state reading")
        state = {
            "visual": {"screenshot": None, "resolution": [240, 160]},
            "player": {"position": None, "location": None, "name": None},
            "game": {
                "money": None, "party": None, "game_state": None, "is_in_battle": None,
                "time": None, "badges": None, "items": None, "item_count": None,
                "pokedex_caught": None, "pokedex_seen": None, "dialog_text": None,
                "progress_context": None
            },
            "map": {
                "tiles": None, "tile_names": None, "metatile_behaviors": None,
                "metatile_info": None, "traversability": None
            }
        }
        
        try:
            # Player information
            coords = self.read_coordinates()
            if coords:
                state["player"]["position"] = {"x": coords[0], "y": coords[1]}
            
            location = self.read_location()
            if location:
                state["player"]["location"] = location
            
            player_name = self.read_player_name()
            if player_name:
                state["player"]["name"] = player_name
            
            # Game information
            state["game"].update({
                "money": self.read_money(),
                "game_state": self.get_game_state(),
                "is_in_battle": self.is_in_battle(),
                "time": self.read_game_time(),
                "badges": self.read_badges(),
                "items": self.read_items(),
                "item_count": self.read_item_count(),
                "pokedex_caught": self.read_pokedex_caught_count(),
                "pokedex_seen": self.read_pokedex_seen_count()
            })
            
            # Battle details
            if state["game"]["is_in_battle"]:
                battle_details = self.read_battle_details()
                if battle_details:
                    state["game"]["battle"] = battle_details
            
            # Dialog text - always try to read it to see if there's any text in buffers
            dialog_text = self.read_dialog()
            if dialog_text:
                state["game"]["dialog_text"] = dialog_text
                logger.info(f"Found dialog text: {dialog_text[:100]}...")
            else:
                logger.debug("No dialog text found in memory buffers")
            
            # Game progress context
            progress_context = self.get_game_progress_context()
            if progress_context:
                state["game"]["progress_context"] = progress_context
            
            # Party Pokemon
            logger.info("About to read party Pokemon")
            party = self.read_party_pokemon()
            logger.info(f"Read party: {len(party) if party else 0} Pokemon")
            if party:
                logger.info(f"Party data: {party}")
                state["player"]["party"] = [
                    {
                        "species_name": pokemon.species_name,
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
                logger.info(f"Added {len(state['player']['party'])} Pokemon to state")
                logger.info(f"Final state party: {state['player']['party']}")
            else:
                logger.warning("No Pokemon found in party")
            
            # Map tiles
            tiles = self.read_map_around_player(radius=7)
            if tiles:
                state["map"]["tiles"] = tiles
                
                # Process tiles for enhanced information
                tile_names = []
                metatile_behaviors = []
                metatile_info = []
                traversability_map = []
                
                for row in tiles:
                    row_names = []
                    row_behaviors = []
                    row_info = []
                    traversability_row = []
                    
                    for tile_data in row:
                        if len(tile_data) >= 4:
                            tile_id, behavior, collision, elevation = tile_data
                        elif len(tile_data) >= 2:
                            tile_id, behavior = tile_data[:2]
                            collision = 0
                            elevation = 0
                        else:
                            tile_id = tile_data[0] if tile_data else 0
                            behavior = None
                            collision = 0
                            elevation = 0
                        
                        # Tile name
                        tile_name = f"Tile_{tile_id:04X}"
                        if behavior is not None and hasattr(behavior, 'name'):
                            tile_name += f"({behavior.name})"
                        row_names.append(tile_name)
                        
                        # Behavior name
                        behavior_name = behavior.name if behavior is not None and hasattr(behavior, 'name') else "UNKNOWN"
                        row_behaviors.append(behavior_name)
                        
                        # Detailed tile info
                        tile_info = {
                            "id": tile_id,
                            "behavior": behavior_name,
                            "collision": collision,
                            "elevation": elevation,
                            "passable": collision == 0,
                            "encounter_possible": self._is_encounter_tile(behavior),
                            "surfable": self._is_surfable_tile(behavior)
                        }
                        row_info.append(tile_info)
                        
                        # Traversability
                        if behavior_name == "NORMAL":
                            traversability_row.append("." if collision == 0 else "0")
                        else:
                            short_name = behavior_name.replace("_", "")[:4]
                            traversability_row.append(short_name)
                    
                    tile_names.append(row_names)
                    metatile_behaviors.append(row_behaviors)
                    metatile_info.append(row_info)
                    traversability_map.append(traversability_row)
                
                state["map"]["tile_names"] = tile_names
                state["map"]["metatile_behaviors"] = metatile_behaviors
                state["map"]["metatile_info"] = metatile_info
                state["map"]["traversability"] = traversability_map
                
        except Exception as e:
            logger.warning(f"Failed to read comprehensive state: {e}")
        
        return state

    def _is_encounter_tile(self, behavior) -> bool:
        """Check if tile can trigger encounters"""
        if not behavior:
            return False
        
        encounter_behaviors = {
            MetatileBehavior.TALL_GRASS, MetatileBehavior.LONG_GRASS, MetatileBehavior.UNUSED_05,
            MetatileBehavior.DEEP_SAND, MetatileBehavior.CAVE, MetatileBehavior.INDOOR_ENCOUNTER,
            MetatileBehavior.POND_WATER, MetatileBehavior.INTERIOR_DEEP_WATER, MetatileBehavior.DEEP_WATER,
            MetatileBehavior.OCEAN_WATER, MetatileBehavior.SEAWEED, MetatileBehavior.ASHGRASS,
            MetatileBehavior.FOOTPRINTS, MetatileBehavior.SEAWEED_NO_SURFACING
        }
        
        return behavior in encounter_behaviors

    def _is_surfable_tile(self, behavior) -> bool:
        """Check if tile can be surfed on"""
        if not behavior:
            return False
        
        surfable_behaviors = {
            MetatileBehavior.POND_WATER, MetatileBehavior.INTERIOR_DEEP_WATER, MetatileBehavior.DEEP_WATER,
            MetatileBehavior.SOOTOPOLIS_DEEP_WATER, MetatileBehavior.OCEAN_WATER, MetatileBehavior.NO_SURFACING,
            MetatileBehavior.SEAWEED, MetatileBehavior.SEAWEED_NO_SURFACING
        }
        
        return behavior in surfable_behaviors

    def test_memory_access(self) -> Dict[str, Any]:
        """Test memory access functionality"""
        diagnostics = {
            'memory_interface': 'unknown',
            'memory_methods': [],
            'save_blocks_found': False,
            'save_block_offsets': None,
            'map_buffer_found': False,
            'basic_reads_working': False
        }
        
        # Test memory interface
        if hasattr(self.memory, 'load8'):
            diagnostics['memory_interface'] = 'mgba_load_methods'
            diagnostics['memory_methods'].extend(['load8', 'load16', 'load32'])
        elif hasattr(self.memory, 'read8'):
            diagnostics['memory_interface'] = 'mgba_read_methods'
            diagnostics['memory_methods'].extend(['read8', 'read16', 'read32'])
        else:
            diagnostics['memory_interface'] = 'direct_indexing'
            diagnostics['memory_methods'].append('__getitem__')
        
        # Test basic memory reads
        try:
            test_val = self._read_u8(0x02000000)
            diagnostics['basic_reads_working'] = True
        except Exception as e:
            diagnostics['basic_read_error'] = str(e)
        
        # Test map buffer detection
        if self._find_map_buffer_addresses():
            diagnostics['map_buffer_found'] = True
            diagnostics['map_buffer_info'] = {
                'address': hex(self._map_buffer_addr),
                'width': self._map_width,
                'height': self._map_height
            }
        
        return diagnostics

    def read_dialog(self) -> str:
        """Read any dialog text currently on screen by scanning text buffers"""
        try:
            # Always try to read dialog text, regardless of game state
            # The game state detection might not be reliable for dialog
            
            # Text buffer addresses from Pokemon Emerald decompilation symbols
            # https://raw.githubusercontent.com/pret/pokeemerald/symbols/pokeemerald.sym
            # Order by size (largest first) to prioritize longer dialog text
            text_buffers = [
                (self.addresses.G_STRING_VAR4, 1000),  # Main string variable 4 (largest) - PRIORITY
                (self.addresses.G_DISPLAYED_STRING_BATTLE, 300),  # Battle dialog text
                (self.addresses.G_STRING_VAR1, 256),   # Main string variable 1
                (self.addresses.G_STRING_VAR2, 256),   # Main string variable 2
                (self.addresses.G_STRING_VAR3, 256),   # Main string variable 3
                (self.addresses.G_BATTLE_TEXT_BUFF1, 16),  # Battle text buffer 1
                (self.addresses.G_BATTLE_TEXT_BUFF2, 16),  # Battle text buffer 2
                (self.addresses.G_BATTLE_TEXT_BUFF3, 16),  # Battle text buffer 3
                # Legacy addresses (keeping for compatibility)
                (self.addresses.TEXT_BUFFER_1, 200),
                (self.addresses.TEXT_BUFFER_2, 200),
                (self.addresses.TEXT_BUFFER_3, 200),
                (self.addresses.TEXT_BUFFER_4, 200),
            ]
            
            dialog_text = ""
            
            for buffer_addr, buffer_size in text_buffers:
                try:
                    # Read the specified amount of bytes for this buffer
                    buffer_bytes = self._read_bytes(buffer_addr, buffer_size)
                    
                    # Look for text patterns
                    text_lines = []
                    current_line = []
                    space_count = 0
                    
                    for byte in buffer_bytes:
                        # Check if this is a valid text character using our existing mapping
                        if self._is_valid_text_byte(byte):
                            space_count = 0
                            current_line.append(byte)
                        elif byte == 0x7F:  # Space character in Emerald
                            space_count += 1
                            current_line.append(byte)
                        elif byte == 0x4E:  # Line break character
                            # End current line
                            if current_line:
                                text = self._decode_pokemon_text(bytes(current_line))
                                if text.strip():
                                    text_lines.append(text)
                                current_line = []
                                space_count = 0
                        elif byte == 0xFF:  # End of string
                            break
                        
                        # If we see too many consecutive spaces, might be end of meaningful text
                        if space_count > 15 and current_line:
                            text = self._decode_pokemon_text(bytes(current_line))
                            if text.strip():
                                text_lines.append(text)
                            current_line = []
                            space_count = 0
                    
                    # Add final line if any
                    if current_line:
                        text = self._decode_pokemon_text(bytes(current_line))
                        if text.strip():
                            text_lines.append(text)
                    
                    # Join lines and check if we got meaningful text
                    potential_text = "\n".join(text_lines)
                    if len(potential_text.strip()) > 5:  # Minimum meaningful length
                        # Clean up the text - remove excessive whitespace and special characters
                        cleaned_text = potential_text.strip()
                        # Remove null bytes and other control characters
                        cleaned_text = ''.join(char for char in cleaned_text if ord(char) >= 32 or char in '\n\t')
                        # Normalize whitespace
                        cleaned_text = ' '.join(cleaned_text.split())
                        
                        if len(cleaned_text) > 5:
                            # Prefer longer text (more likely to be full dialog)
                            if len(cleaned_text) > len(dialog_text):
                                dialog_text = cleaned_text
                                logger.debug(f"Found better dialog text: {dialog_text[:100]}...")
                            # If this is the first meaningful text found, use it
                            elif not dialog_text:
                                dialog_text = cleaned_text
                                logger.debug(f"Found dialog text: {dialog_text[:100]}...")
                        
                except Exception as e:
                    logger.debug(f"Failed to read from buffer 0x{buffer_addr:08X} (size: {buffer_size}): {e}")
                    continue
            
            return dialog_text.strip()
            
        except Exception as e:
            logger.warning(f"Failed to read dialog: {e}")
            return ""

    def _is_valid_text_byte(self, byte: int) -> bool:
        """Check if a byte represents a valid text character in Pokemon Emerald"""
        # Use the EmeraldCharmap to check if byte is valid
        charmap = EmeraldCharmap()
        return byte < len(charmap.charmap) and charmap.charmap[byte] != ""

    def read_flags(self) -> Dict[str, bool]:
        """Read game flags to track progress and visited locations"""
        try:
            # Get SaveBlock1 pointer
            save_block_1_ptr = self._read_u32(self.addresses.SAVE_BLOCK1_PTR)
            if save_block_1_ptr == 0:
                logger.warning("SaveBlock1 pointer is null")
                return {}
            
            # Read flags from SaveBlock1
            flags_addr = save_block_1_ptr + self.addresses.SAVE_BLOCK1_FLAGS_OFFSET
            flags_data = self._read_bytes(flags_addr, 300)  # Flags are 300 bytes in SaveBlock1
            
            flags = {}
            
            # Check system flags (badges, visited locations, etc.)
            system_flags_start = self.addresses.SYSTEM_FLAGS_START
            system_flags_byte = system_flags_start // 8
            system_flags_bit = system_flags_start % 8
            
            # Badge flags
            badge_flags = [
                ("badge_01", 0x7), ("badge_02", 0x8), ("badge_03", 0x9), ("badge_04", 0xa),
                ("badge_05", 0xb), ("badge_06", 0xc), ("badge_07", 0xd), ("badge_08", 0xe)
            ]
            
            for badge_name, flag_offset in badge_flags:
                flag_byte = system_flags_byte + flag_offset // 8
                flag_bit = flag_offset % 8
                if flag_byte < len(flags_data):
                    flags[badge_name] = bool(flags_data[flag_byte] & (1 << flag_bit))
            
            # Visited location flags
            location_flags = [
                ("visited_littleroot", 0xF), ("visited_oldale", 0x10), ("visited_dewford", 0x11),
                ("visited_lavaridge", 0x12), ("visited_fallarbor", 0x13), ("visited_verdanturf", 0x14),
                ("visited_pacifidlog", 0x15), ("visited_petalburg", 0x16), ("visited_slateport", 0x17),
                ("visited_mauville", 0x18), ("visited_rustboro", 0x19), ("visited_fortree", 0x1A),
                ("visited_lilycove", 0x1B), ("visited_mossdeep", 0x1C), ("visited_sootopolis", 0x1D),
                ("visited_ever_grande", 0x1E)
            ]
            
            for location_name, flag_offset in location_flags:
                flag_byte = system_flags_byte + flag_offset // 8
                flag_bit = flag_offset % 8
                if flag_byte < len(flags_data):
                    flags[location_name] = bool(flags_data[flag_byte] & (1 << flag_bit))
            
            # Champion flag
            champion_flag_byte = system_flags_byte + 0x1F // 8
            champion_flag_bit = 0x1F % 8
            if champion_flag_byte < len(flags_data):
                flags["is_champion"] = bool(flags_data[champion_flag_byte] & (1 << champion_flag_bit))
            
            # Pokedex and other system flags
            pokedex_flag_byte = system_flags_byte + 0x1 // 8
            pokedex_flag_bit = 0x1 % 8
            if pokedex_flag_byte < len(flags_data):
                flags["has_pokedex"] = bool(flags_data[pokedex_flag_byte] & (1 << pokedex_flag_bit))
            
            logger.info(f"Read {len(flags)} game flags")
            return flags
            
        except Exception as e:
            logger.warning(f"Failed to read flags: {e}")
            return {}

    def get_game_progress_context(self) -> Dict[str, Any]:
        """Get context about game progress for better dialog understanding"""
        try:
            flags = self.read_flags()
            badges = self.read_badges()
            party = self.read_party_pokemon()
            
            context = {
                "badges_obtained": len(badges),
                "badge_names": badges,
                "party_size": len(party) if party else 0,
                "has_pokedex": flags.get("has_pokedex", False),
                "is_champion": flags.get("is_champion", False),
                "visited_locations": [k for k, v in flags.items() if k.startswith("visited_") and v],
                "flags": flags
            }
            
            # Add party info if available
            if party:
                context["party_levels"] = [p.level for p in party]
                context["party_species"] = [p.species_name for p in party]
            
            return context
            
        except Exception as e:
            logger.warning(f"Failed to get game progress context: {e}")
            return {}
