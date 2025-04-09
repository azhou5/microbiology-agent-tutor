import json
import traceback
import re
from Backend.LLM_utils import run_LLM, run_LLM_for_revealed_info

def extract_revealed_info(response, conversation_history):
    """Extract revealed information from the response and conversation history using LLM."""
    revealed_info = {
        "history": {},
        "exam": {},
        "labs": {}
    }
    
    # Add initial guidance if no history exists
    if not conversation_history:
        revealed_info["history"]["Start exploring"] = "Ask questions about symptoms, history, and exposures"
        revealed_info["exam"]["Physical examination"] = "Ask to examine specific body systems"
        revealed_info["labs"]["Diagnostic tests"] = "Request specific labs or tests when ready"
        return revealed_info
    
    try:
        # Prepare context for the LLM
        context = ""
        
        # Add current response if any
        if isinstance(response, dict):
            if "case_presentation" in response:
                context += f"Current response (case presentation): {response['case_presentation']}\n\n"
            elif "agent" in response and "response" in response:
                context += f"Current response ({response['agent']}): {response['response']}\n\n"
        elif isinstance(response, str) and response:
            context += f"Current response: {response}\n\n"
        
        # Add conversation history
        context += "Previous conversation:\n"
        for i, item in enumerate(conversation_history):
            question = item.get("user_message", "")
            answer = item.get("ai_response", "")
            if question and answer:
                context += f"Q{i+1}: {question}\nA{i+1}: {answer}\n\n"
        
        # Prepare the system prompt for categorization
        system_prompt = """You are an expert medical information organizer. 
        Your task is to extract and categorize key medical information from a clinical conversation. 
        Organize the information into three categories:
        1. Patient History: symptoms, complaints, timeline, medical history, risk factors, etc.
        2. Physical Examination: vitals, physical findings, observations, etc.
        3. Labs & Tests: lab results, imaging findings, diagnostic tests, etc.
        
        IMPORTANT: Focus on extracting NEW information from the most recent message exchange. 
        Extract only facts and findings that are medically relevant.
        Extract information in discrete, granular items rather than as long paragraphs.
        
        Format your response as a valid JSON object with these three categories as keys, and each entry as a key-value pair within its category.
        Each entry's key should be a brief description of the finding (1-5 words), and the value should be the specific details (5-15 words, concise).
        
        You MUST return a valid, complete JSON object. Do not include any explanations or notes outside the JSON structure.

        For example:
        {
            "history": {
                "Duration of symptoms": "5 days of fever",
                "Main complaint": "Shortness of breath"
            },
            "exam": {
                "Temperature": "101.2°F",
                "Lung examination": "Crackles in right lower lobe"
            },
            "labs": {
                "White blood cell count": "Elevated at 14,500",
                "Chest X-ray": "Right lower lobe infiltrate"
            }
        }"""
        
        # Create the user prompt
        user_prompt = f"""Please extract and categorize the NEW medical information from this clinical conversation.
Focus particularly on the most recent exchange to identify information that wasn't known before.

Current response: 
{context[:context.find('Previous conversation:') if 'Previous conversation:' in context else len(context)]}

Previous conversation context (for reference only):
{context[context.find('Previous conversation:'):] if 'Previous conversation:' in context else ""}

Remember to format your response as a valid JSON object with three categories: history, exam, and labs.
Include only relevant medical findings, formatted as concise key-value pairs.

Return ONLY the JSON object with no additional text."""
        
        # Call the specialized LLM function for revealed info
        result = run_LLM_for_revealed_info(system_prompt, user_prompt, "o3-mini")
        
        # Parse the result as JSON
        if result and result.strip():
            try:
                # Try to clean the result first - extract only JSON content
                # Remove any markdown formatting or explanation text
                json_content = result
                
                # If response contains ```json blocks, extract just the JSON
                if "```json" in result and "```" in result.split("```json", 1)[1]:
                    json_content = result.split("```json", 1)[1].split("```", 1)[0].strip()
                # If it contains just ``` blocks, extract from there
                elif "```" in result and "```" in result.split("```", 1)[1]:
                    json_content = result.split("```", 1)[1].split("```", 1)[0].strip()
                
                # Additional cleaning: remove any text before { and after }
                start_idx = json_content.find('{')
                end_idx = json_content.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_content = json_content[start_idx:end_idx+1]
                
                # Try to parse the JSON
                try:
                    parsed_result = json.loads(json_content)
                except json.JSONDecodeError as json_err:
                    print(f"First JSON parsing attempt failed: {str(json_err)}")
                    
                    # Try to fix common JSON errors
                    # 1. Fix missing closing quotes
                    fixed_json = re.sub(r':\s*"([^"]*?)(?=,|})', r': "\1"', json_content)
                    # 2. Fix missing commas
                    fixed_json = re.sub(r'"\s*}', '"}', fixed_json)
                    fixed_json = re.sub(r'"\s*{', '",{', fixed_json)
                    # 3. Fix trailing commas
                    fixed_json = re.sub(r',\s*}', '}', fixed_json)
                    
                    try:
                        parsed_result = json.loads(fixed_json)
                        print("Successfully parsed JSON after fixing format issues")
                    except json.JSONDecodeError:
                        # If auto-fixing failed, fall back to the rule-based approach
                        print("JSON fixing attempts failed, falling back to rule-based extraction")
                        return _extract_revealed_info_fallback(response, conversation_history)
                
                # Extract categorized information
                if "history" in parsed_result and isinstance(parsed_result["history"], dict):
                    revealed_info["history"].update(parsed_result["history"])
                
                if "exam" in parsed_result and isinstance(parsed_result["exam"], dict):
                    revealed_info["exam"].update(parsed_result["exam"])
                
                if "labs" in parsed_result and isinstance(parsed_result["labs"], dict):
                    revealed_info["labs"].update(parsed_result["labs"])
                
            except Exception as e:
                print(f"Error parsing LLM JSON response: {str(e)}")
                print(f"Raw LLM response: {result}")
                print(traceback.format_exc())
                # Fall back to the old method in case of JSON parsing error
                return _extract_revealed_info_fallback(response, conversation_history)
        else:
            print("Empty response from LLM for information extraction")
            # Fall back to the old method in case of empty response
            return _extract_revealed_info_fallback(response, conversation_history)
    
    except Exception as e:
        print(f"Error extracting revealed info with LLM: {str(e)}")
        print(traceback.format_exc())
        # Fall back to the old method in case of any exception
        return _extract_revealed_info_fallback(response, conversation_history)
    
    return revealed_info

def _extract_revealed_info_fallback(response, conversation_history):
    """The original extract_revealed_info implementation used as a fallback."""
    revealed_info = {
        "history": {},
        "exam": {},
        "labs": {}
    }
    
    # Add initial guidance if no history exists
    if not conversation_history:
        revealed_info["history"]["Start exploring"] = "Ask questions about symptoms, history, and exposures"
        revealed_info["exam"]["Physical examination"] = "Ask to examine specific body systems"
        revealed_info["labs"]["Diagnostic tests"] = "Request specific labs or tests when ready"
    
    # Try to extract information from the current response
    try:
        if isinstance(response, dict):
            # Handle case presentation
            if "case_presentation" in response:
                revealed_info["history"]["Initial Presentation"] = response["case_presentation"]
            
            # Handle responses with agent information
            if "agent" in response and "response" in response:
                content = response["response"]
                if response["agent"] == "patient":
                    # Add patient response to history
                    key = "Patient response"
                    revealed_info["history"][key] = content[:100] + "..." if len(content) > 100 else content
                
                elif response["agent"] == "case_presenter":
                    # Check if it contains exam or lab information
                    if any(term in content.lower() for term in ["exam", "vitals", "temperature", "pulse", "pressure"]):
                        key = "Physical examination"
                        revealed_info["exam"][key] = content[:100] + "..." if len(content) > 100 else content
                    elif any(term in content.lower() for term in ["lab", "test", "culture", "blood", "urine"]):
                        key = "Lab results"
                        revealed_info["labs"][key] = content[:100] + "..." if len(content) > 100 else content
    
        # Analyze conversation history to build up revealed info
        for item in conversation_history:
            question = item.get("user_message", "")
            answer = item.get("ai_response", "")
            
            if not answer:
                continue
                
            # Categorize based on question content
            if any(term in question.lower() for term in ["symptom", "feel", "pain", "history"]):
                key = question[:30] + "..." if len(question) > 30 else question
                revealed_info["history"][key] = answer[:100] + "..." if len(answer) > 100 else answer
                
            elif any(term in question.lower() for term in ["test", "lab", "xray", "culture", "blood"]):
                key = question[:30] + "..." if len(question) > 30 else question
                revealed_info["labs"][key] = answer[:100] + "..." if len(answer) > 100 else answer
                
            elif any(term in question.lower() for term in ["exam", "vital", "temp", "pulse"]):
                key = question[:30] + "..." if len(question) > 30 else question
                revealed_info["exam"][key] = answer[:100] + "..." if len(answer) > 100 else answer
    
    except Exception as e:
        print(f"Error in fallback revealed info extraction: {str(e)}")
    
    return revealed_info
