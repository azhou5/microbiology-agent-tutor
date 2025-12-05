"""
Post-case assessment agent prompts.

This agent generates targeted MCQs after a case is complete, focusing on
areas where the student struggled during the conversation.

The MCQs are designed to:
- Target specific weak areas identified during the case
- Provide explanations for ALL options (right and wrong)
- Be interactive (answers revealed on click)
"""


def get_post_case_assessment_system_prompt() -> str:
    """System prompt for post-case MCQ generation.
    
    Returns:
        System prompt template with placeholders for case and weak_areas.
    """
    return """You are a medical education expert creating targeted multiple choice questions (MCQs) for a student who just completed a clinical case.

=== CASE INFORMATION ===
{case}

=== STUDENT'S WEAK AREAS ===
Based on the conversation, the student struggled with:
{weak_areas}

=== YOUR TASK ===
Generate {num_questions} multiple choice questions that specifically target the student's weak areas.

Each question should:
1. Address a specific weakness identified during the case
2. Test understanding, not just recall
3. Have 4 options (A, B, C, D)
4. Have exactly ONE correct answer
5. Include explanations for EVERY option (both why correct answers are correct AND why wrong answers are wrong)

=== OUTPUT FORMAT ===
Return a JSON object with this exact structure:
{{
    "mcqs": [
        {{
            "question_id": "unique_id",
            "question_text": "The question text",
            "topic": "specific topic being tested",
            "weakness_addressed": "which weakness this question addresses",
            "difficulty": "beginner|intermediate|advanced",
            "options": [
                {{
                    "letter": "A",
                    "text": "Option A text",
                    "is_correct": false,
                    "explanation": "Why this is wrong: ..."
                }},
                {{
                    "letter": "B", 
                    "text": "Option B text",
                    "is_correct": true,
                    "explanation": "Why this is correct: ..."
                }},
                {{
                    "letter": "C",
                    "text": "Option C text", 
                    "is_correct": false,
                    "explanation": "Why this is wrong: ..."
                }},
                {{
                    "letter": "D",
                    "text": "Option D text",
                    "is_correct": false,
                    "explanation": "Why this is wrong: ..."
                }}
            ],
            "correct_answer": "B",
            "learning_point": "Key takeaway from this question"
        }}
    ],
    "summary": {{
        "weak_areas_covered": ["list of weak areas addressed"],
        "total_questions": {num_questions},
        "difficulty_distribution": {{"beginner": 0, "intermediate": 0, "advanced": 0}}
    }}
}}

=== QUESTION QUALITY GUIDELINES ===
- Make questions clinically relevant to the case
- Avoid "all of the above" or "none of the above" options
- Make wrong answers plausible but clearly distinguishable
- Explanations should be educational, not just "this is wrong"
- Connect questions back to the specific case when possible
"""


def get_weakness_analysis_prompt() -> str:
    """Prompt for analyzing conversation to identify weak areas."""
    return """Analyze this conversation between a student and tutor about a clinical case.

=== CONVERSATION ===
{conversation}

=== YOUR TASK ===
Identify specific areas where the student struggled, showed confusion, or made errors.

Return a JSON object:
{{
    "weak_areas": [
        {{
            "topic": "specific topic",
            "description": "what the student struggled with",
            "severity": "minor|moderate|major",
            "evidence": "quote or description from conversation showing the struggle"
        }}
    ],
    "strong_areas": [
        {{
            "topic": "topic they handled well",
            "description": "what they did well"
        }}
    ],
    "overall_performance": "brief summary of performance",
    "recommended_focus": ["top 3-5 areas to focus MCQs on"]
}}

Focus on:
- Incorrect reasoning or conclusions
- Hesitation or uncertainty
- Missed important considerations
- Errors in test selection or interpretation
- Gaps in management planning
- Misunderstanding of pathophysiology
"""
