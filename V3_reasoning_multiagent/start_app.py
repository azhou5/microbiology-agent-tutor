#!/usr/bin/env python3
"""
Startup script for MicroTutor on Render
Runs validation before starting the main application
"""

import os
import sys
import subprocess
import time

def run_validation():
    """Run the deployment validation script"""
    print("🔍 Running deployment validation...")
    
    try:
        # Run the validation script
        result = subprocess.run([
            sys.executable, "validate_deployment.py"
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        # Print validation output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running validation: {str(e)}")
        return False

def start_application():
    """Start the main application"""
    print("🚀 Starting MicroTutor application...")
    
    try:
        # Import and run the main app
        from app import app
        
        # Get port from environment (Render sets this)
        port = int(os.getenv("PORT", 8000))
        
        print(f"🌐 Starting server on port {port}")
        print(f"🔧 Using {os.getenv('USE_AZURE_OPENAI', 'false')} for Azure OpenAI")
        
        # Use Flask's built-in development server for local development
        # For production, use Gunicorn: gunicorn -w 4 -b 0.0.0.0:8000 app:app
        app.run(host="0.0.0.0", port=port, debug=False)
        
    except Exception as e:
        print(f"❌ Error starting application: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main startup function"""
    print("=" * 60)
    print("🎓 MicroTutor - Starting Up")
    print("=" * 60)
    
    # Step 1: Run validation
    if not run_validation():
        print("\n💥 Validation failed - stopping deployment")
        sys.exit(1)
    
    print("\n✅ Validation passed - starting application")
    time.sleep(1)  # Brief pause for readability
    
    # Step 2: Start the application
    start_application()

if __name__ == "__main__":
    main()
