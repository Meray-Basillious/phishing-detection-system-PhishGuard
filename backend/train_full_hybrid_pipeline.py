from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

from services.phase2_models import (
    ARTIFACT_DIR,
    URL_INTEL_PATH,
    build_content_text,
    extract_url_feature_row,
)
from services.phishing_detector import PhishingDetector
from services.training_data_loader import TrainingDataLoader


HYBRID_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts" / "hybrid"
HYBRID_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def train_content_model(email_df: pd.DataFrame) -> Tuple[Any, Dict[str, Any]]:
    required_columns = ["sender", "subject", "body", "label", "source"]
    missing = [col for col in required_columns if col not in email_df.columns]
    if missing:
        raise ValueError(
            f"train_content_model() is missing required columns: {missing}. "
            f"Available columns: {list(email_df.columns)}"
        )

    df = email_df[required_columns].copy()

    if "urls" in email_df.columns:
        df["urls"] = email_df["urls"]
    else:
        df["urls"] = [[] for _ in range(len(df))]

    df["text"] = df.apply(
        lambda row: build_content_text(
            sender=row.get("sender", ""),
            subject=row.get("subject", ""),
            body=row.get("body", ""),
            urls=row.get("urls", []),
        ),
        axis=1,
    )

    df = df[df["text"].astype(str).str.len() >= 20].copy()

    if "label" not in df.columns:
        raise ValueError(
            f"'label' column disappeared inside train_content_model(). "
            f"Available columns now: {list(df.columns)}"
        )

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)

    if df.empty:
        raise ValueError("No usable rows left for content model training after preprocessing")

    train_df, test_df = train_test_split(
        df[["text", "label", "source"]],
        test_size=0.20,
        random_state=42,
        stratify=df["label"],
    )

    content_model = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                min_df=3,
                max_features=12000,
                sublinear_tf=True,
                strip_accents="unicode",
            )),
            ("char", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=3,
                max_features=8000,
                sublinear_tf=True,
                strip_accents="unicode",
            )),
        ])),
        ("classifier", LogisticRegression(
            max_iter=5000,
            class_weight="balanced",
            solver="saga",
            C=1.0,
            random_state=42,
        )),
    ])

    content_model.fit(train_df["text"], train_df["label"])
    preds = content_model.predict(test_df["text"])
    probs = content_model.predict_proba(test_df["text"])[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(test_df["label"], preds)), 4),
        "precision": round(float(precision_score(test_df["label"], preds, zero_division=0)), 4),
        "recall": round(float(recall_score(test_df["label"], preds, zero_division=0)), 4),
        "f1": round(float(f1_score(test_df["label"], preds, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(test_df["label"], probs)), 4),
        "train_samples": int(len(train_df)),
        "test_samples": int(len(test_df)),
    }
    return content_model, metrics


def build_url_feature_frame(url_df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for _, row in url_df.iterrows():
        url = str(row["url"]).strip()
        label = int(row["label"])
        source = str(row.get("source", ""))

        if not url:
            continue

        try:
            # Use the same runtime feature extractor used during inference.
            feats = extract_url_feature_row(url, body="")
            feats["label"] = label
            feats["url"] = url
            feats["source"] = source
            rows.append(feats)
        except Exception:
            continue

    if not rows:
        raise ValueError("No URL feature rows could be extracted")

    feature_df = pd.DataFrame(rows)
    feature_df = feature_df.drop_duplicates(subset=["url", "label"]).reset_index(drop=True)
    return feature_df


def train_url_model(url_df: pd.DataFrame) -> Tuple[Any, List[str], Dict[str, Any]]:
    feature_df = build_url_feature_frame(url_df)

    excluded = {"label", "url", "source"}
    feature_columns = [col for col in feature_df.columns if col not in excluded]

    if not feature_columns:
        raise ValueError(
            f"No usable URL feature columns found. Available columns: {list(feature_df.columns)}"
        )

    train_df, test_df = train_test_split(
        feature_df,
        test_size=0.20,
        random_state=42,
        stratify=feature_df["label"],
    )

    url_model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced_subsample",
        min_samples_leaf=2,
        max_features="sqrt",
        n_jobs=-1,
    )

    url_model.fit(train_df[feature_columns], train_df["label"])
    preds = url_model.predict(test_df[feature_columns])
    probs = url_model.predict_proba(test_df[feature_columns])[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(test_df["label"], preds)), 4),
        "precision": round(float(precision_score(test_df["label"], preds, zero_division=0)), 4),
        "recall": round(float(recall_score(test_df["label"], preds, zero_division=0)), 4),
        "f1": round(float(f1_score(test_df["label"], preds, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(test_df["label"], probs)), 4),
        "train_samples": int(len(train_df)),
        "test_samples": int(len(test_df)),
        "feature_count": int(len(feature_columns)),
    }

    print(f"URL feature columns used: {feature_columns}")
    return url_model, feature_columns, metrics


def save_phase2_artifacts(
    content_model: Any,
    url_model: Any,
    url_feature_columns: List[str],
    content_metrics: Dict[str, Any],
    url_metrics: Dict[str, Any],
    email_sources: List[str],
    url_sources: List[str],
    email_df: pd.DataFrame,
    url_df: pd.DataFrame,
) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    content_model_path = ARTIFACT_DIR / "content_model.joblib"
    url_model_path = ARTIFACT_DIR / "url_model.joblib"
    metadata_path = ARTIFACT_DIR / "metadata.json"

    joblib.dump(content_model, content_model_path)
    joblib.dump(url_model, url_model_path)

    metadata = {
        "trained_at": pd.Timestamp.now("UTC").isoformat(),
        "artifact_dir": str(ARTIFACT_DIR),
        "content_model_path": str(content_model_path),
        "url_model_path": str(url_model_path),
        "url_intel_path": str(URL_INTEL_PATH),
        "url_feature_columns": url_feature_columns,
        "content_metrics": content_metrics,
        "url_metrics": url_metrics,
        "training_stats": {
            "content_samples_total": int(len(email_df)),
            "url_model_samples_total": int(len(url_df)),
            "content_label_distribution": {
                "phishing": int((email_df["label"] == 1).sum()),
                "safe": int((email_df["label"] == 0).sum()),
            },
            "url_label_distribution": {
                "phishing": int((url_df["label"] == 1).sum()),
                "safe": int((url_df["label"] == 0).sum()),
            },
        },
        "data_sources": [
            *[
                {
                    "name": Path(path).name,
                    "source": path,
                    "purpose": "Email training corpus",
                }
                for path in email_sources
            ],
            *[
                {
                    "name": Path(path).name,
                    "source": path,
                    "purpose": "URL training corpus",
                }
                for path in url_sources
            ],
        ],
        "notes": [
            "Content model is trained from all CSVs under backend/training_data/email.",
            "URL model is trained from all CSVs under backend/training_data/url using the runtime URL feature extractor.",
            "Hybrid calibrator is trained after Phase 2 artifacts are written, so inference can use calibrated ML + Gemini routing together.",
        ],
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved Phase 2 artifacts into {ARTIFACT_DIR}")


def confidence_to_num(label: str) -> float:
    mapping = {
        "low": 0.25,
        "medium": 0.50,
        "high": 0.75,
        "very high": 0.95,
    }
    return float(mapping.get(str(label).lower(), 0.25))


def build_calibrator_features(email_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    detector = PhishingDetector()
    rows: List[Dict[str, float]] = []
    labels: List[int] = []

    for _, row in email_df.iterrows():
        analysis = detector.analyze_email(
            sender=str(row.get("sender", "")),
            recipient=str(row.get("recipient", "")),
            subject=str(row.get("subject", "")),
            body=str(row.get("body", "")),
            headers={},
        )

        component_scores = analysis.get("component_scores", {})
        ml_scores = analysis.get("ml_scores", {})
        threats = [t for t in analysis.get("threats", []) if t != "No immediate threats detected"]

        rows.append({
            "overall_risk_score": float(analysis.get("overall_risk_score", 0.0)),
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
            "threat_count": float(len(threats)),
            "baseline_confidence_numeric": confidence_to_num(analysis.get("confidence", "low")),
        })
        labels.append(int(row["label"]))

    X = pd.DataFrame(rows)
    y = pd.Series(labels, name="label")
    return X, y


def train_hybrid_calibrator(email_df: pd.DataFrame) -> Tuple[Any, Dict[str, Any]]:
    X, y = build_calibrator_features(email_df)

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
    }

    metadata = {
        "trained_at": pd.Timestamp.now("UTC").isoformat(),
        "feature_order": list(X.columns),
        "model_type": "Calibrated Logistic Regression",
        "metrics": metrics,
    }
    return calibrated, metadata


def save_hybrid_artifacts(model: Any, metadata: Dict[str, Any]) -> None:
    HYBRID_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = HYBRID_ARTIFACT_DIR / "final_calibrator.joblib"
    metadata_path = HYBRID_ARTIFACT_DIR / "metadata.json"

    joblib.dump(model, model_path)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Saved hybrid calibrator to {model_path}")
    print(f"Saved hybrid metadata to {metadata_path}")


def main() -> None:
    loader = TrainingDataLoader()

    email_loaded = loader.load_all_email_csvs()
    email_df = loader.add_extracted_urls(email_loaded.frame)
    print(f"Loaded {len(email_df)} normalized email rows from {len(email_loaded.source_files)} files")

    url_loaded = loader.load_all_url_csvs()
    url_df = url_loaded.frame
    print(f"Loaded {len(url_df)} normalized URL rows from {len(url_loaded.source_files)} files")

    print(f"Email columns before training: {list(email_df.columns)}")
    print(f"URL columns before training: {list(url_df.columns)}")

    content_model, content_metrics = train_content_model(email_df)
    print("Content model metrics:", content_metrics)

    url_model, feature_columns, url_metrics = train_url_model(url_df)
    print("URL model metrics:", url_metrics)

    save_phase2_artifacts(
        content_model=content_model,
        url_model=url_model,
        url_feature_columns=feature_columns,
        content_metrics=content_metrics,
        url_metrics=url_metrics,
        email_sources=email_loaded.source_files,
        url_sources=url_loaded.source_files,
        email_df=email_df,
        url_df=url_df,
    )

    hybrid_model, hybrid_metadata = train_hybrid_calibrator(email_df)
    print("Hybrid calibrator metrics:", hybrid_metadata["metrics"])
    save_hybrid_artifacts(hybrid_model, hybrid_metadata)

    print("\nTraining pipeline complete.")


if __name__ == "__main__":
    main()