
import os
import numpy as np
import faiss
import pickle
import sys

from microtutor.utils.embedding_utils import get_embedding


# Load FAISS index and texts for example retrieval
base_dir = os.path.dirname(__file__)
index_path = os.path.join(base_dir, 'output_index.faiss')
texts_path = os.path.join(base_dir, 'output_index.faiss.texts')
index = None
texts = None
try:
    with open(index_path, 'rb') as f:
        index = pickle.load(f)
    with open(texts_path, 'rb') as f:
        texts = pickle.load(f)
except Exception as e:
    print(f"⚠️ Warning: Failed to load FAISS index or texts: {e}")


def retrieve_similar_examples(input_text: str, history: list, k: int = 3) -> list[str]:
    """Embed the last four messages + current user input, then fetch top-k similar feedback examples."""
    if index is None or texts is None:
        return []
    
    try:
        recent_context = ""
        if history:
            recent_context = "Chat history:\n"
            for message in history[-5:-1]:  # same slice as in index creation
                if "role" in message and "content" in message:
                    recent_context += f"{message['role']}: {message['content']}\n"
        embedding_input = recent_context + f"Rated message: {input_text}"
        emb = get_embedding(embedding_input)
        distances, indices = index.search(np.array([emb]).astype('float32'), k=k)
        return [texts[idx] for idx in indices[0]]
    except Exception as e:
        print(f"⚠️ Warning: Failed to retrieve similar examples: {e}")
        return []


