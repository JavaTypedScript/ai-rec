import React, { useState } from "react";
import { API_WEBHOOK } from "../api";

export default function RegisterWebhook() {
  const [appName, setAppName] = useState("");
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    try {
      const res = await fetch(`${API_WEBHOOK}/api/webhooks/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ app_name: appName, webhook_url: url }),
      });
      if (!res.ok) throw new Error("Failed to register webhook");
      setMessage("✅ App registered successfully!");
      setAppName("");
      setUrl("");
    } catch (err) {
      setMessage("❌ " + err.message);
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mt-6">
      <h2 className="text-xl font-semibold mb-3">Register External App</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="text"
          placeholder="App Name"
          value={appName}
          onChange={(e) => setAppName(e.target.value)}
          required
          className="border w-full px-3 py-2 rounded"
        />
        <input
          type="url"
          placeholder="Webhook URL (https://example.com/webhook)"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          className="border w-full px-3 py-2 rounded"
        />
        <button
          type="submit"
          className="bg-blue-600 text-white px-4 py-2 rounded w-full hover:bg-blue-700"
        >
          Register
        </button>
      </form>
      {message && <p className="mt-3 text-sm text-gray-700">{message}</p>}
    </div>
  );
}
