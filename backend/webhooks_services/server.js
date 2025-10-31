import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import dotenv from "dotenv";

import webhookRoutes from "./routes/webhooks.js";
import appRoutes from "./routes/apps.js";

dotenv.config();
const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(bodyParser.json());

app.use("/api/webhooks", webhookRoutes);
app.use("/api/apps", appRoutes);

app.listen(PORT, () => console.log(`Webhook service running at http://localhost:${PORT}`));
