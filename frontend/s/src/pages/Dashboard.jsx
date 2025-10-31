import React from 'react';
import AppList from '../components/AppList';
import RegisterWebhook from '../components/RegisterWebhook';

function Dashboard() {
  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold mb-8">Webhook Dashboard</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <RegisterWebhook />
          <AppList />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;