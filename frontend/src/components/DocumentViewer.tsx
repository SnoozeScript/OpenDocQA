import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';

interface DocumentViewerProps {
  apiKey: string;
}

interface DocumentInfo {
  document_id: string;
  filename: string;
  upload_time: string;
  file_size: number;
  content_type: string;
  text_length?: number;
  has_docling_data: boolean;
  processing_complete: boolean;
  processing_time?: number;
  processing_error?: string;
}

interface Summary {
  document_id: string;
  summary: string;
  processed_with_docling: boolean;
  processing_time: number;
  tokens_used?: number;
}

interface KeyPoint {
  point: string;
  relevance?: number;
}

interface KeyPointsResponse {
  document_id: string;
  key_points: KeyPoint[];
  processed_with_docling: boolean;
  processing_time: number;
  tokens_used?: number;
}

const DocumentViewer: React.FC<DocumentViewerProps> = ({ apiKey }) => {
  const { documentId } = useParams<{ documentId: string }>();
  const [activeTab, setActiveTab] = useState<'summary' | 'keyPoints' | 'query'>('summary');
  const [documentInfo, setDocumentInfo] = useState<DocumentInfo | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [keyPoints, setKeyPoints] = useState<KeyPointsResponse | null>(null);
  const [query, setQuery] = useState('');
  const [queryResponse, setQueryResponse] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isQuerying, setIsQuerying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocumentInfo = useCallback(async () => {
    if (!documentId) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }
      
      const response = await fetch(`/api/document/${documentId}`, {
        method: 'GET',
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setDocumentInfo(data);
    } catch (err) {
      setError('Failed to load document information.');
      console.error('Error fetching document:', err);
    } finally {
      setIsLoading(false);
    }
  }, [documentId, apiKey]);

  const fetchSummary = useCallback(async () => {
    if (!documentId || !documentInfo?.processing_complete) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }
      
      const response = await fetch(`/api/document/${documentId}/summary?max_length=1000`, {
        method: 'GET',
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setSummary(data);
    } catch (err) {
      setError('Failed to load document summary.');
      console.error('Error fetching summary:', err);
    } finally {
      setIsLoading(false);
    }
  }, [documentId, documentInfo, apiKey]);

  const fetchKeyPoints = useCallback(async () => {
    if (!documentId || !documentInfo?.processing_complete) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }
      
      const response = await fetch(`/api/document/${documentId}/key_points?max_points=10`, {
        method: 'GET',
        headers
      });
      
      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setKeyPoints(data);
    } catch (err) {
      setError('Failed to load document key points.');
      console.error('Error fetching key points:', err);
    } finally {
      setIsLoading(false);
    }
  }, [documentId, documentInfo, apiKey]);

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || !documentId || !documentInfo?.processing_complete) return;
    
    setIsQuerying(true);
    setError(null);
    
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }
      
      const response = await fetch(`/api/document/${documentId}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ query: query.trim() })
      });
      
      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setQueryResponse(data.response);
    } catch (err) {
      setError('Failed to query the document.');
      console.error('Error querying document:', err);
    } finally {
      setIsQuerying(false);
    }
  };

  useEffect(() => {
    fetchDocumentInfo();
  }, [fetchDocumentInfo]);

  useEffect(() => {
    if (documentInfo?.processing_complete) {
      if (activeTab === 'summary') {
        fetchSummary();
      } else if (activeTab === 'keyPoints') {
        fetchKeyPoints();
      }
    }
  }, [activeTab, documentInfo, fetchSummary, fetchKeyPoints]);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  if (isLoading && !documentInfo) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex justify-center items-center py-12">
          <div className="loading-spinner"></div>
          <span className="ml-2 text-gray-600">Loading document...</span>
        </div>
      </div>
    );
  }

  if (error && !documentInfo) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          <p>{error}</p>
        </div>
        <Link to="/documents" className="text-indigo-600 hover:text-indigo-800">
          &larr; Back to documents
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Document Header */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-800 mb-2">{documentInfo?.filename}</h1>
            <div className="flex flex-wrap gap-4 text-sm text-gray-500">
              <div>Uploaded: {documentInfo?.upload_time ? formatDate(documentInfo.upload_time) : 'Unknown'}</div>
              <div>Size: {documentInfo?.file_size ? formatFileSize(documentInfo.file_size) : 'Unknown'}</div>
              {documentInfo?.text_length && <div>Length: {documentInfo.text_length.toLocaleString()} characters</div>}
            </div>
          </div>
          <Link to="/documents" className="text-indigo-600 hover:text-indigo-800 text-sm flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
            Back to documents
          </Link>
        </div>
        
        {documentInfo?.processing_error && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <p className="font-medium">Processing Error</p>
            <p>{documentInfo.processing_error}</p>
          </div>
        )}
        
        {!documentInfo?.processing_complete && !documentInfo?.processing_error && (
          <div className="mt-4 bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded flex items-center">
            <div className="loading-spinner mr-3"></div>
            <p>Document is still being processed. Some features may be unavailable.</p>
          </div>
        )}
      </div>

      {/* Document Analysis Tabs */}
      {documentInfo?.processing_complete && (
        <>
          <div className="bg-white rounded-lg shadow-md overflow-hidden mb-6">
            <div className="border-b border-gray-200">
              <nav className="flex -mb-px">
                <button
                  onClick={() => setActiveTab('summary')}
                  className={`py-4 px-6 text-center border-b-2 font-medium text-sm flex-1 ${
                    activeTab === 'summary'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Summary
                </button>
                <button
                  onClick={() => setActiveTab('keyPoints')}
                  className={`py-4 px-6 text-center border-b-2 font-medium text-sm flex-1 ${
                    activeTab === 'keyPoints'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Key Points
                </button>
                <button
                  onClick={() => setActiveTab('query')}
                  className={`py-4 px-6 text-center border-b-2 font-medium text-sm flex-1 ${
                    activeTab === 'query'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Ask Questions
                </button>
              </nav>
            </div>
            
            <div className="p-6">
              {activeTab === 'summary' && (
                <div>
                  <h2 className="text-xl font-bold text-gray-800 mb-4">Document Summary</h2>
                  {isLoading ? (
                    <div className="flex justify-center items-center py-8">
                      <div className="loading-spinner"></div>
                      <span className="ml-2 text-gray-600">Generating summary...</span>
                    </div>
                  ) : error ? (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                      <p>{error}</p>
                    </div>
                  ) : summary ? (
                    <>
                      <div className="prose max-w-none">
                        <p className="text-gray-700 whitespace-pre-line">{summary.summary}</p>
                      </div>
                      <div className="mt-4 text-xs text-gray-500">
                        Generated in {summary.processing_time.toFixed(2)}s 
                        {summary.tokens_used && ` • ${summary.tokens_used} tokens used`}
                        {summary.processed_with_docling && ` • Enhanced with Docling`}
                      </div>
                    </>
                  ) : (
                    <p className="text-gray-500">No summary available.</p>
                  )}
                </div>
              )}
              
              {activeTab === 'keyPoints' && (
                <div>
                  <h2 className="text-xl font-bold text-gray-800 mb-4">Key Points</h2>
                  {isLoading ? (
                    <div className="flex justify-center items-center py-8">
                      <div className="loading-spinner"></div>
                      <span className="ml-2 text-gray-600">Extracting key points...</span>
                    </div>
                  ) : error ? (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                      <p>{error}</p>
                    </div>
                  ) : keyPoints && keyPoints.key_points.length > 0 ? (
                    <>
                      <ul className="space-y-3">
                        {keyPoints.key_points.map((point, index) => (
                          <li key={index} className="flex">
                            <div className="flex-shrink-0 mr-2">
                              <div className="h-6 w-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-sm font-medium">
                                {index + 1}
                              </div>
                            </div>
                            <div className="text-gray-700">{point.point}</div>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-4 text-xs text-gray-500">
                        Generated in {keyPoints.processing_time.toFixed(2)}s 
                        {keyPoints.tokens_used && ` • ${keyPoints.tokens_used} tokens used`}
                        {keyPoints.processed_with_docling && ` • Enhanced with Docling`}
                      </div>
                    </>
                  ) : (
                    <p className="text-gray-500">No key points available.</p>
                  )}
                </div>
              )}
              
              {activeTab === 'query' && (
                <div>
                  <h2 className="text-xl font-bold text-gray-800 mb-4">Ask Questions About This Document</h2>
                  <form onSubmit={handleQuerySubmit} className="mb-6">
                    <div className="flex">
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Ask a question about this document..."
                        className="flex-grow px-4 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        disabled={isQuerying}
                      />
                      <button
                        type="submit"
                        disabled={isQuerying || !query.trim()}
                        className={`px-4 py-2 rounded-r-md font-medium ${
                          isQuerying || !query.trim()
                            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            : 'bg-indigo-600 text-white hover:bg-indigo-700'
                        }`}
                      >
                        {isQuerying ? (
                          <div className="flex items-center">
                            <div className="loading-spinner mr-2"></div>
                            <span>Thinking...</span>
                          </div>
                        ) : (
                          'Ask'
                        )}
                      </button>
                    </div>
                  </form>
                  
                  {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
                      <p>{error}</p>
                    </div>
                  )}
                  
                  {queryResponse && (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                      <h3 className="font-medium text-gray-800 mb-2">Answer:</h3>
                      <p className="text-gray-700 whitespace-pre-line">{queryResponse}</p>
                    </div>
                  )}
                  
                  {!queryResponse && !error && !isQuerying && (
                    <div className="text-center py-8 text-gray-500">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <p>Ask questions to get insights from this document.</p>
                      <p className="text-sm mt-2">Examples: "What are the main arguments?", "Summarize the conclusion", "What evidence supports...?"</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default DocumentViewer;
