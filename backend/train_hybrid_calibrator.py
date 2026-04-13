from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from services.enterprise_dataset_loader import EnterpriseDatasetLoader
from services.hybrid_analyzer import HYBRID_ARTIFACT_DIR
from services.phishing_detector import PhishingDetector

try:
    from services.gemini_analyzer import GeminiPhishingAnalyzer
except Exception:
    GeminiPhishingAnalyzer = None  # type: ignore


DEFAULT_FEATURE_ORDER = [
    "overall_risk_score",
    "sender_score",
    "subject_score",
    "body_score",
    "url_score",
    "urgency_score",
    "impersonation_score",
    "history_score",
    "header_score",
    "ml_content_score",
    "ml_url_score",
    "intel_exact_match_count",
    "intel_domain_match_count",
    "threat_count",
    "baseline_confidence_numeric",
    "gemini_available",
    "gemini_is_phishing",
    "gemini_threat_confidence",
    "gemini_social_engineering_score",
    "gemini_tactic_count",
    "gemini_issue_count",
    "gemini_contradiction_count",
]


def baseline_confidence_numeric(confidence_label: str) -> float:
    mapping = {
        "low": 0.25,
        "medium": 0.50,
        "high": 0.75,
        "very high": 0.95,
    }
    return float(mapping.get(str(confidence_label).lower(), 0.25))


def build_feature_row(
    baseline: Dict[str, Any],
    gemini_result: Dict[str, Any],
) -> Dict[str, float]:
    component_scores = baseline.get("component_scores", {})
    ml_scores = baseline.get("ml_scores", {})
    threats = [t for t in baseline.get("threats", []) if t != "No immediate threats detected"]

    return {
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
        "intel_exact_match_count": float(ml_scores.get("intel_exact_match_count", 0.0)),
        "intel_domain_match_count": float(ml_scores.get("intel_domain_match_count", 0.0)),
        "threat_count": float(len(threats)),
        "baseline_confidence_numeric": baseline_confidence_numeric(baseline.get("confidence", "low")),
        "gemini_available": 1.0 if gemini_result.get("available") else 0.0,
        "gemini_is_phishing": 1.0 if gemini_result.get("is_phishing") else 0.0,
        "gemini_threat_confidence": float(gemini_result.get("threat_confidence", 0.0)),
        "gemini_social_engineering_score": float(gemini_result.get("social_engineering_score", 0.0)),
        "gemini_tactic_count": float(len(gemini_result.get("tactics_detected", []))),
        "gemini_issue_count": float(len(gemini_result.get("contextual_issues", []))),
        "gemini_contradiction_count": float(len(gemini_result.get("contradictions", []))),
    }


def maybe_run_gemini(
    gemini,
    sender: str,
    subject: str,
    body: str,
    baseline: Dict[str, Any],
    use_gemini: bool,
) -> Dict[str, Any]:
    if not use_gemini or gemini is None:
        return {
            "available": False,
            "is_phishing": False,
            "threat_confidence": 0.0,
            "social_engineering_score": 0.0,
            "tactics_detected": [],
            "contextual_issues": [],
            "contradictions": [],
        }

    baseline_score = float(baseline.get("overall_risk_score", 0.0))
    threat_count = len([t for t in baseline.get("threats", []) if t != "No immediate threats detected"])
    ml_scores = baseline.get("ml_scores", {})
    intel_matches = int(ml_scores.get("intel_exact_match_count", 0)) + int(ml_scores.get("intel_domain_match_count", 0))

    routing = gemini.should_route_to_llm(
        baseline_score=baseline_score,
        threat_count=threat_count,
        intel_matches=intel_matches,
    )

    if not routing.should_route:
        return {
            "available": False,
            "is_phishing": False,
            "threat_confidence": 0.0,
            "social_engineering_score": 0.0,
            "tactics_detected": [],
            "contextual_issues": [],
            "contradictions": [],
        }

    llm_context = {
        "overall_risk_score": baseline_score,
        **{k: float(v) for k, v in baseline.get("component_scores", {}).items()},
        "threat_count": threat_count,
    }

    return gemini.analyze_email_semantics(
        sender=sender,
        subject=subject,
        body=body,
        urls=[],
        ml_scores=llm_context,
    )


def featurize_dataset(
    df: pd.DataFrame,
    use_gemini: bool,
) -> Tuple[pd.DataFrame, pd.Series]:
    baseline_detector = PhishingDetector()
    gemini = None

    if use_gemini and GeminiPhishingAnalyzer is not None:
        try:
            gemini = GeminiPhishingAnalyzer()
        except Exception:
            gemini = None

    rows: List[Dict[str, float]] = []
    labels: List[int] = []

    for idx, record in df.iterrows():
        headers = {}
        if isinstance(record.get("headers", ""), str) and record.get("headers", "").strip():
            headers = {}

        baseline = baseline_detector.analyze_email(
            sender=str(record.get("sender", "")),
            recipient=str(record.get("recipient", "")),
            subject=str(record.get("subject", "")),
            body=str(record.get("body", "")),
            headers=headers,
        )

        gemini_result = maybe_run_gemini(
            gemini=gemini,
            sender=str(record.get("sender", "")),
            subject=str(record.get("subject", "")),
            body=str(record.get("body", "")),
            baseline=baseline,
            use_gemini=use_gemini,
        )

        rows.append(build_feature_row(baseline, gemini_result))
        labels.append(int(record["label"]))

        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1} samples...")

    return pd.DataFrame(rows), pd.Series(labels, name="label")


def train_calibrator(X: pd.DataFrame, y: pd.Series) -> Tuple[Any, Dict[str, Any]]:
    feature_order = DEFAULT_FEATURE_ORDER
    X = X[feature_order]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    base_model = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            max_iter=4000,
            class_weight="balanced",
            random_state=42,
        )),
    ])

    calibrated = CalibratedClassifierCV(
        estimator=base_model,
        method="sigmoid",
        cv=5,
    )
    calibrated.fit(X_train, y_train)

    probs = calibrated.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.50).astype(int)

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, preds)), 4),
        "precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probs)), 4),
        "average_precision": round(float(average_precision_score(y_test, probs)), 4),
        "brier_score": round(float(brier_score_loss(y_test, probs)), 4),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "class_balance_positive": round(float(y.mean()), 4),
        "classification_report": classification_report(y_test, preds, zero_division=0, output_dict=True),
    }

    metadata = {
        "model_type": "Calibrated Logistic Regression meta-classifier",
        "feature_order": feature_order,
        "metrics": metrics,
    }
    return calibrated, metadata


def save_artifacts(model: Any, metadata: Dict[str, Any], dataset_paths: List[str], use_gemini: bool) -> None:
    HYBRID_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = HYBRID_ARTIFACT_DIR / "final_calibrator.joblib"
    metadata_path = HYBRID_ARTIFACT_DIR / "metadata.json"

    joblib.dump(model, model_path)

    metadata = dict(metadata)
    metadata["datasets_used"] = dataset_paths
    metadata["use_gemini_during_training"] = use_gemini
    metadata["trained_at"] = pd.Timestamp.utcnow().isoformat()

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved calibrator to: {model_path}")
    print(f"Saved metadata to: {metadata_path}")
    print(json.dumps(metadata["metrics"], indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train final calibrated hybrid phishing decision layer."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        help="Path to enterprise-style phishing dataset CSV. Can be repeated.",
    )
    parser.add_argument(
        "--use-gemini",
        action="store_true",
        help="Include Gemini semantic features during feature generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    loader = EnterpriseDatasetLoader(args.dataset)
    df = loader.load()

    print(f"Loaded {len(df)} normalized messages from {len(args.dataset)} dataset(s).")
    print(df["label"].value_counts(dropna=False).to_string())

    X, y = featurize_dataset(df, use_gemini=args.use_gemini)
    model, metadata = train_calibrator(X, y)
    save_artifacts(model, metadata, args.dataset, args.use_gemini)


if __name__ == "__main__":
    main()