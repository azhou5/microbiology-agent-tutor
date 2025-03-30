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
import traceback
from langchain.chat_models import AzureChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import random  # Add import for random selection
import time  # Add import for time formatting

os.chdir('/Users/andrewzhou/Documents/Clinical Research/Medical_Microbiology_Tutor/Workspace/microbiology_agent_tutor/')

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

# Initialize the summarization LLM once per application instance
summarize_llm = None
summarize_cache = {}

def initialize_summarize_llm():
    """Initialize the summarization LLM if needed."""
    global summarize_llm
    
    if summarize_llm is not None:
        return summarize_llm
        
    try:
        summarize_llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=0.3,
            model="gpt-4o-mini"  # Use the smaller model for efficiency
        )
        print("Initialized summarization LLM successfully")
        return summarize_llm
    except Exception as e:
        print(f"Error initializing summarization LLM: {str(e)}")
        return None

# Initialize summarization LLM at startup
initialize_summarize_llm()

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
        
        # Only add initial guidance if no real information has been revealed yet
        if not hasattr(tutor_instance, '_revealed_info_initialized'):
            print("Initializing revealed info with initial guidance")
            revealed_info["history"]["Start exploring"] = "Ask questions about symptoms, history, and exposures"
            revealed_info["exam"]["Physical examination"] = "Ask to examine specific body systems"
            revealed_info["labs"]["Diagnostic tests"] = "Request specific labs or tests when ready"
            tutor_instance._revealed_info_initialized = True
        
        # Extract information from the current response
        if isinstance(response, dict):
            # Handle case presentation - only if it's the actual initial case info
            if "case_presentation" in response and "full_case" in response:
                revealed_info["history"]["Initial Presentation"] = response["case_presentation"]
                print(f"Added initial presentation: {response['case_presentation']}")
            
            # Handle physical exam responses - only if it's actual exam findings
            if "exam_type" in response and "response" in response and response.get("agent") == "case_presenter":
                exam_type = response["exam_type"]
                exam_response = response["response"]
                # Only add if the response contains actual findings (not error messages or generic responses)
                if exam_type and exam_response and any(term in exam_response.lower() for term in [
                    "auscultation", "palpation", "percussion", "inspection", "tenderness", "rales", 
                    "crackles", "wheezes", "murmur", "rhythm", "sound", "reflex", "strength", 
                    "sensation", "range", "motion", "pulse", "pressure", "temperature"
                ]):
                    key = f"Examined {exam_type}"
                    revealed_info["exam"][key] = summarize_text(exam_response)
                    print(f"Added exam finding: {key} = {exam_response[:100]}...")
            
            # Check if this is a patient response and add it directly to history if so
            if response.get("agent") == "patient" and "response" in response:
                patient_response = response["response"]
                if patient_response and len(patient_response) > 10:  # Ensure it's a substantial response
                    # Extract what the patient was asked about from the conversation if possible
                    question = "Patient response"
                    # Check if we have a previous message to use as the question
                    if hasattr(tutor_instance, 'last_user_message'):
                        question = tutor_instance.last_user_message[:50] + '...' if len(tutor_instance.last_user_message) > 50 else tutor_instance.last_user_message
                    
                    key = f"Patient: {question}"
                    # Only add if this exact response isn't already in history
                    if not any(summarize_text(patient_response) == value for value in revealed_info["history"].values()):
                        revealed_info["history"][key] = summarize_text(patient_response)
                        print(f"Added direct patient response to history: {patient_response[:100]}...")
        
        # Debug patient agent existence and structure
        if hasattr(tutor_instance, 'patient'):
            print(f"Patient agent exists: {tutor_instance.patient}")
            if hasattr(tutor_instance.patient, 'conversation_history'):
                print(f"Patient conversation history exists with {len(tutor_instance.patient.conversation_history)} items")
                # Print first 3 items as a sample if available
                for i, item in enumerate(tutor_instance.patient.conversation_history[:3]):
                    print(f"Patient history item {i}: question='{item.get('question', '')}', response='{item.get('response', '')[:50]}...'")
            else:
                print("Patient agent exists but has no conversation_history attribute")
        else:
            print("No patient agent found in tutor_instance")
        
        # Get revealed info from the case presenter agent
        if hasattr(tutor_instance, 'case_presenter'):
            # Process conversation history
            if hasattr(tutor_instance.case_presenter, 'conversation_history'):
                print(f"Processing case presenter conversation history with {len(tutor_instance.case_presenter.conversation_history)} items")
                for item in tutor_instance.case_presenter.conversation_history:
                    question = item.get('question', '').lower()
                    response_text = item.get('response', '')
                    
                    if not response_text:
                        continue
                        
                    # Skip responses that are clearly not case-specific information
                    if any(phrase in response_text.lower() for phrase in [
                        "could you elaborate", "can you explain", "tell me more",
                        "what do you think", "please specify", "be more specific",
                        "interesting thought", "good question", "let's focus",
                        "that's a good point", "you're on the right track"
                    ]):
                        continue
                    
                    print(f"Processing Q&A: '{question}' -> '{response_text[:100]}...'")
                    
                    # Categorize based on question content and ensure response has actual findings
                    if any(term in question for term in ['symptom', 'feel', 'pain', 'history', 'when', 'how long', 'duration', 'start', 'begin', 'onset', 'since', 'fever', 'cough', 'chest', 'breath', 'headache', 'nausea', 'vomit', 'diarrhea', 'appetite', 'weight', 'fatigue', 'tired', 'weak', 'sweat', 'chills']):
                        # Only add if response contains actual symptoms or history
                        if any(term in response_text.lower() for term in ['day', 'week', 'month', 'ago', 'since', 'started', 'began', 'developed', 'noticed', 'experienced']):
                            key = question[:50] + '...' if len(question) > 50 else question
                            revealed_info["history"][key] = summarize_text(response_text)
                            print(f"Added history item: {key}")
                    elif any(term in question for term in ['test', 'lab', 'xray', 'x-ray', 'ct', 'mri', 'culture', 'blood', 'urine', 'csf', 'imaging', 'diagnostic', 'result']):
                        # Only add if response contains actual values or results
                        if any(term in response_text.lower() for term in ['result', 'show', 'reveal', 'found', 'positive', 'negative', 'elevated', 'normal', 'abnormal', 'mm', 'mg', 'dl', 'ml', '/']):
                            key = question[:50] + '...' if len(question) > 50 else question
                            revealed_info["labs"][key] = summarize_text(response_text)
                            print(f"Added labs item: {key}")
                    elif any(term in question for term in ['exam', 'check', 'look', 'auscultate', 'palpate', 'percuss', 'observe', 'vital', 'temperature', 'pulse', 'pressure', 'listen', 'heart', 'lung', 'abdomen', 'neuro', 'skin', 'lymph', 'neck', 'head', 'eye', 'ear', 'nose', 'throat', 'mouth', 'extremity', 'reflex']):
                        # Only add if response contains actual physical findings
                        if any(term in response_text.lower() for term in ['auscultation', 'palpation', 'percussion', 'tenderness', 'rales', 'crackles', 'wheezes', 'murmur', 'rhythm', 'sound', 'reflex', 'strength', 'sensation', 'range', 'motion']):
                            key = question[:50] + '...' if len(question) > 50 else question
                            revealed_info["exam"][key] = summarize_text(response_text)
                            print(f"Added exam item: {key}")
        
        # Check if we also have a patient agent with conversation history
        if hasattr(tutor_instance, 'patient') and hasattr(tutor_instance.patient, 'conversation_history'):
            print(f"Processing patient conversation history with {len(tutor_instance.patient.conversation_history)} items")
            for item in tutor_instance.patient.conversation_history:
                question = item.get('question', '').lower()
                response_text = item.get('response', '')
                
                if not response_text or len(response_text) < 10:  # Skip very short responses
                    continue
                    
                # Skip responses that are clearly not case-specific information
                if any(phrase in response_text.lower() for phrase in [
                    "i don't know", "i'm not sure", "you'd have to ask", 
                    "i can't remember", "maybe you should", "what do you mean",
                    "could you explain", "i don't understand"
                ]):
                    continue
                    
                print(f"Processing patient Q&A: '{question}' -> '{response_text[:100]}...'")
                
                # Create a unique key based on the question
                key = f"Patient: {question[:50] + '...' if len(question) > 50 else question}"
                
                # Only add if this exact response isn't already in history
                summarized_response = summarize_text(response_text)
                if not any(summarized_response == value for value in revealed_info["history"].values()):
                    # Add to history by default, since almost all patient responses are about history
                    revealed_info["history"][key] = summarized_response
                    print(f"Added patient history item: {key}")
                    
                    # Optional: Check if this contains any lab values that should also go in labs section
                    if any(term in response_text.lower() for term in ['test', 'positive', 'negative', 'blood', 'urine', 'result', 'culture']):
                        if any(term in response_text.lower() for term in ['result', 'show', 'reveal', 'found', 'positive', 'negative', 'elevated', 'normal', 'abnormal', 'mm', 'mg', 'dl', 'ml', '/']):
                            lab_key = f"Patient labs: {question[:40] + '...' if len(question) > 40 else question}"
                            revealed_info["labs"][lab_key] = summarized_response
                            print(f"Added patient response to labs section: {lab_key}")
        
        # Remove the initial guidance messages if we have actual information
        if (revealed_info["history"] or revealed_info["exam"] or revealed_info["labs"]) and hasattr(tutor_instance, '_revealed_info_initialized'):
            if "Start exploring" in revealed_info["history"] and len(revealed_info["history"]) > 1:
                del revealed_info["history"]["Start exploring"]
            if "Physical examination" in revealed_info["exam"] and len(revealed_info["exam"]) > 1:
                del revealed_info["exam"]["Physical examination"]
            if "Diagnostic tests" in revealed_info["labs"] and len(revealed_info["labs"]) > 1:
                del revealed_info["labs"]["Diagnostic tests"]
        
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
        session_id = f"session_{os.urandom(8).hex()}"
        print(f"Created new session ID: {session_id}")
        
        # Initialize a tutor instance
        tutors[session_id] = MedicalMicrobiologyTutor()
        
        # Generate a new case for the specified organism
        tutor = tutors[session_id]
        print(f"Starting case generation for organism: {organism} (random: {is_random_case})")
        
        # Generate the case
        async def generate_events():
            try:
                # Initial event
                print(f"Sending start event for {organism}")
                yield f"event: start\ndata: Starting case generation for {'' if is_random_case else organism}...\n\n"
                await asyncio.sleep(0.1)
                
                # Indicate that case generation has started
                print(f"Sending update event for {organism}")
                yield f"event: update\ndata: Generating case...\n\n"
                
                # Start the case for the specified organism
                print(f"Calling tutor.start_new_case with organism: {organism}")
                response = tutor.start_new_case(organism)
                print(f"Case generated successfully for {organism}, response type: {type(response)}")
                
                # Format the response for the frontend
                formatted_response = process_response(response)
                print(f"Formatted response (first 100 chars): {formatted_response[:100]}...")
                
                # Get revealed info for side panel
                revealed_info = extract_revealed_info(response, tutor)
                print(f"Extracted revealed info for side panel with {len(revealed_info.get('history', {}))} history items")
                
                # Create a response payload with the case info
                payload = {
                    "message": formatted_response,
                    "session_id": session_id,
                    "status": "success",
                    "is_random_case": is_random_case,
                    "revealed_info": revealed_info
                }
                
                # Send the full response payload
                print(f"Sending complete event with payload (size: {len(json.dumps(payload))})")
                yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                print(f"Complete event sent successfully for {organism}")
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
        
        # Handle errors
        async def error_event():
            error_payload = {
                "error": "Failed to generate case",
                "phase": "initialization"
            }
            yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        
        return StreamingResponse(generate_events(), media_type="text/event-stream")
    except Exception as e:
        print(f"Error in start_case: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/start_case")
async def start_case_get(request: Request, organism: str = None):
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
        session_id = f"session_{os.urandom(8).hex()}"
        print(f"Created new session ID: {session_id}")
        
        # Initialize a tutor instance
        tutors[session_id] = MedicalMicrobiologyTutor()
        
        # Generate a new case for the specified organism
        tutor = tutors[session_id]
        print(f"Starting case generation for organism: {organism} (random: {is_random_case})")
        
        # Generate the case asynchronously
        async def generate_events():
            try:
                # Initial event
                print(f"Sending start event for {organism}")
                yield f"event: start\ndata: Starting case generation for {'' if is_random_case else organism}...\n\n"
                await asyncio.sleep(0.1)
                
                # Indicate that case generation has started
                print(f"Sending update event for {organism}")
                yield f"event: update\ndata: Generating case...\n\n"
                
                # Start the case for the specified organism
                print(f"Calling tutor.start_new_case with organism: {organism}")
                response = tutor.start_new_case(organism)
                print(f"Case generated successfully for {organism}, response type: {type(response)}")
                
                # Format the response for the frontend
                formatted_response = process_response(response)
                print(f"Formatted response (first 100 chars): {formatted_response[:100]}...")
                
                # Get revealed info for side panel
                revealed_info = extract_revealed_info(response, tutor)
                print(f"Extracted revealed info for side panel with {len(revealed_info.get('history', {}))} history items")
                
                # Create a response payload with the case info
                payload = {
                    "message": formatted_response,
                    "session_id": session_id, 
                    "status": "success",
                    "is_random_case": is_random_case,
                    "revealed_info": revealed_info
                }
                
                # Send the full response payload
                print(f"Sending complete event with payload (size: {len(json.dumps(payload))})")
                yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                print(f"Complete event sent successfully for {organism}")
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
        
        # Handle errors
        async def error_event():
            error_payload = {
                "error": "Failed to generate case",
                "phase": "initialization"
            }
            yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        
        return StreamingResponse(generate_events(), media_type="text/event-stream")
    except Exception as e:
        print(f"Error in start_case_get: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # Store the last user message for context
        tutor.last_user_message = message
        
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
                    revealed_info["exam"][f"Examined {exam_type}"] = summarize_text(exam_response)
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
        
        # Store the last user message for context
        tutor.last_user_message = message
        
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
                    revealed_info["exam"][f"Examined {exam_type}"] = summarize_text(exam_response)
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

def summarize_text(text, max_length=100):
    """Summarize text using GPT-4o mini if it's longer than max_length."""
    global summarize_cache
    
    if not text or len(text) <= max_length:
        return text
    
    # Check cache first
    if text in summarize_cache:
        return summarize_cache[text]
    
    # Get LLM
    llm = initialize_summarize_llm()
    if llm is None:
        return text[:max_length] + "..."
    
    try:
        # Create prompt for summarization
        messages = [
            SystemMessage(content="""You are a medical information summarizer for a clinical teaching application.
            Your task is to summarize detailed medical information into concise, clinically useful summaries.
            
            Guidelines:
            1. ALWAYS preserve specific numbers (vital signs, lab values, etc.)
            2. ALWAYS preserve specific findings (rales, murmurs, rashes, etc.)
            3. ALWAYS preserve timing information (onset, duration, frequency)
            4. ALWAYS preserve anatomical locations
            5. ALWAYS preserve pertinent negatives
            6. Use proper medical terminology
            7. Keep your summary to 1-2 short, factual sentences
            8. Focus on objective findings over subjective interpretations
            
            Examples:
            Input: "The patient reports a fever that started 3 days ago, reaching 39.2°C at its highest. They also note a productive cough with yellow sputum, and chest pain that worsens with deep breathing. They deny any hemoptysis or night sweats."
            Output: "Fever of 39.2°C for 3 days with productive yellow sputum and pleuritic chest pain; no hemoptysis or night sweats."
            
            Input: "On examination of the chest, there are crackles in the right lower lobe with decreased breath sounds. No wheezing is appreciated. Tactile fremitus is increased in the affected area. The left lung is clear to auscultation."
            Output: "Right lower lobe crackles with decreased breath sounds and increased tactile fremitus; left lung clear."
            
            Input: "Labs show WBC 15.2, neutrophils 85%, bands 8%. CRP is elevated at 85. Blood cultures are pending. Procalcitonin is 2.4."
            Output: "WBC 15.2 (85% neutrophils, 8% bands), CRP 85, procalcitonin 2.4; cultures pending."
            """),
            HumanMessage(content=f"Summarize this medical information, preserving all specific clinical details: {text}")
        ]
        
        # Get summary
        response = llm.invoke(messages)
        summary = response.content.strip()
        
        print(f"Summarized text from {len(text)} chars to {len(summary)} chars")
        
        # Cache the result
        summarize_cache[text] = summary
        
        return summary
    except Exception as e:
        print(f"Error summarizing text: {str(e)}")
        # Fall back to truncation if summarization fails
        return text[:max_length] + "..."