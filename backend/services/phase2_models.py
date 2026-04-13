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


def extract_url_feature_row(url: str, body: str = "") -> dict:
    """
    Extract canonical URL features used by the runtime URL model.

    This version is defensive against malformed URLs that can appear in
    real phishing corpora, such as invalid ports or broken netloc syntax.
    """
    import math
    import re
    from urllib.parse import urlparse

    def safe_int_bool(value: bool) -> int:
        return 1 if value else -1

    def safe_len(value: str) -> int:
        return len(value or "")

    def safe_port(parsed_url) -> int | None:
        try:
            return parsed_url.port
        except ValueError:
            return None

    def safe_hostname(parsed_url) -> str:
        try:
            return (parsed_url.hostname or "").lower()
        except Exception:
            return ""

    def safe_path(parsed_url) -> str:
        try:
            return parsed_url.path or ""
        except Exception:
            return ""

    def safe_query(parsed_url) -> str:
        try:
            return parsed_url.query or ""
        except Exception:
            return ""

    def normalize_url(raw_url: str) -> str:
        raw_url = str(raw_url or "").strip()

        # Remove surrounding punctuation often attached in email bodies
        raw_url = raw_url.strip("[](){}<>'\".,;")

        if not raw_url:
            return ""

        # Add scheme if missing
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", raw_url):
            raw_url = "http://" + raw_url

        return raw_url

    normalized_url = normalize_url(url)
    parsed_url = urlparse(normalized_url)

    hostname = safe_hostname(parsed_url)
    path = safe_path(parsed_url)
    query = safe_query(parsed_url)
    port = safe_port(parsed_url)

    full_url = normalized_url
    domain = hostname
    subdomain = ""

    if hostname:
        parts = hostname.split(".")
        if len(parts) > 2:
            subdomain = ".".join(parts[:-2])

    url_length = safe_len(full_url)
    domain_length = safe_len(domain)
    path_length = safe_len(path)
    query_length = safe_len(query)

    digit_count = sum(ch.isdigit() for ch in full_url)
    letter_count = sum(ch.isalpha() for ch in full_url)
    special_count = sum(not ch.isalnum() for ch in full_url)

    dot_count = full_url.count(".")
    hyphen_count = full_url.count("-")
    underscore_count = full_url.count("_")
    slash_count = full_url.count("/")
    question_count = full_url.count("?")
    equal_count = full_url.count("=")
    at_count = full_url.count("@")
    ampersand_count = full_url.count("&")
    percent_count = full_url.count("%")

    https_flag = safe_int_bool(parsed_url.scheme.lower() == "https")
    ip_flag = safe_int_bool(bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", domain)))
    shortening_flag = safe_int_bool(
        any(shortener in domain for shortener in [
            "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "ow.ly", "buff.ly", "rb.gy"
        ])
    )
    at_symbol_flag = safe_int_bool("@" in full_url)
    double_slash_flag = safe_int_bool(full_url.rfind("//") > 7)
    hyphen_domain_flag = safe_int_bool("-" in domain)

    # FIX: do not crash on malformed port
    port_flag = -1 if (port is not None and port not in {80, 443}) else 1

    suspicious_tld_flag = safe_int_bool(
        any(domain.endswith(tld) for tld in [".tk", ".ml", ".ga", ".cf", ".gq", ".work", ".zip", ".country"])
    )

    punycode_flag = safe_int_bool("xn--" in domain)
    long_url_flag = safe_int_bool(url_length > 75)
    long_domain_flag = safe_int_bool(domain_length > 25)
    many_subdomains_flag = safe_int_bool(subdomain.count(".") >= 2 if subdomain else False)

    phishing_keywords = [
        "login", "verify", "secure", "account", "update", "signin", "banking",
        "confirm", "password", "invoice", "payment", "wallet", "alert", "suspended"
    ]
    keyword_flag = safe_int_bool(any(keyword in full_url.lower() for keyword in phishing_keywords))

    body_lower = (body or "").lower()
    url_lower = full_url.lower()

    body_domain_mismatch_flag = 1
    if body_lower and domain:
        visible_domains = re.findall(r"https?://([a-zA-Z0-9.-]+)", body_lower)
        if visible_domains:
            mismatch = any(domain not in vis.lower() for vis in visible_domains[:5])
            body_domain_mismatch_flag = -1 if mismatch else 1

    entropy = 0.0
    if full_url:
        probs = [full_url.count(c) / len(full_url) for c in set(full_url)]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)

    return {
        "url_length": url_length,
        "domain_length": domain_length,
        "path_length": path_length,
        "query_length": query_length,
        "digit_count": digit_count,
        "letter_count": letter_count,
        "special_count": special_count,
        "dot_count": dot_count,
        "hyphen_count": hyphen_count,
        "underscore_count": underscore_count,
        "slash_count": slash_count,
        "question_count": question_count,
        "equal_count": equal_count,
        "at_count": at_count,
        "ampersand_count": ampersand_count,
        "percent_count": percent_count,
        "https_flag": https_flag,
        "ip_flag": ip_flag,
        "shortening_flag": shortening_flag,
        "at_symbol_flag": at_symbol_flag,
        "double_slash_flag": double_slash_flag,
        "hyphen_domain_flag": hyphen_domain_flag,
        "port_flag": port_flag,
        "suspicious_tld_flag": suspicious_tld_flag,
        "punycode_flag": punycode_flag,
        "long_url_flag": long_url_flag,
        "long_domain_flag": long_domain_flag,
        "many_subdomains_flag": many_subdomains_flag,
        "keyword_flag": keyword_flag,
        "body_domain_mismatch_flag": body_domain_mismatch_flag,
        "entropy": entropy,
    }

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
        
    def predict_url_score(self, body: str, urls: list[str]) -> float:
        if not self.is_ready or self.url_model is None:
            return 0.0

        if not urls:
            return 0.0

        scores = []

        for url in urls:
            try:
                feature_row = extract_url_feature_row(url, body=body)
                X = pd.DataFrame([feature_row])[self.url_feature_columns]
                prob = float(self.url_model.predict_proba(X)[0, 1])
                scores.append(prob)
            except Exception:
                # Skip malformed URLs instead of crashing the whole analysis
                continue

        if not scores:
            return 0.0

        return max(scores)
    
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
