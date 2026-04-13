from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


@dataclass
class DatasetSpec:
    path: Path
    source_name: str


class EnterpriseDatasetLoader:
    """
    Load realistic phishing/benign enterprise-style email datasets from CSV files.

    Expected flexible schema:
    Required:
      - label
      - body or content

    Optional:
      - sender
      - recipient
      - subject
      - headers
      - source
      - split

    Accepted positive labels:
      phishing, phish, malicious, fraud, bec, 1, true, yes
    Accepted negative labels:
      safe, benign, legit, legitimate, ham, normal, 0, false, no
    """

    POSITIVE = {"phishing", "phish", "malicious", "fraud", "bec", "1", "true", "yes"}
    NEGATIVE = {"safe", "benign", "legit", "legitimate", "ham", "normal", "0", "false", "no"}

    def __init__(self, csv_paths: Iterable[str]) -> None:
        self.specs: List[DatasetSpec] = [
            DatasetSpec(path=Path(p).expanduser().resolve(), source_name=Path(p).stem)
            for p in csv_paths
        ]

    def load(self) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []

        for spec in self.specs:
            if not spec.path.exists():
                raise FileNotFoundError(f"Dataset not found: {spec.path}")

            df = pd.read_csv(spec.path)
            normalized = self._normalize_frame(df, spec.source_name)
            frames.append(normalized)

        if not frames:
            raise ValueError("No datasets loaded")

        merged = pd.concat(frames, ignore_index=True)
        merged = merged.drop_duplicates(
            subset=["sender", "recipient", "subject", "body", "label"],
            keep="first",
        ).reset_index(drop=True)

        return merged

    def _normalize_frame(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        column_map = {c.lower().strip(): c for c in df.columns}

        body_col = self._first_match(column_map, ["body", "content", "text", "message", "email_body"])
        label_col = self._first_match(column_map, ["label", "is_phishing", "target", "class"])
        sender_col = self._first_match(column_map, ["sender", "from", "from_email", "email_from"])
        recipient_col = self._first_match(column_map, ["recipient", "to", "to_email", "email_to"])
        subject_col = self._first_match(column_map, ["subject", "title"])
        headers_col = self._first_match(column_map, ["headers", "raw_headers"])
        split_col = self._first_match(column_map, ["split", "dataset_split"])
        source_col = self._first_match(column_map, ["source", "dataset"])

        if body_col is None or label_col is None:
            raise ValueError(
                f"Dataset {source_name} must include body/content and label columns. "
                f"Found columns: {list(df.columns)}"
            )

        out = pd.DataFrame({
            "sender": df[sender_col].fillna("").astype(str) if sender_col else "",
            "recipient": df[recipient_col].fillna("").astype(str) if recipient_col else "",
            "subject": df[subject_col].fillna("").astype(str) if subject_col else "",
            "body": df[body_col].fillna("").astype(str),
            "headers": df[headers_col].fillna("").astype(str) if headers_col else "",
            "split": df[split_col].fillna("").astype(str) if split_col else "",
            "source": df[source_col].fillna(source_name).astype(str) if source_col else source_name,
        })

        out["label"] = df[label_col].apply(self._normalize_label)

        out = out.dropna(subset=["label"])
        out["label"] = out["label"].astype(int)
        out["body"] = out["body"].astype(str).str.strip()
        out["subject"] = out["subject"].astype(str).str.strip()
        out["sender"] = out["sender"].astype(str).str.strip()
        out["recipient"] = out["recipient"].astype(str).str.strip()
        out["headers"] = out["headers"].astype(str)

        out = out[out["body"].str.len() > 0].reset_index(drop=True)
        return out

    @classmethod
    def _normalize_label(cls, value: object) -> Optional[int]:
        if pd.isna(value):
            return None

        text = str(value).strip().lower()

        if text in cls.POSITIVE:
            return 1
        if text in cls.NEGATIVE:
            return 0

        try:
            numeric = int(float(text))
            return 1 if numeric == 1 else 0 if numeric == 0 else None
        except Exception:
            return None

    @staticmethod
    def _first_match(column_map: dict[str, str], candidates: list[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate in column_map:
                return column_map[candidate]
        return None