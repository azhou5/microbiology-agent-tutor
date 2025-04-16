from openai import AzureOpenAI
import os
import dotenv
dotenv.load_dotenv()

def run_patient(input: str, case: str, history: list) -> str:
    """Responds as the patient. When the user asks a question directed at the patient, you should use this tool to get the patient's response."""
    system_prompt = """You are a patient. You are answering questions from a tutor. 
    You should respond in a way that is consistent with a patient's response. 

    When the student asks for specific information from the case about the patient, provide ONLY that information, as IF you ARE the patient. 
    For example: "How long has this been going on for?" leads to "Patient: Around 5 days."
If the information asked by the student is NOT present in the case, just say that the pt does not know/does not remember, or simply 'No'. 
    For example: "What did you scrape your knee on?" -> "Patient: I don't remember!". or "Did you also have a rash?" -> "No, I did not." 
    If the student asks: "What do you think might be going on" remember that you are a patient who does not know! At this point you can either just say "I don't know" Or try to throw them off. Don't give the right answer. 
    You should be concise and to the point. 

    Here is the case:
    {case}

    Here is the history of the conversation:
    {history}

    You should respond to the most recent query from the patient's perspective given the rules above. 
    """
    client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )

    response = client.chat.completions.create(
        model="o3-mini",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": input}],
    )

    return response.choices[0].message.content

