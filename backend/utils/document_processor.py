import os
import logging
import tempfile
from typing import List, Dict, Any, Optional, Union, Tuple
import pdfplumber
import pytesseract
from PIL import Image
import io
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document as LangchainDocument
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS, Chroma
from PyPDF2 import PdfReader
from unstructured.partition.pdf import partition_pdf
from tqdm import tqdm
import nltk
from nltk.tokenize import sent_tokenize

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Download NLTK data for sentence tokenization
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class DocumentProcessor:
    """Enhanced document processor for better text extraction and understanding"""
    
    def __init__(self, use_ocr: bool = True, embedding_model: str = "text-embedding-3-small"):
        """Initialize the document processor
        
        Args:
            use_ocr: Whether to use OCR for image-based PDFs
            embedding_model: The OpenAI embedding model to use
        """
        self.use_ocr = use_ocr
        self.embedding_model = embedding_model
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def process_pdf(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Process a PDF file with enhanced extraction
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Tuple of (extracted_text, metadata)
        """
        extracted_text = ""
        metadata = {"page_count": 0, "has_ocr": False, "has_images": False}
        
        try:
            # First try pdfplumber for text extraction
            with pdfplumber.open(file_path) as pdf:
                metadata["page_count"] = len(pdf.pages)
                pages_text = []
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append(text)
                    
                    # Check if page has images
                    if page.images:
                        metadata["has_images"] = True
                
                extracted_text = "\n\n".join(pages_text)
            
            # If no text was extracted or OCR is forced, try OCR
            if (not extracted_text.strip() or self.use_ocr) and metadata["has_images"]:
                logger.info("Using OCR for PDF processing")
                ocr_text = self._extract_with_ocr(file_path)
                if ocr_text.strip():
                    extracted_text = ocr_text if not extracted_text.strip() else f"{extracted_text}\n\n{ocr_text}"
                    metadata["has_ocr"] = True
            
            # If still no text, try unstructured-pdf as a fallback
            if not extracted_text.strip():
                logger.info("Using unstructured-pdf for extraction")
                elements = partition_pdf(file_path)
                extracted_text = "\n\n".join([str(element) for element in elements])
            
            # If still no text, try PyPDF2 as a last resort
            if not extracted_text.strip():
                logger.info("Using PyPDF2 for extraction")
                with open(file_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    pages_text = []
                    for page in pdf_reader.pages:
                        text = page.extract_text() or ""
                        if text.strip():
                            pages_text.append(text)
                    extracted_text = "\n\n".join(pages_text)
            
            # Add metadata about extraction
            metadata["extraction_method"] = "pdfplumber"
            if metadata.get("has_ocr", False):
                metadata["extraction_method"] += "+ocr"
            
            return extracted_text, metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return f"Error processing PDF: {str(e)}", {"error": "pdf_processing_error"}
    
    def _extract_with_ocr(self, file_path: str) -> str:
        """Extract text from PDF using OCR
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text from OCR
        """
        try:
            from pdf2image import convert_from_path
            
            # Convert PDF to images
            images = convert_from_path(file_path)
            ocr_texts = []
            
            # Process each image with OCR
            for img in images:
                text = pytesseract.image_to_string(img)
                if text.strip():
                    ocr_texts.append(text)
            
            return "\n\n".join(ocr_texts)
        except Exception as e:
            logger.error(f"OCR extraction error: {str(e)}")
            return ""
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[LangchainDocument]:
        """Split text into manageable chunks for processing
        
        Args:
            text: The text to split
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of LangchainDocument objects
        """
        metadata = metadata or {}
        documents = []
        
        # First try to split by sentences for more natural chunks
        try:
            sentences = sent_tokenize(text)
            current_chunk = ""
            current_chunk_size = 0
            max_chunk_size = 1000
            
            for sentence in sentences:
                if current_chunk_size + len(sentence) <= max_chunk_size:
                    current_chunk += sentence + " "
                    current_chunk_size += len(sentence) + 1
                else:
                    if current_chunk:
                        documents.append(LangchainDocument(
                            page_content=current_chunk.strip(),
                            metadata=metadata
                        ))
                    current_chunk = sentence + " "
                    current_chunk_size = len(sentence) + 1
            
            # Add the last chunk
            if current_chunk:
                documents.append(LangchainDocument(
                    page_content=current_chunk.strip(),
                    metadata=metadata
                ))
        except Exception as e:
            logger.warning(f"Error in sentence-based chunking: {str(e)}. Falling back to default chunker.")
            # Fall back to the default chunker
            texts = self.text_splitter.split_text(text)
            documents = [LangchainDocument(page_content=t, metadata=metadata) for t in texts]
        
        return documents
    
    def create_vector_store(self, documents: List[LangchainDocument], store_type: str = "faiss") -> Union[FAISS, Chroma]:
        """Create a vector store from document chunks
        
        Args:
            documents: List of document chunks
            store_type: Type of vector store to create ("faiss" or "chroma")
            
        Returns:
            Vector store object
        """
        if not documents:
            raise ValueError("No documents provided for vector store creation")
        
        if store_type.lower() == "faiss":
            return FAISS.from_documents(documents, self.embeddings)
        elif store_type.lower() == "chroma":
            return Chroma.from_documents(documents, self.embeddings)
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}")
    
    def semantic_search(self, vector_store: Union[FAISS, Chroma], query: str, k: int = 5) -> List[Tuple[LangchainDocument, float]]:
        """Perform semantic search on the vector store
        
        Args:
            vector_store: The vector store to search
            query: The search query
            k: Number of results to return
            
        Returns:
            List of (document, score) tuples
        """
        return vector_store.similarity_search_with_score(query, k=k)
    
    def extract_document_structure(self, text: str) -> Dict[str, Any]:
        """Extract document structure information
        
        Args:
            text: The document text
            
        Returns:
            Dictionary with structure information
        """
        structure = {
            "sections": [],
            "estimated_word_count": len(text.split()),
            "estimated_sentence_count": 0
        }
        
        try:
            # Try to identify sections by looking for patterns
            lines = text.split('\n')
            current_section = None
            section_content = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Heuristic for section headers
                if (len(line) < 100 and line.isupper()) or (len(line) < 100 and line.endswith(':')) or (len(line) < 50 and line[0].isdigit() and '.' in line[:5]):
                    # Save previous section if exists
                    if current_section and section_content:
                        structure["sections"].append({
                            "title": current_section,
                            "content_preview": " ".join(section_content[:3]) + "..." if len(section_content) > 3 else " ".join(section_content),
                            "word_count": sum(len(s.split()) for s in section_content)
                        })
                    
                    current_section = line
                    section_content = []
                else:
                    section_content.append(line)
            
            # Add the last section
            if current_section and section_content:
                structure["sections"].append({
                    "title": current_section,
                    "content_preview": " ".join(section_content[:3]) + "..." if len(section_content) > 3 else " ".join(section_content),
                    "word_count": sum(len(s.split()) for s in section_content)
                })
            
            # Count sentences
            try:
                sentences = sent_tokenize(text)
                structure["estimated_sentence_count"] = len(sentences)
            except:
                structure["estimated_sentence_count"] = text.count('.') + text.count('!') + text.count('?')
        
        except Exception as e:
            logger.error(f"Error extracting document structure: {str(e)}")
        
        return structure

# Helper function to process a document file
def process_document_file(file_path: str, use_ocr: bool = True) -> Dict[str, Any]:
    """Process a document file and return extracted information
    
    Args:
        file_path: Path to the document file
        use_ocr: Whether to use OCR for image-based content
        
    Returns:
        Dictionary with processed document information
    """
    processor = DocumentProcessor(use_ocr=use_ocr)
    result = {
        "text": "",
        "metadata": {},
        "chunks": [],
        "structure": {},
        "vector_store": None
    }
    
    try:
        # Process based on file type
        if file_path.lower().endswith('.pdf'):
            text, metadata = processor.process_pdf(file_path)
            result["text"] = text
            result["metadata"] = metadata
            
            # Extract document structure
            result["structure"] = processor.extract_document_structure(text)
            
            # Chunk the document
            chunks = processor.chunk_text(text, metadata)
            result["chunks"] = [{"text": doc.page_content, "metadata": doc.metadata} for doc in chunks]
            
            # Create vector store
            if chunks:
                result["vector_store"] = processor.create_vector_store(chunks)
        else:
            result["text"] = "Unsupported file type"
            result["metadata"] = {"error": "unsupported_file_type"}
    
    except Exception as e:
        logger.error(f"Error in document processing: {str(e)}")
        result["text"] = f"Error processing document: {str(e)}"
        result["metadata"] = {"error": "processing_error"}
    
    return result
