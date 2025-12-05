"""
PostCaseAssessmentTool - Generates targeted MCQs after case completion.

This tool:
1. Analyzes the conversation to identify student weak areas
2. Generates MCQs specifically targeting those weaknesses
3. Returns structured MCQ data for interactive display

Called AFTER the case is complete (not during conversation).
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from microtutor.schemas.tools.tool_models import AgenticTool
from microtutor.schemas.tools.tool_errors import ToolLLMError
from microtutor.core.llm.llm_router import chat_complete
from microtutor.prompts.post_case_assessment_prompts import (
    get_post_case_assessment_system_prompt,
    get_weakness_analysis_prompt
)
from microtutor.core.logging.logging_config import log_agent_context

logger = logging.getLogger(__name__)


@dataclass
class MCQOption:
    """A single MCQ option."""
    letter: str
    text: str
    is_correct: bool
    explanation: str


@dataclass
class MCQ:
    """A complete MCQ with metadata."""
    question_id: str
    question_text: str
    topic: str
    weakness_addressed: str
    difficulty: str
    options: List[MCQOption]
    correct_answer: str
    learning_point: str


@dataclass
class WeakArea:
    """An identified weak area from conversation analysis."""
    topic: str
    description: str
    severity: str
    evidence: str


@dataclass
class AssessmentResult:
    """Complete assessment result with MCQs and metadata."""
    mcqs: List[MCQ]
    weak_areas_covered: List[str]
    total_questions: int
    difficulty_distribution: Dict[str, int]


class PostCaseAssessmentTool(AgenticTool):
    """Generates targeted MCQs based on student's weak areas during the case.
    
    This tool is called AFTER the case is complete. It:
    1. Analyzes the full conversation history
    2. Identifies areas where the student struggled
    3. Generates MCQs targeting those specific weaknesses
    4. Returns structured data for interactive frontend display
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize post-case assessment tool."""
        super().__init__(config)
        self.interaction_counter = 0
        self.default_num_questions = config.get('default_num_questions', 5)
    
    def _format_conversation_for_analysis(self, conversation_history: List[Dict]) -> str:
        """Format conversation history for weakness analysis."""
        if not conversation_history:
            return "No conversation history available."
        
        formatted = []
        for msg in conversation_history:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            formatted.append(f"{role}: {content}")
        
        return "\n\n".join(formatted)
    
    def _analyze_weaknesses(
        self, 
        conversation_history: List[Dict], 
        model: str
    ) -> List[WeakArea]:
        """Analyze conversation to identify student weak areas."""
        try:
            conversation_text = self._format_conversation_for_analysis(conversation_history)
            
            prompt = get_weakness_analysis_prompt().format(
                conversation=conversation_text
            )
            
            response = chat_complete(
                system_prompt="You are an expert medical educator analyzing student performance.",
                user_prompt=prompt,
                model=model
            )
            
            # Parse JSON response
            result = json.loads(response)
            
            weak_areas = []
            for wa in result.get('weak_areas', []):
                weak_areas.append(WeakArea(
                    topic=wa.get('topic', 'Unknown'),
                    description=wa.get('description', ''),
                    severity=wa.get('severity', 'moderate'),
                    evidence=wa.get('evidence', '')
                ))
            
            # Also get recommended focus areas
            recommended = result.get('recommended_focus', [])
            logger.info(f"Identified {len(weak_areas)} weak areas, recommended focus: {recommended}")
            
            return weak_areas, recommended
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse weakness analysis JSON: {e}")
            # Return default weak areas
            return [WeakArea(
                topic="Clinical reasoning",
                description="General clinical reasoning assessment",
                severity="moderate",
                evidence="Unable to parse specific weaknesses"
            )], ["Clinical reasoning"]
        except Exception as e:
            logger.error(f"Weakness analysis failed: {e}")
            raise ToolLLMError(f"Failed to analyze weaknesses: {e}")
    
    def _generate_mcqs(
        self,
        case: str,
        weak_areas: List[WeakArea],
        recommended_focus: List[str],
        num_questions: int,
        model: str
    ) -> AssessmentResult:
        """Generate MCQs targeting identified weak areas."""
        try:
            # Format weak areas for prompt
            weak_areas_text = "\n".join([
                f"- {wa.topic}: {wa.description} (severity: {wa.severity})"
                for wa in weak_areas
            ])
            
            if recommended_focus:
                weak_areas_text += f"\n\nRecommended focus areas: {', '.join(recommended_focus)}"
            
            prompt = get_post_case_assessment_system_prompt().format(
                case=case,
                weak_areas=weak_areas_text,
                num_questions=num_questions
            )
            
            response = chat_complete(
                system_prompt="",
                user_prompt=prompt,
                model=model
            )
            
            # Parse JSON response
            result = json.loads(response)
            
            mcqs = []
            for mcq_data in result.get('mcqs', []):
                options = [
                    MCQOption(
                        letter=opt['letter'],
                        text=opt['text'],
                        is_correct=opt['is_correct'],
                        explanation=opt['explanation']
                    )
                    for opt in mcq_data.get('options', [])
                ]
                
                mcqs.append(MCQ(
                    question_id=mcq_data.get('question_id', str(uuid.uuid4())),
                    question_text=mcq_data['question_text'],
                    topic=mcq_data.get('topic', 'General'),
                    weakness_addressed=mcq_data.get('weakness_addressed', ''),
                    difficulty=mcq_data.get('difficulty', 'intermediate'),
                    options=options,
                    correct_answer=mcq_data['correct_answer'],
                    learning_point=mcq_data.get('learning_point', '')
                ))
            
            summary = result.get('summary', {})
            
            return AssessmentResult(
                mcqs=mcqs,
                weak_areas_covered=summary.get('weak_areas_covered', [wa.topic for wa in weak_areas]),
                total_questions=len(mcqs),
                difficulty_distribution=summary.get('difficulty_distribution', {})
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MCQ JSON: {e}")
            raise ToolLLMError(f"Failed to parse MCQ response: {e}")
        except Exception as e:
            logger.error(f"MCQ generation failed: {e}")
            raise ToolLLMError(f"Failed to generate MCQs: {e}")
    
    def _call_llm(self, prompt: str, **kwargs) -> str:
        """Required by AgenticTool but not directly used."""
        return ""
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute post-case assessment to generate targeted MCQs.
        
        Args:
            case: Case description
            conversation_history: Full conversation from the case
            num_questions: Number of MCQs to generate (default: 5)
            model: LLM model to use
            
        Returns:
            Dict with MCQs structured for interactive display
        """
        try:
            # Validate required parameters
            if 'case' not in kwargs:
                raise ValueError("Missing required parameter: case")
            if 'conversation_history' not in kwargs:
                raise ValueError("Missing required parameter: conversation_history")
            
            case = kwargs['case']
            conversation_history = kwargs['conversation_history']
            num_questions = kwargs.get('num_questions', self.default_num_questions)
            model = kwargs.get('model', self.llm_config.get('model', 'gpt-4'))
            
            # Step 1: Analyze conversation for weak areas
            logger.info("Analyzing conversation for student weak areas...")
            weak_areas, recommended_focus = self._analyze_weaknesses(
                conversation_history, model
            )
            
            # Step 2: Generate targeted MCQs
            logger.info(f"Generating {num_questions} targeted MCQs...")
            assessment = self._generate_mcqs(
                case=case,
                weak_areas=weak_areas,
                recommended_focus=recommended_focus,
                num_questions=num_questions,
                model=model
            )
            
            # Log interaction
            log_agent_context(
                case_id="post_case_assessment",
                agent_name="post_case_assessment",
                interaction_id=self.interaction_counter,
                system_prompt="Post-case MCQ generation",
                user_prompt=f"Generate {num_questions} MCQs for weak areas",
                feedback_examples="",
                full_context=f"Weak areas: {[wa.topic for wa in weak_areas]}",
                metadata={
                    "num_questions": num_questions,
                    "weak_areas_count": len(weak_areas)
                }
            )
            
            self.interaction_counter += 1
            
            # Convert to serializable format
            mcqs_data = []
            for mcq in assessment.mcqs:
                mcqs_data.append({
                    "question_id": mcq.question_id,
                    "question_text": mcq.question_text,
                    "topic": mcq.topic,
                    "weakness_addressed": mcq.weakness_addressed,
                    "difficulty": mcq.difficulty,
                    "options": [
                        {
                            "letter": opt.letter,
                            "text": opt.text,
                            "is_correct": opt.is_correct,
                            "explanation": opt.explanation
                        }
                        for opt in mcq.options
                    ],
                    "correct_answer": mcq.correct_answer,
                    "learning_point": mcq.learning_point
                })
            
            return {
                "success": True,
                "result": {
                    "mcqs": mcqs_data,
                    "summary": {
                        "weak_areas_covered": assessment.weak_areas_covered,
                        "total_questions": assessment.total_questions,
                        "difficulty_distribution": assessment.difficulty_distribution
                    }
                },
                "metadata": {
                    "agent": "post_case_assessment",
                    "interaction_count": self.interaction_counter,
                    "weak_areas_analyzed": [wa.topic for wa in weak_areas],
                    "questions_generated": len(assessment.mcqs)
                }
            }
            
        except Exception as e:
            logger.error(f"Post-case assessment failed: {e}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }


# Convenience function
def run_post_case_assessment(
    case: str,
    conversation_history: List[Dict],
    num_questions: int = 5,
    model: str = None
) -> Dict[str, Any]:
    """Generate post-case assessment MCQs.
    
    Args:
        case: Case description
        conversation_history: Full conversation history
        num_questions: Number of MCQs to generate
        model: LLM model to use
        
    Returns:
        Dict with MCQs and metadata
    """
    config = {
        "name": "post_case_assessment",
        "description": "Generates targeted MCQs after case completion",
        "type": "AgenticTool",
        "default_num_questions": num_questions
    }
    
    tool = PostCaseAssessmentTool(config)
    return tool.execute(
        case=case,
        conversation_history=conversation_history,
        num_questions=num_questions,
        model=model
    )
