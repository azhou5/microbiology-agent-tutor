import os
from openai import AzureOpenAI
def get_embeddings_batch(texts):
    """
    Get embeddings for a batch of text strings using OpenAI's embedding model.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """

    client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        )
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [data.embedding for data in response.data]
import os
import re
import json
import pickle
import numpy as np
import faiss
from tqdm import tqdm
from openai import AzureOpenAI  # Ensure this is installed/configured

# -------------------------------------------------------------------
# Load and parse multiline log entries
# -------------------------------------------------------------------

def load_multiline_log_entries(log_file_path):
    """
    Load log entries where each entry starts with a timestamp line and has a JSON block.
    Handles multiline JSON logs.
    """
    entries = []
    current_entry = []

    with open(log_file_path, 'r') as f:
        for line in f:
            # Detect start of new log entry
            if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - INFO - {', line):
                if current_entry:
                    entries.append('\n'.join(current_entry))
                    current_entry = []
            current_entry.append(line.strip())

        # Append last entry
        if current_entry:
            entries.append('\n'.join(current_entry))

    return entries

def parse_log_entry(log_block):
    """
    Extract and parse JSON inside a single multiline log block.
    """
    match = re.search(r'{.*}', log_block, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return None
    return None

def prepare_text_from_log_entry(log_entry):
    """
    Extract and combine rated message with any visible chat history into flat text.
    """
    if not log_entry:
        return ""
    
    text_parts = []
    rated_message ="Rated message: " + log_entry["rated_message"]

    # Add rated message


    # Add visible chat history
    if "visible_chat_history" in log_entry and log_entry["visible_chat_history"]:
        text_parts.append("Chat history:")
        for message in log_entry["visible_chat_history"][-5:-1]:  # Changed from -4 to -5 to get last 4 messages
            if "role" in message and "content" in message:
                text_parts.append(f"{message['role']}: {message['content']}")
    rating = log_entry.get('rating', None)
    if rating == '':
        rating = None
    
    feedback = log_entry.get('feedback_text', None)
    if feedback == '':
        feedback = None
    if rating is not None and feedback is not None:
        rating_text = f"The expert rating of this message is {rating}/5 (higher is better). The feedback that the expert gave was \"{feedback}\""
    elif rating is not None:
        rating_text = f"The expert rating of this message is {rating}/5 (higher is better)."
    elif feedback is not None:
        rating_text = f"The feedback that the expert gave was \"{feedback}\""
    else:
        rating_text = ""


    replacement = log_entry.get('replacement', None)


    if replacement is not None and replacement != "":
        replacement = "The replacement message is: " + replacement
    else:
        replacement = ""

    return (" ".join(text_parts), rating_text, rated_message, replacement) 

# -------------------------------------------------------------------
# Azure/OpenAI Embedding Utility
# -------------------------------------------------------------------

def get_embedding(text):
    """
    Get a single embedding from Azure OpenAI.
    """
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )

    response = client.embeddings.create(
        model="text-embedding-3-small",  # Adjust if using another model
        input=text
    )
    return response.data[0].embedding

def get_embeddings_batch(text_list):
    """
    Get embeddings for a batch of texts.
    """
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text_list
    )

    return [item.embedding for item in response.data]

# -------------------------------------------------------------------
# Main Function: Logs to FAISS Index
# -------------------------------------------------------------------

def convert_logs_to_faiss_index(log_file_path, faiss_index_path, batch_size=32):
    # Load and parse log entries
    log_entries = load_multiline_log_entries(log_file_path)

    # Prepare text list
    texts = []
    feedback_list = []
    rated_messages_list= []
    replacement_list = []
    for entry in log_entries:
        log_data = parse_log_entry(entry)
        if log_data:
            text, feedback, rated_text, replacement = prepare_text_from_log_entry(log_data)
            if text:
                texts.append(text)
                feedback_list.append(feedback)
                rated_messages_list.append(rated_text)
                replacement_list.append(replacement)


    print(f"Found {len(texts)} valid log messages.")

    if not texts:
        raise ValueError("No valid text entries found in logs.")
    
    # Determine embedding dimension
    sample_emb = get_embedding(texts[0])
    print(texts[0])
    embedding_dim = len(sample_emb)
    print(embedding_dim) 

    # Generate embeddings in batches
    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Generating Embeddings"):
        batch = texts[i:i+batch_size]
        try:
            batch_embeddings = get_embeddings_batch(batch)
        except Exception as e:
            print(f"Batch embedding failed: {e}")
            batch_embeddings = [np.zeros(embedding_dim)] * len(batch)

        # Append each embedding, using zeros if failed
        for j, emb in enumerate(batch_embeddings):
            if emb:
                embeddings.append(emb)
            else:
                embeddings.append(np.zeros(embedding_dim))

    # Save to FAISS index
    text_with_feedback = [] 
    for c in range(len(texts)):
        text_with_feedback.append(rated_messages_list[c] + texts[c] + feedback_list[c] + replacement_list[c])
    

    embeddings = np.array(embeddings).astype('float32')
    index = faiss.IndexFlatL2(embedding_dim)
    index.add(embeddings)

    with open(faiss_index_path, 'wb') as f:
        pickle.dump(index, f)

    with open(faiss_index_path + '.texts', 'wb') as f:
        pickle.dump(text_with_feedback, f)

    print(f"Saved FAISS index and texts to: {faiss_index_path}")
    return index, texts

# -------------------------------------------------------------------
# Example usage
# -------------------------------------------------------------------

if __name__ == "__main__":
    log_path = "feedback_data/feedback.log"
    faiss_path = "output_index.faiss"    

    convert_logs_to_faiss_index(log_path, faiss_path)