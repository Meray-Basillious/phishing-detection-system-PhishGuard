"""
Model Comparison Script for URL and Content Classification
Trains multiple ML models and compares their performance metrics
"""

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
import time

import joblib
import pandas as pd
import numpy as np
from sklearn.datasets import fetch_openml
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    ExtraTreesClassifier,
    VotingClassifier,
    AdaBoostClassifier,
)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.naive_bayes import GaussianNB, MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, confusion_matrix, classification_report
)
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

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
COMPARISON_RESULTS_DIR = ARTIFACT_DIR.parent / 'model_comparison'


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


# ===============================
# URL MODEL COMPARISONS
# ===============================

def train_and_evaluate_url_model(model, model_name: str, train_X, test_X, train_y, test_y, training_time_limit=None):
    """Train and evaluate a URL model, returning metrics and timing"""
    print(f"\n{'='*60}")
    print(f"Training: {model_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    try:
        model.fit(train_X, train_y)
        training_time = time.time() - start_time
        
        if training_time_limit and training_time > training_time_limit:
            print(f"⚠️  Training exceeded time limit ({training_time:.2f}s > {training_time_limit}s)")
        
        predictions = model.predict(test_X)
        probabilities = model.predict_proba(test_X)[:, 1] if hasattr(model, 'predict_proba') else predictions
        
        metrics = {
            'model_name': model_name,
            'accuracy': round(accuracy_score(test_y, predictions), 4),
            'precision': round(precision_score(test_y, predictions, zero_division=0), 4),
            'recall': round(recall_score(test_y, predictions, zero_division=0), 4),
            'f1': round(f1_score(test_y, predictions, zero_division=0), 4),
            'roc_auc': round(roc_auc_score(test_y, probabilities), 4),
            'training_time_seconds': round(training_time, 4),
            'train_samples': len(train_X),
            'test_samples': len(test_X),
            'status': 'success'
        }
        
        # 5-fold cross validation
        cv_scores = cross_val_score(model, train_X, train_y, cv=5, scoring='f1')
        metrics['cv_f1_mean'] = round(cv_scores.mean(), 4)
        metrics['cv_f1_std'] = round(cv_scores.std(), 4)
        
        print(f"✅ {model_name} trained successfully")
        print(f"   Accuracy: {metrics['accuracy']:.4f} | F1: {metrics['f1']:.4f} | ROC-AUC: {metrics['roc_auc']:.4f}")
        print(f"   Training Time: {training_time:.2f}s")
        print(f"   CV F1 Score: {metrics['cv_f1_mean']:.4f} ± {metrics['cv_f1_std']:.4f}")
        
        return model, metrics
    
    except Exception as e:
        training_time = time.time() - start_time
        print(f"❌ Error training {model_name}: {str(e)}")
        return None, {
            'model_name': model_name,
            'training_time_seconds': round(training_time, 4),
            'status': f'error: {str(e)}'
        }


def train_url_models_comparison(url_frame: pd.DataFrame):
    """Train and compare multiple URL models"""
    feature_columns = [column for column in url_frame.columns if column != 'label']
    train_frame, test_frame = train_test_split(
        url_frame,
        test_size=0.2,
        random_state=42,
        stratify=url_frame['label'],
    )
    
    train_X = train_frame[feature_columns]
    test_X = test_frame[feature_columns]
    train_y = train_frame['label']
    test_y = test_frame['label']
    
    models = {
        'Random Forest (Original - 300 trees)': RandomForestClassifier(
            n_estimators=300,
            random_state=42,
            class_weight='balanced_subsample',
            min_samples_leaf=2,
            n_jobs=-1,
        ),
        'Gradient Boosting': GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=7,
            random_state=42,
        ),
        'Extra Trees Classifier': ExtraTreesClassifier(
            n_estimators=300,
            random_state=42,
            class_weight='balanced_subsample',
            n_jobs=-1,
        ),
        'AdaBoost': AdaBoostClassifier(
            n_estimators=200,
            learning_rate=0.8,
            random_state=42,
        ),
        'XGBoost-style Gradient Boosting (More aggressive)': GradientBoostingClassifier(
            n_estimators=300,
            learning_rate=0.15,
            max_depth=5,
            subsample=0.8,
            random_state=42,
        ),
        'SVM (RBF Kernel)': SVC(
            kernel='rbf',
            C=1.0,
            gamma='scale',
            class_weight='balanced',
            probability=True,
            random_state=42,
        ),
        'KNeighbors (k=5)': KNeighborsClassifier(
            n_neighbors=5,
            n_jobs=-1,
        ),
        'KNeighbors (k=15)': KNeighborsClassifier(
            n_neighbors=15,
            n_jobs=-1,
        ),
    }
    
    trained_models = {}
    all_metrics = []
    
    for model_name, model in models.items():
        trained_model, metrics = train_and_evaluate_url_model(
            model, model_name, train_X, test_X, train_y, test_y
        )
        if trained_model:
            trained_models[model_name] = trained_model
        all_metrics.append(metrics)
    
    return trained_models, all_metrics, feature_columns


# ===============================
# CONTENT MODEL COMPARISONS
# ===============================

def train_and_evaluate_content_model(model, model_name: str, train_X, test_X, train_y, test_y):
    """Train and evaluate a content model, returning metrics and timing"""
    print(f"\n{'='*60}")
    print(f"Training: {model_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    try:
        model.fit(train_X, train_y)
        training_time = time.time() - start_time
        
        predictions = model.predict(test_X)
        probabilities = model.predict_proba(test_X)[:, 1]
        
        metrics = {
            'model_name': model_name,
            'accuracy': round(accuracy_score(test_y, predictions), 4),
            'precision': round(precision_score(test_y, predictions, zero_division=0), 4),
            'recall': round(recall_score(test_y, predictions, zero_division=0), 4),
            'f1': round(f1_score(test_y, predictions, zero_division=0), 4),
            'roc_auc': round(roc_auc_score(test_y, probabilities), 4),
            'training_time_seconds': round(training_time, 4),
            'train_samples': len(train_X),
            'test_samples': len(test_X),
            'status': 'success'
        }
        
        print(f"✅ {model_name} trained successfully")
        print(f"   Accuracy: {metrics['accuracy']:.4f} | F1: {metrics['f1']:.4f} | ROC-AUC: {metrics['roc_auc']:.4f}")
        print(f"   Training Time: {training_time:.2f}s")
        
        return model, metrics
    
    except Exception as e:
        training_time = time.time() - start_time
        print(f"❌ Error training {model_name}: {str(e)}")
        return None, {
            'model_name': model_name,
            'training_time_seconds': round(training_time, 4),
            'status': f'error: {str(e)}'
        }


def train_content_models_comparison(content_frame: pd.DataFrame):
    """Train and compare multiple content models"""
    train_frame, test_frame = train_test_split(
        content_frame,
        test_size=0.2,
        random_state=42,
        stratify=content_frame['label'],
    )

    # Define feature extraction pipeline (shared)
    feature_pipeline = Pipeline([
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
    ])
    
    # Fit feature pipeline on training data
    feature_pipeline.fit(train_frame['text'])
    train_X = feature_pipeline.transform(train_frame['text'])
    test_X = feature_pipeline.transform(test_frame['text'])
    train_y = train_frame['label']
    test_y = test_frame['label']

    models = {
        'Logistic Regression (Original - saga)': LogisticRegression(
            max_iter=3000,
            class_weight='balanced',
            solver='saga',
            random_state=42,
        ),
        'Logistic Regression (lbfgs)': LogisticRegression(
            max_iter=3000,
            class_weight='balanced',
            solver='lbfgs',
            random_state=42,
        ),
        'Logistic Regression (liblinear)': LogisticRegression(
            max_iter=3000,
            class_weight='balanced',
            solver='liblinear',
            random_state=42,
            C=0.1,
        ),
        'SVM (Linear)': SVC(
            kernel='linear',
            C=1.0,
            class_weight='balanced',
            probability=True,
            random_state=42,
            max_iter=10000,
        ),
        'Naive Bayes (Multinomial)': MultinomialNB(
            alpha=1.0,
        ),
        'Neural Network (MLP)': MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            learning_rate='adaptive',
            max_iter=1000,
            random_state=42,
        ),
    }
    
    trained_models = {}
    all_metrics = []
    
    for model_name, model in models.items():
        trained_model, metrics = train_and_evaluate_content_model(
            model, model_name, train_X, test_X, train_y, test_y
        )
        if trained_model:
            trained_models[model_name] = trained_model
        all_metrics.append(metrics)
    
    return trained_models, all_metrics


def create_comparison_report(url_metrics, content_metrics):
    """Create a detailed comparison report"""
    report = {
        'comparison_timestamp': datetime.now(timezone.utc).isoformat(),
        'url_models': {
            'metrics': url_metrics,
            'insights': generate_insights(url_metrics, 'URL Models'),
        },
        'content_models': {
            'metrics': content_metrics,
            'insights': generate_insights(content_metrics, 'Content Models'),
        }
    }
    return report


def generate_insights(metrics_list, model_type: str):
    """Generate insights from model comparison"""
    successful_models = [m for m in metrics_list if m.get('status') == 'success']
    
    if not successful_models:
        return {'error': 'No successful models to compare'}
    
    insights = {
        'best_model': {},
        'worst_model': {},
        'average_metrics': {},
        'model_recommendations': []
    }
    
    # Best and worst by F1 score
    best = max(successful_models, key=lambda x: x.get('f1', 0))
    worst = min(successful_models, key=lambda x: x.get('f1', 0))
    
    insights['best_model'] = {
        'name': best['model_name'],
        'f1': best['f1'],
        'accuracy': best['accuracy'],
        'roc_auc': best['roc_auc'],
        'training_time': best['training_time_seconds']
    }
    
    insights['worst_model'] = {
        'name': worst['model_name'],
        'f1': worst['f1'],
        'accuracy': worst['accuracy'],
        'roc_auc': worst['roc_auc'],
    }
    
    # Average metrics
    avg_accuracy = np.mean([m['accuracy'] for m in successful_models])
    avg_f1 = np.mean([m['f1'] for m in successful_models])
    avg_roc_auc = np.mean([m['roc_auc'] for m in successful_models])
    avg_time = np.mean([m['training_time_seconds'] for m in successful_models])
    
    insights['average_metrics'] = {
        'accuracy': round(avg_accuracy, 4),
        'f1': round(avg_f1, 4),
        'roc_auc': round(avg_roc_auc, 4),
        'training_time_seconds': round(avg_time, 4),
    }
    
    # Recommendations
    insights['model_recommendations'] = [
        f"🏆 Best {model_type} by F1 Score: {best['model_name']} (F1: {best['f1']:.4f})",
        f"⚡ Fastest {model_type}: {min(successful_models, key=lambda x: x['training_time_seconds'])['model_name']}",
        f"🎯 Most Balanced {model_type} (Accuracy × F1): {max(successful_models, key=lambda x: x['accuracy'] * x['f1'])['model_name']}",
    ]
    
    return insights


def main() -> None:
    parser = argparse.ArgumentParser(description='Train and compare Phase 2 phishing detection models.')
    parser.add_argument('--skip-download', action='store_true', help='Skip public dataset downloads.')
    parser.add_argument('--url-only', action='store_true', help='Train only URL models.')
    parser.add_argument('--content-only', action='store_true', help='Train only content models.')
    args = parser.parse_args()

    print("\n" + "="*80)
    print("PHISHING DETECTION MODEL COMPARISON")
    print("="*80)
    
    print('\nLoading datasets...')
    nigerian_content, nigerian_urls = load_nigerian_fraud_dataset()
    content_frames = [nigerian_content]
    url_frames = [nigerian_urls]

    if not args.skip_download:
        print('Downloading SMS Spam dataset...')
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

    url_frame = pd.concat(url_frames, ignore_index=True) if url_frames else pd.DataFrame(columns=['url', 'label', 'source'])
    url_frame = url_frame.drop_duplicates(subset=['url', 'label']) if not url_frame.empty else url_frame

    print(f"Content samples: {len(content_frame)}")
    print(f"URL samples: {len(url_frame)}")

    url_metrics = []
    content_metrics = []

    # Train URL models
    if not args.content_only:
        print("\n" + "="*80)
        print("TRAINING & COMPARING URL MODELS")
        print("="*80)
        print('\nLoading URL dataset from OpenML...')
        base_url_frame = load_url_dataset()
        local_url_feature_frame = build_url_feature_dataset(url_frame)
        full_url_frame = pd.concat([base_url_frame, local_url_feature_frame], ignore_index=True)
        print(f"Total URL samples for training: {len(full_url_frame)}")
        
        trained_url_models, url_metrics, feature_columns = train_url_models_comparison(full_url_frame)

    # Train content models
    if not args.url_only:
        print("\n" + "="*80)
        print("TRAINING & COMPARING CONTENT MODELS")
        print("="*80)
        trained_content_models, content_metrics = train_content_models_comparison(content_frame)

    # Generate comparison report
    print("\n" + "="*80)
    print("GENERATING COMPARISON REPORT")
    print("="*80)
    
    report = create_comparison_report(url_metrics, content_metrics)
    
    # Save report
    COMPARISON_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = COMPARISON_RESULTS_DIR / 'model_comparison_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"\n✅ Report saved to: {report_path}")

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY - URL MODELS")
    print("="*80)
    if url_metrics:
        df_url = pd.DataFrame(url_metrics)
        print(df_url[['model_name', 'accuracy', 'f1', 'roc_auc', 'training_time_seconds']].to_string(index=False))
        print(f"\n{report['url_models']['insights']['model_recommendations'][0]}")

    print("\n" + "="*80)
    print("SUMMARY - CONTENT MODELS")
    print("="*80)
    if content_metrics:
        df_content = pd.DataFrame(content_metrics)
        print(df_content[['model_name', 'accuracy', 'f1', 'roc_auc', 'training_time_seconds']].to_string(index=False))
        if content_metrics[0].get('status') == 'success':
            print(f"\n{report['content_models']['insights']['model_recommendations'][0]}")

    print("\n" + "="*80)
    print("MODEL COMPARISON COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
