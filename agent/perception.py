import time
import logging
from utils.vlm import VLM
from utils.state_formatter import format_state_for_llm, format_state_summary
from agent.system_prompt import system_prompt

# Set up module logging
logger = logging.getLogger(__name__)

def perception_step(frame, state_data, vlm):
    """
    Observe and describe your current situation using both visual and comprehensive state data.
    Returns (observation, slow_thinking_needed)
    """
    # Format the comprehensive state context using the utility
    state_context = format_state_for_llm(state_data)
    
    # Log the state data being used
    state_summary = format_state_summary(state_data)
    logger.info("[PERCEPTION] Processing frame with comprehensive state data")
    logger.info(f"[PERCEPTION] State: {state_summary}")
    logger.info(f"[PERCEPTION] State context length: {len(state_context)} characters")
    
    perception_prompt = f"""
    ★★★ COMPREHENSIVE GAME STATE DATA ★★★
    
    {state_context}
    
    ★★★ VISUAL ANALYSIS TASK ★★★
    
    You are the agent, actively playing Pokemon Emerald. Observe and describe your current situation in detail using both the visual frame and the comprehensive game state data above.

    Based on the visual frame and the above state data, describe your current situation:
    - CUTSCENE or TITLE SCREEN: What does the cutscene or title screen show?
    - MAP: You are navigating a terrain (city, forest, grassland, etc.). Are there any interactable locations (NPCs, items, doors)? What are the traversable vs. non-traversable areas? Use your position coordinates to understand where you are.
    - BATTLE: Analyze the battle situation using both visual and state data. What moves are available? What's the strategy?
    - DIALOGUE: What is the character telling you? How important is this information? Can you respond to the NPC?
    - MENU: What menu are you in? What options are available? What should you select based on your current needs?
    
    Combine visual observation with the state data to give a complete picture of the current situation.
    """
    
    observation = vlm.get_query(frame, system_prompt + perception_prompt, "PERCEPTION")
    
    # Determine if slow thinking is needed based on visual scene and state changes
    scene_check_prompt = f"""
    ★★★ COMPREHENSIVE GAME STATE DATA ★★★
    
    {state_context}
    
    ★★★ SLOW THINKING DECISION ★★★
    
    Based on the current state and visual frame above:
    
    Does this scene represent a significant change that requires planning? Consider:
    - Entering/exiting battle
    - Reaching a new map/location
    - Encountering important NPCs or story events
    - Significant changes in pokemon party or game state
    
    Answer YES or NO.
    """
    scene_response = vlm.get_query(frame, scene_check_prompt, "PERCEPTION-SCENE_CHECK").strip().lower()
    slow_thinking_needed = ("yes" in scene_response)

    '''
    # If on a map, try to generate a traversability analysis
    if ("map" in observation.lower() or "navigating" in observation.lower() or "terrain" in observation.lower()) and not state_data.get('game', {}).get('in_battle', False):
        map_prompt = f"""
        ★★★ COMPREHENSIVE GAME STATE DATA ★★★
        
        {state_context}
        
        ★★★ TRAVERSABILITY MAP GENERATION ★★★
        
        Based on the current game frame and your position data above:
        
        Analyze the traversability of the visible area. Output a text-based map using these symbols:
        - . for traversable ground/paths
        - # for walls, trees, or obstacles  
        - P for the player character
        - D for doors/building entrances
        - N for NPCs you can interact with
        - I for items on the ground
        - W for water (might need Surf)
        - ~ for tall grass (wild pokemon encounters)
        
        The map should be a small grid showing the immediate area around the player.
        Example:
        #####
        #~.~#
        #.P.#
        #D.N#
        #####
        Legend: P=Player, D=Door, N=NPC, I=Item, .=path, #=obstacle, ~=grass, W=water
        
        Only output the map and legend, nothing else.
        """
        text_map = vlm.get_query(frame, map_prompt, "PERCEPTION-MAP")
        observation = {"description": observation, "text_map": text_map, "state_data": state_context}
    else:
    '''
    observation = {"description": observation, "state_data": state_context}
    
    logger.info(f"[PERCEPTION] Slow thinking needed: {slow_thinking_needed}")
    return observation, slow_thinking_needed 