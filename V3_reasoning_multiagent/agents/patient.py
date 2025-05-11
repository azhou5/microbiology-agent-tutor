from openai import AzureOpenAI
import os
import dotenv
import numpy as np
import faiss
import pickle

dotenv.load_dotenv()

# Load FAISS index and texts
index_path = os.path.join(os.path.dirname(__file__), '..', 'output_index.faiss')
texts_path = os.path.join(os.path.dirname(__file__), '..', 'output_index.faiss.texts')

with open(index_path, 'rb') as f:
    index = pickle.load(f)
with open(texts_path, 'rb') as f:
    texts = pickle.load(f)

def get_embedding(text):
    """Get embedding for a text using Azure OpenAI."""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def run_patient(input: str, case: str, history: list) -> str:
    """Responds as the patient. When the user asks a question directed at the patient, you should use this tool to get the patient's response."""
    # Format the recent history similar to how the index was created
    recent_context = ""
    if history:
        recent_context = "Chat history:\n"
        for message in history[-5:-1]:  # Get last 4 messages like in index generation
            if isinstance(message, dict) and "role" in message and "content" in message:
                recent_context += f"{message['role']}: {message['content']}\n"
    
    # Combine recent history with current query for embedding
    embedding_text = recent_context 
    
    # Get embedding for the combined text
    embedding = get_embedding(embedding_text)
    
    # Search for similar messages
    distances, indices = index.search(np.array([embedding]).astype('float32'), k=3)
    
    # Get the 3 most similar examples
    similar_examples = [texts[idx] for idx in indices[0]]
    examples_text = "\n\nSimilar examples with feedback, including the rated messsage and expert feedback:\n" + "\n---\n".join(similar_examples)
    
    system_prompt = f"""You are a patient. You are answering questions from a tutor. 
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

    {examples_text}
    You should respond to the most recent query from the patient's perspective given the rules above. 
    You will be given some examples of similar exchanges between a patient and a tutor, as well as a manual rating of the quality of the response and feedback. 
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

