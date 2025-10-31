import React, { useState, useEffect } from 'react';

function AppList() {
  const [apps, setApps] = useState([]);

  useEffect(() => {
    // Fetch your registered webhooks/apps here
    // setApps(fetchedApps);
  }, []);

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h3 className="text-xl font-bold mb-4">Registered Applications</h3>
      {apps.length === 0 ? (
        <p className="text-gray-500">No applications registered yet.</p>
      ) : (
        <ul className="space-y-2">
          {apps.map((app, index) => (
            <li key={index} className="p-3 border border-gray-200 rounded-md">
              <div className="font-medium">{app.name}</div>
              <div className="text-sm text-gray-600">{app.url}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AppList;