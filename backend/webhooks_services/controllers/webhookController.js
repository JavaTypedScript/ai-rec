import sqlite3 from "sqlite3";
import axios from "axios";

const db = new sqlite3.Database("./db/webhooks.db");

// Create table on startup
db.run(`
  CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT,
    webhook_url TEXT
  )
`);

export const registerWebhook = (req, res) => {
  const { app_name, webhook_url } = req.body;
  if (!app_name || !webhook_url)
    return res.status(400).json({ error: "Missing app_name or webhook_url" });

  db.run("INSERT INTO webhooks (app_name, webhook_url) VALUES (?, ?)", [app_name, webhook_url], function (err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ id: this.lastID, message: "Webhook registered successfully" });
  });
};

export const listWebhooks = (req, res) => {
  db.all("SELECT * FROM webhooks", [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
};

export const triggerWebhooks = async (req, res) => {
  const { event, data } = req.body;
  db.all("SELECT webhook_url FROM webhooks", [], async (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });

    const results = [];
    for (const { webhook_url } of rows) {
      try {
        await axios.post(webhook_url, { event, data });
        results.push({ webhook_url, status: "success" });
      } catch (error) {
        results.push({ webhook_url, status: "failed", error: error.message });
      }
    }
    res.json({ message: "Webhooks triggered", results });
  });
};
