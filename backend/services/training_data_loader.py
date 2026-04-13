from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from services.phase2_models import extract_urls_from_text


POSITIVE_EMAIL_LABELS = {
    "phishing", "phish", "malicious", "fraud", "scam", "spam", "bec", "1", "true", "yes"
}
NEGATIVE_EMAIL_LABELS = {
    "safe", "benign", "legit", "legitimate", "ham", "normal", "0", "false", "no"
}


@dataclass
class LoadedDataset:
    frame: pd.DataFrame
    source_files: list[str]


class TrainingDataLoader:
    def __init__(self, backend_root: Optional[Path] = None) -> None:
        self.backend_root = backend_root or Path(__file__).resolve().parents[1]
        self.email_dir = self.backend_root / "training_data" / "email"
        self.url_dir = self.backend_root / "training_data" / "url"
        self.processed_dir = self.backend_root / "training_data" / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def load_all_email_csvs(self) -> LoadedDataset:
        csv_files = sorted(self.email_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No email CSVs found in {self.email_dir}")

        frames: list[pd.DataFrame] = []
        source_files: list[str] = []

        for path in csv_files:
            try:
                raw = self._safe_read_csv(path)
                normalized = self._normalize_email_frame(raw, path.stem)
                if not normalized.empty:
                    frames.append(normalized)
                    source_files.append(str(path))
                    print(f"[email] loaded {path.name}: {len(normalized)} rows")
                else:
                    print(f"[email] skipped {path.name}: no usable normalized rows")
            except Exception as exc:
                print(f"[email] skipped {path.name}: {exc}")

        if not frames:
            raise ValueError("No usable email rows found after normalization")

        merged = pd.concat(frames, ignore_index=True)

        merged = merged.drop_duplicates(
            subset=["sender", "recipient", "subject", "body", "label"],
            keep="first",
        ).reset_index(drop=True)

        merged.to_csv(self.processed_dir / "normalized_email_training.csv", index=False)
        print(f"[email] merged rows: {len(merged)}")
        return LoadedDataset(frame=merged, source_files=source_files)

    def load_all_url_csvs(self) -> LoadedDataset:
        csv_files = sorted(self.url_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No URL CSVs found in {self.url_dir}")

        frames: list[pd.DataFrame] = []
        source_files: list[str] = []

        for path in csv_files:
            try:
                raw = self._safe_read_csv(path)
                normalized = self._normalize_url_frame(raw, path.stem)
                if not normalized.empty:
                    frames.append(normalized)
                    source_files.append(str(path))
                    print(f"[url] loaded {path.name}: {len(normalized)} rows")
                else:
                    print(f"[url] skipped {path.name}: no usable normalized rows")
            except Exception as exc:
                print(f"[url] skipped {path.name}: {exc}")

        if not frames:
            raise ValueError("No usable URL rows found after normalization")

        merged = pd.concat(frames, ignore_index=True)
        merged = merged.drop_duplicates(subset=["url", "label"], keep="first").reset_index(drop=True)

        merged.to_csv(self.processed_dir / "normalized_url_training.csv", index=False)
        print(f"[url] merged rows: {len(merged)}")
        return LoadedDataset(frame=merged, source_files=source_files)

    def _safe_read_csv(self, path: Path) -> pd.DataFrame:
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                return pd.read_csv(path, encoding=encoding, low_memory=False)
            except Exception:
                pass

        for encoding in encodings:
            try:
                return pd.read_csv(
                    path,
                    encoding=encoding,
                    engine="python",
                    sep=None,
                    on_bad_lines="skip",
                )
            except Exception:
                pass

        for encoding in encodings:
            for sep in [",", "\t", ";", "|"]:
                try:
                    return pd.read_csv(
                        path,
                        encoding=encoding,
                        engine="python",
                        sep=sep,
                        on_bad_lines="skip",
                        quoting=csv.QUOTE_MINIMAL,
                    )
                except Exception:
                    pass

        raise ValueError(f"Could not parse CSV safely: {path}")

    def _normalize_email_frame(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        columns = {c.lower().strip(): c for c in df.columns}

        # Special handling for Nazario-style files
        if source_name.lower() == "nazario":
            return self._normalize_nazario(df, source_name)

        sender_col = self._find_column(columns, ["sender", "from", "from_email", "email_from"])
        recipient_col = self._find_column(columns, ["recipient", "receiver", "to", "to_email", "email_to"])
        subject_col = self._find_column(columns, ["subject", "title"])
        body_col = self._find_column(columns, ["body", "content", "text", "message", "email_body"])
        label_col = self._find_column(columns, ["label", "is_phishing", "class", "target"])
        date_col = self._find_column(columns, ["date", "timestamp", "datetime"])
        headers_col = self._find_column(columns, ["headers", "raw_headers"])

        if body_col is None or label_col is None:
            return pd.DataFrame()

        out = pd.DataFrame({
            "sender": df[sender_col].fillna("").astype(str) if sender_col else "",
            "recipient": df[recipient_col].fillna("").astype(str) if recipient_col else "",
            "subject": df[subject_col].fillna("").astype(str) if subject_col else "",
            "body": df[body_col].fillna("").astype(str),
            "headers": df[headers_col].fillna("").astype(str) if headers_col else "",
            "date": df[date_col].fillna("").astype(str) if date_col else "",
            "source": source_name,
        })

        out["label"] = df[label_col].apply(self._normalize_email_label)
        out = out.dropna(subset=["label"]).copy()
        if out.empty:
            return out

        out["label"] = out["label"].astype(int)
        out = self._clean_email_rows(out)
        return out

    def _normalize_nazario(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        columns = {c.lower().strip(): c for c in df.columns}

        sender_col = self._find_column(columns, ["sender"])
        recipient_col = self._find_column(columns, ["receiver", "recipient"])
        subject_col = self._find_column(columns, ["subject"])
        body_col = self._find_column(columns, ["body"])
        label_col = self._find_column(columns, ["label"])
        date_col = self._find_column(columns, ["date"])
        urls_col = self._find_column(columns, ["urls"])

        if body_col is None or label_col is None:
            return pd.DataFrame()

        out = pd.DataFrame({
            "sender": df[sender_col].fillna("").astype(str) if sender_col else "",
            "recipient": df[recipient_col].fillna("").astype(str) if recipient_col else "",
            "subject": df[subject_col].fillna("").astype(str) if subject_col else "",
            "body": df[body_col].fillna("").astype(str),
            "headers": "",
            "date": df[date_col].fillna("").astype(str) if date_col else "",
            "source": source_name,
        })

        # Nazario label appears to be positive-only phishing in your sample.
        # Keep generic normalization so mixed labels still work if present.
        out["label"] = df[label_col].apply(self._normalize_email_label)

        # urls column in this dataset behaves more like a count/flag than raw URLs
        if urls_col is not None:
            out["url_count_hint"] = pd.to_numeric(df[urls_col], errors="coerce").fillna(0).astype(int)
        else:
            out["url_count_hint"] = 0

        out = out.dropna(subset=["label"]).copy()
        if out.empty:
            return out

        out["label"] = out["label"].astype(int)
        out = self._clean_email_rows(out)
        return out

    def _clean_email_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        for col in ["sender", "recipient", "subject", "body", "headers", "date"]:
            if col in out.columns:
                out[col] = out[col].fillna("").astype(str).str.strip()

        # Remove empty bodies
        out = out[out["body"].str.len() > 0]

        # Remove obviously corrupted giant multi-message blobs
        out = out[out["body"].str.len() <= 50000]

        # If a "body" appears to contain many concatenated messages, drop it
        out = out[
            out["body"].apply(
                lambda x: len(re.findall(r"\bFrom [^\n]+", x)) <= 3
            )
        ]

        # Remove rows that are almost entirely headers / raw transport metadata
        out = out[
            out["body"].apply(
                lambda x: (
                    x.lower().count("received:") <= 12
                    and x.lower().count("x-spam-") <= 12
                )
            )
        ]

        return out.reset_index(drop=True)

    def _normalize_url_frame(self, df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        columns = {c.lower().strip(): c for c in df.columns}

        # PhiUSIIL special handling
        if source_name.lower() == "phiusiil_phishing_url_dataset":
            url_col = self._find_column(columns, ["url"])
            label_col = self._find_column(columns, ["label"])

            if url_col is None or label_col is None:
                return pd.DataFrame()

            out = pd.DataFrame({
                "url": df[url_col].fillna("").astype(str).str.strip(),
                "source": source_name,
            })

            # PhiUSIIL: 1 = legitimate, 0 = phishing
            out["label"] = df[label_col].apply(self._normalize_phiusiil_label)
            out = out.dropna(subset=["label"])
            if out.empty:
                return out

            out["label"] = out["label"].astype(int)
            out = out[out["url"].str.len() > 0].reset_index(drop=True)
            return out

        # Generic URL files
        url_col = self._find_column(columns, ["url", "urls", "full_url", "link", "website", "domain"])
        label_col = self._find_column(columns, ["label", "class", "result", "target", "status"])

        if source_name.lower() in {"phishing", "not-phishing"}:
            if url_col is None:
                return pd.DataFrame()

            out = pd.DataFrame({
                "url": df[url_col].fillna("").astype(str).str.strip(),
                "source": source_name,
            })
            out["label"] = 1 if source_name.lower() == "phishing" else 0
            out = out[out["url"].str.len() > 0].reset_index(drop=True)
            return out

        if url_col is None or label_col is None:
            return pd.DataFrame()

        out = pd.DataFrame({
            "url": df[url_col].fillna("").astype(str).str.strip(),
            "source": source_name,
        })
        out["label"] = df[label_col].apply(self._normalize_generic_binary_label)
        out = out.dropna(subset=["label"])
        if out.empty:
            return out

        out["label"] = out["label"].astype(int)
        out = out[out["url"].str.len() > 0].reset_index(drop=True)
        return out

    @staticmethod
    def _find_column(columns: dict[str, str], candidates: Iterable[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate in columns:
                return columns[candidate]
        return None

    @staticmethod
    def _normalize_email_label(value: object) -> Optional[int]:
        if pd.isna(value):
            return None
        text = str(value).strip().lower()

        if text in POSITIVE_EMAIL_LABELS:
            return 1
        if text in NEGATIVE_EMAIL_LABELS:
            return 0

        try:
            numeric = int(float(text))
            if numeric == 1:
                return 1
            if numeric == 0:
                return 0
        except Exception:
            pass
        return None

    @staticmethod
    def _normalize_generic_binary_label(value: object) -> Optional[int]:
        if pd.isna(value):
            return None
        text = str(value).strip().lower()

        if text in {"phishing", "malicious", "bad", "1", "true", "yes"}:
            return 1
        if text in {"legitimate", "benign", "safe", "good", "0", "false", "no"}:
            return 0

        try:
            numeric = int(float(text))
            if numeric == 1:
                return 1
            if numeric == 0:
                return 0
        except Exception:
            pass
        return None

    @staticmethod
    def _normalize_phiusiil_label(value: object) -> Optional[int]:
        if pd.isna(value):
            return None
        try:
            numeric = int(float(value))
        except Exception:
            return None

        if numeric == 1:
            return 0  # legitimate
        if numeric == 0:
            return 1  # phishing
        return None

    @staticmethod
    def add_extracted_urls(email_df: pd.DataFrame) -> pd.DataFrame:
        df = email_df.copy()
        df["urls"] = df["body"].apply(extract_urls_from_text)
        df["url_count"] = df["urls"].apply(len)
        return df