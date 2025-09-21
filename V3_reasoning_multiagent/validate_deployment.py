#!/usr/bin/env python3
"""
Deployment validation script for MicroTutor
Tests API connectivity before main application starts
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
# Try to load from the .env file, but don't fail if it doesn't exist (Render uses environment variables)
env_file_path = os.path.join(os.path.dirname(__file__), 'dot_env_microtutor.txt')
if os.path.exists(env_file_path):
    load_dotenv(dotenv_path=env_file_path)
else:
    print("ℹ️  No .env file found, using environment variables (expected on Render)")
    load_dotenv()  # Load from system environment variables

def test_api_connection():
    """Test the configured API connection"""
    print("🔍 Validating API configuration...")
    
    # Check which API is configured
    use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    print(f"📋 Configuration:")
    print(f"   USE_AZURE_OPENAI: {use_azure}")
    print(f"   Azure endpoint: {'✅ Set' if azure_endpoint else '❌ Missing'}")
    print(f"   Azure API key: {'✅ Set' if azure_api_key else '❌ Missing'}")
    print(f"   OpenAI API key: {'✅ Set' if openai_api_key else '❌ Missing'}")
    
    # Validate credentials are present
    if use_azure:
        if not azure_endpoint or not azure_api_key:
            print("❌ ERROR: Azure OpenAI selected but credentials missing!")
            return False
        print("✅ Azure OpenAI credentials found")
    else:
        if not openai_api_key:
            print("❌ ERROR: Personal OpenAI selected but API key missing!")
            return False
        print("✅ Personal OpenAI API key found")
    
    # Test actual API call
    try:
        print("🧪 Testing API connection...")
        
        if use_azure:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
            )
            model_name = "o4-mini-0416"
            deployment_name = os.getenv("AZURE_OPENAI_O4_MINI_DEPLOYMENT", "o4-mini-0416")
        else:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            model_name = "gpt-5-mini-2025-08-07"
            deployment_name = model_name
        
        # Make a simple test call
        start_time = time.time()
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'API test successful' and nothing else."}
            ],
            max_tokens=10,
            temperature=0
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        response_text = response.choices[0].message.content.strip()
        
        if "API test successful" in response_text:
            print(f"✅ API test successful!")
            print(f"   Model: {model_name}")
            print(f"   Response time: {response_time:.2f}s")
            print(f"   Response: {response_text}")
            return True
        else:
            print(f"❌ Unexpected response: {response_text}")
            return False
            
    except Exception as e:
        print(f"❌ API test failed: {str(e)}")
        return False

def main():
    """Main validation function"""
    print("=" * 60)
    print("🚀 MicroTutor Deployment Validation")
    print("=" * 60)
    
    # Test API connection
    if test_api_connection():
        print("\n✅ Deployment validation PASSED!")
        print("🎉 Ready to start MicroTutor application")
        sys.exit(0)
    else:
        print("\n❌ Deployment validation FAILED!")
        print("💥 Cannot start application - fix configuration issues")
        sys.exit(1)

if __name__ == "__main__":
    main()
