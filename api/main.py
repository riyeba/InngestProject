


import os
import shutil
import logging
import inngest
import inngest.fast_api
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form

# LlamaIndex Imports
from llama_index.core import StorageContext, VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client import AsyncQdrantClient

# 1. Load Environment Variables
load_dotenv()

# 2. Global Configuration
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
openai_key = os.getenv("OPENAI_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")
qdrant_key = os.getenv("QDRANT_API_KEY")

llm = OpenAI(model="gpt-4o-mini", api_key=openai_key)

# 3. Initialize Clients
inngest_client = inngest.Inngest(
    app_id="fast_api_example",
    logger=logging.getLogger("uvicorn"),
)



# Connect to Qdrant
qdrant_client = AsyncQdrantClient(
    url=qdrant_url,
    api_key=qdrant_key,
    port=None,  
    timeout=60
)

# Setup Vector Store
vector_store = QdrantVectorStore(aclient=qdrant_client, collection_name="demo")
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# 4. The Durable Inngest Function
@inngest_client.create_function(
    fn_id="import-product-documents",
    trigger=inngest.TriggerEvent(event="shop/product.imported"),
    concurrency=[
        inngest.Concurrency(limit=1)
    ]
)
async def import_product_documents(ctx: inngest.Context):
    target_file = ctx.event.data.get("file_path")
    query_text = ctx.event.data.get("user_question")

    # STEP 1: Load Data
    
    async def index_logic():
        documents = SimpleDirectoryReader(input_files=[target_file]).load_data()
        VectorStoreIndex.from_documents(
            documents, 
            storage_context=storage_context,
            use_async=True
        )
        # This return ONLY exits 'index_logic', NOT 'import_product_documents'
        return {"status": "success", "count": len(documents)}
    
    step_result = await ctx.step.run("index-to-qdrant", index_logic)
 

    # STEP 3: Query the engine (The code will reach here!)
    async def query_logic():
        index = VectorStoreIndex.from_vector_store(vector_store)
        query_engine = index.as_query_engine(llm=llm)
        response = await query_engine.aquery(query_text)
        return str(response)

    final_answer = await ctx.step.run("generate-rag-response", query_logic)

    # Final return for the whole workflow
    return {"answer": final_answer, "indexing_meta": step_result}
   

# 5. FastAPI Setup
app = FastAPI()

# Serve Inngest
inngest.fast_api.serve(app, inngest_client, [import_product_documents])

UPLOAD_DIR = "uploaded_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload-and-index")
async def upload_document(
    question: str = Form(...), 
    file: UploadFile = File(...)
):
    # Save the file locally
    local_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    full_absolute_path = os.path.abspath(local_path)
    
    # Trigger the durable workflow
    await inngest_client.send(
        inngest.Event(
            name="shop/product.imported",
            data={
                "file_path": full_absolute_path,
                "user_question": question  
            }
        )
    )
    
    return {
        "message": f"File {file.filename} queued for processing.",
        "status": "In-progress"
    }