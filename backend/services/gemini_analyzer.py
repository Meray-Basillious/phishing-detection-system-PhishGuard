from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import google.generativeai as genai


class GeminiPhishingAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        self.generation_config = {
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
            "top_p": 0.8,
            "max_output_tokens": 1200,
        }

    def should_route_to_llm(self, baseline_score: float, threat_count: int, intel_matches: int) -> tuple[bool, str]:
        low = float(os.getenv("USE_GEMINI_THRESHOLD_LOW", "0.25"))
        high = float(os.getenv("USE_GEMINI_THRESHOLD_HIGH", "0.80"))

        if intel_matches > 0:
            return False, "Known phishing IOC already matched"
        if baseline_score < low and threat_count == 0:
            return False, "Clearly low-risk message"
        if low <= baseline_score < high:
            return True, "Ambiguous message"
        if baseline_score >= high:
            return True, "High-risk message for semantic confirmation"
        return False, "No Gemini routing"

    def analyze_email_semantics(
        self,
        sender: str,
        subject: str,
        body: str,
        urls: List[str],
        ml_scores: Dict[str, Any],
    ) -> Dict[str, Any]:
        body_preview = body[:1500] + ("..." if len(body) > 1500 else "")
        urls_str = ", ".join(urls[:10]) if urls else "No URLs"

        prompt = f"""
You are a phishing email analyst.

Analyze the email semantically. Return strict JSON only.

From: {sender}
Subject: {subject}
Body: {body_preview}
URLs: {urls_str}

ML context:
{json.dumps(ml_scores, ensure_ascii=False)}

Return:
{{
  "is_phishing": true,
  "threat_type": "BEC|Credential Harvesting|Advance Fee Fraud|Invoice Fraud|Impersonation|Generic Phishing|Benign|Unknown",
  "threat_confidence": 0.0,
  "tactics_detected": ["urgency", "authority"],
  "contextual_issues": ["issue 1"],
  "social_engineering_score": 0.0,
  "contradictions": ["contradiction 1"],
  "explanation": "2-3 sentence explanation",
  "recommendation": "Recommended action"
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config,
            )
            parsed = self._extract_json(response.text)

            return {
                "available": True,
                "error": None,
                "is_phishing": bool(parsed.get("is_phishing", False)),
                "threat_type": str(parsed.get("threat_type", "Unknown")),
                "threat_confidence": self._safe_float(parsed.get("threat_confidence", 0.0)),
                "tactics_detected": self._safe_list(parsed.get("tactics_detected")),
                "contextual_issues": self._safe_list(parsed.get("contextual_issues")),
                "social_engineering_score": self._safe_float(parsed.get("social_engineering_score", 0.0)),
                "contradictions": self._safe_list(parsed.get("contradictions")),
                "explanation": str(parsed.get("explanation", "")).strip(),
                "recommendation": str(parsed.get("recommendation", "")).strip(),
            }
        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
                "is_phishing": False,
                "threat_type": "LLM Unavailable",
                "threat_confidence": 0.0,
                "tactics_detected": [],
                "contextual_issues": [],
                "social_engineering_score": 0.0,
                "contradictions": [],
                "explanation": "",
                "recommendation": "Fallback to ML-only decision",
            }

    def generate_hybrid_explanation(
        self,
        baseline: Dict[str, Any],
        gemini_analysis: Dict[str, Any],
        final_score: float,
        final_verdict: str,
    ) -> str:
        threats = baseline.get("threats", [])[:3]
        tactics = gemini_analysis.get("tactics_detected", [])[:3]

        parts = [f"Final verdict: {final_verdict.upper()} ({final_score:.2f})."]
        if threats:
            parts.append(f"Baseline indicators: {', '.join(threats)}.")
        if tactics:
            parts.append(f"Gemini detected tactics: {', '.join(tactics)}.")
        recommendation = gemini_analysis.get("recommendation", "")
        if recommendation:
            parts.append(recommendation)
        return " ".join(parts).strip()

    @staticmethod
    def create_hybrid_score(ml_score: float, gemini_confidence: float, ml_confidence: float) -> float:
        if gemini_confidence >= 0.90:
            return 0.35 * ml_score + 0.65 * gemini_confidence
        if ml_confidence >= 0.85 and ml_confidence > gemini_confidence:
            return 0.70 * ml_score + 0.30 * gemini_confidence
        return 0.55 * ml_score + 0.45 * gemini_confidence

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in Gemini response")
        return json.loads(match.group(0))

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            v = float(value)
        except Exception:
            return 0.0
        return max(0.0, min(1.0, v))

    @staticmethod
    def _safe_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]