import os
from qdrant_client.http.models import PointStruct
from qdrant_client import QdrantClient, models
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv
import uuid  # For generating UUIDs

# Load environment variables
load_dotenv()

# Initialize Azure OpenAI client
embeddings = AzureOpenAIEmbeddings(
    model="text-embedding-3-large",
    azure_deployment="text-embedding-3-large",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
)

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=200)

# Define the batch size based on approximate size per point
BATCH_SIZE = 100  # Number of points per batch

def upsert_to_qdrant_by_chapter(folder_path, chapter_name=None):
    """
    Upserts embeddings to Qdrant collections for each chapter from text files in the specified folder.
    
    :param folder_path: Path to the folder containing text files.
    :param chapter_name: Specific chapter to process (default: None processes all chapters).
    """
    if chapter_name:
        file_list = [f"{chapter_name}.txt"]
    else:
        file_list = [f for f in os.listdir(folder_path) if f.endswith(".txt")]
    
    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)
        loader = TextLoader(file_path)
        pages = [page for page in loader.lazy_load()]
        
        texts = text_splitter.split_documents(pages)
        
        # Collection name is based on the chapter name (without .txt extension)
        collection_name = f"{os.path.splitext(file_name)[0]}_collection"
        
        if not qdrant_client.collection_exists(collection_name):
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=3072, distance=models.Distance.COSINE),
            )
            print(f"Created new collection: {collection_name}")
        
        print(f"Processing '{file_name}' with {len(texts)} chunks...")
        
        points = []
        for idx, text in enumerate(texts):
            embedding = embeddings.embed_query(text.page_content)
            payload = {
                "filename": file_name,
                "text": text.page_content,
                "chunk_id": idx,
            }
            point_id = str(uuid.uuid4())
            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))
            
            # If we have reached the batch size, upsert the batch
            if len(points) >= BATCH_SIZE:
                qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"Upserted {len(points)} points to '{collection_name}'")
                points = []  # Reset the batch
        
        # If there are any remaining points after the loop, upsert them
        if points:
            qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            print(f"Upserted {len(points)} points to '{collection_name}'")

if __name__ == "__main__":
    # Upsert embeddings for all files in the folder
    folder_path = "background_info"
    upsert_to_qdrant_by_chapter(folder_path=folder_path)
    print("Embeddings stored in individual collections successfully!") 