from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

from services.gemini_analyzer import GeminiPhishingAnalyzer
from services.phase2_models import extract_urls_from_text
from services.phishing_detector import PhishingDetector


HYBRID_ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "hybrid"
CALIBRATOR_PATH = HYBRID_ARTIFACT_DIR / "final_calibrator.joblib"
METADATA_PATH = HYBRID_ARTIFACT_DIR / "metadata.json"


class HybridPhishingAnalyzer:
    def __init__(self) -> None:
        self.baseline = PhishingDetector()
        self.phase2_models = self.baseline.phase2_models

        self.gemini: Optional[GeminiPhishingAnalyzer] = None
        try:
            self.gemini = GeminiPhishingAnalyzer()
        except Exception as exc:
            print(f"[Gemini init error] {exc}")
            self.gemini = None

        self.calibrator = None
        if CALIBRATOR_PATH.exists():
            try:
                self.calibrator = joblib.load(CALIBRATOR_PATH)
            except Exception:
                self.calibrator = None

        self.metadata: Dict[str, Any] = {}
        if METADATA_PATH.exists():
            try:
                self.metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
            except Exception:
                self.metadata = {}

    def analyze_email(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = headers or {}

        baseline = self.baseline.analyze_email(sender, recipient, subject, body, headers)
        urls = extract_urls_from_text(body)

        ml_scores = baseline.get("ml_scores", {})
        real_threats = [t for t in baseline.get("threats", []) if t != "No immediate threats detected"]
        intel_matches = int(ml_scores.get("intel_exact_match_count", 0)) + int(
            ml_scores.get("intel_domain_match_count", 0)
        )

        gemini_used = False
        routing_reason = "Gemini unavailable"
        gemini_result: Dict[str, Any] = {
            "available": False,
            "final_component_scores": {},
            "final_overall_risk_score": baseline.get("overall_risk_score", 0.0),
            "final_verdict": baseline.get("verdict", "safe"),
            "confidence": baseline.get("confidence", "low"),
            "threat_types": baseline.get("threats", []),
            "social_engineering_tactics": [],
            "ml_disagreements": [],
            "reasoning_summary": "",
            "recommended_action": "",
        }

        if self.gemini is not None:
            should_route, routing_reason = self.gemini.should_route_to_llm(
                baseline_score=float(baseline.get("overall_risk_score", 0.0)),
                threat_count=len(real_threats),
                intel_matches=intel_matches,
            )
            if should_route:
                gemini_used = True
                gemini_result = self.gemini.analyze_email_for_final_decision(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    urls=urls,
                    baseline_analysis=baseline,
                )

        if gemini_result.get("available"):
            final_component_scores = gemini_result["final_component_scores"]
            final_score = float(gemini_result["final_overall_risk_score"])
            final_verdict = str(gemini_result["final_verdict"]).lower()
            final_confidence = gemini_result.get("confidence", "medium")
            final_threats = gemini_result.get("threat_types") or baseline.get("threats", [])
            decision_authority = "gemini"
        else:
            final_component_scores = baseline.get("component_scores", {})
            final_score = float(baseline.get("overall_risk_score", 0.0))
            final_verdict = str(baseline.get("verdict", "safe")).lower()
            final_confidence = baseline.get("confidence", "low")
            final_threats = baseline.get("threats", [])
            decision_authority = "baseline_ml"

        hybrid_explanation = ""
        if self.gemini is not None and gemini_result.get("available"):
            hybrid_explanation = self.gemini.build_final_explanation(
                baseline_analysis=baseline,
                gemini_result=gemini_result,
            )

        result = dict(baseline)
        result.update({
            "analysis_type": "ML_ADVISOR_GEMINI_FINAL" if gemini_used else "ML_ONLY_FALLBACK",
            "component_scores": final_component_scores,
            "overall_risk_score": round(final_score, 4),
            "hybrid_score": round(final_score, 4),
            "verdict": final_verdict,
            "hybrid_verdict": final_verdict,
            "is_phishing": final_verdict == "phishing",
            "confidence": final_confidence,
            "threats": final_threats,
            "gemini_used": gemini_used,
            "routing_reason": routing_reason,
            "gemini_analysis": gemini_result,
            "hybrid_explanation": hybrid_explanation,
            "final_model_metadata": self.metadata,
            "decision_authority": decision_authority,
            "baseline_ml_analysis": {
                "overall_risk_score": baseline.get("overall_risk_score", 0.0),
                "verdict": baseline.get("verdict", "unknown"),
                "confidence": baseline.get("confidence", "low"),
                "component_scores": baseline.get("component_scores", {}),
                "threats": baseline.get("threats", []),
                "ml_scores": baseline.get("ml_scores", {}),
            },
        })
        if gemini_used:
            print("[Gemini result]", gemini_result)
        return result