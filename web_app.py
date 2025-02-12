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

def process_response(response: Union[str, dict]) -> str:
    """Process response from AgentLite to ensure it's in string format."""
    print(f"Processing response: {response}")  # Add logging
    if isinstance(response, dict):
        # Handle case presentation
        if "case_presentation" in response:
            return response["case_presentation"]
        # Handle error messages
        if "error" in response:
            return f"Error: {response['error']}"
        # Handle feedback
        if "feedback" in response:
            return response["feedback"]
        # Handle other dictionary responses
        return json.dumps(response)
    return str(response)

async def stream_response(response_text: str) -> AsyncGenerator[str, None]:
    """Stream a response text chunk by chunk."""
    try:
        # Clean and process the response text
        response_text = process_response(response_text)
        
        # Split response into reasonable chunks (e.g., by sentences or fixed length)
        chunks = response_text.split('. ')
        for chunk in chunks:
            if chunk:
                # Add period back if it was removed by split
                chunk = chunk + ('.' if not chunk.endswith('.') else '')
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.1)  # Add a small delay between chunks
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_msg = f"Error streaming response: {str(e)}\n{traceback.format_exc()}"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        yield "data: [DONE]\n\n"

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
        
        return StreamingResponse(
            stream_response(initial_case),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Error starting case: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Add logging
        return StreamingResponse(
            stream_response(error_msg),
            media_type="text/event-stream"
        )

@app.post("/chat")
async def chat(request: Request, message: str = Form(...), session_id: str = Form(...)):
    try:
        tutor = tutors.get(session_id)
        if not tutor:
            return StreamingResponse(
                stream_response("Session not found. Please start a new case."),
                media_type="text/event-stream"
            )
        
        # Handle special commands
        if message.lower().strip() == "new case":
            initial_case = tutor.start_new_case()
            return StreamingResponse(
                stream_response(initial_case),
                media_type="text/event-stream"
            )
        
        # Create a task package for the manager agent
        task = TaskPackage(
            instruction=message,
            task_creator=tutor.id
        )
        
        # Let the manager agent handle the routing
        response = tutor(task)
        
        return StreamingResponse(
            stream_response(response),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}\n{traceback.format_exc()}"
        return StreamingResponse(
            stream_response(error_msg),
            media_type="text/event-stream"
        )

@app.post("/reset")
async def reset(request: Request, session_id: str = Form(...)):
    try:
        tutor = tutors.get(session_id)
        if tutor:
            tutor.reset()
        return StreamingResponse(
            stream_response("Session reset. Click 'Start New Case' to begin."),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Error resetting session: {str(e)}\n{traceback.format_exc()}"
        return StreamingResponse(
            stream_response(error_msg),
            media_type="text/event-stream"
        )