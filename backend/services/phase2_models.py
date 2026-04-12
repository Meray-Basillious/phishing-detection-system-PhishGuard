from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse
import json
import re

import joblib
import pandas as pd


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / 'artifacts' / 'phase2'
CONTENT_MODEL_PATH = ARTIFACT_DIR / 'content_model.joblib'
URL_MODEL_PATH = ARTIFACT_DIR / 'url_model.joblib'
URL_INTEL_PATH = ARTIFACT_DIR / 'url_intel.joblib'
METADATA_PATH = ARTIFACT_DIR / 'metadata.json'

URL_FEATURE_NAMES = [
    'having_IP_Address',
    'URL_Length',
    'Shortining_Service',
    'having_At_Symbol',
    'double_slash_redirecting',
    'Prefix_Suffix',
    'having_Sub_Domain',
    'SSLfinal_State',
    'Domain_registeration_length',
    'Favicon',
    'port',
    'HTTPS_token',
    'Request_URL',
    'URL_of_Anchor',
    'Links_in_tags',
    'SFH',
    'Submitting_to_email',
    'Abnormal_URL',
    'Redirect',
    'on_mouseover',
    'RightClick',
    'popUpWidnow',
    'Iframe',
    'age_of_domain',
    'DNSRecord',
    'web_traffic',
    'Page_Rank',
    'Google_Index',
    'Links_pointing_to_page',
    'Statistical_report',
]

SHORTENING_DOMAINS = {
    'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'buff.ly', 'ow.ly',
    'is.gd', 'cutt.ly', 'rebrand.ly', 'shorturl.at', 'rb.gy', 'bitly.com',
}

SUSPICIOUS_QUERY_KEYS = {'redirect', 'url', 'next', 'target', 'continue', 'dest', 'destination'}


def build_content_text(sender: str, subject: str, body: str, urls: Optional[List[str]] = None) -> str:
    """Combine email fields into one text representation for the content model."""
    url_text = ' '.join(urls or [])
    parts = [sender or '', subject or '', body or '', url_text]
    return ' '.join(part.strip() for part in parts if part).strip()


def extract_urls_from_text(body: str) -> List[str]:
    """Extract URLs from free-form email text."""
    if not body:
        return []

    pattern = r"(https?://[^\s<>'\"]+|www\.[^\s<>'\"]+)"
    return re.findall(pattern, body)


def _normalize_url(url: str) -> str:
    normalized_url = (url or '').strip()
    if normalized_url.startswith('www.'):
        normalized_url = f'http://{normalized_url}'
    return normalized_url


def normalize_url_for_lookup(url: str) -> str:
    """Normalize URL text for exact-match threat-intel lookup."""
    normalized_url = _normalize_url(url).lower().strip()
    if not normalized_url:
        return ''

    try:
        parsed_url = urlparse(normalized_url)
    except ValueError:
        return ''
    scheme = parsed_url.scheme or 'http'
    hostname = (parsed_url.hostname or '').lower()
    if not hostname:
        return ''

    path = parsed_url.path or '/'
    if path != '/':
        path = path.rstrip('/') or '/'

    query = parsed_url.query.strip()
    normalized_value = f'{scheme}://{hostname}{path}'
    if query:
        normalized_value += f'?{query}'

    return normalized_value


def extract_domain_for_lookup(url_or_domain: str) -> str:
    """Extract a normalized host/domain for domain-level intel matching."""
    raw_value = (url_or_domain or '').strip().lower()
    if not raw_value:
        return ''

    try:
        parsed_url = urlparse(_normalize_url(raw_value))
    except ValueError:
        return ''
    hostname = (parsed_url.hostname or '').strip().lower()

    if not hostname:
        hostname = raw_value.split('/')[0].split(':')[0].strip().lower()

    return hostname.lstrip('.').rstrip('.')


def _parse_url_parts(url: str):
    parsed_url = urlparse(_normalize_url(url))
    host = parsed_url.hostname or ''
    path = parsed_url.path or ''
    query = parsed_url.query or ''
    return parsed_url, host.lower(), path.lower(), query.lower()


def _safe_ip_address(hostname: str) -> bool:
    try:
        ip_address(hostname)
        return True
    except Exception:
        return False


def _registered_domain(hostname: str) -> str:
    if not hostname:
        return ''

    parts = hostname.split('.')
    if len(parts) <= 2:
        return hostname
    return '.'.join(parts[-2:])


def _has_suspicious_query(query: str) -> bool:
    if not query:
        return False
    query_keys = {key.lower() for key in parse_qs(query, keep_blank_values=True).keys()}
    return bool(query_keys & SUSPICIOUS_QUERY_KEYS)


def _contains_brand_like_tokens(value: str) -> bool:
    value = value.lower()
    brand_tokens = ['paypal', 'amazon', 'apple', 'microsoft', 'google', 'office365', 'outlook', 'docusign']
    return any(token in value for token in brand_tokens)


def _ternary(length: int, low_threshold: int, high_threshold: int) -> int:
    if length < low_threshold:
        return 1
    if length > high_threshold:
        return -1
    return 0


def extract_url_feature_row(url: str, body: str = '') -> Dict[str, int]:
    """Extract phishing-websites-style features from a single URL.

    The original benchmark dataset stores these as ternary values, so the
    extractor emits -1/0/1 where possible and falls back to neutral values when
    a browser-only feature cannot be observed from a raw email URL.
    """
    normalized_url = _normalize_url(url)
    parsed_url, host, path, query = _parse_url_parts(normalized_url)
    full_url = normalized_url.lower()
    registered_domain = _registered_domain(host)
    host_parts = [part for part in host.split('.') if part]
    subdomain_count = max(len(host_parts) - 2, 0)

    shortener_flag = -1 if registered_domain in SHORTENING_DOMAINS else 1
    ip_flag = -1 if host and _safe_ip_address(host) else 1
    at_flag = -1 if '@' in full_url else 1
    double_slash_flag = -1 if full_url.count('//') > 1 else 1
    prefix_suffix_flag = -1 if '-' in registered_domain else 1
    subdomain_flag = 1 if subdomain_count <= 1 else 0 if subdomain_count == 2 else -1
    ssl_flag = 1 if parsed_url.scheme == 'https' else -1
    registration_length_flag = _ternary(len(registered_domain), 12, 20)
    port_flag = -1 if parsed_url.port and parsed_url.port not in {80, 443} else 1
    https_token_flag = -1 if 'https' in registered_domain and parsed_url.scheme != 'https' else 1
    redirect_flag = -1 if _has_suspicious_query(query) or 'redirect' in path else 1
    abnormal_url_flag = -1 if ip_flag == -1 or prefix_suffix_flag == -1 else 1
    submitting_to_email_flag = -1 if 'mailto:' in full_url or '@' in query else 1

    url_length_flag = _ternary(len(full_url), 54, 75)
    favicon_flag = -1 if _contains_brand_like_tokens(host) and prefix_suffix_flag == -1 else 1
    request_url_flag = -1 if path.count('/') > 4 or query else 1
    url_of_anchor_flag = -1 if '#' in full_url else 1
    links_in_tags_flag = 0
    sfh_flag = -1 if any(token in path for token in ['login', 'signin', 'verify', 'update']) else 1
    mouseover_flag = 0
    right_click_flag = 0
    popup_flag = 0
    iframe_flag = 0
    age_of_domain_flag = -1 if len(registered_domain) > 18 else 1
    dns_record_flag = 0
    web_traffic_flag = -1 if 'utm_' in query or 'campaign' in query else 0
    page_rank_flag = 0
    google_index_flag = 1 if 'google' in registered_domain else 0
    links_pointing_flag = -1 if body and normalized_url in body else 0
    statistical_report_flag = -1 if _contains_brand_like_tokens(path) or _contains_brand_like_tokens(query) else 0

    feature_values = {
        'having_IP_Address': ip_flag,
        'URL_Length': url_length_flag,
        'Shortining_Service': shortener_flag,
        'having_At_Symbol': at_flag,
        'double_slash_redirecting': double_slash_flag,
        'Prefix_Suffix': prefix_suffix_flag,
        'having_Sub_Domain': subdomain_flag,
        'SSLfinal_State': ssl_flag,
        'Domain_registeration_length': registration_length_flag,
        'Favicon': favicon_flag,
        'port': port_flag,
        'HTTPS_token': https_token_flag,
        'Request_URL': request_url_flag,
        'URL_of_Anchor': url_of_anchor_flag,
        'Links_in_tags': links_in_tags_flag,
        'SFH': sfh_flag,
        'Submitting_to_email': submitting_to_email_flag,
        'Abnormal_URL': abnormal_url_flag,
        'Redirect': redirect_flag,
        'on_mouseover': mouseover_flag,
        'RightClick': right_click_flag,
        'popUpWidnow': popup_flag,
        'Iframe': iframe_flag,
        'age_of_domain': age_of_domain_flag,
        'DNSRecord': dns_record_flag,
        'web_traffic': web_traffic_flag,
        'Page_Rank': page_rank_flag,
        'Google_Index': google_index_flag,
        'Links_pointing_to_page': links_pointing_flag,
        'Statistical_report': statistical_report_flag,
    }

    return feature_values


@dataclass
class Phase2ModelBundle:
    """Load and score the Phase 2 training artifacts."""

    artifact_dir: Path = ARTIFACT_DIR

    def __post_init__(self) -> None:
        self.content_model = self._load_joblib(self.artifact_dir / 'content_model.joblib')
        self.url_model = self._load_joblib(self.artifact_dir / 'url_model.joblib')
        self.url_intel = self._load_joblib(self.artifact_dir / 'url_intel.joblib')
        self.metadata = self._load_json(self.artifact_dir / 'metadata.json')

    @property
    def is_ready(self) -> bool:
        return self.content_model is not None or self.url_model is not None or self.url_intel is not None

    @property
    def has_url_intel(self) -> bool:
        return self.url_intel is not None

    def _load_joblib(self, path: Path):
        if not path.exists():
            return None

        try:
            return joblib.load(path)
        except Exception:
            return None

    def _load_json(self, path: Path) -> Dict:
        if not path.exists():
            return {}

        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def predict_content_score(self, sender: str, subject: str, body: str, urls: Optional[List[str]] = None) -> float:
        if self.content_model is None:
            return 0.0

        text = build_content_text(sender, subject, body, urls)
        if not text:
            return 0.0

        try:
            probability = self.content_model.predict_proba([text])[0][1]
            return float(max(0.0, min(1.0, probability)))
        except Exception:
            return 0.0

    def predict_url_score(self, body: str, urls: Optional[List[str]] = None) -> float:
        url_list = urls if urls is not None else extract_urls_from_text(body)
        if not url_list:
            return 0.0

        intel_summary = self.inspect_url_intel(url_list)
        intel_score = float(intel_summary.get('score', 0.0))

        if self.url_model is None:
            return intel_score

        probability_scores = []
        for url in url_list:
            feature_row = extract_url_feature_row(url, body=body)
            ordered_row = pd.DataFrame([
                {feature_name: feature_row[feature_name] for feature_name in URL_FEATURE_NAMES}
            ], columns=URL_FEATURE_NAMES)
            try:
                probability = self.url_model.predict_proba(ordered_row)[0][1]
                probability_scores.append(float(probability))
            except Exception:
                continue

        if not probability_scores:
            return intel_score

        model_score = float(max(probability_scores))
        return max(model_score, intel_score)

    def inspect_url_intel(self, urls: List[str]) -> Dict[str, object]:
        """Return URL intel matches and a score for extracted URLs."""
        if not self.url_intel or not urls:
            return {
                'score': 0.0,
                'exact_match_count': 0,
                'domain_match_count': 0,
                'matched_urls': [],
                'matched_domains': [],
            }

        phishing_urls = self.url_intel.get('phishing_urls', set())
        phishing_domains = self.url_intel.get('phishing_domains', set())

        matched_urls = []
        matched_domains = []
        max_score = 0.0

        for raw_url in urls:
            normalized_url = normalize_url_for_lookup(raw_url)
            domain = extract_domain_for_lookup(raw_url)

            if normalized_url and normalized_url in phishing_urls:
                matched_urls.append(normalized_url)
                max_score = max(max_score, 1.0)
                continue

            if domain:
                domain_tokens = domain.split('.')
                domain_variants = ['.'.join(domain_tokens[index:]) for index in range(len(domain_tokens) - 1)]
                if any(variant in phishing_domains for variant in domain_variants):
                    matched_domains.append(domain)
                    max_score = max(max_score, 0.92)

        return {
            'score': max_score,
            'exact_match_count': len(set(matched_urls)),
            'domain_match_count': len(set(matched_domains)),
            'matched_urls': sorted(set(matched_urls))[:10],
            'matched_domains': sorted(set(matched_domains))[:10],
        }
