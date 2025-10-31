import React, { useState } from 'react';
import RecommenderPanel from './components/RecommenderPanel';
import Dashboard from './pages/Dashboard';

function App() {
  const [activeTab, setActiveTab] = useState("recommender");

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Navbar */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto flex justify-between items-center p-4">
          <h1 className="text-2xl font-bold text-gray-800">AI Recommender BaaS</h1>
          <div className="space-x-4">
            <button
              className={`px-4 py-2 rounded ${activeTab === "recommender" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"}`}
              onClick={() => setActiveTab("recommender")}
            >
              Recommender Studio
            </button>
            <button
              className={`px-4 py-2 rounded ${activeTab === "dashboard" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"}`}
              onClick={() => setActiveTab("dashboard")}
            >
              Webhook Dashboard
            </button>
          </div>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === "recommender" ? (
        <RecommenderPanel />
      ) : (
        <Dashboard />
      )}
    </div>
  );
}

export default App;