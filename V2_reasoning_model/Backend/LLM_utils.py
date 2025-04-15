import openai
from openai import AzureOpenAI
import os
import time
import copy
import json
import pickle
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

client = AzureOpenAI(
  azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
  api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
  api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
)

# Define model to deployment name mapping
MODEL_DEPLOYMENTS = {
    "o3-mini": "o3-mini",  # Use actual deployment name for o3-mini
    "gpt-4o": "gpt-4o"
}

def run_LLM(system_prompt, input_prompt, iterations, model="o3-mini"):
    """
    Runs the LLM with the given prompts and returns the response.

    Args:
        system_prompt (str): System-level prompt for the LLM.
        input_prompt (str): Input-level prompt for the LLM.
        iterations (int): Number of iterations to run.
        model (str): Model name to use.

    Returns:
        str: Text response from the LLM, or None if invalid.
    """
    # Maximum retries for empty responses
    max_empty_retries = 2
    empty_retry_count = 0
    
    while empty_retry_count <= max_empty_retries:
        # Call the GPT API
        LLM_answer = GPT_api(system_prompt, input_prompt, iterations, model)

        # Debugging: Log raw response
        print(f"Raw LLM response: {LLM_answer}")

        # Ensure the response is a list and extract the first item if necessary
        if isinstance(LLM_answer, list):
            if len(LLM_answer) == 0:
                print("Error: LLM returned an empty list.")
                empty_retry_count += 1
                if empty_retry_count <= max_empty_retries:
                    print(f"Retrying due to empty response (attempt {empty_retry_count}/{max_empty_retries})...")
                    continue
                return None
            LLM_answer = LLM_answer[0]  # Use the first element in the list

        # Validate the response type
        if not isinstance(LLM_answer, str) or LLM_answer.strip() == "":
            print(f"Error: Invalid LLM response type or empty string: {LLM_answer}")
            empty_retry_count += 1
            if empty_retry_count <= max_empty_retries:
                print(f"Retrying due to empty response (attempt {empty_retry_count}/{max_empty_retries})...")
                continue
            return None

        # If we got a valid response, return it
        return LLM_answer

    # If we've exhausted all retries, return None
    return None


def run_LLM_for_revealed_info(system_prompt, input_prompt, model="o3-mini"):
    """
    Specialized function for revealed info extraction with higher token limits.
    
    Args:
        system_prompt (str): System-level prompt for the LLM.
        input_prompt (str): Input-level prompt for the LLM.
        model (str): Model name to use.
        
    Returns:
        str: Text response from the LLM, or None if invalid.
    """
    # Maximum retries for empty responses
    max_retries = 3
    retry_count = 0
    
    while retry_count <= max_retries:
        # Create message array
        message = [{"role": "system", "content": system_prompt}, {"role": "user", "content": input_prompt}]
        
        try:
            # Get the deployment name for the model
            deployment_name = MODEL_DEPLOYMENTS.get(model, model)
            
            # Create base parameters
            api_params = {
                "model": deployment_name,
                "messages": message,
                "max_completion_tokens": 1500  # Increased token limit for complete JSON
            }
            
            # Only add temperature for models that support it (not o3-mini)
            if model != "o3-mini":
                api_params["temperature"] = 0.1  # Lower temperature for more consistent JSON formatting
            
            # Make API call with configured parameters
            response = client.chat.completions.create(**api_params)
            
            reply = response.choices[0].message.content
            print(f"Raw LLM response for revealed info: {reply[:100]}...")
            
            # Validate response
            if not reply or reply.strip() == "":
                print("Error: Empty response from LLM")
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"Retrying due to empty response (attempt {retry_count}/{max_retries})...")
                    continue
                return None
            
            return reply
            
        except Exception as e:
            print(f"Error in LLM call for revealed info: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                print(f"Retrying after error (attempt {retry_count}/{max_retries})...")
                continue
            return None
    
    # If we've exhausted all retries, return None
    return None


def GPT_api(system_prompt, prompt, n_responses=1, model="o3-mini"):
    """
    Interacts with the GPT API to get responses.

    Parameters:
        system_prompt (str): The system prompt for the GPT model.
        prompt (str): The user prompt.
        n_responses (int): Number of responses to generate.
        model (str): The model to use.

    Returns:
        list: List of responses from the GPT model.
    """
    responses = []
    message = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    for _ in range(n_responses):
        response = generate_response(message, model=model)
        responses.append(response)
    return responses


def generate_response(message, model, retries=3, backoff_factor=2):
    """
    Generates a response from the OpenAI API, with error handling and retry logic.

    Parameters:
        message (list): List of message dictionaries for the conversation.
        model (str): The model to use for the request.
        retries (int): Number of retry attempts for transient errors.
        backoff_factor (int): Factor by which to increase the wait time between retries.

    Returns:
        str: The response content from the OpenAI API, or None if the request fails.
    """
    # Get the deployment name for the model
    deployment_name = MODEL_DEPLOYMENTS.get(model, model)
    
    # Print debugging information
    print(f"Using model/deployment: {model} -> {deployment_name}")
    print(f"API version: {os.getenv('AZURE_OPENAI_API_VERSION')}")
    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    
    for attempt in range(retries):
        try:
            # Simplified call with only required parameters
            response = client.chat.completions.create(
                model=deployment_name,
                messages=message,
                max_completion_tokens=800
            )
            reply = response.choices[0].message.content
            return reply
        except openai.APIError as e:
            print(f"OpenAI API returned an API Error: {e} (attempt {attempt + 1}/{retries})")
        except openai.APIConnectionError as e:
            print(f"Failed to connect to OpenAI API: {e} (attempt {attempt + 1}/{retries})")
        except openai.RateLimitError as e:
            print(f"OpenAI API request exceeded rate limit: {e} (attempt {attempt + 1}/{retries})")
        except Exception as e:
            print(f"An unexpected error occurred: {e} (attempt {attempt + 1}/{retries})")
        
        # Wait before retrying
        if attempt < retries - 1:
            wait_time = backoff_factor ** attempt
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    # Return None if all retries fail
    print("All retry attempts failed.")
    return None
    
    