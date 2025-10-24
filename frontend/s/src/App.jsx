import React, { useState, useEffect, useCallback } from 'react';
import Papa from 'papaparse';

const API_URL = 'http://localhost:8000';

// --- UI Components (re-usable) ---
const Input = (props) => (
  <input {...props} className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
);
const Select = (props) => (
  <select {...props} className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white" >
    {props.children}
  </select>
);
const Button = ({ children, ...props }) => (
  <button {...props} className="w-full px-4 py-2 font-semibold text-white bg-blue-600 rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50" >
    {children}
  </button>
);
const Card = ({ children, className }) => (
  <div className={`p-6 bg-white rounded-lg shadow-md ${className || ''}`}>
    {children}
  </div>
);

// --- Schema Mapper Component ---
const SchemaMapper = ({ title, headers, schema, onChange, schemaKeys }) => (
  <div className="p-4 mt-4 border border-gray-200 rounded-lg">
    <h3 className="font-semibold text-gray-700">{title}</h3>
    <div className="space-y-3 mt-2">
      {schemaKeys.map(({ key, label, multi }) => (
        <div key={key}>
          <label className="block text-sm font-medium text-gray-700">{label}</label>
          <Select
            multiple={multi}
            value={schema[key]}
            onChange={(e) => {
              const value = multi
                ? Array.from(e.target.selectedOptions, (opt) => opt.value)
                : e.target.value;
              onChange({ ...schema, [key]: value });
            }}
            className={multi ? "h-24" : ""}
          >
            {!multi && <option value="">Select a column...</option>}
            {headers.map((h) => <option key={h} value={h}>{h}</option>)}
          </Select>
          {multi && <p className="text-xs text-gray-500">Hold Ctrl/Cmd to select multiple.</p>}
        </div>
      ))}
    </div>
  </div>
);

// --- Main App Component ---
function App() {
  // --- Form State ---
  const [projectName, setProjectName] = useState('');
  const [contentFile, setContentFile] = useState(null);
  const [interactionFile, setInteractionFile] = useState(null);
  
  const [contentHeaders, setContentHeaders] = useState([]);
  const [interactionHeaders, setInteractionHeaders] = useState([]);
  
  const [contentSchema, setContentSchema] = useState({ item_id: '', item_title: '', feature_cols: [] });
  const [interactionSchema, setInteractionSchema] = useState({ user_id: '', item_id: '', rating: '' });

  // --- App Status State ---
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [currentStatus, setCurrentStatus] = useState('idle');
  const [errorMessage, setErrorMessage] = useState('');

  // --- Recommendation State ---
  const [itemsList, setItemsList] = useState([]);
  const [usersList, setUsersList] = useState([]);
  const [selectedItemTitle, setSelectedItemTitle] = useState('');
  const [selectedUserId, setSelectedUserId] = useState('');
  const [recommendations, setRecommendations] = useState(null);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  // --- File Header Parsing Effects ---
  const parseHeaders = (file, setHeaders) => {
    if (file) {
      Papa.parse(file, {
        header: true, preview: 1,
        complete: (results) => setHeaders(results.meta.fields || []),
      });
    } else {
      setHeaders([]);
    }
  };
  useEffect(() => parseHeaders(contentFile, setContentHeaders), [contentFile]);
  useEffect(() => parseHeaders(interactionFile, setInteractionHeaders), [interactionFile]);

  // --- Data Fetching Effects ---
  const fetchProjects = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/projects/`);
      const data = await response.json();
      setProjects(data);
    } catch (error) { console.error('Failed to fetch projects:', error); }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  // --- Status Polling Effect ---
  useEffect(() => {
    if (currentStatus === 'processing' && selectedProjectId) {
      const interval = setInterval(() => checkProjectStatus(selectedProjectId), 3000);
      return () => clearInterval(interval);
    }
  }, [currentStatus, selectedProjectId]);

  // --- API Callbacks ---
  const checkProjectStatus = async (projectId) => {
    try {
      const response = await fetch(`${API_URL}/project/${projectId}/status`);
      if (!response.ok) throw new Error('Failed to get status');
      const data = await response.json();
      
      setCurrentStatus(data.status);
      setProjects(prev => prev.map(p => p.id === projectId ? data : p));
      
      if (data.status === 'ready') {
        handleSelectProject(data.id); // This will trigger data fetches
      }
      if (data.status === 'error') {
        setErrorMessage('Project processing failed.');
      }
    } catch (error) {
      console.error('Status check failed:', error);
      setCurrentStatus('error');
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!projectName || (!contentFile && !interactionFile)) {
      setErrorMessage('Project name and at least one file are required.');
      return;
    }
    
    setErrorMessage('');
    setCurrentStatus('uploading');
    setRecommendations(null);

    const formData = new FormData();
    formData.append('project_name', projectName);
    
    if (contentFile) {
      formData.append('content_file', contentFile);
      formData.append('content_schema_json', JSON.stringify(contentSchema));
    }
    if (interactionFile) {
      formData.append('interaction_file', interactionFile);
      formData.append('interaction_schema_json', JSON.stringify(interactionSchema));
    }

    try {
      const response = await fetch(`${API_URL}/create-project/`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await response.json();
      setSelectedProjectId(data.id);
      setCurrentStatus('processing');
      fetchProjects(); // Refresh the list
    } catch (error) {
      setErrorMessage(error.message);
      setCurrentStatus('error');
    }
  };

  const handleSelectProject = async (projectId) => {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;
    
    setSelectedProjectId(projectId);
    setCurrentStatus(project.status);
    setRecommendations(null);
    setErrorMessage('');
    setItemsList([]);
    setUsersList([]);
    
    if (project.status === 'ready' && project.model_type) {
      // Fetch items for content/hybrid models
      if (['content', 'hybrid'].includes(project.model_type)) {
        try {
          const res = await fetch(`${API_URL}/project/${projectId}/items`);
          const data = await res.json();
          setItemsList(data);
          setSelectedItemTitle(data[0]?.title || '');
        } catch (e) { console.error("Failed to fetch items"); }
      }
      // Fetch users for collaborative/hybrid models
      if (['collaborative', 'hybrid'].includes(project.model_type)) {
         try {
          const res = await fetch(`${API_URL}/project/${projectId}/users`);
          const data = await res.json();
          setUsersList(data);
          setSelectedUserId(data[0]?.id || '');
        } catch (e) { console.error("Failed to fetch users"); }
      }
    }
  };

  const handleGetRecommendations = async (e) => {
    e.preventDefault();
    if (!selectedProject) return;

    setIsLoadingRecs(true);
    setRecommendations(null);
    setErrorMessage('');

    const params = new URLSearchParams();
    if (['content', 'hybrid'].includes(selectedProject.model_type)) {
      params.append('item_title', selectedItemTitle);
    }
    if (['collaborative', 'hybrid'].includes(selectedProject.model_type)) {
      params.append('user_id', selectedUserId);
    }

    try {
      const url = `${API_URL}/project/${selectedProjectId}/recommendations?${params.toString()}`;
      const response = await fetch(url);
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to get recommendations');
      }
      const data = await response.json();
      setRecommendations(data.recommendations);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoadingRecs(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* --- LEFT COLUMN: Create & Manage --- */}
        <div className="lg:col-span-2 space-y-8">
          <Card>
            <h2 className="text-2xl font-bold mb-4">Create New Recommender Project</h2>
            <form onSubmit={handleCreateProject} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">Project Name</label>
                <Input type="text" placeholder="e.g., My Movie Recommender"
                  value={projectName} onChange={(e) => setProjectName(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Content File Upload */}
                <div className="p-4 border border-dashed border-gray-300 rounded-lg">
                  <h3 className="font-semibold text-lg text-gray-800">1. Content Data (Optional)</h3>
                  <p className="text-sm text-gray-500">Item details (e.g., movies.csv)</p>
                  <Input type="file" accept=".csv" className="mt-4"
                    onChange={(e) => setContentFile(e.target.files ? e.target.files[0] : null)}
                  />
                  {contentFile && (
                    <SchemaMapper
                      title="Map Content Schema"
                      headers={contentHeaders}
                      schema={contentSchema}
                      onChange={setContentSchema}
                      schemaKeys={[
                        { key: 'item_id', label: 'Item ID Column' },
                        { key: 'item_title', label: 'Item Title Column' },
                        { key: 'feature_cols', label: 'Feature Columns (for content)', multi: true },
                      ]}
                    />
                  )}
                </div>
                
                {/* Interaction File Upload */}
                <div className="p-4 border border-dashed border-gray-300 rounded-lg">
                  <h3 className="font-semibold text-lg text-gray-800">2. Interaction Data (Optional)</h3>
                  <p className="text-sm text-gray-500">User ratings (e.g., ratings.csv)</p>
                  <Input type="file" accept=".csv" className="mt-4"
                    onChange={(e) => setInteractionFile(e.target.files ? e.target.files[0] : null)}
                  />
                  {interactionFile && (
                    <SchemaMapper
                      title="Map Interaction Schema"
                      headers={interactionHeaders}
                      schema={interactionSchema}
                      onChange={setInteractionSchema}
                      schemaKeys={[
                        { key: 'user_id', label: 'User ID Column' },
                        { key: 'item_id', label: 'Item ID Column' },
                        { key: 'rating', label: 'Rating Column' },
                      ]}
                    />
                  )}
                </div>
              </div>
              
              <Button type="submit" disabled={currentStatus === 'uploading' || currentStatus === 'processing'}>
                {currentStatus === 'uploading' && 'Uploading...'}
                {currentStatus === 'processing' && 'Processing...'}
                {currentStatus !== 'uploading' && currentStatus !== 'processing' && 'Create Project & Train Model'}
              </Button>
            </form>
          </Card>

          {/* Recommendations Card */}
          <Card>
            <h2 className="text-2xl font-bold mb-4">Get Recommendations</h2>
            {!selectedProjectId ? (
              <p className="text-gray-500">Please select a "Ready" project from the list to begin.</p>
            ) : currentStatus === 'processing' ? (
              <div className="text-center p-8">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                <p className="mt-4 font-semibold text-blue-600">Processing project...</p>
              </div>
            ) : errorMessage ? (
               <div className="p-4 bg-red-100 text-red-700 rounded-md">{errorMessage}</div>
            ) : currentStatus === 'ready' && selectedProject ? (
              <form onSubmit={handleGetRecommendations} className="space-y-4">
                <h3 className="text-lg font-semibold">Project: <span className="text-blue-600">{selectedProject.project_name}</span></h3>
                <p className="text-sm text-gray-600">Model Type: <span className="font-medium uppercase text-gray-800">{selectedProject.model_type}</span></p>

                {/* Dynamic Inputs based on Model Type */}
                {(selectedProject.model_type === 'content' || selectedProject.model_type === 'hybrid') && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Select Item</label>
                    <Select value={selectedItemTitle} onChange={e => setSelectedItemTitle(e.target.value)}>
                      {itemsList.map(item => <option key={item.id} value={item.title}>{item.title}</option>)}
                    </Select>
                  </div>
                )}
                {(selectedProject.model_type === 'collaborative' || selectedProject.model_type === 'hybrid') && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Select User</label>
                    <Select value={selectedUserId} onChange={e => setSelectedUserId(e.target.value)}>
                      {usersList.map(user => <option key={user.id} value={user.id}>{user.id}</option>)}
                    </Select>
                  </div>
                )}
                
                <Button type="submit" disabled={isLoadingRecs}>
                  {isLoadingRecs ? 'Getting Recommendations...' : 'Get Recommendations'}
                </Button>
                
                {/* Results */}
                {recommendations && (
                  <div className="pt-4">
                    <h3 className="text-lg font-semibold">Results:</h3>
                    <ul className="mt-2 list-disc list-inside space-y-1">
                      {recommendations.map((rec, index) => {
                        const titleKey = Object.keys(rec).find(k => k.toLowerCase().includes('title') || k.toLowerCase().includes('name'));
                        const idKey = Object.keys(rec).find(k => k.toLowerCase().includes('id'));
                        return (
                          <li key={index} className="text-gray-700">
                            {titleKey ? rec[titleKey] : `ID: ${rec[idKey]}`}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}
              </form>
            ) : null}
          </Card>
        </div>

        {/* --- RIGHT COLUMN: Project List --- */}
        <Card className="lg:col-span-1 h-full">
          <h2 className="text-2xl font-bold mb-4">My Projects</h2>
          <ul className="space-y-3">
            {projects.length === 0 && <p className="text-gray-500">No projects created yet.</p>}
            {projects.map(p => (
              <li 
                key={p.id}
                onClick={() => handleSelectProject(p.id)}
                className={`p-4 border rounded-md cursor-pointer ${selectedProjectId === p.id ? 'bg-blue-50 border-blue-400 shadow-sm' : 'hover:bg-gray-50 border-gray-200'}`}
              >
                <div className="font-semibold text-gray-800">{p.project_name}</div>
                <div className="flex justify-between items-center mt-1">
                  <span className={`text-xs font-medium uppercase px-2 py-0.5 rounded-full ${
                    p.model_type === 'content' ? 'bg-green-100 text-green-800' :
                    p.model_type === 'collaborative' ? 'bg-yellow-100 text-yellow-800' :
                    p.model_type === 'hybrid' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {p.model_type || 'N/A'}
                  </span>
                  <span className={`text-sm font-medium ${
                    p.status === 'ready' ? 'text-green-600' :
                    p.status === 'error' ? 'text-red-600' : 'text-yellow-600'
                  }`}>
                    {p.status}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </Card>

      </div>
    </div>
  );
}

export default App;