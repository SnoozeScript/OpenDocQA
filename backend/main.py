from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Query, Path, Depends, status, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from typing import Dict, Any, List, Optional, Union, Callable, Annotated
import os
import uuid
import logging
import json
import time
import asyncio
from datetime import datetime, timedelta
import shutil
from pathlib import Path as FilePath
import traceback
import io
from functools import lru_cache
import re

# Secure filename function (similar to werkzeug.utils.secure_filename)
def secure_filename(filename):
    """Return a secure version of a filename."""
    if not filename:
        return ''
    filename = str(filename).strip().replace(' ', '_')
    # Remove non-ASCII characters
    filename = re.sub(r'[^\w\._-]', '', filename)
    # Remove multiple dots
    filename = re.sub(r'\.+', '.', filename)
    # Ensure it's not starting with a dot
    if filename.startswith('.'):
        filename = 'file' + filename
    return filename

# Import our custom modules
from utils.parser import parse_file_with_docling
from utils.docling_processor import DoclingProcessor
from agents.llm_agent import LLMAgent

# Configure environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# App Settings
class Settings:
    PROJECT_NAME: str = "Document Analysis API"
    PROJECT_DESCRIPTION: str = "API for document analysis with Docling integration"
    API_VERSION: str = "1.0.0"
    UPLOAD_FOLDER: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    ALLOWED_EXTENSIONS: set = {"pdf", "txt", "csv", "xlsx", "xls"}
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16 MB
    ENABLE_DOCLING: bool = True
    ENABLE_OCR: bool = True
    API_KEY_NAME: str = "X-API-Key"
    API_KEY: Optional[str] = os.getenv("API_KEY", None)
    ENABLE_AUTH: bool = False  # Set to True to enable API key authentication
    
@lru_cache()
def get_settings():
    return Settings()

# Request Processing Time Middleware
class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

# Error Logging Middleware
class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error", "error": str(e)}
            )

# API Key Dependency
async def verify_api_key(request: Request, settings: Settings = Depends(get_settings)):
    if not settings.ENABLE_AUTH:
        return True
    
    api_key = request.headers.get(settings.API_KEY_NAME)
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return True

# Initialize FastAPI app
app = FastAPI(
    title=get_settings().PROJECT_NAME,
    description=get_settings().PROJECT_DESCRIPTION,
    version=get_settings().API_VERSION,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
)

# Configure Middleware
app.add_middleware(ProcessTimeMiddleware)
app.add_middleware(ErrorLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create uploads directory if it doesn't exist
os.makedirs(get_settings().UPLOAD_FOLDER, exist_ok=True)

# Serve static files
app.mount("/uploads", StaticFiles(directory=get_settings().UPLOAD_FOLDER), name="uploads")

# In-memory document store
doc_store = {}

# Custom exception handler
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    return await http_exception_handler(request, exc)

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=get_settings().PROJECT_NAME,
        version=get_settings().API_VERSION,
        description=get_settings().PROJECT_DESCRIPTION,
        routes=app.routes,
    )
    
    # Add custom security scheme if auth is enabled
    if get_settings().ENABLE_AUTH:
        openapi_schema["components"] = openapi_schema.get("components", {})
        openapi_schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": get_settings().API_KEY_NAME,
            }
        }
        openapi_schema["security"] = [{"ApiKeyAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Custom documentation endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{get_settings().PROJECT_NAME} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{get_settings().PROJECT_NAME} - ReDoc",
    )

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in get_settings().ALLOWED_EXTENSIONS

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": get_settings().API_VERSION,
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Document Analysis API with Docling Integration",
        "documentation": "/docs",
        "version": get_settings().API_VERSION,
    }

# Models for request/response validation
from pydantic import BaseModel

class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    upload_time: str
    processed_with_docling: bool
    file_size: int
    content_type: str
    processing_time: float

class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    upload_time: str
    file_size: int
    content_type: str
    processing_complete: bool
    processing_error: Optional[str] = None

class DocumentList(BaseModel):
    documents: List[DocumentListItem]
    count: int

class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    upload_time: str
    file_size: int
    content_type: str
    text_length: Optional[int] = None
    has_docling_data: bool
    processing_complete: bool
    processing_time: Optional[float] = None
    processing_error: Optional[str] = None

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    document_id: str
    query: str
    response: str
    processed_with_docling: bool
    processing_time: float
    tokens_used: Optional[int] = None

class KeyPoint(BaseModel):
    point: str
    relevance: Optional[float] = None

class KeyPointsResponse(BaseModel):
    document_id: str
    key_points: List[KeyPoint]
    processed_with_docling: bool
    processing_time: float
    tokens_used: Optional[int] = None

class Insight(BaseModel):
    topic: str
    description: str
    confidence: Optional[float] = None

class InsightsResponse(BaseModel):
    document_id: str
    insights: List[Insight]
    processed_with_docling: bool
    processing_time: float
    tokens_used: Optional[int] = None

class DeleteResponse(BaseModel):
    document_id: str
    message: str
    filename: str
    file_deleted: bool

class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    upload_time: str
    processed_with_docling: bool
    file_size: int
    content_type: str
    processing_time: float

# Background task for document processing
async def process_document_in_background(document_id: str, file_path: str, filename: str):
    try:
        start_time = time.time()
        # Process the file with Docling
        with open(file_path, "rb") as f:
            document = parse_file_with_docling(f)
        
        processing_time = time.time() - start_time
        
        # Update document in store with processed data
        if document_id in doc_store:
            doc_store[document_id].update({
                "document": document,
                "processing_complete": True,
                "processing_time": processing_time,
                "processed_with_docling": hasattr(document, 'docling_data') and bool(document.docling_data)
            })
            
            logger.info(f"Background processing complete for document: {filename}, ID: {document_id}, time: {processing_time:.2f}s")
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")
        if document_id in doc_store:
            doc_store[document_id].update({
                "processing_complete": True,
                "processing_error": str(e),
                "error_traceback": traceback.format_exc()
            })

@app.post("/api/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    settings: Settings = Depends(get_settings),
    api_key: bool = Depends(verify_api_key)
):
    """
    Upload a document for analysis
    
    - **file**: The document file to upload (PDF, TXT, CSV, XLSX, XLS)
    """
    try:
        # Validate file
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="No file provided or filename is empty"
            )
        
        filename = file.filename
        if not allowed_file(filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Read file content to check size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Check file size
        if file_size > settings.MAX_CONTENT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_CONTENT_LENGTH / (1024 * 1024):.1f} MB"
            )
        
        # Generate a unique ID for the document
        document_id = str(uuid.uuid4())
        
        # Create a temporary file to store the uploaded content
        safe_filename = secure_filename(filename)
        temp_file_path = os.path.join(settings.UPLOAD_FOLDER, f"{document_id}_{safe_filename}")
        
        # Save the uploaded file
        with open(temp_file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Reset file position for future reads
        await file.seek(0)
        
        # Store initial document info
        upload_time = datetime.now().isoformat()
        doc_store[document_id] = {
            "filename": filename,
            "safe_filename": safe_filename,
            "upload_time": upload_time,
            "file_path": temp_file_path,
            "file_size": file_size,
            "content_type": file.content_type,
            "processing_complete": False
        }
        
        # Add background task for processing
        background_tasks.add_task(
            process_document_in_background,
            document_id,
            temp_file_path,
            filename
        )
        
        logger.info(f"Uploaded document: {filename}, ID: {document_id}, Size: {file_size/1024:.1f} KB")
        
        # Return document info immediately
        return DocumentResponse(
            document_id=document_id,
            filename=filename,
            upload_time=upload_time,
            processed_with_docling=False,  # Processing happens in background
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            processing_time=0.0  # Will be updated after background processing
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={
                "message": "Server error during file upload",
                "error": str(e)
            }
        )

@app.get("/api/documents", response_model=DocumentList)
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of documents to return"),
    api_key: bool = Depends(verify_api_key)
):
    """
    List all uploaded documents with pagination
    
    - **skip**: Number of documents to skip (for pagination)
    - **limit**: Maximum number of documents to return
    """
    try:
        documents = []
        sorted_docs = sorted(
            doc_store.items(),
            key=lambda x: x[1].get("upload_time", ""),
            reverse=True
        )
        
        # Apply pagination
        paginated_docs = sorted_docs[skip:skip + limit]
        
        for doc_id, doc_info in paginated_docs:
            doc_item = DocumentListItem(
                document_id=doc_id,
                filename=doc_info["filename"],
                upload_time=doc_info["upload_time"],
                file_size=doc_info.get("file_size", 0),
                content_type=doc_info.get("content_type", "application/octet-stream"),
                processing_complete=doc_info.get("processing_complete", True),
                processing_error=doc_info.get("processing_error", None)
            )
            documents.append(doc_item)
        
        return DocumentList(documents=documents, count=len(doc_store))
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}"
        )

@app.get("/api/document/{document_id}", response_model=DocumentInfo)
async def get_document(
    document_id: str = Path(..., description="The ID of the document to retrieve"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Get document information
    
    - **document_id**: The ID of the document to retrieve
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        doc_info = doc_store[document_id]
        
        # Check if document is still processing
        if not doc_info.get("processing_complete", True):
            return DocumentInfo(
                document_id=document_id,
                filename=doc_info["filename"],
                upload_time=doc_info["upload_time"],
                file_size=doc_info.get("file_size", 0),
                content_type=doc_info.get("content_type", "application/octet-stream"),
                has_docling_data=False,
                processing_complete=False
            )
        
        # Check for processing errors
        if "processing_error" in doc_info:
            return DocumentInfo(
                document_id=document_id,
                filename=doc_info["filename"],
                upload_time=doc_info["upload_time"],
                file_size=doc_info.get("file_size", 0),
                content_type=doc_info.get("content_type", "application/octet-stream"),
                has_docling_data=False,
                processing_complete=True,
                processing_error=doc_info["processing_error"],
                processing_time=doc_info.get("processing_time", 0.0)
            )
        
        # Get document data
        document = doc_info.get("document")
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document data not found in storage"
            )
        
        return DocumentInfo(
            document_id=document_id,
            filename=doc_info["filename"],
            upload_time=doc_info["upload_time"],
            file_size=doc_info.get("file_size", 0),
            content_type=doc_info.get("content_type", "application/octet-stream"),
            text_length=len(document.text) if hasattr(document, 'text') else 0,
            has_docling_data=hasattr(document, 'docling_data') and bool(document.docling_data),
            processing_complete=True,
            processing_time=doc_info.get("processing_time", 0.0)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

@app.post("/api/document/{document_id}/query", response_model=QueryResponse)
async def query_document(
    document_id: str = Path(..., description="The ID of the document to query"),
    query_request: QueryRequest = Body(..., description="The query to run against the document"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Query a document with a specific question
    
    - **document_id**: The ID of the document to query
    - **query_request**: The query to run against the document
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        doc_info = doc_store[document_id]
        
        # Check if document is still processing
        if not doc_info.get("processing_complete", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still being processed. Try again later."
            )
        
        # Check for processing errors
        if "processing_error" in doc_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {doc_info['processing_error']}"
            )
        
        document = doc_info.get("document")
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document data not found in storage"
            )
        
        # Initialize LLM agent
        llm_agent = LLMAgent()
        
        # Query the document
        start_time = time.time()
        result = await asyncio.to_thread(
            llm_agent.analyze_document, 
            document, 
            query_request.query
        )
        processing_time = time.time() - start_time
        
        logger.info(f"Query processed for document {document_id} in {processing_time:.2f}s")
        
        return QueryResponse(
            document_id=document_id,
            query=query_request.query,
            response=result.get("response", ""),
            processed_with_docling=hasattr(document, 'docling_data') and bool(document.docling_data),
            processing_time=processing_time,
            tokens_used=result.get("tokens_used")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying document: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

# Summary response model
class SummaryResponse(BaseModel):
    document_id: str
    summary: str
    processed_with_docling: bool
    processing_time: float
    tokens_used: Optional[int] = None

@app.get("/api/document/{document_id}/summary", response_model=SummaryResponse)
async def summarize_document(
    document_id: str = Path(..., description="The ID of the document to summarize"),
    max_length: int = Query(500, ge=100, le=2000, description="Maximum length of the summary"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Get a summary of the document
    
    - **document_id**: The ID of the document to summarize
    - **max_length**: Maximum length of the summary in characters
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        doc_info = doc_store[document_id]
        
        # Check if document is still processing
        if not doc_info.get("processing_complete", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still being processed. Try again later."
            )
        
        # Check for processing errors
        if "processing_error" in doc_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {doc_info['processing_error']}"
            )
        
        document = doc_info.get("document")
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document data not found in storage"
            )
        
        # Initialize LLM agent
        llm_agent = LLMAgent()
        
        # Summarize the document
        start_time = time.time()
        result = await asyncio.to_thread(
            llm_agent.summarize_document, 
            document,
            max_length
        )
        processing_time = time.time() - start_time
        
        logger.info(f"Summary generated for document {document_id} in {processing_time:.2f}s")
        
        return SummaryResponse(
            document_id=document_id,
            summary=result.get("summary", ""),
            processed_with_docling=hasattr(document, 'docling_data') and bool(document.docling_data),
            processing_time=processing_time,
            tokens_used=result.get("tokens_used")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing document: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

@app.get("/api/document/{document_id}/key_points", response_model=KeyPointsResponse)
async def extract_key_points(
    document_id: str = Path(..., description="The ID of the document to extract key points from"),
    max_points: int = Query(10, ge=3, le=30, description="Maximum number of key points to extract"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Extract key points from the document
    
    - **document_id**: The ID of the document to extract key points from
    - **max_points**: Maximum number of key points to extract
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        doc_info = doc_store[document_id]
        
        # Check if document is still processing
        if not doc_info.get("processing_complete", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still being processed. Try again later."
            )
        
        # Check for processing errors
        if "processing_error" in doc_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {doc_info['processing_error']}"
            )
        
        document = doc_info.get("document")
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document data not found in storage"
            )
        
        # Initialize LLM agent
        llm_agent = LLMAgent()
        
        # Extract key points
        start_time = time.time()
        result = await asyncio.to_thread(
            llm_agent.extract_key_points, 
            document,
            max_points
        )
        processing_time = time.time() - start_time
        
        # Convert key points to model format
        key_points_list = []
        for point in result.get("key_points", []):
            if isinstance(point, dict):
                key_points_list.append(KeyPoint(
                    point=point.get("point", ""),
                    relevance=point.get("relevance")
                ))
            elif isinstance(point, str):
                key_points_list.append(KeyPoint(point=point))
        
        logger.info(f"Key points extracted for document {document_id} in {processing_time:.2f}s")
        
        return KeyPointsResponse(
            document_id=document_id,
            key_points=key_points_list,
            processed_with_docling=hasattr(document, 'docling_data') and bool(document.docling_data),
            processing_time=processing_time,
            tokens_used=result.get("tokens_used")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting key points: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

# Structure response model
class DocumentStructure(BaseModel):
    document_id: str
    has_docling_data: bool
    structure: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    processing_time: Optional[float] = None

@app.get("/api/document/{document_id}/structure", response_model=DocumentStructure)
async def analyze_document_structure(
    document_id: str = Path(..., description="The ID of the document to analyze structure"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Analyze the structure of the document
    
    - **document_id**: The ID of the document to analyze structure
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        doc_info = doc_store[document_id]
        
        # Check if document is still processing
        if not doc_info.get("processing_complete", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still being processed. Try again later."
            )
        
        # Check for processing errors
        if "processing_error" in doc_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {doc_info['processing_error']}"
            )
        
        document = doc_info.get("document")
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document data not found in storage"
            )
        
        start_time = time.time()
        
        # Check if document has docling data
        if not hasattr(document, 'docling_data') or not document.docling_data:
            processing_time = time.time() - start_time
            return DocumentStructure(
                document_id=document_id,
                has_docling_data=False,
                message="Document was not processed with Docling or no structure data is available",
                processing_time=processing_time
            )
        
        # Return the document structure
        processing_time = time.time() - start_time
        logger.info(f"Structure analysis retrieved for document {document_id} in {processing_time:.2f}s")
        
        return DocumentStructure(
            document_id=document_id,
            has_docling_data=True,
            structure=document.docling_data,
            processing_time=processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing document structure: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

@app.get("/api/document/{document_id}/insights", response_model=InsightsResponse)
async def get_document_insights(
    document_id: str = Path(..., description="The ID of the document to get insights from"),
    max_insights: int = Query(5, ge=1, le=15, description="Maximum number of insights to extract"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Get insights from the document
    
    - **document_id**: The ID of the document to get insights from
    - **max_insights**: Maximum number of insights to extract
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        doc_info = doc_store[document_id]
        
        # Check if document is still processing
        if not doc_info.get("processing_complete", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still being processed. Try again later."
            )
        
        # Check for processing errors
        if "processing_error" in doc_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {doc_info['processing_error']}"
            )
        
        document = doc_info.get("document")
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document data not found in storage"
            )
        
        # Initialize LLM agent
        llm_agent = LLMAgent()
        
        # Get insights
        start_time = time.time()
        result = await asyncio.to_thread(
            llm_agent.get_insights, 
            document,
            max_insights
        )
        processing_time = time.time() - start_time
        
        # Convert insights to model format
        insights_list = []
        for insight in result.get("insights", []):
            if isinstance(insight, dict):
                insights_list.append(Insight(
                    topic=insight.get("topic", ""),
                    description=insight.get("description", ""),
                    confidence=insight.get("confidence")
                ))
            elif isinstance(insight, str):
                insights_list.append(Insight(topic="Insight", description=insight))
        
        logger.info(f"Insights extracted for document {document_id} in {processing_time:.2f}s")
        
        return InsightsResponse(
            document_id=document_id,
            insights=insights_list,
            processed_with_docling=hasattr(document, 'docling_data') and bool(document.docling_data),
            processing_time=processing_time,
            tokens_used=result.get("tokens_used")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document insights: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

@app.delete("/api/document/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str = Path(..., description="The ID of the document to delete"),
    api_key: bool = Depends(verify_api_key)
):
    """
    Delete a document and its associated file
    
    - **document_id**: The ID of the document to delete
    """
    try:
        if document_id not in doc_store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Document not found"
            )
        
        # Get document info
        doc_info = doc_store[document_id]
        filename = doc_info["filename"]
        
        # Remove from doc_store
        del doc_store[document_id]
        
        # Remove file if it exists
        file_deleted = False
        file_path = os.path.join(get_settings().UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                file_deleted = True
                logger.info(f"Deleted file: {file_path}")
            except Exception as file_error:
                logger.error(f"Error deleting file {file_path}: {str(file_error)}")
        
        logger.info(f"Document {document_id} deleted successfully")
        
        return DeleteResponse(
            document_id=document_id,
            message=f"Document {document_id} deleted successfully",
            filename=filename,
            file_deleted=file_deleted
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Server error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
