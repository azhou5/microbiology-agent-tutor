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
from typing import AsyncGenerator, Union, List
from typing import AsyncGenerator, Union, List
import traceback

os.chdir('/Users/sanjatkanjilal/My Drive/Research - Gdrive/Projects/Code/microbiology-agent-tutor')

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

# Available organisms for case generation
# This list could be expanded or loaded from a database/config file
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

@app.get("/api/organisms", response_class=HTMLResponse)
async def get_organisms():
    """API endpoint to get a list of available organisms"""
    return json.dumps(AVAILABLE_ORGANISMS)

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

def extract_revealed_info(response, tutor_instance):
    """Extract revealed information from the response and tutor state."""
    revealed_info = {
        "history": {},
        "exam": {},
        "labs": {}
    }
    
    try:
        print("Extracting revealed info...")
        
        # Add a basic test entry to each category to ensure visibility
        if not hasattr(tutor_instance, '_revealed_info_initialized'):
            print("Initializing revealed info with test entries")
            revealed_info["history"]["Start exploring"] = "Ask questions about symptoms, history, and exposures"
            revealed_info["exam"]["Physical examination"] = "Ask to examine specific body systems"
            revealed_info["labs"]["Diagnostic tests"] = "Request specific labs or tests when ready"
            tutor_instance._revealed_info_initialized = True
        
        # Extract exam type if present in the response
        exam_type = None
        if isinstance(response, dict):
            if "exam_type" in response:
                exam_type = response["exam_type"]
                print(f"Found exam_type in response: {exam_type}")
                
        # Get revealed info from the case presenter agent
        if hasattr(tutor_instance, 'case_presenter'):
            # Add exam categories from revealed_info set
            if hasattr(tutor_instance.case_presenter, 'revealed_info'):
                print(f"Case presenter revealed_info: {tutor_instance.case_presenter.revealed_info}")
                for category in tutor_instance.case_presenter.revealed_info:
                    if category.endswith('_exam'):
                        revealed_info["exam"][category] = "Examined"
                        print(f"Added exam category: {category}")
                    elif category in ["symptoms", "fever", "pain", "cough"]:
                        revealed_info["history"][f"Asked about {category}"] = "Revealed"
                        print(f"Added symptom category: {category}")
                    elif category in ["epidemiology", "travel", "exposure", "contact"]:
                        revealed_info["history"][f"Asked about {category}"] = "Revealed"
                        print(f"Added epidemiology category: {category}")
                    elif category in ["medical_history", "medications", "allergies"]:
                        revealed_info["history"][f"Asked about {category}"] = "Revealed"
                        print(f"Added medical history category: {category}")
                    elif category in ["labs", "tests", "imaging", "blood", "culture"]:
                        revealed_info["labs"][f"Asked about {category}"] = "Revealed"
                        print(f"Added lab category: {category}")
            
            # Add conversation history items to appropriate categories
            if hasattr(tutor_instance.case_presenter, 'conversation_history'):
                print(f"Processing conversation history with {len(tutor_instance.case_presenter.conversation_history)} items")
                for item in tutor_instance.case_presenter.conversation_history:
                    question = item.get('question', '').lower()
                    response_text = item.get('response', '')
                    
                    print(f"Processing question: '{question}'")
                    
                    # Improved question categorization logic
                    if any(term in question for term in ['symptom', 'feel', 'pain', 'history', 'when did', 'how long', 'duration', 'started', 'begin', 'onset', 'since when', 'fever', 'cough', 'chest', 'breathing', 'headache']):
                        key = question[:30] + '...' if len(question) > 30 else question
                        revealed_info["history"][key] = response_text[:50] + '...' if len(response_text) > 50 else response_text
                        print(f"Added history item: {key}")
                    elif any(term in question for term in ['test', 'lab', 'xray', 'ct', 'mri', 'culture', 'blood', 'imaging', 'diagnostic']):
                        key = question[:30] + '...' if len(question) > 30 else question
                        revealed_info["labs"][key] = response_text[:50] + '...' if len(response_text) > 50 else response_text
                        print(f"Added labs item: {key}")
                    elif any(term in question for term in ['exam', 'check', 'look', 'auscultate', 'palpate', 'observe', 'vital', 'temperature', 'pulse', 'pressure', 'listen']):
                        key = question[:30] + '...' if len(question) > 30 else question
                        revealed_info["exam"][key] = response_text[:50] + '...' if len(response_text) > 50 else response_text
                        print(f"Added exam item: {key}")
        
        # Check if we also have a patient agent with conversation history
        if hasattr(tutor_instance, 'patient') and hasattr(tutor_instance.patient, 'conversation_history'):
            print(f"Processing patient conversation history with {len(tutor_instance.patient.conversation_history)} items")
            for item in tutor_instance.patient.conversation_history:
                question = item.get('question', '').lower()
                response_text = item.get('response', '')
                
                print(f"Processing patient question: '{question}'")
                
                # Similar categorization as above
                if any(term in question for term in ['symptom', 'feel', 'pain', 'history', 'when did', 'how long', 'duration', 'started', 'begin', 'onset', 'since when']):
                    key = question[:30] + '...' if len(question) > 30 else question
                    revealed_info["history"][key] = response_text[:50] + '...' if len(response_text) > 50 else response_text
                    print(f"Added patient history item: {key}")
        
        # Add the current exam_type if found
        if exam_type:
            revealed_info["exam"][exam_type] = "Examined"
            print(f"Added current exam_type: {exam_type}")
            
        # Print the final revealed info for debugging
        print(f"Final revealed_info: {revealed_info}")
            
        return revealed_info
    except Exception as e:
        print(f"Error extracting revealed info: {str(e)}")
        print(traceback.format_exc())  # Add stack trace for better debugging
        return revealed_info

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
async def start_case(request: Request, organism: str = Form(None)):
    try:
        # First try to get the organism from the form data
        form_data = await request.form()
        organism_param = organism or form_data.get("organism")
        
        # If still not found, try to get from query params
        if not organism_param:
            query_params = request.query_params
            organism_param = query_params.get("organism")
            
        # Validate the organism
        if not organism_param:
            raise ValueError("Please specify an organism")
            
        cleaned_organism = organism_param.strip().lower()
            
        # Create a new tutor instance
        tutor = MedicalMicrobiologyTutor()
        session_id = "test_session"  # In a real app, generate unique session IDs
        tutors[session_id] = tutor
        
        # Get the initial case with the specified organism
        initial_case = tutor.start_new_case(organism=cleaned_organism)
        
        # Ensure we have a response to stream
        if not initial_case:
            initial_case = f"Error: No case was generated for {cleaned_organism}. Please try again."
        
        # Log the response for debugging
        print(f"Initial case response: {initial_case}")
        
        # Extract any revealed information
        try:
            revealed_info = extract_revealed_info(initial_case, tutor)
            # Ensure we have initial values
            if not revealed_info.get("history") and not revealed_info.get("exam") and not revealed_info.get("labs"):
                revealed_info["history"] = {"Start exploring": "Ask questions about symptoms, history, and exposures"}
                revealed_info["exam"] = {"Physical examination": "Ask to examine specific body systems"}
                revealed_info["labs"] = {"Diagnostic tests": "Request specific labs or tests when ready"}
                print("Added initial values to empty revealed_info")
        except Exception as e:
            print(f"Error extracting revealed info: {str(e)}")
            print(traceback.format_exc())
            # Initialize with default values
            revealed_info = {
                "history": {"Start exploring": "Ask questions about symptoms, history, and exposures"},
                "exam": {"Physical examination": "Ask to examine specific body systems"},
                "labs": {"Diagnostic tests": "Request specific labs or tests when ready"}
            }
        
        async def generate_events():
            try:
                # Process the response
                processed_response = process_response(initial_case)
                # Combine response with revealed info
                response_data = {
                    'chunk': processed_response,
                    'revealed_info': revealed_info,
                    'organism': cleaned_organism
                }
                # Send the processed response as a data event
                yield f"data: {json.dumps(response_data)}\n\n"
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

@app.get("/start_case")
async def start_case_get(request: Request, organism: str = None):
    try:
        # Get organism from query params
        organism_param = organism or request.query_params.get("organism")
            
        # Validate the organism
        if not organism_param:
            raise ValueError("Please specify an organism")
            
        cleaned_organism = organism_param.strip().lower()
        print(f"Starting case generation for organism: {cleaned_organism}")
            
        # Create a new tutor instance
        tutor = MedicalMicrobiologyTutor()
        session_id = "test_session"  # In a real app, generate unique session IDs
        tutors[session_id] = tutor
        
        # Get the initial case with the specified organism
        try:
            print(f"Calling tutor.start_new_case with organism: {cleaned_organism}")
            initial_case = tutor.start_new_case(organism=cleaned_organism)
            
            # Check if we got a valid response
            if not initial_case:
                print(f"No case was generated for {cleaned_organism}, using default message")
                initial_case = f"A new case involving {cleaned_organism} has been started. What would you like to know about the patient?"
        except Exception as e:
            print(f"Error in tutor.start_new_case: {str(e)}")
            print(traceback.format_exc())
            initial_case = f"Error generating case for {cleaned_organism}: {str(e)[:100]}... Let's try to continue with a basic case."
        
        # Log the response for debugging
        print(f"Initial case response type: {type(initial_case)}")
        if isinstance(initial_case, str):
            print(f"Initial case response (first 100 chars): {initial_case[:100]}...")
        elif isinstance(initial_case, dict):
            print(f"Initial case response keys: {initial_case.keys()}")
        
        # Extract any revealed information
        try:
            revealed_info = extract_revealed_info(initial_case, tutor)
            # Ensure we have initial values
            if not revealed_info.get("history") and not revealed_info.get("exam") and not revealed_info.get("labs"):
                revealed_info["history"] = {"Start exploring": "Ask questions about symptoms, history, and exposures"}
                revealed_info["exam"] = {"Physical examination": "Ask to examine specific body systems"}
                revealed_info["labs"] = {"Diagnostic tests": "Request specific labs or tests when ready"}
                print("Added initial values to empty revealed_info")
        except Exception as e:
            print(f"Error extracting revealed info: {str(e)}")
            print(traceback.format_exc())
            # Initialize with default values
            revealed_info = {
                "history": {"Start exploring": "Ask questions about symptoms, history, and exposures"},
                "exam": {"Physical examination": "Ask to examine specific body systems"},
                "labs": {"Diagnostic tests": "Request specific labs or tests when ready"}
            }
        
        async def generate_events():
            try:
                # Process the response
                processed_response = process_response(initial_case)
                print(f"Processed response (first 100 chars): {processed_response[:100]}...")
                
                # Combine response with revealed info
                response_data = {
                    'chunk': processed_response,
                    'revealed_info': revealed_info,
                    'organism': cleaned_organism
                }
                
                # Send the processed response as a data event
                yield f"data: {json.dumps(response_data)}\n\n"
                # Send the completion event
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_msg = f"Error streaming response: {str(e)}"
                print(f"Error in generate_events: {error_msg}")
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream"
        )
    except Exception as e:
        error_msg = f"Error starting case: {str(e)}\n{traceback.format_exc()}"
        print(f"Error in start_case_get: {error_msg}")
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
        print(f"Received chat request with message: '{message}' and session_id: '{session_id}'")
        
        tutor = tutors.get(session_id)
        if not tutor:
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
                initial_case = tutor.start_new_case(organism=organism)
            else:
                # Default organism if none specified
                organism = "staphylococcus aureus"
                print(f"Starting new case with default organism: {organism}")
                initial_case = tutor.start_new_case(organism=organism)
                
            # Extract any revealed information
            revealed_info = extract_revealed_info(initial_case, tutor)
            
            # Process the response
            processed_response = process_response(initial_case)
            
            # Return JSON response
            return {
                "chunk": processed_response,
                "revealed_info": revealed_info,
                "organism": organism
            }
        
        # Create a task package for the manager agent
        print(f"Creating task package for message: '{message}'")
        task = TaskPackage(
            instruction=message,
            task_creator=tutor.id
        )
        
        # Let the manager agent handle the routing
        try:
            print("Calling tutor with task")
            response = tutor(task)
            print(f"Response from tutor: {type(response)}")
            if isinstance(response, dict):
                print(f"Response keys: {response.keys()}")
        except Exception as e:
            print(f"Error in tutor call: {str(e)}")
            print(traceback.format_exc())
            return {
                "error": f"Error processing your message: {str(e)}",
                "chunk": f"Tutor: I'm sorry, I encountered an error processing your message. Please try again or start a new case."
            }
        
        # Extract revealed information
        try:
            revealed_info = extract_revealed_info(response, tutor)
            # Ensure we have initial values
            if not revealed_info.get("history") and not revealed_info.get("exam") and not revealed_info.get("labs"):
                revealed_info["history"] = {"Start exploring": "Ask questions about symptoms, history, and exposures"}
                revealed_info["exam"] = {"Physical examination": "Ask to examine specific body systems"}
                revealed_info["labs"] = {"Diagnostic tests": "Request specific labs or tests when ready"}
                print("Added initial values to empty revealed_info in chat endpoint")
        except Exception as e:
            print(f"Error extracting revealed info: {str(e)}")
            print(traceback.format_exc())
            # Initialize with default values
            revealed_info = {
                "history": {"Start exploring": "Ask questions about symptoms, history, and exposures"},
                "exam": {"Physical examination": "Ask to examine specific body systems"},
                "labs": {"Diagnostic tests": "Request specific labs or tests when ready"}
            }
        
        # Process the response
        try:
            processed_response = process_response(response)
            print(f"Processed response (first 100 chars): {processed_response[:100] if processed_response else 'None'}...")
            
            # Check for physical exam info directly in the response
            if isinstance(response, dict) and "exam_type" in response:
                exam_type = response["exam_type"]
                exam_response = response.get("response", "")
                
                # Add this exam info directly to revealed info
                if exam_type and exam_response:
                    print(f"Adding physical exam info directly from response: {exam_type}")
                    revealed_info["exam"][f"Examined {exam_type}"] = exam_response[:50] + "..." if len(exam_response) > 50 else exam_response
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            processed_response = f"Tutor: Error processing response: {str(e)}"
        
        # Create response data
        response_data = {
            'chunk': processed_response,
            'revealed_info': revealed_info
        }
        
        # Add exam_type if it exists in the response
        if isinstance(response, dict) and "exam_type" in response:
            response_data["exam_type"] = response["exam_type"]
            
        # Add organism if it exists
        if hasattr(tutor, 'current_organism') and tutor.current_organism:
            response_data["organism"] = tutor.current_organism
        
        # Log the response data we're sending back
        print(f"Sending response data: {json.dumps(response_data, default=str)[:500]}...")
            
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

@app.post("/reset")
async def reset(request: Request, session_id: str = Form(...)):
    try:
        print(f"Resetting session '{session_id}'")
        tutor = tutors.get(session_id)
        if tutor:
            tutor.reset()
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

@app.get("/chat_alt")
async def chat_alt(request: Request):
    try:
        # Get message and session_id from query params
        message = request.query_params.get("message")
        session_id = request.query_params.get("session_id", "test_session")
        
        if not message:
            return {"error": "No message provided", "chunk": "Tutor: Please provide a message."}
        
        print(f"Received chat_alt request with message: '{message}' and session_id: '{session_id}'")
        
        tutor = tutors.get(session_id)
        if not tutor:
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
                initial_case = tutor.start_new_case(organism=organism)
            else:
                # Default organism if none specified
                organism = "staphylococcus aureus"
                print(f"Starting new case with default organism: {organism}")
                initial_case = tutor.start_new_case(organism=organism)
                
            # Extract any revealed information
            revealed_info = extract_revealed_info(initial_case, tutor)
            
            # Process the response
            processed_response = process_response(initial_case)
            
            # Return JSON response
            return {
                "chunk": processed_response,
                "revealed_info": revealed_info,
                "organism": organism
            }
        
        # Create a task package for the manager agent
        print(f"Creating task package for message: '{message}'")
        task = TaskPackage(
            instruction=message,
            task_creator=tutor.id
        )
        
        # Let the manager agent handle the routing
        try:
            print("Calling tutor with task")
            response = tutor(task)
            print(f"Response from tutor: {type(response)}")
            if isinstance(response, dict):
                print(f"Response keys: {response.keys()}")
        except Exception as e:
            print(f"Error in tutor call: {str(e)}")
            print(traceback.format_exc())
            return {
                "error": f"Error processing your message: {str(e)}",
                "chunk": f"Tutor: I'm sorry, I encountered an error processing your message. Please try again or start a new case."
            }
        
        # Extract revealed information
        try:
            revealed_info = extract_revealed_info(response, tutor)
            # Ensure we have initial values
            if not revealed_info.get("history") and not revealed_info.get("exam") and not revealed_info.get("labs"):
                revealed_info["history"] = {"Start exploring": "Ask questions about symptoms, history, and exposures"}
                revealed_info["exam"] = {"Physical examination": "Ask to examine specific body systems"}
                revealed_info["labs"] = {"Diagnostic tests": "Request specific labs or tests when ready"}
                print("Added initial values to empty revealed_info in chat endpoint")
        except Exception as e:
            print(f"Error extracting revealed info: {str(e)}")
            print(traceback.format_exc())
            # Initialize with default values
            revealed_info = {
                "history": {"Start exploring": "Ask questions about symptoms, history, and exposures"},
                "exam": {"Physical examination": "Ask to examine specific body systems"},
                "labs": {"Diagnostic tests": "Request specific labs or tests when ready"}
            }
        
        # Process the response
        try:
            processed_response = process_response(response)
            print(f"Processed response (first 100 chars): {processed_response[:100] if processed_response else 'None'}...")
            
            # Check for physical exam info directly in the response
            if isinstance(response, dict) and "exam_type" in response:
                exam_type = response["exam_type"]
                exam_response = response.get("response", "")
                
                # Add this exam info directly to revealed info
                if exam_type and exam_response:
                    print(f"Adding physical exam info directly from response: {exam_type}")
                    revealed_info["exam"][f"Examined {exam_type}"] = exam_response[:50] + "..." if len(exam_response) > 50 else exam_response
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            processed_response = f"Tutor: Error processing response: {str(e)}"
        
        # Create response data
        response_data = {
            'chunk': processed_response,
            'revealed_info': revealed_info
        }
        
        # Add exam_type if it exists in the response
        if isinstance(response, dict) and "exam_type" in response:
            response_data["exam_type"] = response["exam_type"]
            
        # Add organism if it exists
        if hasattr(tutor, 'current_organism') and tutor.current_organism:
            response_data["organism"] = tutor.current_organism
            
        # Return JSON response
        return response_data
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        print(f"Error in chat_alt endpoint: {error_msg}")
        print(traceback.format_exc())
        return {
            "error": error_msg,
            "chunk": f"Tutor: An error occurred while processing your message. Please try again."
        }

@app.get("/reset_alt")
async def reset_alt(request: Request):
    try:
        # Get session_id from query params
        session_id = request.query_params.get("session_id", "test_session")
        
        print(f"Resetting session '{session_id}' via GET endpoint")
        tutor = tutors.get(session_id)
        if tutor:
            tutor.reset()
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