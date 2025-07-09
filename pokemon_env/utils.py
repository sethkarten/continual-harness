"""
Utility functions for Pokemon Emerald memory reading
"""

from typing import List, Tuple, Optional
from .enums import MetatileBehavior, PokemonType, PokemonSpecies, Move


def is_passable_behavior(behavior: MetatileBehavior) -> bool:
    """
    Check if a metatile behavior allows the player to walk on it
    
    Args:
        behavior: The metatile behavior to check
        
    Returns:
        True if the tile is passable, False otherwise
    """
    # List of behaviors that are passable
    passable_behaviors = {
        MetatileBehavior.NORMAL,
        MetatileBehavior.TALL_GRASS,
        MetatileBehavior.LONG_GRASS,
        MetatileBehavior.SHORT_GRASS,
        MetatileBehavior.SAND,
        MetatileBehavior.ASHGRASS,
        MetatileBehavior.FOOTPRINTS,
        MetatileBehavior.PUDDLE,
        MetatileBehavior.SHALLOW_WATER,
        MetatileBehavior.ICE,
        MetatileBehavior.THIN_ICE,
        MetatileBehavior.CRACKED_ICE,
        MetatileBehavior.HOT_SPRINGS,
        MetatileBehavior.MUDDY_SLOPE,
        MetatileBehavior.BUMPY_SLOPE,
        MetatileBehavior.CRACKED_FLOOR,
        MetatileBehavior.VERTICAL_RAIL,
        MetatileBehavior.HORIZONTAL_RAIL,
        MetatileBehavior.ISOLATED_VERTICAL_RAIL,
        MetatileBehavior.ISOLATED_HORIZONTAL_RAIL,
    }
    
    return behavior in passable_behaviors


def is_encounter_behavior(behavior: MetatileBehavior) -> bool:
    """
    Check if a metatile behavior can trigger wild Pokemon encounters
    
    Args:
        behavior: The metatile behavior to check
        
    Returns:
        True if the tile can trigger encounters, False otherwise
    """
    encounter_behaviors = {
        MetatileBehavior.TALL_GRASS,
        MetatileBehavior.LONG_GRASS,
        MetatileBehavior.INDOOR_ENCOUNTER,
        MetatileBehavior.CAVE,
        MetatileBehavior.DEEP_WATER,
        MetatileBehavior.OCEAN_WATER,
        MetatileBehavior.SHALLOW_WATER,
    }
    
    return behavior in encounter_behaviors


def is_surfable_behavior(behavior: MetatileBehavior) -> bool:
    """
    Check if a metatile behavior allows surfing
    
    Args:
        behavior: The metatile behavior to check
        
    Returns:
        True if the tile is surfable, False otherwise
    """
    surfable_behaviors = {
        MetatileBehavior.DEEP_WATER,
        MetatileBehavior.OCEAN_WATER,
        MetatileBehavior.SHALLOW_WATER,
        MetatileBehavior.POND_WATER,
        MetatileBehavior.INTERIOR_DEEP_WATER,
        MetatileBehavior.SOOTOPOLIS_DEEP_WATER,
    }
    
    return behavior in surfable_behaviors


def get_type_effectiveness(attacking_type: PokemonType, defending_type: PokemonType) -> float:
    """
    Calculate type effectiveness between two Pokemon types
    
    Args:
        attacking_type: The type of the attacking move
        defending_type: The type of the defending Pokemon
        
    Returns:
        Effectiveness multiplier (0.0, 0.25, 0.5, 1.0, 2.0, or 4.0)
    """
    # Type effectiveness chart (simplified - only includes common types)
    # This is a basic implementation - a full chart would be much larger
    effectiveness_chart = {
        PokemonType.NORMAL: {
            PokemonType.ROCK: 0.5,
            PokemonType.GHOST: 0.0,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.FIRE: {
            PokemonType.FIRE: 0.5,
            PokemonType.WATER: 0.5,
            PokemonType.GRASS: 2.0,
            PokemonType.ICE: 2.0,
            PokemonType.BUG: 2.0,
            PokemonType.ROCK: 0.5,
            PokemonType.DRAGON: 0.5,
            PokemonType.STEEL: 2.0,
        },
        PokemonType.WATER: {
            PokemonType.FIRE: 2.0,
            PokemonType.WATER: 0.5,
            PokemonType.GRASS: 0.5,
            PokemonType.GROUND: 2.0,
            PokemonType.ROCK: 2.0,
            PokemonType.DRAGON: 0.5,
        },
        PokemonType.GRASS: {
            PokemonType.FIRE: 0.5,
            PokemonType.WATER: 2.0,
            PokemonType.GRASS: 0.5,
            PokemonType.POISON: 0.5,
            PokemonType.GROUND: 2.0,
            PokemonType.FLYING: 0.5,
            PokemonType.BUG: 0.5,
            PokemonType.ROCK: 2.0,
            PokemonType.DRAGON: 0.5,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.ELECTRIC: {
            PokemonType.WATER: 2.0,
            PokemonType.GRASS: 0.5,
            PokemonType.ELECTRIC: 0.5,
            PokemonType.GROUND: 0.0,
            PokemonType.FLYING: 2.0,
            PokemonType.DRAGON: 0.5,
        },
        PokemonType.ICE: {
            PokemonType.FIRE: 0.5,
            PokemonType.WATER: 0.5,
            PokemonType.GRASS: 2.0,
            PokemonType.ICE: 0.5,
            PokemonType.GROUND: 2.0,
            PokemonType.FLYING: 2.0,
            PokemonType.DRAGON: 2.0,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.FIGHTING: {
            PokemonType.NORMAL: 2.0,
            PokemonType.ICE: 2.0,
            PokemonType.POISON: 0.5,
            PokemonType.FLYING: 0.5,
            PokemonType.PSYCHIC: 0.5,
            PokemonType.BUG: 0.5,
            PokemonType.ROCK: 2.0,
            PokemonType.GHOST: 0.0,
            PokemonType.STEEL: 2.0,
            PokemonType.DARK: 2.0,
        },
        PokemonType.POISON: {
            PokemonType.GRASS: 2.0,
            PokemonType.POISON: 0.5,
            PokemonType.GROUND: 0.5,
            PokemonType.ROCK: 0.5,
            PokemonType.GHOST: 0.5,
            PokemonType.STEEL: 0.0,
        },
        PokemonType.GROUND: {
            PokemonType.FIRE: 2.0,
            PokemonType.GRASS: 0.5,
            PokemonType.ELECTRIC: 2.0,
            PokemonType.POISON: 2.0,
            PokemonType.FLYING: 0.0,
            PokemonType.BUG: 0.5,
            PokemonType.ROCK: 2.0,
            PokemonType.STEEL: 2.0,
        },
        PokemonType.FLYING: {
            PokemonType.GRASS: 2.0,
            PokemonType.ELECTRIC: 0.5,
            PokemonType.FIGHTING: 2.0,
            PokemonType.BUG: 2.0,
            PokemonType.ROCK: 0.5,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.PSYCHIC: {
            PokemonType.FIGHTING: 2.0,
            PokemonType.POISON: 2.0,
            PokemonType.PSYCHIC: 0.5,
            PokemonType.DARK: 0.0,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.BUG: {
            PokemonType.FIRE: 0.5,
            PokemonType.GRASS: 2.0,
            PokemonType.FIGHTING: 0.5,
            PokemonType.POISON: 0.5,
            PokemonType.FLYING: 0.5,
            PokemonType.PSYCHIC: 2.0,
            PokemonType.GHOST: 0.5,
            PokemonType.DARK: 2.0,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.ROCK: {
            PokemonType.FIRE: 2.0,
            PokemonType.ICE: 2.0,
            PokemonType.FIGHTING: 0.5,
            PokemonType.GROUND: 0.5,
            PokemonType.FLYING: 2.0,
            PokemonType.BUG: 2.0,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.GHOST: {
            PokemonType.NORMAL: 0.0,
            PokemonType.PSYCHIC: 2.0,
            PokemonType.GHOST: 2.0,
            PokemonType.DARK: 0.5,
        },
        PokemonType.DRAGON: {
            PokemonType.DRAGON: 2.0,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.DARK: {
            PokemonType.FIGHTING: 0.5,
            PokemonType.PSYCHIC: 2.0,
            PokemonType.GHOST: 2.0,
            PokemonType.DARK: 0.5,
            PokemonType.STEEL: 0.5,
        },
        PokemonType.STEEL: {
            PokemonType.FIRE: 0.5,
            PokemonType.WATER: 0.5,
            PokemonType.ELECTRIC: 0.5,
            PokemonType.ICE: 2.0,
            PokemonType.ROCK: 2.0,
            PokemonType.STEEL: 0.5,
        },
    }
    
    if attacking_type in effectiveness_chart and defending_type in effectiveness_chart[attacking_type]:
        return effectiveness_chart[attacking_type][defending_type]
    
    return 1.0  # Normal effectiveness


def format_time(hours: int, minutes: int, seconds: int) -> str:
    """
    Format game time in a human-readable format
    
    Args:
        hours: Number of hours
        minutes: Number of minutes
        seconds: Number of seconds
        
    Returns:
        Formatted time string
    """
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_money(amount: int) -> str:
    """
    Format money amount with commas
    
    Args:
        amount: Money amount in cents
        
    Returns:
        Formatted money string
    """
    return f"${amount:,}"


def get_pokemon_type_names(type1: PokemonType, type2: Optional[PokemonType] = None) -> str:
    """
    Get formatted type names for a Pokemon
    
    Args:
        type1: Primary type
        type2: Secondary type (optional)
        
    Returns:
        Formatted type string
    """
    if type2 is None or type1 == type2:
        return type1.name.replace("_", " ")
    else:
        return f"{type1.name.replace('_', ' ')} / {type2.name.replace('_', ' ')}"
