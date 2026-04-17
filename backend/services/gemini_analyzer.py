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
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.05")),
            "top_p": 0.8,
            "max_output_tokens": 2400,
        }
        print("[Gemini] API key detected:", bool(self.api_key))
        print("[Gemini] Model:", self.model_name)

    def should_route_to_llm(self, baseline_score: float, threat_count: int, intel_matches: int) -> tuple[bool, str]:
        always_route = os.getenv("USE_GEMINI_ALWAYS", "true").lower() == "true"
        if always_route:
            return True, "Gemini final review enabled for all emails"
        if intel_matches > 0:
            return True, "Known IOC matched"
        if baseline_score < 0.10 and threat_count == 0:
            return False, "Clearly low-risk email"
        return True, "Gemini review for non-trivial email"

    def analyze_email_for_final_decision(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        urls: List[str],
        baseline_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        body_preview = body[:4000] + ("..." if len(body) > 4000 else "")
        urls_str = ", ".join(urls[:15]) if urls else "No URLs"

        prompt = f"""
You are the FINAL phishing adjudication engine for an enterprise email security system.

The ML system already provided preliminary scores. Your job is to CORRECT weak ML judgments and produce the FINAL component scores and FINAL verdict.

You must pay special attention to these cases because ML often under-scores them:
1. identity claims such as "I am X", "This is X", "My name is X"
2. celebrity or public figure impersonation
3. executive / finance / payroll impersonation
4. requests for money, wire transfers, gift cards, payment, or bank details
5. secrecy language such as "keep this confidential", "don't tell anyone"
6. urgency pressure such as "right now", "today", "immediately"
7. generic email senders pretending to be someone important

If the email claims to be a famous person or executive and asks for money or secrecy, impersonation_score and urgency_score should NOT be near zero.

Return final scores for:
- sender_score
- subject_score
- body_score
- url_score
- urgency_score
- impersonation_score
- history_score
- header_score

Each score must be a float 0.0 to 1.0.

Email:
From: {sender}
To: {recipient}
Subject: {subject}
Body:
{body_preview}

Extracted URLs:
{urls_str}

Baseline ML analysis:
{json.dumps(baseline_analysis, ensure_ascii=False, indent=2)}

Return STRICT JSON ONLY:
{{
  "final_component_scores": {{
    "sender_score": 0.0,
    "subject_score": 0.0,
    "body_score": 0.0,
    "url_score": 0.0,
    "urgency_score": 0.0,
    "impersonation_score": 0.0,
    "history_score": 0.0,
    "header_score": 0.0
  }},
  "final_overall_risk_score": 0.0,
  "final_verdict": "safe",
  "confidence": "low",
  "threat_types": ["type 1"],
  "social_engineering_tactics": ["urgency"],
  "ml_disagreements": ["what ML under-scored or over-scored"],
  "reasoning_summary": "Brief explanation of the final decision.",
  "recommended_action": "What the user should do next."
}}

final_verdict must be exactly one of:
"safe", "suspicious", "phishing"

confidence must be exactly one of:
"low", "medium", "high", "very high"
"""

        try:
            response = self.model.generate_content(prompt, generation_config=self.generation_config)
            parsed = self._extract_json(response.text)

            final_component_scores = self._normalize_component_scores(
                parsed.get("final_component_scores", {})
            )

            final_score = self._safe_float(parsed.get("final_overall_risk_score", 0.0))
            final_verdict = str(parsed.get("final_verdict", "safe")).strip().lower()
            if final_verdict not in {"safe", "suspicious", "phishing"}:
                final_verdict = self._verdict_from_score(final_score)

            confidence = str(parsed.get("confidence", "medium")).strip().lower()
            if confidence not in {"low", "medium", "high", "very high"}:
                confidence = "medium"

            return {
                "available": True,
                "error": None,
                "final_component_scores": final_component_scores,
                "final_overall_risk_score": final_score,
                "final_verdict": final_verdict,
                "confidence": confidence,
                "threat_types": self._safe_list(parsed.get("threat_types")),
                "social_engineering_tactics": self._safe_list(parsed.get("social_engineering_tactics")),
                "ml_disagreements": self._safe_list(parsed.get("ml_disagreements")),
                "reasoning_summary": str(parsed.get("reasoning_summary", "")).strip(),
                "recommended_action": str(parsed.get("recommended_action", "")).strip(),
                "raw_text": response.text,
            }
        except Exception as exc:
            print(f"[Gemini runtime error] {exc}")
            return {
                "available": False,
                "error": str(exc),
                "final_component_scores": {},
                "final_overall_risk_score": 0.0,
                "final_verdict": "safe",
                "confidence": "low",
                "threat_types": [],
                "social_engineering_tactics": [],
                "ml_disagreements": [],
                "reasoning_summary": "",
                "recommended_action": "Fallback to ML-only decision because Gemini is unavailable.",
                "raw_text": "",
            }

    def build_final_explanation(self, baseline_analysis: Dict[str, Any], gemini_result: Dict[str, Any]) -> str:
        parts = []
        parts.append(
            f"Baseline ML score was {float(baseline_analysis.get('overall_risk_score', 0.0)):.2f} "
            f"with verdict {str(baseline_analysis.get('verdict', 'unknown')).upper()}."
        )
        parts.append(
            f"Gemini final decision is {str(gemini_result.get('final_verdict', 'safe')).upper()} "
            f"with score {float(gemini_result.get('final_overall_risk_score', 0.0)):.2f}."
        )
        if gemini_result.get("ml_disagreements"):
            parts.append("Gemini corrected ML on: " + ", ".join(gemini_result["ml_disagreements"][:3]) + ".")
        if gemini_result.get("reasoning_summary"):
            parts.append(gemini_result["reasoning_summary"])
        if gemini_result.get("recommended_action"):
            parts.append(gemini_result["recommended_action"])
        return " ".join(parts).strip()

    @staticmethod
    def _verdict_from_score(score: float) -> str:
        if score >= 0.75:
            return "phishing"
        if score >= 0.45:
            return "suspicious"
        return "safe"

    @staticmethod
    def _normalize_component_scores(scores: Dict[str, Any]) -> Dict[str, float]:
        required = [
            "sender_score",
            "subject_score",
            "body_score",
            "url_score",
            "urgency_score",
            "impersonation_score",
            "history_score",
            "header_score",
        ]
        out: Dict[str, float] = {}
        for key in required:
            out[key] = GeminiPhishingAnalyzer._safe_float(scores.get(key, 0.0))
        return out

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in Gemini response")
        return json.loads(match.group(0))

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            value = float(value)
        except Exception:
            return 0.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _safe_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(x).strip() for x in value if str(x).strip()]