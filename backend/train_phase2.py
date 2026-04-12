from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import argparse
import json
import re
import sqlite3
import subprocess
import tempfile
import zipfile
from urllib.request import urlopen

import joblib
import pandas as pd
from sklearn.datasets import fetch_openml
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from services.phase2_models import (
    ARTIFACT_DIR,
    URL_INTEL_PATH,
    URL_FEATURE_NAMES,
    build_content_text,
    extract_domain_for_lookup,
    extract_url_feature_row,
    extract_urls_from_text,
    normalize_url_for_lookup,
)


NIGERIAN_FRAUD_PATH = Path(__file__).resolve().parents[1] / 'test_data' / 'Nigerian_Fraud.csv'
SMS_SPAM_URL = 'https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip'
PHISHING_DATABASE_REPO = 'https://github.com/Phishing-Database/Phishing.Database'
LOCAL_DB_PATHS = [
    Path(__file__).resolve().parents[0] / 'instance' / 'phishing_db.db',
    Path(__file__).resolve().parents[1] / 'frontend' / 'instance' / 'phishing_db.db',
]


def load_nigerian_fraud_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(NIGERIAN_FRAUD_PATH)
    frame = frame.fillna('')

    text_frame = pd.DataFrame({
        'sender': frame.get('sender', ''),
        'subject': frame.get('subject', ''),
        'body': frame.get('body', ''),
        'urls': frame.get('urls', ''),
    })
    frame['text'] = text_frame.apply(
        lambda row: build_content_text(str(row['sender']), str(row['subject']), str(row['body']), [str(row['urls'])] if row['urls'] else None),
        axis=1,
    )
    frame['label'] = frame['label'].astype(int)

    url_records = []
    for _, row in frame.iterrows():
        label_value = int(row['label'])
        body_text = str(row.get('body', ''))
        explicit_url = str(row.get('urls', '')).strip()

        urls = set(extract_urls_from_text(body_text))
        if explicit_url and explicit_url != '0':
            urls.add(explicit_url)

        for url in urls:
            normalized_url = normalize_url_for_lookup(url)
            if normalized_url:
                url_records.append({'url': normalized_url, 'label': label_value, 'source': 'Nigerian_Fraud.csv'})

    return frame[['text', 'label']], pd.DataFrame(url_records)


def load_sms_spam_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    with urlopen(SMS_SPAM_URL, timeout=60) as response:
        archive = zipfile.ZipFile(BytesIO(response.read()))
        raw_lines = archive.read('SMSSpamCollection').decode('utf-8', errors='replace').splitlines()

    records = []
    url_records = []
    for raw_line in raw_lines:
        if '\t' not in raw_line:
            continue
        label_text, message_text = raw_line.split('\t', 1)
        label_value = 1 if label_text.strip().lower() == 'spam' else 0
        records.append({
            'text': message_text.strip(),
            'label': label_value,
        })

        for url in extract_urls_from_text(message_text.strip()):
            normalized_url = normalize_url_for_lookup(url)
            if normalized_url:
                url_records.append({'url': normalized_url, 'label': label_value, 'source': 'SMS Spam Collection'})

    return pd.DataFrame(records), pd.DataFrame(url_records)


def load_sqlite_email_feedback(db_paths: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    content_records = []
    url_records = []

    for db_path in db_paths:
        if not db_path.exists():
            continue

        connection = sqlite3.connect(db_path)
        try:
            query = """
                SELECT sender, subject, body, is_phishing
                FROM emails
                WHERE body IS NOT NULL AND subject IS NOT NULL AND sender IS NOT NULL AND is_phishing IS NOT NULL
            """
            frame = pd.read_sql_query(query, connection)
        except Exception:
            connection.close()
            continue
        finally:
            connection.close()

        if frame.empty:
            continue

        frame['label'] = frame['is_phishing'].astype(int)
        frame['text'] = frame.apply(
            lambda row: build_content_text(str(row['sender']), str(row['subject']), str(row['body'])),
            axis=1,
        )

        for _, row in frame.iterrows():
            label_value = int(row['label'])
            for url in extract_urls_from_text(str(row['body'])):
                normalized_url = normalize_url_for_lookup(url)
                if normalized_url:
                    url_records.append({'url': normalized_url, 'label': label_value, 'source': str(db_path)})

        content_records.extend(frame[['text', 'label']].to_dict('records'))

    return pd.DataFrame(content_records), pd.DataFrame(url_records)


def load_url_dataset() -> pd.DataFrame:
    features, targets = fetch_openml(name='PhishingWebsites', version=1, as_frame=True, return_X_y=True)
    frame = features.copy()
    frame['label'] = (targets.astype(str) == '-1').astype(int)
    frame['label'] = frame['label'].astype(int)

    for feature_name in URL_FEATURE_NAMES:
        if feature_name not in frame.columns:
            frame[feature_name] = 0

    return frame[URL_FEATURE_NAMES + ['label']]


def build_url_feature_dataset(url_records: pd.DataFrame) -> pd.DataFrame:
    if url_records.empty:
        return pd.DataFrame(columns=URL_FEATURE_NAMES + ['label'])

    rows = []
    for _, record in url_records.iterrows():
        url_value = str(record.get('url', '')).strip()
        if not url_value:
            continue

        feature_row = extract_url_feature_row(url_value)
        feature_row['label'] = int(record.get('label', 0))
        rows.append(feature_row)

    if not rows:
        return pd.DataFrame(columns=URL_FEATURE_NAMES + ['label'])

    return pd.DataFrame(rows)


def _read_intel_lines(file_path: Path) -> list[str]:
    if not file_path.exists():
        return []

    lines = []
    for raw_line in file_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        value = raw_line.strip()
        if not value or value.startswith('#'):
            continue
        lines.append(value)

    return lines


def load_phishing_database_intel(skip_download: bool) -> dict[str, object]:
    phishing_urls = set()
    phishing_domains = set()

    if skip_download:
        return {
            'phishing_urls': phishing_urls,
            'phishing_domains': phishing_domains,
            'repo_version': None,
            'source': PHISHING_DATABASE_REPO,
        }

    with tempfile.TemporaryDirectory(prefix='phishing-database-') as temp_dir:
        repo_dir = Path(temp_dir) / 'Phishing.Database'
        subprocess.run(
            ['git', 'clone', '--depth', '1', PHISHING_DATABASE_REPO, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
        )

        active_links = _read_intel_lines(repo_dir / 'phishing-links-ACTIVE.txt')
        active_domains = _read_intel_lines(repo_dir / 'phishing-domains-ACTIVE.txt')

        for url in active_links:
            normalized_url = normalize_url_for_lookup(url)
            if normalized_url:
                phishing_urls.add(normalized_url)
                domain = extract_domain_for_lookup(normalized_url)
                if domain:
                    phishing_domains.add(domain)

        for domain in active_domains:
            normalized_domain = extract_domain_for_lookup(domain)
            if normalized_domain:
                phishing_domains.add(normalized_domain)

        readme = (repo_dir / 'README.md').read_text(encoding='utf-8', errors='ignore')
        version_match = re.search(r'Version:\s*(V\.[0-9\-\.]+)', readme)
        repo_version = version_match.group(1) if version_match else None

    return {
        'phishing_urls': phishing_urls,
        'phishing_domains': phishing_domains,
        'repo_version': repo_version,
        'source': PHISHING_DATABASE_REPO,
    }


def train_content_model(content_frame: pd.DataFrame):
    train_frame, test_frame = train_test_split(
        content_frame,
        test_size=0.2,
        random_state=42,
        stratify=content_frame['label'],
    )

    content_model = Pipeline([
        ('features', FeatureUnion([
            ('word', TfidfVectorizer(
                ngram_range=(1, 2),
                min_df=2,
                max_features=15000,
                stop_words='english',
                sublinear_tf=True,
            )),
            ('char', TfidfVectorizer(
                analyzer='char_wb',
                ngram_range=(3, 5),
                min_df=2,
                max_features=10000,
                sublinear_tf=True,
            )),
        ])),
        ('classifier', LogisticRegression(
            max_iter=3000,
            class_weight='balanced',
            solver='saga',
            random_state=42,
        )),
    ])

    content_model.fit(train_frame['text'], train_frame['label'])
    predictions = content_model.predict(test_frame['text'])
    probabilities = content_model.predict_proba(test_frame['text'])[:, 1]

    metrics = {
        'accuracy': round(accuracy_score(test_frame['label'], predictions), 4),
        'precision': round(precision_score(test_frame['label'], predictions, zero_division=0), 4),
        'recall': round(recall_score(test_frame['label'], predictions, zero_division=0), 4),
        'f1': round(f1_score(test_frame['label'], predictions, zero_division=0), 4),
        'roc_auc': round(roc_auc_score(test_frame['label'], probabilities), 4),
        'train_samples': int(len(train_frame)),
        'test_samples': int(len(test_frame)),
    }

    return content_model, metrics


def train_url_model(url_frame: pd.DataFrame):
    feature_columns = [column for column in url_frame.columns if column != 'label']
    train_frame, test_frame = train_test_split(
        url_frame,
        test_size=0.2,
        random_state=42,
        stratify=url_frame['label'],
    )

    url_model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        class_weight='balanced_subsample',
        min_samples_leaf=2,
        n_jobs=-1,
    )

    url_model.fit(train_frame[feature_columns], train_frame['label'])
    predictions = url_model.predict(test_frame[feature_columns])
    probabilities = url_model.predict_proba(test_frame[feature_columns])[:, 1]

    metrics = {
        'accuracy': round(accuracy_score(test_frame['label'], predictions), 4),
        'precision': round(precision_score(test_frame['label'], predictions, zero_division=0), 4),
        'recall': round(recall_score(test_frame['label'], predictions, zero_division=0), 4),
        'f1': round(f1_score(test_frame['label'], predictions, zero_division=0), 4),
        'roc_auc': round(roc_auc_score(test_frame['label'], probabilities), 4),
        'train_samples': int(len(train_frame)),
        'test_samples': int(len(test_frame)),
    }

    return url_model, feature_columns, metrics


def save_artifacts(content_model, url_model, url_feature_columns, content_metrics, url_metrics, url_intel, training_stats) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    content_model_path = ARTIFACT_DIR / 'content_model.joblib'
    url_model_path = ARTIFACT_DIR / 'url_model.joblib'
    url_intel_path = URL_INTEL_PATH
    metadata_path = ARTIFACT_DIR / 'metadata.json'

    joblib.dump(content_model, content_model_path)
    joblib.dump(url_model, url_model_path)
    joblib.dump(
        {
            'phishing_urls': set(url_intel.get('phishing_urls', set())),
            'phishing_domains': set(url_intel.get('phishing_domains', set())),
        },
        url_intel_path,
    )

    metadata = {
        'trained_at': datetime.now(timezone.utc).isoformat(),
        'artifact_dir': str(ARTIFACT_DIR),
        'content_model_path': str(content_model_path),
        'url_model_path': str(url_model_path),
        'url_intel_path': str(url_intel_path),
        'url_feature_columns': url_feature_columns,
        'content_metrics': content_metrics,
        'url_metrics': url_metrics,
        'training_stats': training_stats,
        'data_sources': [
            {
                'name': 'Nigerian_Fraud.csv',
                'source': 'Repository bundled training corpus',
                'purpose': 'Phishing-style advance-fee fraud language',
            },
            {
                'name': 'UCI SMS Spam Collection',
                'source': SMS_SPAM_URL,
                'purpose': 'Public ham/spam language for content-pattern recognition',
            },
            {
                'name': 'Local SQLite Email Feedback',
                'source': ', '.join(str(path) for path in db_paths if path.exists()) if (db_paths := LOCAL_DB_PATHS) else 'N/A',
                'purpose': 'Use repository-local analyst feedback for supervised retraining',
            },
            {
                'name': 'OpenML PhishingWebsites',
                'source': 'https://www.openml.org/d/4534',
                'purpose': 'Public phishing URL feature benchmark for URL-analysis training',
            },
            {
                'name': 'Phishing.Database ACTIVE URLs/Domains',
                'source': url_intel.get('source', PHISHING_DATABASE_REPO),
                'purpose': 'Known phishing URL/domain threat intelligence for URL analysis inside email bodies',
            },
        ],
        'notes': [
            'Content model is a TF-IDF text classifier trained on all local and public labeled corpora available to the project.',
            'URL model is a random forest trained on phishing-websites benchmark features plus URL features extracted from local labeled bodies.',
            'Known phishing URL intelligence is matched against URLs extracted from email bodies for direct IOC coverage.',
        ],
        'phishing_database_version': url_intel.get('repo_version'),
        'phishing_database_counts': {
            'active_urls': int(len(url_intel.get('phishing_urls', set()))),
            'active_domains': int(len(url_intel.get('phishing_domains', set()))),
        },
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return ARTIFACT_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description='Train the Phase 2 phishing detection models.')
    parser.add_argument('--skip-download', action='store_true', help='Skip public dataset downloads and reuse only local data where possible.')
    args = parser.parse_args()

    print('Loading content datasets...')
    nigerian_content, nigerian_urls = load_nigerian_fraud_dataset()
    content_frames = [nigerian_content]
    url_frames = [nigerian_urls]

    if not args.skip_download:
        sms_content, sms_urls = load_sms_spam_dataset()
        content_frames.append(sms_content)
        url_frames.append(sms_urls)

    sqlite_content, sqlite_urls = load_sqlite_email_feedback(LOCAL_DB_PATHS)
    if not sqlite_content.empty:
        content_frames.append(sqlite_content)
    if not sqlite_urls.empty:
        url_frames.append(sqlite_urls)

    content_frame = pd.concat(content_frames, ignore_index=True).dropna()
    content_frame['text'] = content_frame['text'].astype(str).str.strip()
    content_frame = content_frame[content_frame['text'] != '']

    local_url_records = pd.concat(url_frames, ignore_index=True) if url_frames else pd.DataFrame(columns=['url', 'label', 'source'])
    local_url_records = local_url_records.drop_duplicates(subset=['url', 'label']) if not local_url_records.empty else local_url_records

    print('Training content model...')
    content_model, content_metrics = train_content_model(content_frame)

    print('Loading URL dataset...')
    base_url_frame = load_url_dataset()
    local_url_feature_frame = build_url_feature_dataset(local_url_records)
    url_frame = pd.concat([base_url_frame, local_url_feature_frame], ignore_index=True)

    print('Training URL model...')
    url_model, url_feature_columns, url_metrics = train_url_model(url_frame)

    print('Loading URL threat intelligence...')
    url_intel = load_phishing_database_intel(args.skip_download)

    if not local_url_records.empty:
        phishing_local_urls = set(
            local_url_records[local_url_records['label'] == 1]['url'].astype(str).map(normalize_url_for_lookup).dropna()
        )
        phishing_local_domains = set(
            local_url_records[local_url_records['label'] == 1]['url'].astype(str).map(extract_domain_for_lookup).dropna()
        )
        url_intel['phishing_urls'].update(url for url in phishing_local_urls if url)
        url_intel['phishing_domains'].update(domain for domain in phishing_local_domains if domain)

    training_stats = {
        'content_samples_total': int(len(content_frame)),
        'content_label_distribution': {
            'phishing': int((content_frame['label'] == 1).sum()),
            'safe': int((content_frame['label'] == 0).sum()),
        },
        'local_url_records': int(len(local_url_records)),
        'local_url_phishing': int((local_url_records['label'] == 1).sum()) if not local_url_records.empty else 0,
        'local_url_safe': int((local_url_records['label'] == 0).sum()) if not local_url_records.empty else 0,
        'url_model_samples_total': int(len(url_frame)),
    }

    artifact_dir = save_artifacts(
        content_model,
        url_model,
        url_feature_columns,
        content_metrics,
        url_metrics,
        url_intel,
        training_stats,
    )
    print(f'Artifacts written to: {artifact_dir}')
    print('Content metrics:', content_metrics)
    print('URL metrics:', url_metrics)
    print('Training stats:', training_stats)
    print('URL intel counts:', {
        'phishing_urls': len(url_intel['phishing_urls']),
        'phishing_domains': len(url_intel['phishing_domains']),
    })


if __name__ == '__main__':
    main()
