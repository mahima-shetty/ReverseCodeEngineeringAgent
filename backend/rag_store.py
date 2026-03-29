import os
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index")
_vectorstore = None
_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings

def init_rag_store():
    global _vectorstore
    
    # Try to load existing index
    try:
        if os.path.exists(FAISS_INDEX_DIR):
            _vectorstore = FAISS.load_local(FAISS_INDEX_DIR, get_embeddings(), allow_dangerous_deserialization=True)
            print("Loaded FAISS index from disk.")
            return
    except Exception as e:
        print(f"Error loading FAISS index: {e}, will recreate it.")

    # Read urls from .env
    links_str = os.getenv("ORACLE_LINKS", "")
    if not links_str:
        print("No ORACLE_LINKS found in environment. Please add comma-separated links to .env.")
        return
        
    urls = [url.strip() for url in links_str.split(",") if url.strip()]
    if not urls:
        print("ORACLE_LINKS environment variable is empty.")
        return
        
    print(f"Loading documents from {len(urls)} URLs...")
    docs = []
    for url in urls:
        try:
            loader = WebBaseLoader(url)
            docs.extend(loader.load())
        except Exception as e:
            print(f"Failed to load {url}: {e}")
            
    if not docs:
        print("No documents were loaded from urls.")
        return
        
    print("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    splits = text_splitter.split_documents(docs)
    
    print("Creating FAISS index with sentence-transformers...")
    try:
        _vectorstore = FAISS.from_documents(splits, get_embeddings())
        _vectorstore.save_local(FAISS_INDEX_DIR)
        print("FAISS index saved successfully.")
    except Exception as e:
        print(f"Error creating FAISS index: {e}")

def get_rag_context(query: str, k: int = 3) -> str:
    global _vectorstore
    if not _vectorstore:
        init_rag_store() # Try initializing one last time if not loaded
    if not _vectorstore:
        return ""
    
    try:
        docs = _vectorstore.similarity_search(query, k=k)
        context_text = "\n\n".join([f"Source ({doc.metadata.get('source')}):\n{doc.page_content}" for doc in docs])
        return context_text
    except Exception as e:
        print(f"Error in RAG search: {e}")
        return ""
