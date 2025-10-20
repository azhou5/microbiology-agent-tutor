"""
Cost tracking for LLM API calls.

Tracks token usage and calculates costs across different models.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime


@dataclass
class TokenUsage:
    """Token usage for a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CostTracker:
    """Tracks token usage and costs for OpenAI/Azure API calls."""
    
    # Cost per 1K tokens (as of 2024-2025)
    COST_PER_1K_TOKENS = {
        "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4.1": {"input": 0.0275, "output": 0.11},  # GPT-4.1 (2025-04-14)
        "o4-mini-2025-04-16": {"input": 0.003, "output": 0.012},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "o4-mini-0416": {"input": 0.0011, "output": 0.0044},
        "o4-mini-2025-04-16": {"input": 0.0011, "output": 0.0044},
        "o3-mini-0131": {"input": 0.00015, "output": 0.0006},
        "gpt-4o-1120": {"input": 0.01, "output": 0.03},
        "gpt-4o-0806": {"input": 0.01, "output": 0.03},
        "gpt-4o-mini-0718": {"input": 0.0005, "output": 0.0015},
        "gpt-4o": {"input": 0.01, "output": 0.03},
        "gpt-4o-mini": {"input": 0.0005, "output": 0.0015},
    }
    
    total_cost: float = 0.0
    token_usage: Dict[str, TokenUsage] = field(default_factory=dict)
    call_history: List[Dict] = field(default_factory=list)
    log_file: str = "llm_interactions.log"
    
    def calculate_cost(self, model: str, usage: TokenUsage) -> float:
        """Calculate cost for a specific API call."""
        if model not in self.COST_PER_1K_TOKENS:
            print(f"Warning: Unknown model '{model}' for cost calculation")
            return 0.0
            
        costs = self.COST_PER_1K_TOKENS[model]
        input_cost = (usage.prompt_tokens / 1000) * costs["input"]
        output_cost = (usage.completion_tokens / 1000) * costs["output"]
        return input_cost + output_cost
    
    def add_usage(self, model: str, usage: TokenUsage, input_text: str = "", output_text: str = "") -> Dict:
        """Track usage and cost for an API call."""
        if model not in self.token_usage:
            self.token_usage[model] = TokenUsage()
        
        # Update cumulative totals
        self.token_usage[model].prompt_tokens += usage.prompt_tokens
        self.token_usage[model].completion_tokens += usage.completion_tokens
        self.token_usage[model].total_tokens += usage.total_tokens
        
        # Calculate cost
        call_cost = self.calculate_cost(model, usage)
        self.total_cost += call_cost
        
        # Record call
        call_record = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            },
            "cost": call_cost
        }
        self.call_history.append(call_record)
        
        # Log if text provided
        if input_text and output_text:
            self._log_interaction(model, input_text, output_text, call_cost, usage.total_tokens)
        
        return call_record
    
    def _log_interaction(self, model: str, input_text: str, output_text: str, cost: float, tokens: int):
        """Log interaction to file."""
        try:
            log_entry = (
                f"\n{'='*80}\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Model: {model}\n"
                f"Cost: ${cost:.4f} | Tokens: {tokens:,}\n"
                f"Input: {input_text[:100]}...\n"
                f"Output: {output_text[:100]}...\n"
                f"{'='*80}\n"
            )
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Warning: Could not write to log: {e}")
    
    def get_summary(self) -> Dict:
        """Get summary of all usage and costs."""
        summary_usage = {}
        for model, usage in self.token_usage.items():
            summary_usage[model] = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost": self.calculate_cost(model, usage)
            }
        
        return {
            "total_cost": self.total_cost,
            "usage_by_model": summary_usage,
            "call_history": self.call_history
        }
    
    def print_summary(self):
        """Print formatted summary."""
        summary = self.get_summary()
        print(f"\n=== Cost Summary ===")
        print(f"Total Cost: ${summary['total_cost']:.4f}")
        
        if summary['usage_by_model']:
            print(f"\nUsage by Model:")
            for model, stats in summary['usage_by_model'].items():
                print(f"  {model}:")
                print(f"    Tokens: {stats['total_tokens']:,} (${stats['cost']:.4f})")
    
    def save_summary(self, filepath: str):
        """Save summary to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.get_summary(), f, indent=2)

