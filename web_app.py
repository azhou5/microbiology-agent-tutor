from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import os
from dotenv import load_dotenv
from tutor import MedicalMicrobiologyTutor
from agentlite.commons import TaskPackage
import json
import asyncio
from typing import AsyncGenerator, Union
import traceback
os.chdir('/Users/andrewzhou/Documents/Clinical Research/Medical_Microbiology_Tutor/Workspace/microbiology_agent_tutor')
# Load environment variables
load_dotenv()

# Verify required environment variables
required_vars = [
    "AZURE_OPENAI_API_KEY", 
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT_NAME"
]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Validate Azure OpenAI deployment configuration
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
if not deployment_name:
    raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME must be set to your Azure OpenAI deployment name")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store tutor instances for different sessions
tutors = {}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

def process_response(response):
    """Process the response and add appropriate speaker labels."""
    try:
        # Log the response for debugging
        print(f"Processing response: {response}")
        
        if isinstance(response, dict):
            # Handle case presentation
            if "case_presentation" in response:
                return f"Doctor: {response['case_presentation']}"
            
            # Handle error messages
            if "error" in response:
                return f"Tutor: Error: {response['error']}"
            
            # Handle feedback
            if "feedback" in response:
                return f"Tutor: {response['feedback']}"
            
            # Handle responses with agent and response fields
            if "response" in response and "agent" in response:
                agent = response["agent"]
                content = response["response"]
                
                if agent == "patient":
                    return f"Patient: {content}"
                elif agent == "case_presenter":
                    return f"Doctor: {content}"
                elif agent == "clinical_reasoning":
                    return f"Tutor: {content}"
                elif agent == "knowledge_assessment":
                    return f"Tutor: {content}"
            
            # If no specific handling, convert dict to string
            return f"Tutor: {json.dumps(response)}"
            
        elif isinstance(response, str):
            # Default to Tutor for string responses
            return f"Tutor: {response}"
        else:
            # Convert any other type to string with Tutor prefix
            return f"Tutor: {str(response)}"
            
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        return f"Tutor: Error processing response: {str(e)}"

def stream_response(response):
    """Stream the response while maintaining speaker labels."""
    if isinstance(response, dict):
        agent = response.get("agent", "")
        content = response.get("response", "")
        
        prefix = ""
        if agent == "patient":
            prefix = "Patient: "
        elif agent == "case_presenter":
            prefix = "Doctor: "
        elif agent == "knowledge_assessment":
            prefix = "Tutor: "
            
        yield prefix
        for chunk in content:
            yield chunk
    else:
        yield "Tutor: "
        for chunk in str(response):
            yield chunk

@app.post("/start_case")
async def start_case(request: Request):
    try:
        tutor = MedicalMicrobiologyTutor()
        session_id = "test_session"  # In a real app, generate unique session IDs
        tutors[session_id] = tutor
        
        # Get the initial case
        initial_case = tutor.start_new_case()
        
        # Ensure we have a response to stream
        if not initial_case:
            initial_case = "Error: No case was generated. Please try again."
        
        # Log the response for debugging
        print(f"Initial case response: {initial_case}")
        
        async def generate_events():
            try:
                # Process the response
                processed_response = process_response(initial_case)
                # Send the processed response as a data event
                yield f"data: {json.dumps({'chunk': processed_response})}\n\n"
                # Send the completion event
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_msg = f"Error streaming response: {str(e)}"
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Error starting case: {str(e)}\n{traceback.format_exc()}"
        async def error_event():
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            error_event(),
            media_type="text/event-stream"
        )

@app.post("/chat")
async def chat(request: Request, message: str = Form(...), session_id: str = Form(...)):
    try:
        tutor = tutors.get(session_id)
        if not tutor:
            async def session_error():
                error_msg = "Session not found. Please start a new case."
                yield f"data: {json.dumps({'chunk': f'Tutor: {error_msg}'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                session_error(),
                media_type="text/event-stream"
            )
        
        # Handle special commands
        if message.lower().strip() == "new case":
            initial_case = tutor.start_new_case()
            async def new_case_events():
                processed_response = process_response(initial_case)
                yield f"data: {json.dumps({'chunk': processed_response})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                new_case_events(),
                media_type="text/event-stream"
            )
        
        # Create a task package for the manager agent
        task = TaskPackage(
            instruction=message,
            task_creator=tutor.id
        )
        
        # Let the manager agent handle the routing
        response = tutor(task)
        
        # Log the response for debugging
        print(f"Raw response from tutor: {response}")
        
        async def generate_events():
            try:
                # Process the response
                processed_response = process_response(response)
                print(f"Processed response: {processed_response}")  # Debug log
                # Send the processed response as a data event
                yield f"data: {json.dumps({'chunk': processed_response})}\n\n"
                # Send the completion event
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_msg = f"Error streaming response: {str(e)}"
                print(f"Error in generate_events: {error_msg}")  # Debug log
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}\n{traceback.format_exc()}"
        print(f"Error in chat endpoint: {error_msg}")  # Debug log
        async def error_event():
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            error_event(),
            media_type="text/event-stream"
        )

@app.post("/reset")
async def reset(request: Request, session_id: str = Form(...)):
    try:
        tutor = tutors.get(session_id)
        if tutor:
            tutor.reset()
        async def reset_events():
            message = "Session reset. Click 'Start New Case' to begin."
            yield f"data: {json.dumps({'chunk': f'Tutor: {message}'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            reset_events(),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Error resetting session: {str(e)}\n{traceback.format_exc()}"
        print(f"Error in reset endpoint: {error_msg}")  # Debug log
        async def error_event():
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            error_event(),
            media_type="text/event-stream"
        )