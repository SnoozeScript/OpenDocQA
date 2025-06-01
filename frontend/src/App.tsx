import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './components/Home';
import DocumentUpload from './components/DocumentUpload';
import DocumentList from './components/DocumentList';
import DocumentViewer from './components/DocumentViewer';

function App() {
  const [apiKey, setApiKey] = useState<string>(localStorage.getItem('docling-api-key') || '');

  useEffect(() => {
    if (apiKey) {
      localStorage.setItem('docling-api-key', apiKey);
    } else {
      localStorage.removeItem('docling-api-key');
    }
  }, [apiKey]);

  return (
    <Router>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navbar apiKey={apiKey} setApiKey={setApiKey} />
        
        <div className="container mx-auto px-4 py-8 flex-grow">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/upload" element={<DocumentUpload apiKey={apiKey} />} />
            <Route path="/documents" element={<DocumentList apiKey={apiKey} />} />
            <Route path="/document/:documentId" element={<DocumentViewer apiKey={apiKey} />} />
          </Routes>
        </div>
        
        <footer className="bg-gray-800 text-white py-6">
          <div className="container mx-auto px-4 text-center">
            <p>© {new Date().getFullYear()} Docling - AI-powered document analysis</p>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
