import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface NavbarProps {
  apiKey: string;
  setApiKey: (key: string) => void;
}

const Navbar: React.FC<NavbarProps> = ({ apiKey, setApiKey }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState(apiKey);
  const location = useLocation();

  const handleSaveApiKey = () => {
    setApiKey(apiKeyInput);
    setIsSettingsOpen(false);
  };

  const isActive = (path: string) => {
    return location.pathname === path ? 'bg-indigo-700' : '';
  };

  return (
    <nav className="bg-indigo-600 text-white shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center space-x-8">
            <Link to="/" className="text-2xl font-bold flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 mr-2" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
              </svg>
              Docling
            </Link>
            
            <div className="hidden md:flex space-x-1">
              <Link to="/" className={`px-3 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition duration-150 ${isActive('/')}`}>
                Home
              </Link>
              <Link to="/upload" className={`px-3 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition duration-150 ${isActive('/upload')}`}>
                Upload
              </Link>
              <Link to="/documents" className={`px-3 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition duration-150 ${isActive('/documents')}`}>
                Documents
              </Link>
            </div>
          </div>
          
          <div className="flex items-center">
            <button 
              onClick={() => setIsSettingsOpen(!isSettingsOpen)} 
              className="flex items-center px-3 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 transition duration-150"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
              </svg>
              Settings
            </button>
            
            {isSettingsOpen && (
              <div className="absolute right-4 top-16 mt-2 w-72 bg-white rounded-md shadow-lg z-50 p-4">
                <h3 className="text-gray-800 font-medium mb-2">API Settings</h3>
                <div className="mb-4">
                  <label className="block text-gray-700 text-sm font-medium mb-1">
                    API Key {apiKey && <span className="text-green-600 text-xs">(Set)</span>}
                  </label>
                  <input
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder="Enter your API key"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Required for authenticated endpoints</p>
                </div>
                <div className="flex justify-end">
                  <button 
                    onClick={() => setIsSettingsOpen(false)} 
                    className="px-3 py-1 text-gray-600 text-sm mr-2"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleSaveApiKey} 
                    className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
                  >
                    Save
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
