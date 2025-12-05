"""
Post-Case Assessment API Routes for MicroTutor V4

API endpoints for generating targeted MCQs based on student weaknesses
identified during case conversations.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from microtutor.tools.post_case_assessment import (
    PostCaseAssessmentTool,
    run_post_case_assessment,
    MCQ,
    MCQOption,
    WeakArea,
    AssessmentResult
)
from microtutor.core.llm import get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessment", tags=["Assessment"])


# Request/Response Models
class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")


class AssessmentGenerateRequest(BaseModel):
    """Request model for generating post-case assessment MCQs."""
    case_id: str = Field(..., description="The case ID")
    organism: str = Field(..., description="The organism/case type")
    conversation_history: List[ConversationMessage] = Field(
        ..., 
        description="Full conversation history from the case"
    )
    num_questions: int = Field(
        5, 
        ge=1, 
        le=10, 
        description="Number of MCQs to generate"
    )


class MCQOptionResponse(BaseModel):
    """Response model for a single MCQ option."""
    letter: str
    text: str
    is_correct: bool
    explanation: str


class MCQResponse(BaseModel):
    """Response model for a single MCQ."""
    question_id: str
    question_text: str
    topic: str
    difficulty: str
    options: List[MCQOptionResponse]
    weakness_addressed: Optional[str] = None
    learning_point: Optional[str] = None


class AssessmentSummary(BaseModel):
    """Summary of the assessment."""
    total_questions: int
    weak_areas_covered: List[str]
    topics_covered: List[str]


class AssessmentResultResponse(BaseModel):
    """Complete assessment result."""
    mcqs: List[MCQResponse]
    summary: AssessmentSummary


class AssessmentGenerateResponse(BaseModel):
    """Response model for assessment generation."""
    success: bool
    result: Optional[AssessmentResultResponse] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Singleton for assessment tool
_assessment_tool: Optional[PostCaseAssessmentTool] = None


def get_assessment_tool() -> PostCaseAssessmentTool:
    """Get or create assessment tool instance."""
    global _assessment_tool
    if _assessment_tool is None:
        llm_client = get_llm_client()
        _assessment_tool = PostCaseAssessmentTool(llm_client=llm_client)
    return _assessment_tool


def convert_assessment_to_response(result: AssessmentResult) -> AssessmentResultResponse:
    """Convert internal AssessmentResult to API response format."""
    mcqs_response = []
    
    for mcq in result.mcqs:
        options_response = [
            MCQOptionResponse(
                letter=opt.letter,
                text=opt.text,
                is_correct=opt.is_correct,
                explanation=opt.explanation
            )
            for opt in mcq.options
        ]
        
        mcqs_response.append(MCQResponse(
            question_id=mcq.question_id,
            question_text=mcq.question_text,
            topic=mcq.topic,
            difficulty=mcq.difficulty,
            options=options_response,
            weakness_addressed=mcq.weakness_addressed,
            learning_point=mcq.learning_point
        ))
    
    weak_areas_covered = [wa.area for wa in result.weak_areas]
    topics_covered = list(set(mcq.topic for mcq in result.mcqs))
    
    return AssessmentResultResponse(
        mcqs=mcqs_response,
        summary=AssessmentSummary(
            total_questions=len(result.mcqs),
            weak_areas_covered=weak_areas_covered,
            topics_covered=topics_covered
        )
    )


@router.post("/generate", response_model=AssessmentGenerateResponse)
async def generate_assessment(request: AssessmentGenerateRequest):
    """
    Generate targeted MCQs based on student weaknesses from the case conversation.
    
    This endpoint analyzes the conversation history to identify areas where
    the student struggled, then generates MCQs specifically targeting those
    weak areas for reinforcement learning.
    
    **Example Request:**
    ```json
    {
        "case_id": "case_123",
        "organism": "staphylococcus_aureus",
        "conversation_history": [
            {"role": "user", "content": "What symptoms does the patient have?"},
            {"role": "assistant", "content": "The patient presents with..."},
            ...
        ],
        "num_questions": 5
    }
    ```
    
    **Example Response:**
    ```json
    {
        "success": true,
        "result": {
            "mcqs": [
                {
                    "question_id": "mcq_1",
                    "question_text": "Which of the following is the most appropriate...",
                    "topic": "Antibiotic Selection",
                    "difficulty": "medium",
                    "options": [
                        {"letter": "A", "text": "...", "is_correct": false, "explanation": "..."},
                        {"letter": "B", "text": "...", "is_correct": true, "explanation": "..."},
                        ...
                    ],
                    "weakness_addressed": "Antibiotic selection for MRSA",
                    "learning_point": "Key learning point..."
                }
            ],
            "summary": {
                "total_questions": 5,
                "weak_areas_covered": ["Antibiotic selection", "Diagnosis"],
                "topics_covered": ["Antibiotic Selection", "Clinical Diagnosis"]
            }
        }
    }
    ```
    """
    try:
        logger.info(f"Generating assessment for case: {request.case_id}")
        
        # Format conversation history
        conversation = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]
        
        # Build case context
        case = {
            "case_id": request.case_id,
            "organism": request.organism
        }
        
        # Use the convenience function for assessment
        result = run_post_case_assessment(
            case=case,
            conversation_history=conversation,
            num_questions=request.num_questions
        )
        
        # Handle dict return from tool.execute()
        if not result.get('success', False):
            error_info = result.get('error', {})
            logger.warning(f"Assessment generation failed: {error_info}")
            return AssessmentGenerateResponse(
                success=False,
                error={
                    "code": "GENERATION_FAILED",
                    "message": error_info.get('message', 'Assessment generation failed')
                },
                metadata={"case_id": request.case_id}
            )
        
        # Extract MCQs from result dict
        result_data = result.get('result', {})
        mcqs_data = result_data.get('mcqs', [])
        summary_data = result_data.get('summary', {})
        
        if mcqs_data:
            # Convert dict format to response format
            mcqs_response = []
            for mcq in mcqs_data:
                options_response = [
                    MCQOptionResponse(
                        letter=opt['letter'],
                        text=opt['text'],
                        is_correct=opt['is_correct'],
                        explanation=opt['explanation']
                    )
                    for opt in mcq.get('options', [])
                ]
                mcqs_response.append(MCQResponse(
                    question_id=mcq.get('question_id', ''),
                    question_text=mcq.get('question_text', ''),
                    topic=mcq.get('topic', ''),
                    difficulty=mcq.get('difficulty', 'medium'),
                    options=options_response,
                    weakness_addressed=mcq.get('weakness_addressed', ''),
                    learning_point=mcq.get('learning_point', '')
                ))
            
            response_data = AssessmentResultResponse(
                mcqs=mcqs_response,
                summary=AssessmentSummary(
                    weak_areas_covered=summary_data.get('weak_areas_covered', []),
                    topics_covered=list(set(mcq.get('topic', '') for mcq in mcqs_data)),
                    total_questions=len(mcqs_data),
                    difficulty_distribution=summary_data.get('difficulty_distribution', {})
                )
            )
            
            logger.info(
                f"Generated {len(mcqs_data)} MCQs for case {request.case_id}"
            )
            
            return AssessmentGenerateResponse(
                success=True,
                result=response_data,
                metadata={
                    "case_id": request.case_id,
                    "organism": request.organism,
                    "questions_requested": request.num_questions,
                    "questions_generated": len(mcqs_data)
                }
            )
        else:
            logger.warning(f"No MCQs generated for case {request.case_id}")
            return AssessmentGenerateResponse(
                success=False,
                error={
                    "code": "NO_QUESTIONS_GENERATED",
                    "message": "Could not generate MCQs. The conversation may be too short or no weak areas were identified."
                },
                metadata={"case_id": request.case_id}
            )
            
    except Exception as e:
        logger.error(f"Assessment generation failed: {e}", exc_info=True)
        return AssessmentGenerateResponse(
            success=False,
            error={
                "code": "GENERATION_FAILED",
                "message": str(e)
            },
            metadata={"case_id": request.case_id}
        )


@router.get("/health")
async def health_check():
    """
    Health check for assessment service.
    
    **Example Response:**
    ```json
    {
        "status": "healthy",
        "service": "Assessment"
    }
    ```
    """
    try:
        # Quick check that we can create the tool
        tool = get_assessment_tool()
        return {
            "status": "healthy",
            "service": "Assessment",
            "tool_available": tool is not None
        }
    except Exception as e:
        logger.error(f"Assessment health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "Assessment",
            "error": str(e)
        }
