\
from __future__ import annotations

import json
from google import genai
from google.genai import types


class AIAnalyzer:
    def __init__(self, config, logger):
        self.cfg = config
        self.logger = logger
        self.client = None
        if config.gemini_enabled and config.gemini_api_key:
            try:
                self.client = genai.Client(
                    api_key=config.gemini_api_key,
                    http_options=types.HttpOptions(timeout=config.gemini_timeout_seconds * 1000),
                )
            except Exception as exc:
                self.logger.warning("Gemini client initialization failed: %s", exc)

    def analyze(self, incident) -> str:
        if not self.client:
            return ""

        payload = {
            "server": self.cfg.server_name,
            "environment": self.cfg.environment,
            "incident": incident.as_dict(),
        }
        prompt = (
            "You are a Linux SRE incident assistant. Analyze ONLY the supplied telemetry. "
            "Do not invent facts. Keep the answer under 180 words. Return plain text with: "
            "Likely cause, Immediate checks (safe/read-only commands only), Risk, and Next step. "
            "Never recommend destructive commands or automatic remediation.\n\n"
            + json.dumps(payload, indent=2)
        )

        try:
            response = self.client.models.generate_content(
                model=self.cfg.gemini_model,
                contents=prompt,
            )
            return (response.text or "").strip()
        except Exception as exc:
            self.logger.warning("Gemini analysis failed: %s", exc)
        return ""

    def close(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
