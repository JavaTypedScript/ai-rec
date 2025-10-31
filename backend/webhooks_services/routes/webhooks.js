import express from "express";
import { registerWebhook, triggerWebhooks, listWebhooks } from "../controllers/webhookController.js";

const router = express.Router();

router.post("/register", registerWebhook);
router.get("/", listWebhooks);
router.post("/trigger", triggerWebhooks);

export default router;
