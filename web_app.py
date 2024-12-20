from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import os
from dotenv import load_dotenv
from tutor import MedicalMicrobiologyTutor
import json
import asyncio
from typing import AsyncGenerator
os.chdir('/Users/andrewzhou/Documents/Clinical Research/Medical_Microbiology_Tutor/Workspace/microbiology_agent_tutor')
# Load environment variables
load_dotenv()

# Verify required environment variables
required_vars = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store tutor instances for different sessions
tutors = {}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

async def stream_response(response_text: str) -> AsyncGenerator[str, None]:
    """Stream a response text chunk by chunk."""
    try:
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
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

@app.post("/start_case")
async def start_case(request: Request):
    try:
        tutor = MedicalMicrobiologyTutor()
        session_id = "test_session"  # In a real app, generate unique session IDs
        tutors[session_id] = tutor
        initial_case = tutor.start_new_case()
        return StreamingResponse(
            stream_response(initial_case),
            media_type="text/event-stream"
        )
    except Exception as e:
        return StreamingResponse(
            stream_response(f"Error starting case: {str(e)}"),
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
        
        response = tutor.handle_input(message)
        return StreamingResponse(
            stream_response(response),
            media_type="text/event-stream"
        )
    except Exception as e:
        return StreamingResponse(
            stream_response(f"Error processing message: {str(e)}"),
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
        return StreamingResponse(
            stream_response(f"Error resetting session: {str(e)}"),
            media_type="text/event-stream"
        )