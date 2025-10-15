"""
MCP MCQ Agent for MicroTutor V4

A specialized agent that handles MCQ-based learning interactions.
This agent can generate MCQs, process responses, and provide feedback
based on clinical guidelines and case context.
"""

import logging
from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime

from microtutor.agents.base_agent import BaseAgent
from microtutor.tools.mcq_tool import MCQTool
from microtutor.models.domain import MCQ, MCQResponse, MCQFeedback
from microtutor.core.logging_config import log_agent_context

logger = logging.getLogger(__name__)


class MCPMCQAgent(BaseAgent):
    """MCP Agent specialized for MCQ-based learning interactions."""
    
    def __init__(self, model_name: str = None, config: Dict[str, Any] = None):
        """Initialize MCP MCQ agent."""
        super().__init__(model_name)
        self.config = config or {}
        
        # Create proper config for MCQ tool
        mcq_config = {
            "name": "mcq_tool",
            "description": "Generates MCQs based on clinical guidelines",
            "type": "AgenticTool",
            "enable_guidelines": True
        }
        self.mcq_tool = MCQTool(mcq_config)
        self.active_mcqs: Dict[str, MCQ] = {}  # Store active MCQs by session_id
        self.session_responses: Dict[str, List[MCQResponse]] = {}  # Track responses per session
        
    def generate_mcq_for_topic(
        self, 
        topic: str, 
        case_context: str = None, 
        difficulty: str = "intermediate",
        session_id: str = None
    ) -> Dict[str, Any]:
        """
        Generate an MCQ for a specific topic based on guidelines.
        
        Args:
            topic: Medical topic for the question
            case_context: Optional case context
            difficulty: Question difficulty level
            session_id: Optional session ID for tracking
            
        Returns:
            Dict containing the generated MCQ and metadata
        """
        try:
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # Generate MCQ using the tool
            result = self.mcq_tool.execute(
                topic=topic,
                case=case_context,
                difficulty=difficulty,
                session_id=session_id
            )
            
            if result['success']:
                # Store the MCQ for this session
                mcq_data = result.get('mcq_data')
                if mcq_data:
                    # Reconstruct MCQ object
                    from microtutor.models.domain import MCQOption
                    
                    options = [
                        MCQOption(
                            letter=opt['letter'],
                            text=opt['text'],
                            is_correct=opt['is_correct']
                        ) for opt in mcq_data['options']
                    ]
                    
                    mcq = MCQ(
                        question_id=mcq_data['question_id'],
                        question_text=mcq_data['question_text'],
                        options=options,
                        correct_answer=mcq_data['correct_answer'],
                        explanation=mcq_data['explanation'],
                        topic=mcq_data['topic'],
                        difficulty=mcq_data['difficulty'],
                        source_guidelines=mcq_data.get('source_guidelines', [])
                    )
                    
                    self.active_mcqs[session_id] = mcq
                
                # Log interaction
                log_agent_context(
                    case_id=session_id or "mcp_mcq_test",
                    agent_name="mcp_mcq_agent",
                    interaction_id=len(self.active_mcqs),
                    system_prompt="MCP MCQ Generation",
                    user_prompt=f"Generate MCQ for topic: {topic}",
                    feedback_examples="",
                    full_context=case_context[:100] + "..." if case_context and len(case_context) > 100 else case_context,
                    metadata={"guidelines_included": True}
                )
                
                return {
                    "success": True,
                    "mcq_display": result['result'],
                    "mcq_data": mcq_data,
                    "session_id": session_id,
                    "metadata": {
                        "agent": "mcp_mcq_agent",
                        "action": "mcq_generated",
                        "topic": topic,
                        "difficulty": difficulty
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Unknown error'),
                    "metadata": {
                        "agent": "mcp_mcq_agent",
                        "action": "mcq_generation_failed"
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to generate MCQ for topic {topic}: {e}")
            return {
                "success": False,
                "error": str(e),
                "metadata": {
                    "agent": "mcp_mcq_agent",
                    "action": "mcq_generation_error"
                }
            }
    
    def process_mcq_response(
        self, 
        session_id: str, 
        selected_answer: str,
        response_time_ms: int = None
    ) -> Dict[str, Any]:
        """
        Process a student's response to an active MCQ.
        
        Args:
            session_id: Session ID containing the active MCQ
            selected_answer: The letter of the selected answer
            response_time_ms: Optional response time in milliseconds
            
        Returns:
            Dict containing feedback and next steps
        """
        try:
            if session_id not in self.active_mcqs:
                return {
                    "success": False,
                    "error": "No active MCQ found for this session",
                    "metadata": {
                        "agent": "mcp_mcq_agent",
                        "action": "no_active_mcq"
                    }
                }
            
            mcq = self.active_mcqs[session_id]
            
            # Process the response using the MCQ tool
            result = self.mcq_tool.process_response(
                mcq_data={
                    "question_id": mcq.question_id,
                    "question_text": mcq.question_text,
                    "options": [
                        {
                            "letter": opt.letter,
                            "text": opt.text,
                            "is_correct": opt.is_correct
                        } for opt in mcq.options
                    ],
                    "correct_answer": mcq.correct_answer,
                    "explanation": mcq.explanation,
                    "topic": mcq.topic,
                    "difficulty": mcq.difficulty,
                    "source_guidelines": mcq.source_guidelines
                },
                selected_answer=selected_answer,
                session_id=session_id
            )
            
            if result['success']:
                # Record the response
                response = MCQResponse(
                    question_id=mcq.question_id,
                    selected_answer=selected_answer,
                    is_correct=result['is_correct'],
                    response_time_ms=response_time_ms,
                    session_id=session_id
                )
                
                if session_id not in self.session_responses:
                    self.session_responses[session_id] = []
                self.session_responses[session_id].append(response)
                
                # Remove the active MCQ
                del self.active_mcqs[session_id]
                
                # Log interaction
                log_agent_context(
                    case_id=session_id or "mcp_mcq_test",
                    agent_name="mcp_mcq_agent",
                    interaction_id=len(self.session_responses.get(session_id, [])),
                    system_prompt="MCP MCQ Response Processing",
                    user_prompt=f"Answered MCQ: {selected_answer}",
                    feedback_examples="",
                    full_context=f"Question: {mcq.question_text[:50]}...",
                    metadata={"feedback_included": True, "guidelines_included": True}
                )
                
                return {
                    "success": True,
                    "feedback_display": result['result'],
                    "is_correct": result['is_correct'],
                    "feedback_data": result['feedback'],
                    "session_id": session_id,
                    "metadata": {
                        "agent": "mcp_mcq_agent",
                        "action": "response_processed",
                        "correct": result['is_correct'],
                        "topic": mcq.topic
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Failed to process response'),
                    "metadata": {
                        "agent": "mcp_mcq_agent",
                        "action": "response_processing_failed"
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to process MCQ response: {e}")
            return {
                "success": False,
                "error": str(e),
                "metadata": {
                    "agent": "mcp_mcq_agent",
                    "action": "response_processing_error"
                }
            }
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of MCQ performance for a session.
        
        Args:
            session_id: Session ID to summarize
            
        Returns:
            Dict containing session summary
        """
        try:
            if session_id not in self.session_responses:
                return {
                    "success": False,
                    "error": "No responses found for this session",
                    "metadata": {
                        "agent": "mcp_mcq_agent",
                        "action": "no_session_data"
                    }
                }
            
            responses = self.session_responses[session_id]
            total_questions = len(responses)
            correct_answers = sum(1 for r in responses if r.is_correct)
            accuracy = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
            
            # Calculate average response time
            response_times = [r.response_time_ms for r in responses if r.response_time_ms]
            avg_response_time = sum(response_times) / len(response_times) if response_times else None
            
            # Get topics covered
            topics = list(set([r.question_id for r in responses]))  # This would need to be improved with actual topic tracking
            
            summary = {
                "success": True,
                "summary": {
                    "total_questions": total_questions,
                    "correct_answers": correct_answers,
                    "accuracy_percentage": round(accuracy, 2),
                    "average_response_time_ms": round(avg_response_time, 2) if avg_response_time else None,
                    "topics_covered": len(topics)
                },
                "metadata": {
                    "agent": "mcp_mcq_agent",
                    "action": "session_summary",
                    "session_id": session_id
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "metadata": {
                    "agent": "mcp_mcq_agent",
                    "action": "summary_error"
                }
            }
    
    def clear_session(self, session_id: str) -> Dict[str, Any]:
        """
        Clear all data for a session.
        
        Args:
            session_id: Session ID to clear
            
        Returns:
            Dict containing operation result
        """
        try:
            # Remove active MCQ if exists
            if session_id in self.active_mcqs:
                del self.active_mcqs[session_id]
            
            # Remove session responses if exists
            if session_id in self.session_responses:
                del self.session_responses[session_id]
            
            return {
                "success": True,
                "message": f"Session {session_id} cleared successfully",
                "metadata": {
                    "agent": "mcp_mcq_agent",
                    "action": "session_cleared",
                    "session_id": session_id
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return {
                "success": False,
                "error": str(e),
                "metadata": {
                    "agent": "mcp_mcq_agent",
                    "action": "clear_error"
                }
            }
    
    def is_available(self) -> bool:
        """Check if MCP MCQ agent is available."""
        return True


# Convenience functions for easy integration
def create_mcp_mcq_agent(model_name: str = None, config: Dict[str, Any] = None) -> MCPMCQAgent:
    """Create a new MCP MCQ agent instance."""
    return MCPMCQAgent(model_name, config)


def generate_mcq_for_guidelines(
    topic: str, 
    case_context: str = None, 
    difficulty: str = "intermediate",
    session_id: str = None
) -> Dict[str, Any]:
    """
    Convenience function to generate an MCQ for guidelines.
    
    Args:
        topic: Medical topic for the question
        case_context: Optional case context
        difficulty: Question difficulty level
        session_id: Optional session ID
        
    Returns:
        Dict containing the generated MCQ
    """
    agent = create_mcp_mcq_agent()
    return agent.generate_mcq_for_topic(topic, case_context, difficulty, session_id)


def process_mcq_answer(session_id: str, selected_answer: str, response_time_ms: int = None) -> Dict[str, Any]:
    """
    Convenience function to process an MCQ answer.
    
    Args:
        session_id: Session ID with active MCQ
        selected_answer: Selected answer letter
        response_time_ms: Optional response time
        
    Returns:
        Dict containing feedback
    """
    agent = create_mcp_mcq_agent()
    return agent.process_mcq_response(session_id, selected_answer, response_time_ms)
