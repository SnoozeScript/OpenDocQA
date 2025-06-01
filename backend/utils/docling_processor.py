import os
import logging
from typing import Dict, Any, List, Optional, Union
from io import BytesIO
import tempfile
import json

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus
from docling.datamodel.pipeline_options import (
    PipelineOptions, 
    EasyOcrOptions, 
    TesseractOcrOptions
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DoclingProcessor:
    """Class to handle document processing using Docling"""
    
    def __init__(self, use_ocr: bool = True, ocr_engine: str = "easyocr"):
        """Initialize the Docling processor
        
        Args:
            use_ocr: Whether to use OCR for scanned documents
            ocr_engine: OCR engine to use ('easyocr' or 'tesseract')
        """
        # Configure pipeline options
        self.pipeline_options = PipelineOptions()
        self.pipeline_options.do_ocr = use_ocr
        
        # Set OCR options based on specified engine
        if use_ocr:
            if ocr_engine.lower() == "easyocr":
                self.pipeline_options.ocr_options = EasyOcrOptions()
            elif ocr_engine.lower() == "tesseract":
                self.pipeline_options.ocr_options = TesseractOcrOptions()
            else:
                logger.warning(f"Unknown OCR engine: {ocr_engine}. Defaulting to EasyOCR.")
                self.pipeline_options.ocr_options = EasyOcrOptions()
        
        # Initialize document converter
        self.converter = DocumentConverter(pipeline_options=self.pipeline_options)
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Process a document file using Docling
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary with processed document information
        """
        try:
            # Convert the document
            result = self.converter.convert(file_path)
            
            # Check conversion status
            if result.status != ConversionStatus.SUCCESS:
                logger.error(f"Conversion failed with status: {result.status}")
                return {
                    "success": False,
                    "error": f"Conversion failed with status: {result.status}",
                    "text": "",
                    "metadata": {}
                }
            
            # Extract document content
            document = result.document
            
            # Get document as markdown
            markdown_content = document.export_to_markdown()
            
            # Get document as JSON
            json_content = document.model_dump_json()
            json_data = json.loads(json_content)
            
            # Create response
            response = {
                "success": True,
                "text": markdown_content,
                "json_data": json_data,
                "metadata": {
                    "title": document.title if hasattr(document, "title") else "",
                    "page_count": len(document.pages) if hasattr(document, "pages") else 0,
                    "has_images": any(page.images for page in document.pages) if hasattr(document, "pages") else False,
                    "extraction_method": "docling"
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing document with Docling: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "metadata": {}
            }
    
    def process_file_object(self, file_obj: BytesIO, filename: str) -> Dict[str, Any]:
        """Process a file object using Docling
        
        Args:
            file_obj: File object (BytesIO)
            filename: Name of the file
            
        Returns:
            Dictionary with processed document information
        """
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                temp_path = temp_file.name
                # Write the file content to the temporary file
                file_obj.seek(0)
                temp_file.write(file_obj.read())
            
            # Process the temporary file
            result = self.process_file(temp_path)
            
            # Clean up the temporary file
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_path}: {str(e)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing file object with Docling: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "metadata": {}
            }
    
    def extract_sections(self, document_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract sections from a document JSON
        
        Args:
            document_json: Document JSON data from Docling
            
        Returns:
            List of sections with title and content
        """
        sections = []
        
        try:
            # Extract sections from the document structure
            if "pages" in document_json:
                for page_idx, page in enumerate(document_json["pages"]):
                    if "blocks" in page:
                        current_section = None
                        section_content = []
                        
                        for block in page["blocks"]:
                            # Check if block is a heading
                            if block.get("type") == "heading":
                                # Save previous section if exists
                                if current_section and section_content:
                                    sections.append({
                                        "title": current_section,
                                        "content": "\n".join(section_content),
                                        "page": page_idx + 1
                                    })
                                
                                # Start new section
                                current_section = block.get("text", "")
                                section_content = []
                            elif block.get("type") == "paragraph" or block.get("type") == "text":
                                # Add to current section content
                                section_content.append(block.get("text", ""))
                        
                        # Add the last section from this page
                        if current_section and section_content:
                            sections.append({
                                "title": current_section,
                                "content": "\n".join(section_content),
                                "page": page_idx + 1
                            })
        except Exception as e:
            logger.error(f"Error extracting sections: {str(e)}")
        
        return sections
    
    def get_document_structure(self, document_json: Dict[str, Any]) -> Dict[str, Any]:
        """Get document structure information
        
        Args:
            document_json: Document JSON data from Docling
            
        Returns:
            Dictionary with document structure information
        """
        structure = {
            "title": document_json.get("title", ""),
            "sections": self.extract_sections(document_json),
            "page_count": len(document_json.get("pages", [])),
            "has_tables": False,
            "has_images": False,
            "has_charts": False
        }
        
        # Check for tables, images, and charts
        for page in document_json.get("pages", []):
            if page.get("tables"):
                structure["has_tables"] = True
            if page.get("images"):
                structure["has_images"] = True
            # Check for charts (might be in images with certain characteristics)
            if page.get("images"):
                for image in page.get("images", []):
                    if image.get("is_chart", False):
                        structure["has_charts"] = True
                        break
        
        return structure


# Helper function to process a document file
def process_document_with_docling(file_path: str, use_ocr: bool = True) -> Dict[str, Any]:
    """Process a document file using Docling
    
    Args:
        file_path: Path to the document file
        use_ocr: Whether to use OCR for scanned documents
        
    Returns:
        Dictionary with processed document information
    """
    processor = DoclingProcessor(use_ocr=use_ocr)
    return processor.process_file(file_path)
