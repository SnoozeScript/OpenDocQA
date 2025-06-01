import os
import logging
from typing import BinaryIO, Dict, Any, Optional, Union
import pandas as pd
import pdfplumber
from io import BytesIO

# Import Docling processor
from utils.docling_processor import DoclingProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TextDocument:
    """Class to represent a text document"""
    
    def __init__(self, text: str, metadata: Optional[Dict[str, Any]] = None, docling_data: Optional[Dict[str, Any]] = None):
        """Initialize a text document
        
        Args:
            text: The text content of the document
            metadata: Optional metadata about the document
            docling_data: Optional Docling processed data
        """
        self.text = text
        self.metadata = metadata or {}
        self.docling_data = docling_data or {}
    
    def __str__(self) -> str:
        return f"TextDocument(length={len(self.text)}, metadata={self.metadata})"


class DocumentParser:
    """Class to handle parsing different document types"""
    
    @staticmethod
    def parse_pdf(file: Union[BinaryIO, BytesIO]) -> TextDocument:
        """Parse a PDF file
        
        Args:
            file: The PDF file object
            
        Returns:
            TextDocument containing the extracted text
        """
        try:
            with pdfplumber.open(file) as pdf:
                pages = []
                metadata = {"page_count": len(pdf.pages)}
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                    else:
                        logger.warning(f"No text extracted from page {i+1}")
                
                full_text = "\n\n".join(pages)
                if not full_text.strip():
                    logger.warning("No text extracted from PDF")
                    return TextDocument("No readable text found in the PDF.", {"error": "empty_pdf"})
                
                return TextDocument(full_text, metadata)
        except Exception as e:
            logger.error(f"Error parsing PDF: {str(e)}")
            return TextDocument(f"Error parsing PDF: {str(e)}", {"error": "pdf_parsing_error"})
    
    @staticmethod
    def parse_csv(file: Union[BinaryIO, BytesIO]) -> TextDocument:
        """Parse a CSV file
        
        Args:
            file: The CSV file object
            
        Returns:
            TextDocument containing the CSV data
        """
        try:
            df = pd.read_csv(file)
            metadata = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns)
            }
            
            # Convert to string representation
            text = df.to_string(index=False)
            
            return TextDocument(text, metadata)
        except Exception as e:
            logger.error(f"Error parsing CSV: {str(e)}")
            return TextDocument(f"Error parsing CSV: {str(e)}", {"error": "csv_parsing_error"})
    
    @staticmethod
    def parse_excel(file: Union[BinaryIO, BytesIO]) -> TextDocument:
        """Parse an Excel file
        
        Args:
            file: The Excel file object
            
        Returns:
            TextDocument containing the Excel data
        """
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file)
            sheet_names = excel_file.sheet_names
            
            all_sheets = []
            metadata = {"sheet_count": len(sheet_names), "sheets": {}}
            
            for sheet_name in sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                sheet_text = f"Sheet: {sheet_name}\n{df.to_string(index=False)}"
                all_sheets.append(sheet_text)
                
                # Add metadata for this sheet
                metadata["sheets"][sheet_name] = {
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns)
                }
            
            # Combine all sheets
            full_text = "\n\n".join(all_sheets)
            
            return TextDocument(full_text, metadata)
        except Exception as e:
            logger.error(f"Error parsing Excel: {str(e)}")
            return TextDocument(f"Error parsing Excel: {str(e)}", {"error": "excel_parsing_error"})


def parse_file_with_docling(file: BinaryIO) -> TextDocument:
    """Parse a file using Docling and fallback to traditional parsers if needed
    
    Args:
        file: The file object to parse
        
    Returns:
        TextDocument containing the parsed content
    """
    try:
        filename = file.filename.lower() if hasattr(file, 'filename') else ''
        parser = DocumentParser()
        
        # Create a copy of the file in memory to avoid issues with file pointers
        file_copy = BytesIO(file.read())
        file.seek(0)  # Reset the original file pointer
        
        # Try to use Docling first for PDF files
        if filename.endswith(".pdf"):
            try:
                # Initialize Docling processor
                docling_processor = DoclingProcessor(use_ocr=True)
                
                # Process with Docling
                docling_result = docling_processor.process_file_object(file_copy, filename)
                file_copy.seek(0)  # Reset file pointer for potential fallback
                
                if docling_result.get("success", False):
                    # Successfully processed with Docling
                    logger.info(f"Successfully processed {filename} with Docling")
                    return TextDocument(
                        text=docling_result.get("text", ""),
                        metadata=docling_result.get("metadata", {}),
                        docling_data=docling_result.get("json_data", {})
                    )
                else:
                    # Docling processing failed, fall back to traditional parser
                    logger.warning(f"Docling processing failed: {docling_result.get('error', 'Unknown error')}. Falling back to traditional parser.")
                    return parser.parse_pdf(file_copy)
            except Exception as e:
                # Error with Docling, fall back to traditional parser
                logger.warning(f"Error using Docling: {str(e)}. Falling back to traditional parser.")
                return parser.parse_pdf(file_copy)
        elif filename.endswith(".csv"):
            return parser.parse_csv(file_copy)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            return parser.parse_excel(file_copy)
        else:
            logger.warning(f"Unsupported file type: {filename}")
            return TextDocument(f"Unsupported file type: {os.path.splitext(filename)[1]}", 
                               {"error": "unsupported_file_type"})
    except Exception as e:
        logger.error(f"Error parsing file: {str(e)}")
        return TextDocument(f"Error parsing file: {str(e)}", {"error": "parsing_error"})
