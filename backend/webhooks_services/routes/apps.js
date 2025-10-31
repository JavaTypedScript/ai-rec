import express from "express";
import { getAppUsage } from "../controllers/appController.js";

const router = express.Router();
router.get("/usage", getAppUsage);

export default router;
