#!/usr/bin/env python3
"""
Comprehensive LLM testing script with menu system
Tests both Azure OpenAI and Personal OpenAI APIs
"""

import os
import sys
import time
from dotenv import load_dotenv
from LLM_utils import run_LLM

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'dot_env_microtutor.txt'))

def get_input_prompt():
    """Get the complex medical microbiology input prompt for testing"""
    return """Please analyze the following complex medical microbiology case and provide a comprehensive differential diagnosis:

A 45-year-old patient presents with:
- High fever (39.5°C) for 3 days
- Severe headache and neck stiffness
- Photophobia and altered mental status
- Petechial rash on trunk and extremities
- Recent travel to sub-Saharan Africa
- No recent antibiotic use
- CSF analysis shows: WBC 1200/μL (90% neutrophils), glucose 25 mg/dL, protein 180 mg/dL
- Gram stain shows gram-negative diplococci

Please provide:
1. Most likely diagnosis with reasoning
2. Three differential diagnoses with supporting evidence
3. Recommended diagnostic tests
4. Treatment approach
5. Prognosis and complications to monitor

Be thorough and educational in your response."""

def get_system_prompt():
    """Get the system prompt for medical microbiology testing"""
    return "You are an expert medical microbiologist and educator. Provide detailed, accurate, and educational responses."

def print_speed_comparison(results, test_type):
    """Print speed comparison results"""
    print("\n" + "="*60)
    print(f"📊 SPEED COMPARISON - {test_type}")
    print("="*60)
    
    successful_results = [r for r in results if r['success']]
    if len(successful_results) >= 2:
        fastest = min(successful_results, key=lambda x: x['time'])
        slowest = max(successful_results, key=lambda x: x['time'])
        speed_improvement = ((slowest['time'] - fastest['time']) / slowest['time']) * 100
        
        print(f"🏆 Fastest: {fastest['model']} ({fastest['time']:.2f}s)")
        print(f"🐌 Slowest: {slowest['model']} ({slowest['time']:.2f}s)")
        print(f"⚡ Speed Improvement: {speed_improvement:.1f}%")
        
        print(f"\n📈 Detailed Comparison:")
        for result in successful_results:
            print(f"  {result['model']}: {result['time']:.2f}s, {result['length']} chars")
    elif len(successful_results) == 1:
        result = successful_results[0]
        print(f"✅ Single Result: {result['model']} ({result['time']:.2f}s, {result['length']} chars)")
    else:
        print("❌ No successful results for comparison")

def test_azure_openai():
    """Test Azure OpenAI API"""
    print("="*60)
    print("Testing Azure OpenAI API")
    print("="*60)
    
    system_prompt = get_system_prompt()
    input_prompt = get_input_prompt()
    
    models_to_test = ["gpt-4o-1120", "o4-mini-0416"]  # Azure models
    results = []
    
    for model in models_to_test:
        print(f"\nTesting Azure model: {model}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            response, cost_summary = run_LLM(
                system_prompt, 
                input_prompt, 
                1, 
                model=model, 
                azure_openai=True,  # Use Azure OpenAI
                log_file="azure_test.log"
            )
            end_time = time.time()
            response_time = end_time - start_time
            
            if response:
                results.append({
                    'model': model,
                    'time': response_time,
                    'length': len(response),
                    'cost': cost_summary,
                    'success': True
                })
                print(f"✅ SUCCESS: {model}")
                print(f"⏱️  Response Time: {response_time:.2f} seconds")
                print(f"📊 Response Length: {len(response)} characters")
                print(f"💰 Cost: {cost_summary}")
                print(f"📝 Response Preview: {response[:200]}...")
            else:
                results.append({
                    'model': model,
                    'time': None,
                    'length': 0,
                    'cost': None,
                    'success': False
                })
                print(f"❌ FAILED: {model} - No response received")
                
        except Exception as e:
            results.append({
                'model': model,
                'time': None,
                'length': 0,
                'cost': None,
                'success': False,
                'error': str(e)
            })
            print(f"❌ ERROR: {model} - {str(e)}")
    
    # Print speed comparison
    print_speed_comparison(results, "Azure OpenAI")

def test_personal_openai():
    """Test Personal OpenAI API"""
    print("\n" + "="*60)
    print("Testing Personal OpenAI API")
    print("="*60)
    
    # Check if personal API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found - skipping personal OpenAI tests")
        print("To test personal OpenAI, add your API key to the .env file:")
        print("OPENAI_API_KEY=your_personal_openai_api_key_here")
        return
    
    system_prompt = get_system_prompt()
    input_prompt = get_input_prompt()
    
    models_to_test = ["o4-mini-2025-04-16", "gpt-5-2025-08-07"]  # Personal OpenAI models
    results = []
    
    for model in models_to_test:
        print(f"\nTesting Personal model: {model}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            response, cost_summary = run_LLM(
                system_prompt, 
                input_prompt, 
                1, 
                model=model, 
                azure_openai=False,  # Use personal OpenAI
                log_file="personal_test.log"
            )
            end_time = time.time()
            response_time = end_time - start_time
            
            if response:
                results.append({
                    'model': model,
                    'time': response_time,
                    'length': len(response),
                    'cost': cost_summary,
                    'success': True
                })
                print(f"✅ SUCCESS: {model}")
                print(f"⏱️  Response Time: {response_time:.2f} seconds")
                print(f"📊 Response Length: {len(response)} characters")
                print(f"💰 Cost: {cost_summary}")
                print(f"📝 Response Preview: {response[:200]}...")
            else:
                results.append({
                    'model': model,
                    'time': None,
                    'length': 0,
                    'cost': None,
                    'success': False
                })
                print(f"❌ FAILED: {model} - No response received")
                
        except Exception as e:
            results.append({
                'model': model,
                'time': None,
                'length': 0,
                'cost': None,
                'success': False,
                'error': str(e)
            })
            print(f"❌ ERROR: {model} - {str(e)}")
    
    # Print speed comparison
    print_speed_comparison(results, "Personal OpenAI")

def test_specific_model():
    """Test a specific model with custom input"""
    print("\n" + "="*60)
    print("Test Specific Model")
    print("="*60)
    
    # Get user input
    print("\nAvailable options:")
    print("1. Azure OpenAI models: gpt-4o-1120, o4-mini-0416")
    print("2. Personal OpenAI models: gpt-4o, gpt-4o-mini, gpt-3.5-turbo, gpt-4")
    
    model = input("\nEnter model name: ").strip()
    if not model:
        print("❌ No model specified")
        return
    
    use_azure = input("Use Azure OpenAI? (y/n, default: y): ").strip().lower()
    azure_openai = use_azure != 'n'
    
    custom_prompt = input("Enter custom prompt (or press Enter for default): ").strip()
    if not custom_prompt:
        custom_prompt = "What is the capital of France? Answer in one sentence."
    
    print(f"\nTesting {model} with {'Azure' if azure_openai else 'Personal'} OpenAI")
    print(f"Prompt: {custom_prompt}")
    print("-" * 40)
    
    try:
        response, cost_summary = run_LLM(
            system_prompt="You are a helpful assistant",
            input_prompt=custom_prompt,
            iterations=1,
            model=model,
            azure_openai=azure_openai,
            log_file="custom_test.log"
        )
        
        if response:
            print(f"✅ SUCCESS: {model}")
            print(f"Response: {response}")
            print(f"Cost: {cost_summary}")
        else:
            print(f"❌ FAILED: {model} - No response received")
            
    except Exception as e:
        print(f"❌ ERROR: {model} - {str(e)}")

def show_menu():
    """Display the main menu"""
    print("\n" + "="*60)
    print("🚀 LLM Testing Suite")
    print("="*60)
    print("1. Test Azure OpenAI (gpt-4o-1120, o4-mini-0416)")
    print("2. Test Personal OpenAI (o4-mini-2025-04-16, gpt-4o-mini)")
    print("3. Test Specific Model (custom input)")
    print("4. Run All Tests")
    print("5. Exit")
    print("="*60)

def run_all_tests():
    """Run all available tests"""
    print("🚀 Running all available tests...")
    
    # Test Azure OpenAI
    test_azure_openai()
    
    # Test Personal OpenAI
    test_personal_openai()
    
    print("\n" + "="*60)
    print("🎉 All tests complete!")
    print("="*60)

def main():
    """Main function with menu system"""
    while True:
        show_menu()
        
        try:
            choice = input("\nEnter your choice (1-5): ").strip()
            
            if choice == '1':
                test_azure_openai()
            elif choice == '2':
                test_personal_openai()
            elif choice == '3':
                test_specific_model()
            elif choice == '4':
                run_all_tests()
            elif choice == '5':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-5.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        # Ask if user wants to continue
        if choice in ['1', '2', '3', '4']:
            continue_test = input("\nPress Enter to continue or 'q' to quit: ").strip().lower()
            if continue_test == 'q':
                print("👋 Goodbye!")
                break

if __name__ == "__main__":
    main()
