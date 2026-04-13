from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np

from services.gemini_analyzer import GeminiPhishingAnalyzer
from services.phase2_models import extract_urls_from_text
from services.phishing_detector import PhishingDetector


HYBRID_ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "hybrid"
CALIBRATOR_PATH = HYBRID_ARTIFACT_DIR / "final_calibrator.joblib"
METADATA_PATH = HYBRID_ARTIFACT_DIR / "metadata.json"


class HybridPhishingAnalyzer:
    def __init__(self) -> None:
        self.baseline = PhishingDetector()

        # IMPORTANT:
        # Expose this for backward compatibility with existing routes/UI code.
        self.phase2_models = self.baseline.phase2_models

        self.gemini: Optional[GeminiPhishingAnalyzer] = None
        try:
            self.gemini = GeminiPhishingAnalyzer()
        except Exception:
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
        component_scores = baseline.get("component_scores", {})
        real_threats = [t for t in baseline.get("threats", []) if t != "No immediate threats detected"]

        intel_matches = int(ml_scores.get("intel_exact_match_count", 0)) + int(
            ml_scores.get("intel_domain_match_count", 0)
        )

        gemini_used = False
        routing_reason = "Gemini unavailable"
        gemini_result = {
            "available": False,
            "is_phishing": False,
            "threat_type": "Not Run",
            "threat_confidence": 0.0,
            "tactics_detected": [],
            "contextual_issues": [],
            "social_engineering_score": 0.0,
            "contradictions": [],
            "explanation": "",
            "recommendation": "",
        }

        if self.gemini is not None:
            should_route, routing_reason = self.gemini.should_route_to_llm(
                baseline_score=float(baseline.get("overall_risk_score", 0.0)),
                threat_count=len(real_threats),
                intel_matches=intel_matches,
            )
            if should_route:
                gemini_used = True
                gemini_result = self.gemini.analyze_email_semantics(
                    sender=sender,
                    subject=subject,
                    body=body,
                    urls=urls,
                    ml_scores={
                        "overall_risk_score": baseline.get("overall_risk_score", 0.0),
                        **component_scores,
                        "ml_content_score": ml_scores.get("content_score", 0.0),
                        "ml_url_score": ml_scores.get("url_score", 0.0),
                        "threat_count": len(real_threats),
                    },
                )

        features = {
            "overall_risk_score": float(baseline.get("overall_risk_score", 0.0)),
            "sender_score": float(component_scores.get("sender_score", 0.0)),
            "subject_score": float(component_scores.get("subject_score", 0.0)),
            "body_score": float(component_scores.get("body_score", 0.0)),
            "url_score": float(component_scores.get("url_score", 0.0)),
            "urgency_score": float(component_scores.get("urgency_score", 0.0)),
            "impersonation_score": float(component_scores.get("impersonation_score", 0.0)),
            "history_score": float(component_scores.get("history_score", 0.0)),
            "header_score": float(component_scores.get("header_score", 0.0)),
            "ml_content_score": float(ml_scores.get("content_score", 0.0)),
            "ml_url_score": float(ml_scores.get("url_score", 0.0)),
            "intel_exact_match_count": float(ml_scores.get("intel_exact_match_count", 0)),
            "intel_domain_match_count": float(ml_scores.get("intel_domain_match_count", 0)),
            "threat_count": float(len(real_threats)),
            "baseline_confidence_numeric": self._confidence_to_num(baseline.get("confidence", "low")),
        }

        feature_order = self.metadata.get("feature_order", list(features.keys()))
        final_score = float(baseline.get("overall_risk_score", 0.0))

        if self.calibrator is not None:
            try:
                row = np.array([[features.get(name, 0.0) for name in feature_order]], dtype=float)
                final_score = float(self.calibrator.predict_proba(row)[0, 1])
            except Exception:
                final_score = float(baseline.get("overall_risk_score", 0.0))
        elif self.gemini is not None:
            final_score = self.gemini.create_hybrid_score(
                ml_score=float(baseline.get("overall_risk_score", 0.0)),
                gemini_confidence=float(gemini_result.get("threat_confidence", 0.0)),
                ml_confidence=self._confidence_to_num(baseline.get("confidence", "low")),
            )

        if intel_matches > 0:
            final_verdict = "phishing"
        elif final_score >= 0.75:
            final_verdict = "phishing"
        elif final_score >= 0.45:
            final_verdict = "suspicious"
        else:
            final_verdict = "safe"

        hybrid_explanation = ""
        if self.gemini is not None:
            hybrid_explanation = self.gemini.generate_hybrid_explanation(
                baseline=baseline,
                gemini_analysis=gemini_result,
                final_score=final_score,
                final_verdict=final_verdict,
            )

        result = dict(baseline)
        result.update({
            "analysis_type": "HYBRID_ML_GEMINI" if gemini_used else "ML_WITH_CALIBRATED_FINALIZER",
            "hybrid_score": round(final_score, 4),
            "hybrid_verdict": final_verdict,
            "verdict": final_verdict,
            "is_phishing": final_verdict == "phishing",
            "gemini_used": gemini_used,
            "routing_reason": routing_reason,
            "gemini_analysis": gemini_result,
            "hybrid_explanation": hybrid_explanation,
            "final_model_metadata": self.metadata,
        })
        return result

    @staticmethod
    def _confidence_to_num(label: str) -> float:
        mapping = {
            "low": 0.25,
            "medium": 0.50,
            "high": 0.75,
            "very high": 0.95,
        }
        return float(mapping.get(str(label).lower(), 0.25))