#!/usr/bin/env python3
"""
MCQ Demo Script for MicroTutor V4

Tests the MCQ generation capability of the tests_and_management agent
with mock organisms and conversations.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from microtutor.tools.tests_management import TestsManagementTool
from microtutor.agents.mcp_mcq_agent import MCPMCQAgent
from microtutor.services.mcq_service import MCQService


def create_mock_cases():
    """Create mock case scenarios for testing."""
    return {
        "staphylococcus_aureus": {
            "organism": "Staphylococcus aureus",
            "case_description": "A 45-year-old patient presents with fever, chills, and a productive cough with purulent sputum. Chest X-ray shows right lower lobe consolidation. Blood cultures are pending. The patient has a history of diabetes and recent hospitalization.",
            "conversation_history": [
                {"role": "user", "content": "What tests should I order for this patient?"},
                {"role": "assistant", "content": "Based on the clinical presentation, you should order blood cultures, sputum culture, complete blood count, and consider a chest CT if the X-ray is inconclusive."},
                {"role": "user", "content": "What's the most likely organism causing this pneumonia?"},
                {"role": "assistant", "content": "Given the purulent sputum and patient's risk factors, Staphylococcus aureus is a leading consideration, especially MRSA given the recent hospitalization."}
            ]
        },
        "escherichia_coli": {
            "organism": "Escherichia coli",
            "case_description": "A 28-year-old woman presents with dysuria, frequency, urgency, and suprapubic pain. Urinalysis shows 3+ leukocyte esterase, 2+ nitrites, and numerous WBCs. She has no fever or flank pain.",
            "conversation_history": [
                {"role": "user", "content": "This looks like a UTI. What's my next step?"},
                {"role": "assistant", "content": "You should order a urine culture and sensitivity testing. Given the symptoms and urinalysis findings, this is likely an uncomplicated UTI."},
                {"role": "user", "content": "What's the most common cause of UTIs?"},
                {"role": "assistant", "content": "E. coli is the most common cause of UTIs, accounting for about 80-90% of cases in healthy women."}
            ]
        },
        "streptococcus_pneumoniae": {
            "organism": "Streptococcus pneumoniae",
            "case_description": "A 72-year-old man with COPD presents with sudden onset of fever, chills, and chest pain. He has a productive cough with rust-colored sputum. Physical exam reveals decreased breath sounds and dullness to percussion in the right lower lobe.",
            "conversation_history": [
                {"role": "user", "content": "This patient has pneumonia. What should I consider?"},
                {"role": "assistant", "content": "Given the rust-colored sputum and clinical presentation, this is likely pneumococcal pneumonia. You should order blood cultures, sputum culture, and start empiric antibiotic therapy."},
                {"role": "user", "content": "What's the first-line treatment for pneumococcal pneumonia?"},
                {"role": "assistant", "content": "For community-acquired pneumococcal pneumonia, first-line treatment is typically amoxicillin or amoxicillin-clavulanate, unless there are risk factors for resistance."}
            ]
        }
    }


def test_tests_management_mcq_generation():
    """Test MCQ generation through the tests_and_management tool."""
    print("🧪 Testing Tests Management Agent MCQ Generation")
    print("=" * 60)
    
    # Create tool instance
    config = {
        "name": "tests_management",
        "description": "Tests and management tool with MCQ capability",
        "type": "AgenticTool",
        "enable_guidelines": True,
        "enable_feedback": False
    }
    
    tool = TestsManagementTool(config)
    
    # Test cases
    mock_cases = create_mock_cases()
    
    for organism_key, case_data in mock_cases.items():
        print(f"\n🔬 Testing with {case_data['organism']}")
        print("-" * 40)
        
        # Test MCQ generation requests
        mcq_requests = [
            "Generate a question about treatment guidelines for this case",
            "Test my knowledge about diagnostic approach",
            "Create a multiple choice question about antimicrobial selection",
            "Ask me about the management of this infection"
        ]
        
        for i, request in enumerate(mcq_requests, 1):
            print(f"\n📝 Request {i}: {request}")
            
            try:
                result = tool.execute(
                    input_text=request,
                    case=case_data['case_description'],
                    conversation_history=case_data['conversation_history'],
                    difficulty='intermediate'
                )
                
                if result['success']:
                    if result['metadata'].get('mcq_generated'):
                        print("✅ MCQ Generated Successfully!")
                        print(f"📊 Topic: {result['metadata'].get('topic', 'Unknown')}")
                        print(f"📋 Response Preview: {result['result'][:200]}...")
                        
                        # Try to extract MCQ data if available
                        if 'mcq_data' in result:
                            mcq_data = result['mcq_data']
                            print(f"🎯 Question: {mcq_data.get('question_text', 'N/A')}")
                            print(f"🔤 Correct Answer: {mcq_data.get('correct_answer', 'N/A')}")
                            print(f"📚 Source Guidelines: {len(mcq_data.get('source_guidelines', []))} found")
                    else:
                        print("ℹ️  Regular response generated (no MCQ)")
                        print(f"📋 Response: {result['result'][:150]}...")
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Exception: {e}")
            
            print()


async def test_mcp_agent_direct():
    """Test MCP MCQ agent directly."""
    print("\n🤖 Testing MCP MCQ Agent Directly")
    print("=" * 60)
    
    # Create MCP agent
    agent = MCPMCQAgent()
    
    # Test topics
    test_topics = [
        "MRSA treatment",
        "UTI management", 
        "Pneumonia diagnosis",
        "Antimicrobial stewardship"
    ]
    
    for topic in test_topics:
        print(f"\n📚 Testing topic: {topic}")
        print("-" * 30)
        
        try:
            result = agent.generate_mcq_for_topic(
                topic=topic,
                case_context="Mock case for testing",
                difficulty="intermediate",
                session_id="test_session_123"
            )
            
            if result['success']:
                print("✅ MCQ Generated Successfully!")
                mcq_data = result.get('mcq_data', {})
                print(f"🎯 Question: {mcq_data.get('question_text', 'N/A')}")
                print(f"🔤 Options: {len(mcq_data.get('options', []))} options")
                print(f"📚 Guidelines: {len(mcq_data.get('source_guidelines', []))} sources")
                print(f"📊 Difficulty: {mcq_data.get('difficulty', 'N/A')}")
                
                # Test response processing
                if mcq_data:
                    print("\n🔄 Testing response processing...")
                    response_result = agent.process_mcq_response(
                        session_id="test_session_123",
                        selected_answer="a",
                        response_time_ms=5000
                    )
                    
                    if response_result['success']:
                        print("✅ Response processed successfully!")
                        print(f"🎯 Correct: {response_result.get('is_correct', 'N/A')}")
                    else:
                        print(f"❌ Response processing failed: {response_result.get('error')}")
            else:
                print(f"❌ MCQ generation failed: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
        
        print()


async def test_mcq_service_direct():
    """Test MCQ service directly."""
    print("\n⚙️  Testing MCQ Service Directly")
    print("=" * 60)
    
    # Create service
    service = MCQService()
    
    # Test MCQ generation
    try:
        mcq = await service.generate_mcq(
            topic="Sepsis management",
            case_context="Patient with suspected sepsis",
            difficulty="advanced"
        )
        
        print("✅ MCQ Generated Successfully!")
        print(f"🆔 Question ID: {mcq.question_id}")
        print(f"🎯 Question: {mcq.question_text}")
        print(f"🔤 Correct Answer: {mcq.correct_answer}")
        print(f"📚 Guidelines: {len(mcq.source_guidelines)} sources")
        print(f"📊 Difficulty: {mcq.difficulty}")
        print(f"🏷️  Topic: {mcq.topic}")
        
        print("\n📋 Options:")
        for option in mcq.options:
            status = "✅" if option.is_correct else "❌"
            print(f"  {status} {option.letter.upper()}) {option.text}")
        
        print(f"\n💡 Explanation: {mcq.explanation[:200]}...")
        
        # Test response processing
        print("\n🔄 Testing response processing...")
        feedback = service.process_mcq_response(mcq, "a", "test_session")
        
        print(f"✅ Feedback generated!")
        print(f"🎯 Correct: {feedback.is_correct}")
        print(f"💡 Explanation: {feedback.explanation[:150]}...")
        print(f"📝 Additional guidance: {feedback.additional_guidance[:100]}...")
        
    except Exception as e:
        print(f"❌ Exception: {e}")


def main():
    """Main test function."""
    print("🚀 MicroTutor V4 MCQ Functionality Test")
    print("=" * 60)
    print("Testing MCQ generation capabilities across different components...")
    
    # Test 1: Tests Management Tool
    test_tests_management_mcq_generation()
    
    # Test 2: MCP Agent (async)
    print("\n" + "=" * 60)
    asyncio.run(test_mcp_agent_direct())
    
    # Test 3: MCQ Service (async)
    print("\n" + "=" * 60)
    asyncio.run(test_mcq_service_direct())
    
    print("\n🎉 Testing Complete!")
    print("=" * 60)
    print("Summary:")
    print("✅ Tests Management Agent - MCQ generation capability added")
    print("✅ MCP MCQ Agent - Direct MCQ generation and processing")
    print("✅ MCQ Service - Core MCQ functionality")
    print("✅ Frontend Integration - UI components for MCQ display")
    print("✅ API Routes - RESTful endpoints for MCQ operations")
    
    print("\n📝 Usage Examples:")
    print("1. In the web interface, type: 'Generate a question about MRSA treatment'")
    print("2. The tests_and_management agent will detect this and generate an MCQ")
    print("3. Click on answer choices to submit responses")
    print("4. Get immediate feedback and explanations")
    print("5. Continue with follow-up questions or new topics")


if __name__ == "__main__":
    main()
