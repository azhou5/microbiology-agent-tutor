"""
Conversation history utilities and case management utilities.

This module provides utilities for:
- Managing conversation history (filtering system messages, preparing LLM messages)
- Case management (checking cached cases, loading first patient sentences)
"""

import os
import json
import logging
from typing import List, Dict, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


def filter_system_messages(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Filter out system messages from conversation history.
    
    Chat history should only contain user/assistant messages (what's shown to users).
    System prompts are added by each agent when calling LLM, not stored in history.
    
    Args:
        history: Full conversation history (may include system messages)
        
    Returns:
        Filtered history with only user and assistant messages
        
    Example:
        >>> history = [
        ...     {"role": "system", "content": "You are a tutor"},
        ...     {"role": "user", "content": "Hello"},
        ...     {"role": "assistant", "content": "Hi there!"}
        ... ]
        >>> filter_system_messages(history)
        [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]
    """
    return [msg for msg in history if msg.get("role") != "system"]


def prepare_llm_messages(
    chat_history: List[Dict[str, str]], 
    system_prompt: str,
    case_description: Optional[str] = None
) -> List[Dict[str, str]]:
    """Prepare messages for LLM call by prepending system prompt to filtered chat history.
    
    This function ensures that:
    1. Chat history is clean (no system messages)
    2. System prompt is added only when calling LLM (not stored in history)
    3. Each agent can use its own system prompt
    4. Case description is optionally included in system prompt
    
    Args:
        chat_history: Chat history (user/assistant messages only, no system prompts)
        system_prompt: System prompt to prepend for this LLM call
        case_description: Optional case description to append to system prompt
        
    Returns:
        Messages array ready for LLM API call: [system, ...chat_history]
        
    Example:
        >>> chat_history = [
        ...     {"role": "user", "content": "Hello"},
        ...     {"role": "assistant", "content": "Hi there!"}
        ... ]
        >>> system_prompt = "You are a helpful tutor"
        >>> prepare_llm_messages(chat_history, system_prompt)
        [
            {"role": "system", "content": "You are a helpful tutor"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    """
    # Ensure chat_history is clean (no system messages)
    clean_history = filter_system_messages(chat_history)
    
    # Build system prompt with optional case description
    full_system_prompt = system_prompt
    if case_description:
        full_system_prompt += f"\n\n=== CASE INFORMATION ===\n{case_description}"
    
    # Prepend system prompt for LLM call
    messages = [{"role": "system", "content": full_system_prompt}]
    messages.extend(clean_history)
    return messages


# -------- Case Management Utilities --------

def normalize_organism_name(organism: str) -> str:
    """Normalize organism name for consistent cache keys.
    
    Args:
        organism: Organism name (e.g., "staphylococcus aureus")
        
    Returns:
        Normalized key (e.g., "staphylococcus_aureus")
    """
    return organism.lower().strip().replace(" ", "_")


@lru_cache(maxsize=1)
def load_first_pt_sentence_json(json_path: str) -> Dict[str, str]:
    """Load the cached first patient sentence JSON file.
    
    Args:
        json_path: Path to the ambiguous_with_ages.json file
        
    Returns:
        Dictionary mapping organism keys to first patient sentence strings, or empty dict if load fails
    """
    try:
        if not os.path.exists(json_path):
            logger.warning(f"First patient sentence JSON file not found at: {json_path}")
            return {}
        with open(json_path, "r") as f:
            data = json.load(f)
            logger.info(f"Successfully loaded first patient sentence JSON from {json_path} with {len(data)} organisms")
            return data
    except Exception as e:
        logger.warning(f"First patient sentence JSON load failed from {json_path}: {e}", exc_info=True)
        return {}


def get_cached_first_pt_sentence(organism: str, first_pt_sentence_path: str) -> Optional[str]:
    """Get cached first patient sentence from ambiguous_with_ages.json.
    
    Args:
        organism: The organism name (e.g., "staphylococcus aureus")
        first_pt_sentence_path: Path to the ambiguous_with_ages.json file
        
    Returns:
        Cached first patient sentence if found, None otherwise
    """
    organism_key = normalize_organism_name(organism)
    sentence_data = load_first_pt_sentence_json(first_pt_sentence_path)
    sentence = sentence_data.get(organism_key)
    
    if sentence:
        logger.info(f"Using cached first patient sentence for organism '{organism}' (key: '{organism_key}')")
    else:
        logger.info(
            f"No cached first patient sentence found for organism '{organism}' (key: '{organism_key}'). "
            f"Available keys: {list(sentence_data.keys())[:5]}..."
        )
    
    return sentence


def load_cached_case_cache(cached_cases_dir: str) -> Dict[str, str]:
    """Load case_cache.json from cached cases directory.
    
    Args:
        cached_cases_dir: Path to the data/cases/cached directory
        
    Returns:
        Dictionary mapping organism keys to full case text, or empty dict if not found
    """
    case_cache_file = os.path.join(cached_cases_dir, "case_cache.json")
    try:
        if os.path.exists(case_cache_file):
            with open(case_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                logger.info(f"Loaded cached case_cache.json with {len(cache_data)} organisms")
                return cache_data
    except Exception as e:
        logger.warning(f"Error loading cached case_cache.json: {e}")
    return {}


def has_cached_case(organism: str, cached_cases_dir: str, case_generator_cache: Optional[Dict[str, str]] = None) -> bool:
    """Check if organism has a cached case in case_cache.json.
    
    Args:
        organism: The organism name
        cached_cases_dir: Path to the data/cases/cached directory
        case_generator_cache: Optional in-memory case cache from CaseGeneratorRAGAgent
        
    Returns:
        True if cached case exists, False otherwise
    """
    try:
        cache_key = normalize_organism_name(organism)
        
        # Check cached case_cache.json (from data/cases/cached/)
        cached_case_cache = load_cached_case_cache(cached_cases_dir)
        if cache_key in cached_case_cache:
            return True
        
        # Check in-memory cache if provided
        if case_generator_cache and cache_key in case_generator_cache:
            return True
        
        return False
    except Exception as e:
        logger.warning(f"Error checking cached case: {e}")
        return False
