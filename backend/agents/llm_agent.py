import os
import json
import logging
from typing import Dict, Any, Optional, List, Union
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Maximum tokens to include in a prompt
MAX_TOKENS = 8000

class LLMAgent:
    """A class to handle interactions with OpenAI's LLM models"""
    
    def __init__(self, model: str = "gpt-4o"):
        """Initialize the LLM agent with the specified model
        
        Args:
            model: The OpenAI model to use for analysis
        """
        self.model = model
        self.client = client
        
        # Verify API key is set
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        
        # System prompts for different tasks
        self.system_prompts = {
            "analyze": "You are a helpful document analysis assistant. Analyze the provided document and answer questions about it accurately and concisely. Use the document structure information to provide more accurate answers.",
            "summarize": "You are a document summarization assistant. Create a comprehensive summary of the provided document. Focus on the main points and key information. Use the document structure to create a well-organized summary.",
            "key_points": "You are a document analysis assistant. Extract the key points from the provided document. Focus on the most important information and insights. Use the document structure to identify the most relevant points.",
            "csv_analysis": "You are a data analysis assistant. Analyze the provided CSV data and answer questions about it. Provide insights and patterns from the data when relevant."
        }
    
    def analyze_document(self, doc: Any, query: str, max_tokens: int = MAX_TOKENS) -> Dict[str, Any]:
        """Analyze a document with a specific query
        
        Args:
            doc: The document object containing text to analyze
            query: The query to ask about the document
            max_tokens: Maximum number of tokens to use from the document
            
        Returns:
            Dict containing the response and metadata
        """
        try:
            # Prepare document content, limiting to max_tokens
            doc_content = doc.text[:max_tokens] if hasattr(doc, 'text') else str(doc)[:max_tokens]
            
            # Check if we have Docling data available
            has_docling_data = hasattr(doc, 'docling_data') and doc.docling_data
            
            # Create system message with instructions
            system_message = {
                "role": "system", 
                "content": self.system_prompts["analyze"]
            }
            
            # Create user message with document and query
            user_content = ""
            
            if has_docling_data:
                # Extract document structure from Docling data
                structure_info = self._extract_structure_info(doc.docling_data)
                
                # Create a more structured prompt with Docling data
                user_content = f"""DOCUMENT TITLE: {structure_info.get('title', 'Untitled Document')}

DOCUMENT STRUCTURE:
{structure_info.get('structure_text', '')}

DOCUMENT CONTENT:
{doc_content}

QUERY:
{query}"""
            else:
                # Standard prompt without Docling data
                user_content = f"DOCUMENT:\n{doc_content}\n\nQUERY:\n{query}"
            
            user_message = {
                "role": "user",
                "content": user_content
            }
            
            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[system_message, user_message],
                temperature=0.3,  # Lower temperature for more factual responses
                max_tokens=1000,   # Limit response length
            )
            
            # Extract and return the response
            result = {
                "response": response.choices[0].message.content,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "used_docling": has_docling_data
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing document: {str(e)}")
            return {"error": str(e), "response": "Sorry, I encountered an error while analyzing the document."}
    
    def _extract_structure_info(self, docling_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured information from Docling data
        
        Args:
            docling_data: The Docling data dictionary
            
        Returns:
            Dictionary with structured information
        """
        result = {
            "title": docling_data.get("title", "Untitled Document"),
            "structure_text": ""
        }
        
        # Build structure text
        structure_parts = []
        
        # Add page count
        pages = docling_data.get("pages", [])
        structure_parts.append(f"- Total pages: {len(pages)}")
        
        # Extract sections/headings
        sections = []
        for page_idx, page in enumerate(pages):
            for block in page.get("blocks", []):
                if block.get("type") == "heading":
                    sections.append(f"- Section: {block.get('text', '')} (Page {page_idx + 1})")
        
        if sections:
            structure_parts.append("\nDocument sections:")
            structure_parts.extend(sections[:10])  # Limit to 10 sections to avoid token bloat
            if len(sections) > 10:
                structure_parts.append(f"...and {len(sections) - 10} more sections")
        
        # Add tables info
        tables_count = sum(len(page.get("tables", [])) for page in pages)
        if tables_count > 0:
            structure_parts.append(f"\n- Document contains {tables_count} tables")
        
        # Add images info
        images_count = sum(len(page.get("images", [])) for page in pages)
        if images_count > 0:
            structure_parts.append(f"- Document contains {images_count} images/figures")
        
        result["structure_text"] = "\n".join(structure_parts)
        return result
    
    def summarize_document(self, doc: Any) -> Dict[str, Any]:
        """Generate a summary of the document
        
        Args:
            doc: The document object containing text to summarize
            
        Returns:
            Dict containing the summary and metadata
        """
        try:
            # Prepare document content
            doc_content = doc.text[:MAX_TOKENS] if hasattr(doc, 'text') else str(doc)[:MAX_TOKENS]
            
            # Check if we have Docling data available
            has_docling_data = hasattr(doc, 'docling_data') and doc.docling_data
            
            # Create system message with instructions
            system_message = {
                "role": "system", 
                "content": self.system_prompts["summarize"]
            }
            
            # Create user message
            user_content = ""
            
            if has_docling_data:
                # Extract document structure from Docling data
                structure_info = self._extract_structure_info(doc.docling_data)
                
                # Create a more structured prompt with Docling data
                user_content = f"""DOCUMENT TITLE: {structure_info.get('title', 'Untitled Document')}

DOCUMENT STRUCTURE:
{structure_info.get('structure_text', '')}

DOCUMENT CONTENT:
{doc_content}

TASK: Provide a comprehensive summary of this document. Include the main points and key information."""
            else:
                # Standard prompt without Docling data
                user_content = f"DOCUMENT:\n{doc_content}\n\nTASK: Provide a comprehensive summary of this document."
            
            user_message = {
                "role": "user",
                "content": user_content
            }
            
            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[system_message, user_message],
                temperature=0.3,
                max_tokens=1000,
            )
            
            # Extract and return the response
            result = {
                "response": response.choices[0].message.content,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "used_docling": has_docling_data
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error summarizing document: {str(e)}")
            return {"error": str(e), "response": "Sorry, I encountered an error while summarizing the document."}
    
    def extract_key_points(self, doc: Any) -> Dict[str, Any]:
        """Extract key points from the document
        
        Args:
            doc: The document object containing text to analyze
            
        Returns:
            Dict containing the key points and metadata
        """
        try:
            # Prepare document content
            doc_content = doc.text[:MAX_TOKENS] if hasattr(doc, 'text') else str(doc)[:MAX_TOKENS]
            
            # Check if we have Docling data available
            has_docling_data = hasattr(doc, 'docling_data') and doc.docling_data
            
            # Create system message with instructions
            system_message = {
                "role": "system", 
                "content": self.system_prompts["key_points"]
            }
            
            # Create user message
            user_content = ""
            
            if has_docling_data:
                # Extract document structure from Docling data
                structure_info = self._extract_structure_info(doc.docling_data)
                
                # Create a more structured prompt with Docling data
                user_content = f"""DOCUMENT TITLE: {structure_info.get('title', 'Untitled Document')}

DOCUMENT STRUCTURE:
{structure_info.get('structure_text', '')}

DOCUMENT CONTENT:
{doc_content}

TASK: Extract and list the key points from this document. Focus on the most important information and insights."""
            else:
                # Standard prompt without Docling data
                user_content = f"DOCUMENT:\n{doc_content}\n\nTASK: Extract and list the key points from this document."
            
            user_message = {
                "role": "user",
                "content": user_content
            }
            
            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[system_message, user_message],
                temperature=0.3,
                max_tokens=1000,
            )
            
            # Extract and return the response
            result = {
                "response": response.choices[0].message.content,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "used_docling": has_docling_data
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting key points: {str(e)}")
            return {"error": str(e), "response": "Sorry, I encountered an error while extracting key points from the document."}
    
    def analyze_csv_data(self, doc: Any, query: str) -> Dict[str, Any]:
        """Analyze CSV data with a specific query
        
        Args:
            doc: The document object containing CSV data
            query: The query about the CSV data
            
        Returns:
            Dict containing the analysis and metadata
        """
        try:
            # Create a specialized prompt for CSV data
            system_message = {
                "role": "system", 
                "content": "You are a data analysis assistant. Analyze the provided CSV data and answer questions about it."
            }
            
            # Create user message with document and query
            user_message = {
                "role": "user",
                "content": f"CSV DATA:\n{doc.text}\n\nQUERY:\n{query}"
            }
            
            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[system_message, user_message],
                temperature=0.2,  # Lower temperature for more factual responses
                max_tokens=1000,   # Limit response length
            )
            
            # Extract and return the response
            result = {
                "response": response.choices[0].message.content,
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing CSV data: {str(e)}")
            return {"error": str(e), "response": "Sorry, I encountered an error while analyzing the CSV data."}

# For backward compatibility
def ask_docling(doc, query):
    """Legacy function for backward compatibility"""
    agent = LLMAgent()
    result = agent.analyze_document(doc, query)
    return result.get("response", "Error analyzing document")

