from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import os
import json
import asyncio
from typing import AsyncGenerator
import traceback
import random
import time
import uuid
import threading

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

from Backend.LLM_utils import run_LLM
from Backend.case import get_case
from Backend.prompts import get_main_prompt
from Backend.revealed_info import extract_revealed_info

# Initialize FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store active sessions
sessions = {}

# Store pending revealed info extractions 
pending_info_extractions = {}

# Available organisms for case generation
AVAILABLE_ORGANISMS = [
    "staphylococcus aureus",
    "streptococcus pneumoniae",
    "escherichia coli",
    "clostridium difficile",
    "pseudomonas aeruginosa",
    "klebsiella pneumoniae",
    "candida albicans",
    "mycobacterium tuberculosis"
]



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/organisms", response_class=HTMLResponse)
async def get_organisms_page(request: Request):
    """Return a page for organism selection"""
    return templates.TemplateResponse("organism_selection.html", {
        "request": request,
        "organisms": AVAILABLE_ORGANISMS
    })

@app.get("/api/organisms")
async def get_organisms():
    """API endpoint to get a list of available organisms"""
    return AVAILABLE_ORGANISMS

@app.post("/start_case")
async def start_case(request: Request, background_tasks: BackgroundTasks, organism: str = Form(None)):
    try:
        if not organism:
            # Redirect to the organism selection page if no organism is specified
            return templates.TemplateResponse("organism_selection.html", {
                "request": request,
                "organisms": AVAILABLE_ORGANISMS
            })
            
        # Check if this is a random case request
        is_random_case = False
        if organism == "RANDOM_CASE":
            # Select a random organism
            organism = random.choice(AVAILABLE_ORGANISMS)
            is_random_case = True
            print(f"Selected random organism: {organism}")
        
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        print(f"Created new session ID: {session_id}")
        
        # Initialize a new session
        sessions[session_id] = {
            "organism": organism,
            "conversation_history": [],
            "case": get_case(organism)
        }
        
        # Generate the case
        async def generate_events():
            try:
                # Initial event
                yield f"event: start\ndata: Starting case generation for {'' if is_random_case else organism}...\n\n"
                await asyncio.sleep(0.1)
                
                # Indicate that case generation has started
                yield f"event: update\ndata: Generating case...\n\n"
                
                # Get the case and generate initial prompt
                case = sessions[session_id]["case"]
                system_prompt = get_main_prompt(case)
                
                # Initial message to start the case
                input_prompt = "Start the case with the initial presenting complaint."
                
                # Run the LLM to get the initial case presentation
                response = run_LLM(system_prompt, input_prompt, 1)
                
                # Store in session
                sessions[session_id]["system_prompt"] = system_prompt
                sessions[session_id]["conversation_history"].append({
                    "user_message": input_prompt,
                    "ai_response": response
                })
                
                # Format the response for the frontend
                formatted_response = response
                
                # Start background task for revealed info extraction
                pending_info_extractions[session_id] = {"status": "processing"}
                background_tasks.add_task(
                    extract_info_background,
                    session_id,
                    response,
                    sessions[session_id]["conversation_history"]
                )
                
                # Create a response payload with the case info
                payload = {
                    "message": formatted_response,
                    "session_id": session_id,
                    "status": "success",
                    "is_random_case": is_random_case,
                    "revealed_info_status": "processing"
                }
                
                # Send the full response payload
                yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                
            except Exception as e:
                traceback_str = traceback.format_exc()
                error_message = f"Error generating case: {str(e)}\n{traceback_str}"
                print(f"Error in generate_events: {error_message}")
                error_payload = {
                    "error": str(e),
                    "details": traceback_str,
                    "phase": "case_generation"
                }
                yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        
        return StreamingResponse(generate_events(), media_type="text/event-stream")
    except Exception as e:
        print(f"Error in start_case: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/start_case")
async def start_case_get(request: Request, organism: str = None):
    """GET version of the start_case endpoint"""
    return await start_case(request, organism=organism)

@app.post("/chat")
async def chat(request: Request, message: str = Form(...), session_id: str = Form(...)):
    try:
        print(f"Received chat request with message: '{message}' and session_id: '{session_id}'")
        
        session = sessions.get(session_id)
        if not session:
            print(f"Session '{session_id}' not found")
            return {
                "error": "Session not found. Please start a new case.",
                "chunk": "Tutor: Session not found. Please start a new case."
            }
        
        # Check if message contains a request for a new case with specific organism
        if message.lower().strip().startswith("new case"):
            print("Processing new case request")
            # Check if an organism is specified
            parts = message.lower().split("with")
            if len(parts) > 1 and parts[1].strip():
                organism = parts[1].strip()
                print(f"Starting new case with organism: {organism}")
            else:
                # Default organism if none specified
                organism = "staphylococcus aureus"
                print(f"Starting new case with default organism: {organism}")
                
            # Reset session and create new case
            session["organism"] = organism
            session["conversation_history"] = []
            session["case"] = get_case(organism)
            
            # Generate initial case presentation
            system_prompt = get_main_prompt(session["case"])
            input_prompt = "Start the case with the initial presenting complaint."
            response = run_LLM(system_prompt, input_prompt, 1)
            
            # Store in session
            session["system_prompt"] = system_prompt
            session["conversation_history"].append({
                "user_message": input_prompt,
                "ai_response": response
            })
            
            # Extract any revealed information
            revealed_info = extract_revealed_info(response, session["conversation_history"])
            
            # Process the response
            processed_response = process_response(response)
            
            # Return JSON response
            return {
                "chunk": processed_response,
                "revealed_info": revealed_info,
                "organism": organism
            }
        
        # Process a regular chat message
        system_prompt = session["system_prompt"]
        
        # Build conversation history context
        conversation_context = ""
        for item in session["conversation_history"]: 
            if "user_message" in item and "ai_response" in item:
                user_msg = item["user_message"]
                ai_resp = item["ai_response"]
                conversation_context += f"User: {user_msg}\nTutor: {ai_resp}\n\n"
        
        # Combine conversation history with current message
        full_prompt = f"{conversation_context}User: {message}\nTutor:"
        print(f"Sending full prompt with conversation history {full_prompt}")
        
        # Run the LLM to get the response
        response = run_LLM(system_prompt, full_prompt, 1, "o3-mini")
        
        # Handle None or empty response from LLM
        if response is None or response == "":
            print("Received empty response from LLM, providing error message instead")
            response = "Tutor: I'm sorry, I couldn't process that request. Please try asking a shorter or simpler question."
        
        # Store in conversation history
        session["conversation_history"].append({
            "user_message": message,
            "ai_response": response
        })
        
        # Extract revealed information
        revealed_info = extract_revealed_info(response, session["conversation_history"])
        
        # Create response data
        response_data = {
            'chunk': response,
            'revealed_info': revealed_info
        }
        
        # Return JSON response
        return response_data
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        print(f"Error in chat endpoint: {error_msg}")
        print(traceback.format_exc())
        return {
            "error": error_msg,
            "chunk": f"Tutor: An error occurred while processing your message. Please try again."
        }

@app.get("/chat_alt")
async def chat_alt(request: Request, background_tasks: BackgroundTasks):
    try:
        # Extract message and session ID from query parameters
        message = request.query_params.get("message", "")
        session_id = request.query_params.get("session_id", "")
        
        print(f"Received chat_alt request with message: '{message}' and session_id: '{session_id}'")
        
        session = sessions.get(session_id)
        if not session:
            print(f"Session '{session_id}' not found")
            return {
                "error": "Session not found. Please start a new case.",
                "chunk": "Tutor: Session not found. Please start a new case.",
                "revealed_info": {}
            }
        
        # Check if message contains a request for a new case with specific organism
        if message.lower().strip().startswith("new case"):
            print("Processing new case request")
            # Check if an organism is specified
            parts = message.lower().split("with")
            if len(parts) > 1 and parts[1].strip():
                organism = parts[1].strip()
                print(f"Starting new case with organism: {organism}")
            else:
                # Default organism if none specified
                organism = "staphylococcus aureus"
                print(f"Starting new case with default organism: {organism}")
                
            # Reset session and create new case
            session["organism"] = organism
            session["conversation_history"] = []
            session["case"] = get_case(organism)
            
            # Generate initial case presentation
            system_prompt = get_main_prompt(session["case"])
            input_prompt = "Start the case with the initial presenting complaint."
            response = run_LLM(system_prompt, input_prompt, 1)
            
            # Store in session
            session["system_prompt"] = system_prompt
            session["conversation_history"].append({
                "user_message": input_prompt,
                "ai_response": response
            })
            
            # Start revealed info extraction in the background
            pending_info_extractions[session_id] = {"status": "processing"}
            background_tasks.add_task(
                extract_info_background,
                session_id,
                response,
                session["conversation_history"]
            )
            
            # Return JSON response immediately without waiting for revealed info
            return {
                "chunk": response,
                "organism": organism,
                "revealed_info_status": "processing"
            }
        
        # Process a regular chat message
        system_prompt = session["system_prompt"]
        
        # Build conversation history context
        conversation_context = ""
        for item in session["conversation_history"]: 
            if "user_message" in item and "ai_response" in item:
                user_msg = item["user_message"]
                ai_resp = item["ai_response"]
                conversation_context += f"User: {user_msg}\nTutor: {ai_resp}\n\n"
        
        # Combine conversation history with current message
        full_prompt = f"{conversation_context}User: {message}\nTutor:"
        print(f"Sending full prompt with conversation history {full_prompt}")
        
        # Run the LLM to get the response
        response = run_LLM(system_prompt, full_prompt, 1, "o3-mini")
        
        # Handle None or empty response from LLM
        if response is None or response == "":
            print("Received empty response from LLM, providing error message instead")
            response = "Tutor: I'm sorry, I couldn't process that request. Please try asking a shorter or simpler question."
        
        # Store in conversation history
        session["conversation_history"].append({
            "user_message": message,
            "ai_response": response
        })
        
        # Start revealed info extraction in the background
        pending_info_extractions[session_id] = {"status": "processing"}
        background_tasks.add_task(
            extract_info_background,
            session_id,
            response,
            session["conversation_history"]
        )
        
        # Return response data immediately, without waiting for revealed info
        response_data = {
            'chunk': response,
            'organism': session.get("organism", ""),
            'revealed_info_status': "processing"
        }
        
        # Return JSON response
        return response_data
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        print(f"Error in chat_alt endpoint: {error_msg}")
        print(traceback.format_exc())
        return {
            "error": error_msg,
            "chunk": f"Tutor: An error occurred while processing your message. Please try again.",
            "revealed_info_status": "error"
        }

@app.get("/reset_alt")
async def reset_alt(request: Request):
    try:
        # Get session_id from query params
        session_id = request.query_params.get("session_id", "")
        
        print(f"Resetting session '{session_id}' via GET endpoint")
        if session_id in sessions:
            # Keep the organism but reset conversation
            organism = sessions[session_id]["organism"]
            sessions[session_id] = {
                "organism": organism,
                "conversation_history": [],
                "case": get_case(organism)
            }
            print(f"Session '{session_id}' reset successfully")
        else:
            print(f"Session '{session_id}' not found")
        
        message = "Session reset. Click 'Start New Case' to begin."
        return {
            "chunk": f"Tutor: {message}"
        }
    except Exception as e:
        error_msg = f"Error resetting session: {str(e)}"
        print(f"Error in reset_alt endpoint: {error_msg}")
        print(traceback.format_exc())
        return {
            "error": error_msg,
            "chunk": "Tutor: Error resetting session. Please try again."
        }

@app.post("/reset")
async def reset(request: Request, session_id: str = Form(...)):
    try:
        print(f"Resetting session '{session_id}'")
        if session_id in sessions:
            # Keep the organism but reset conversation
            organism = sessions[session_id]["organism"]
            sessions[session_id] = {
                "organism": organism,
                "conversation_history": [],
                "case": get_case(organism)
            }
            print(f"Session '{session_id}' reset successfully")
        else:
            print(f"Session '{session_id}' not found")
        
        message = "Session reset. Click 'Start New Case' to begin."
        return {
            "chunk": f"Tutor: {message}"
        }
    except Exception as e:
        error_msg = f"Error resetting session: {str(e)}"
        print(f"Error in reset endpoint: {error_msg}")
        print(traceback.format_exc())
        return {
            "error": error_msg,
            "chunk": "Tutor: Error resetting session. Please try again."
        }

@app.get("/test_case")
async def test_case(request: Request, background_tasks: BackgroundTasks):
    """Start a test case using the pre-existing case file."""
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        print(f"Created new test session ID: {session_id}")
        
        # Read the case file
        case_file_path = "Outputs/case.txt"
        try:
            with open(case_file_path, 'r') as file:
                case_content = file.read()
                print(f"Successfully loaded test case file: {len(case_content)} characters")
        except Exception as e:
            error_msg = f"Error reading test case file: {str(e)}"
            print(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Initialize a new session with the test case
        sessions[session_id] = {
            "organism": "Test Case",
            "conversation_history": [],
            "case": case_content,
            "is_test_case": True
        }
        
        # Generate the case asynchronously
        async def generate_events():
            try:
                # Initial event
                yield f"event: start\ndata: Starting test case...\n\n"
                await asyncio.sleep(0.1)
                
                # Indicate that case loading has started
                yield f"event: update\ndata: Loading test case...\n\n"
                
                # Get the case and generate initial prompt
                case = sessions[session_id]["case"]
                # Generate the main system prompt for the case
                system_prompt = get_main_prompt(case)
                # Initial input prompt to start the case
                input_prompt = "Start the case with the initial presenting complaint."
                
                print(f"System prompt: {system_prompt[:100]}...")
                print(f"Input prompt: {input_prompt}")
                
                # Run the LLM to get the initial case presentation
                response = run_LLM(system_prompt, input_prompt, 1, "o3-mini")
                
                print(f"Initial response: {response}")
                
                # Store in session with proper system prompt
                sessions[session_id]["system_prompt"] = system_prompt
                sessions[session_id]["conversation_history"].append({
                    "user_message": input_prompt,
                    "ai_response": response
                })
                
                # Start background task for revealed info extraction
                pending_info_extractions[session_id] = {"status": "processing"}
                background_tasks.add_task(
                    extract_info_background,
                    session_id,
                    response,
                    sessions[session_id]["conversation_history"]
                )
                
                # Create a response payload with the case info
                payload = {
                    "message": response,
                    "session_id": session_id,
                    "status": "success",
                    "is_test_case": True,
                    "revealed_info_status": "processing"
                }
                
                # Send the full response payload
                yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                
            except Exception as e:
                traceback_str = traceback.format_exc()
                error_message = f"Error loading test case: {str(e)}\n{traceback_str}"
                print(f"Error in generate_events: {error_message}")
                error_payload = {
                    "error": str(e),
                    "details": traceback_str,
                    "phase": "test_case_loading"
                }
                yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        
        return StreamingResponse(generate_events(), media_type="text/event-stream")
    except Exception as e:
        print(f"Error in test_case: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

def extract_info_background(session_id, response, conversation_history):
    """Extract revealed info in a background thread."""
    try:
        print(f"Starting background revealed info extraction for session {session_id}")
        # Extract revealed info using the LLM-based approach
        revealed_info = extract_revealed_info(response, conversation_history)
        
        # Store the result in the pending_info_extractions dict
        pending_info_extractions[session_id] = {
            "status": "completed",
            "revealed_info": revealed_info,
            "timestamp": time.time()
        }
        print(f"Completed background revealed info extraction for session {session_id}")
    except Exception as e:
        print(f"Error in background revealed info extraction: {str(e)}")
        print(traceback.format_exc())
        # Store error status
        pending_info_extractions[session_id] = {
            "status": "error", 
            "error": str(e),
            "timestamp": time.time()
        }

@app.get("/get_revealed_info")
async def get_revealed_info(session_id: str):
    """Endpoint to get the latest revealed info for a session."""
    try:
        # Check if we have any pending info extraction for this session
        if session_id in pending_info_extractions:
            info = pending_info_extractions[session_id]
            
            # If completed, return the info and remove from pending
            if info["status"] == "completed":
                revealed_info = info["revealed_info"]
                # Keep extraction result for 5 minutes before removing
                if time.time() - info["timestamp"] > 300:  # 5 minutes
                    del pending_info_extractions[session_id]
                return {"status": "success", "revealed_info": revealed_info}
            
            # If error occurred, return error 
            elif info["status"] == "error":
                return {"status": "error", "error": info["error"]}
            
            # If still processing
            else:
                return {"status": "processing"}
        
        # If no pending extraction exists
        return {"status": "not_found"}
    
    except Exception as e:
        print(f"Error getting revealed info: {str(e)}")
        return {"status": "error", "error": str(e)}

@app.get("/get_conversation")
async def get_conversation(session_id: str):
    """Endpoint to get the conversation history for a session."""
    try:
        # Check if the session exists
        if session_id not in sessions:
            return {"error": "Session not found"}
        
        # Get the conversation history
        conversation_history = sessions[session_id].get("conversation_history", [])
        
        # Return the conversation history
        return {
            "status": "success", 
            "conversation_history": conversation_history,
            "organism": sessions[session_id].get("organism", "unknown")
        }
    
    except Exception as e:
        print(f"Error getting conversation history: {str(e)}")
        print(traceback.format_exc())
        return {"status": "error", "error": str(e)}

def main():
    """Run the application with uvicorn."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()