"""
Centralized logging configuration for MicroTutor V4.

Sets up comprehensive logging to the logs/ directory including:
- Conversation history per case
- Tool calls and agent context
- LLM interactions
- Feedback logs
- Debug logs
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import json


class MicroTutorLogger:
    """Centralized logger for MicroTutor with structured file output."""
    
    def __init__(self, logs_dir: Optional[Path] = None):
        """
        Initialize the logger.
        
        Args:
            logs_dir: Directory for log files (defaults to logs/ in project root)
        """
        if logs_dir is None:
            # Get project root (V4_refactor)
            project_root = Path(__file__).parent.parent.parent.parent
            logs_dir = project_root / "logs"
        
        self.logs_dir = Path(logs_dir)
        self._setup_directories()
        self._setup_loggers()
    
    def _setup_directories(self):
        """Create logging directories if they don't exist."""
        # Main logs directory
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories for organization
        (self.logs_dir / "conversations").mkdir(exist_ok=True)
        (self.logs_dir / "tools").mkdir(exist_ok=True)
        (self.logs_dir / "agents").mkdir(exist_ok=True)
        (self.logs_dir / "feedback").mkdir(exist_ok=True)
        (self.logs_dir / "llm").mkdir(exist_ok=True)
    
    def _setup_loggers(self):
        """Set up different loggers for different purposes."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 1. Main debug log
        self.debug_logger = self._create_file_logger(
            'debug',
            self.logs_dir / 'debug.log',
            log_format
        )
        
        # 2. LLM interactions log
        self.llm_logger = self._create_file_logger(
            'llm_interactions',
            self.logs_dir / 'llm' / 'llm_interactions.log',
            log_format
        )
        
        # 3. Tool calls log
        self.tool_logger = self._create_file_logger(
            'tool_calls',
            self.logs_dir / 'tools' / 'tool_calls.log',
            log_format
        )
        
        # 4. Feedback logs
        self.feedback_logger = self._create_file_logger(
            'feedback',
            self.logs_dir / 'feedback' / 'feedback.log',
            log_format
        )
        
        self.case_feedback_logger = self._create_file_logger(
            'case_feedback',
            self.logs_dir / 'feedback' / 'case_feedback.log',
            log_format
        )
        
        # 5. Agent context log
        self.agent_logger = self._create_file_logger(
            'agent_context',
            self.logs_dir / 'agents' / 'agent_context.log',
            log_format
        )
    
    def _create_file_logger(self, name: str, filepath: Path, format_str: str) -> logging.Logger:
        """Create a logger that writes to a specific file."""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to root logger
        
        # Remove existing handlers
        logger.handlers = []
        
        # Add file handler
        handler = logging.FileHandler(filepath)
        handler.setFormatter(logging.Formatter(format_str))
        logger.addHandler(handler)
        
        return logger
    
    def log_conversation_turn(self, case_id: str, role: str, content: str, metadata: Optional[dict] = None):
        """
        Log a conversation turn to a case-specific file.
        
        Args:
            case_id: Unique case identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (tools used, etc.)
        """
        conv_file = self.logs_dir / "conversations" / f"{case_id}.jsonl"
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        
        with open(conv_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def log_tool_call(self, case_id: str, tool_name: str, arguments: dict, result: str, metadata: Optional[dict] = None):
        """
        Log a tool call with its result.
        
        Args:
            case_id: Unique case identifier
            tool_name: Name of the tool called
            arguments: Tool arguments
            result: Tool result
            metadata: Optional additional metadata
        """
        self.tool_logger.info(
            f"TOOL_CALL | case_id={case_id} | tool={tool_name} | "
            f"args={json.dumps(arguments)} | result_len={len(result)}"
        )
        
        # Also save detailed tool log
        tool_file = self.logs_dir / "tools" / f"{case_id}_tools.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result[:500],  # Truncate long results
            "metadata": metadata or {}
        }
        
        with open(tool_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def log_agent_context(self, case_id: str, agent_name: str, context: dict):
        """
        Log agent's internal context/state.
        
        Args:
            case_id: Unique case identifier
            agent_name: Name of the agent
            context: Agent's context dictionary
        """
        self.agent_logger.info(
            f"AGENT_CONTEXT | case_id={case_id} | agent={agent_name}"
        )
        
        # Save detailed context
        agent_file = self.logs_dir / "agents" / f"{case_id}_{agent_name}.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "context": context
        }
        
        with open(agent_file, 'a') as f:
            f.write(json.dumps(entry, default=str) + '\n')
    
    def log_llm_interaction(self, case_id: str, model: str, messages: list, response: str, 
                           tokens_used: Optional[dict] = None, metadata: Optional[dict] = None):
        """
        Log LLM API call and response.
        
        Args:
            case_id: Unique case identifier
            model: LLM model name
            messages: Input messages
            response: LLM response
            tokens_used: Token usage dict
            metadata: Optional metadata
        """
        self.llm_logger.info(
            f"LLM_CALL | case_id={case_id} | model={model} | "
            f"messages_count={len(messages)} | "
            f"tokens={tokens_used or 'unknown'}"
        )
        
        # Save detailed LLM log
        llm_file = self.logs_dir / "llm" / f"{case_id}_llm.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "messages": messages,
            "response": response,
            "tokens_used": tokens_used,
            "metadata": metadata or {}
        }
        
        with open(llm_file, 'a') as f:
            f.write(json.dumps(entry, default=str) + '\n')
    
    def log_feedback(self, case_id: str, rating: int, message: str, feedback_text: str, 
                    replacement_text: str = "", organism: str = ""):
        """
        Log user feedback on a response.
        
        Args:
            case_id: Unique case identifier
            rating: User rating (1-5)
            message: Message being rated
            feedback_text: User's feedback text
            replacement_text: Optional replacement text
            organism: Organism for the case
        """
        self.feedback_logger.info(
            f"FEEDBACK | case_id={case_id} | organism={organism} | "
            f"rating={rating} | message_len={len(message)} | "
            f"feedback_len={len(feedback_text)}"
        )
    
    def log_case_feedback(self, case_id: str, detail: int, helpfulness: int, 
                         accuracy: int, comments: str, organism: str):
        """
        Log overall case feedback.
        
        Args:
            case_id: Unique case identifier
            detail: Detail rating (1-4)
            helpfulness: Helpfulness rating (1-4)
            accuracy: Accuracy rating (1-4)
            comments: Additional comments
            organism: Organism for the case
        """
        self.case_feedback_logger.info(
            f"CASE_FEEDBACK | case_id={case_id} | organism={organism} | "
            f"detail={detail} | helpfulness={helpfulness} | "
            f"accuracy={accuracy} | comments_len={len(comments)}"
        )
    
    def log_agent_context(self, case_id: str, agent_name: str, interaction_id: int,
                         system_prompt: str, user_prompt: str, feedback_examples: str = "",
                         full_context: str = "", metadata: dict = None):
        """
        Log complete agent context for debugging.
        
        Args:
            case_id: Unique case identifier
            agent_name: Name of the agent (tutor, patient, socratic, hint)
            interaction_id: Sequential interaction number for this case
            system_prompt: System prompt sent to the agent
            user_prompt: User prompt sent to the agent
            feedback_examples: Feedback examples appended (if any)
            full_context: Complete context the agent sees
            metadata: Additional metadata
        """
        self.agent_logger.info(
            f"AGENT_CONTEXT | case_id={case_id} | agent={agent_name} | "
            f"interaction={interaction_id} | context_len={len(full_context)}"
        )
        
        # Save detailed agent context
        agent_file = self.logs_dir / "agents" / f"{agent_name}_context.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "case_id": case_id,
            "agent_name": agent_name,
            "interaction_id": interaction_id,
            "system_prompt": system_prompt,
            "conversation_context": {
                "user_prompt": user_prompt,
                "feedback_examples": feedback_examples,
                "full_context": full_context
            },
            "metadata": metadata or {}
        }
        
        with open(agent_file, 'a') as f:
            f.write(json.dumps(entry, default=str) + '\n')
    
    def get_conversation_history(self, case_id: str) -> list:
        """
        Read conversation history for a case.
        
        Args:
            case_id: Unique case identifier
            
        Returns:
            List of conversation entries
        """
        conv_file = self.logs_dir / "conversations" / f"{case_id}.jsonl"
        
        if not conv_file.exists():
            return []
        
        history = []
        with open(conv_file, 'r') as f:
            for line in f:
                if line.strip():
                    history.append(json.loads(line))
        
        return history


# Global logger instance
_logger_instance = None


def get_logger() -> MicroTutorLogger:
    """Get the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = MicroTutorLogger()
    return _logger_instance


def log_conversation_turn(case_id: str, role: str, content: str, metadata: Optional[dict] = None):
    """Convenience function to log a conversation turn."""
    get_logger().log_conversation_turn(case_id, role, content, metadata)


def log_tool_call(case_id: str, tool_name: str, arguments: dict, result: str, metadata: Optional[dict] = None):
    """Convenience function to log a tool call."""
    get_logger().log_tool_call(case_id, tool_name, arguments, result, metadata)


def log_agent_context(case_id: str, agent_name: str, interaction_id: int,
                     system_prompt: str, user_prompt: str, feedback_examples: str = "",
                     full_context: str = "", metadata: dict = None):
    """Convenience function to log agent context."""
    get_logger().log_agent_context(case_id, agent_name, interaction_id, system_prompt, 
                                  user_prompt, feedback_examples, full_context, metadata)


def log_llm_interaction(case_id: str, model: str, messages: list, response: str, 
                       tokens_used: Optional[dict] = None, metadata: Optional[dict] = None):
    """Convenience function to log LLM interaction."""
    get_logger().log_llm_interaction(case_id, model, messages, response, tokens_used, metadata)

