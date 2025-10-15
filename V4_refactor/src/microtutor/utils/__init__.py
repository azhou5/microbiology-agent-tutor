"""
Utility modules for the Microbiology Tutor application.
"""

# Import embedding utilities directly to avoid circular imports
try:
    from .embedding_utils import get_embedding, get_embeddings_batch, get_embedding_model_name, get_embedding_dimension
    __all__ = ["get_embedding", "get_embeddings_batch", "get_embedding_model_name", "get_embedding_dimension"]
except ImportError as e:
    # If there are import issues, we'll handle them gracefully
    print(f"Warning: Could not import embedding utilities: {e}")
    __all__ = []
