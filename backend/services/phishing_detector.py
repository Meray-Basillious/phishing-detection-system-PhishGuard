import re
import unicodedata
from email.utils import parseaddr
from typing import Dict, List

from models import Email
from services.phase2_models import Phase2ModelBundle


class PhishingDetector:
    """AI-powered phishing detection engine"""

    def __init__(self):
        self.phishing_keywords = [
            'verify', 'confirm', 'update', 'validate', 'urgent',
            'act now', 'click here', 'suspended', 'limited time',
            'reactivate', 'confirm identity', 'authenticate', 'sign in',
            'invoice', 'payment', 'wire transfer', 'beneficiary',
            'bank account', 'security notice', 'payroll', 'gift card'
        ]

        self.suspicion_phrases = [
            'click here immediately', 'verify your account',
            'confirm your identity', 'update your information',
            'account suspended', 'unusual activity', 'action required',
            'strictly confidential', 'keep this matter secret',
            'urgent response', 'next of kin', 'security company',
            'foreign partner', 'beneficiary of the fund', 'risk free transaction'
        ]

        self.suspicious_domains = [
            'gmail-security', 'paypal-verify', 'amazon-account',
            'apple-support', 'microsoft-account', 'bank-secure'
        ]

        self.generic_mail_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'live.com', 'mail.com', 'aol.com'
        }

        self.brand_keywords = [
            'paypal', 'amazon', 'apple', 'microsoft', 'google',
            'office365', 'outlook', 'docusign', 'dropbox'
        ]

        self.advance_fee_keywords = [
            'beneficiary', 'next of kin', 'foreign partner', 'security company',
            'consignment', 'diplomatic box', 'transfer the fund', 'million united states dollars',
            'inheritance', 'strictly confidential', 'confidential business proposal',
            'urgent assistance', 'percentage for you', 'risk free transaction',
            'bank account', 'compensate you', 'trusted foreign', 'await your urgent response'
        ]

        self.bec_keywords = [
            'wire transfer', 'gift card', 'invoice', 'accounts payable',
            'payment', 'purchase order', 'payroll', 'remittance',
            'bank details', 'vendor update', 'approve this transfer'
        ]

        self.secrecy_keywords = [
            'confidential', 'secret', 'do not disclose', 'keep this matter',
            'private', 'without raising eyebrow', 'strictly to yourself'
        ]

        self.high_confidence_threats = {
            'Credential Harvesting Detected',
            'Advance Fee Fraud Pattern',
            'Business Email Compromise Pattern',
            'Sender Impersonation Detected',
            'Sender Authentication Mismatch',
            'Unicode Lookalike Domain Detected',
            'ML Content Pattern Match',
            'ML URL Pattern Match',
            'Known Phishing URL Match'
        }

        self.score_weights = {
            'sender_score': 0.18,
            'subject_score': 0.12,
            'body_score': 0.25,
            'url_score': 0.15,
            'urgency_score': 0.10,
            'impersonation_score': 0.10,
            'history_score': 0.05,
            'header_score': 0.05,
        }

        self.phase2_models = Phase2ModelBundle()

    def analyze_email(self, sender: str, recipient: str, subject: str, body: str, headers: Dict = None) -> Dict:
        """
        Main analysis function - analyzes email for phishing indicators.

        Args:
            sender: Email sender address or From header value.
            recipient: Email recipient address.
            subject: Email subject line.
            body: Email body content.
            headers: Optional email headers.

        Returns:
            Dictionary with analysis results including risk score, verdict, and threats.
        """
        headers = headers or {}
        parsed_sender = self._parse_sender(sender)

        scores = {
            'sender_score': self._analyze_sender(parsed_sender),
            'subject_score': self._analyze_subject(subject),
            'body_score': self._analyze_body(body),
            'url_score': self._check_urls(body),
            'urgency_score': self._check_urgency(subject, body),
            'impersonation_score': self._check_impersonation(parsed_sender, subject, body),
            'history_score': self._check_sender_history(parsed_sender['email'], recipient),
            'header_score': self._analyze_headers(parsed_sender, headers),
        }

        ml_scores = self._score_with_phase2_models(parsed_sender, subject, body)
        scores['ml_content_score'] = ml_scores['content_score']
        scores['ml_url_score'] = ml_scores['url_score']

        risk_scores = dict(scores)
        if ml_scores['content_score'] > 0:
            risk_scores['body_score'] = max(
                risk_scores['body_score'],
                (risk_scores['body_score'] * 0.55) + (ml_scores['content_score'] * 0.45)
            )

        if ml_scores['url_score'] > 0:
            risk_scores['url_score'] = max(
                risk_scores['url_score'],
                (risk_scores['url_score'] * 0.4) + (ml_scores['url_score'] * 0.6)
            )

        overall_risk = sum(
            risk_scores[component] * weight
            for component, weight in self.score_weights.items()
        )

        threats = self._identify_threats(parsed_sender, recipient, subject, body, headers)
        if ml_scores['content_score'] >= 0.85:
            threats.append('ML Content Pattern Match')
        if ml_scores['url_score'] >= 0.85:
            threats.append('ML URL Pattern Match')
        if ml_scores.get('intel_exact_match_count', 0) > 0 or ml_scores.get('intel_domain_match_count', 0) > 0:
            threats.append('Known Phishing URL Match')
        verdict = self._determine_verdict(overall_risk, threats)

        return {
            'overall_risk_score': round(overall_risk, 3),
            'verdict': verdict,
            'is_phishing': verdict == 'phishing',
            'confidence': self._calculate_confidence(overall_risk, threats),
            'component_scores': scores,
            'ml_scores': ml_scores,
            'threats': threats,
            'recommendations': self._generate_recommendations(verdict, overall_risk, threats),
            'normalized_sender': parsed_sender['email'] or parsed_sender['raw'],
            'raw_sender': parsed_sender['raw'],
            'phase2_models_enabled': self.phase2_models.is_ready,
            'phase2_data_sources': self.phase2_models.metadata.get('data_sources', []),
        }
    
    def _analyze_sender(self, parsed_sender: Dict[str, str]) -> float:
        """Analyze sender email for suspicious patterns"""
        score = 0.0
        sender_lower = parsed_sender['raw'].lower()
        sender_email = parsed_sender['email']
        sender_domain = parsed_sender['domain']
        sender_local = parsed_sender['local_part']

        if not self._is_valid_email(sender_email):
            score += 0.35

        if self._has_malformed_from_address(parsed_sender['raw'], sender_email):
            score += 0.2

        for domain in self.suspicious_domains:
            if domain in sender_lower or domain in sender_domain:
                score += 0.35
                break

        if re.search(r'\d{4,}', sender_local):
            score += 0.1

        if sender_domain in self.generic_mail_domains:
            if re.search(r'(admin|support|security|verify|update|finance|billing|payroll)', sender_local):
                score += 0.2

        if self._has_unicode_or_punycode_spoofing(sender_domain):
            score += 0.25

        if self._looks_like_brand_domain(sender_domain):
            score += 0.25

        if self._display_name_impersonates_brand(parsed_sender['display_name'], sender_domain):
            score += 0.2
        
        return min(score, 1.0)
    
    def _analyze_subject(self, subject: str) -> float:
        """Analyze email subject for phishing indicators"""
        score = 0.0
        subject_lower = subject.lower()
        
        # Check for phishing keywords
        for keyword in self.phishing_keywords:
            if keyword in subject_lower:
                score += 0.08
        
        # Check for urgency indicators
        urgency_words = ['urgent', '!!', 'asap', 'immediate', 'alert', 'critical']
        for word in urgency_words:
            if word in subject_lower:
                score += 0.12

        if any(word in subject_lower for word in ['account', 'password', 'security']):
            score += 0.1

        if any(keyword in subject_lower for keyword in self.bec_keywords):
            score += 0.18

        if any(keyword in subject_lower for keyword in self.advance_fee_keywords[:8]):
            score += 0.18
        
        return min(score, 1.0)
    
    def _analyze_body(self, body: str) -> float:
        """Analyze email body content for phishing indicators"""
        score = 0.0
        body_lower = body.lower()
        
        # Check suspicious phrases
        for phrase in self.suspicion_phrases:
            if phrase in body_lower:
                score += 0.15
        
        # Check for credential requests
        credential_keywords = ['password', 'pin', 'ssn', 'credit card', 'bank account']
        for keyword in credential_keywords:
            if keyword in body_lower:
                score += 0.12

        advance_fee_hits = sum(1 for keyword in self.advance_fee_keywords if keyword in body_lower)
        score += min(advance_fee_hits * 0.08, 0.4)

        bec_hits = sum(1 for keyword in self.bec_keywords if keyword in body_lower)
        score += min(bec_hits * 0.08, 0.3)

        secrecy_hits = sum(1 for keyword in self.secrecy_keywords if keyword in body_lower)
        score += min(secrecy_hits * 0.06, 0.18)

        if re.search(r'(?:us\$|usd|\$)\s?[\d,]+', body_lower) or re.search(r'\b\d+\s*(million|billion)\b', body_lower):
            score += 0.12

        if re.search(r'(bank account|beneficiary|foreign partner|security company|next of kin)', body_lower):
            score += 0.18
        
        if body_lower.count('!') > 3:
            score += 0.08

        if self._check_common_misspellings(body):
            score += 0.08
        
        return min(score, 1.0)
    
    def _check_urls(self, body: str) -> float:
        """Check for suspicious URLs in email body"""
        urls = self._extract_urls(body)
        score = 0.0
        suspicious_count = 0

        for url in urls:
            if self._is_suspicious_url(url):
                suspicious_count += 1

        if len(urls) > 0:
            score = (suspicious_count / len(urls)) * 0.9

        return min(score, 1.0)
    
    def _is_suspicious_url(self, url: str) -> bool:
        """Check if URL contains suspicious patterns"""
        suspicious_patterns = [
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP address instead of domain
            r'bit\.ly|tinyurl|short\.link',        # URL shorteners
            r'%[0-9a-fA-F]{2}',                    # Encoded characters
            r'@',
        ]

        if any(re.search(pattern, url) for pattern in suspicious_patterns):
            return True

        domain = self._extract_domain_from_url(url)
        if domain.count('.') >= 4:
            return True

        if domain.startswith('xn--') or '.xn--' in domain:
            return True

        if self._has_unicode_or_punycode_spoofing(domain):
            return True

        if self._looks_like_brand_domain(domain):
            return True

        return False
    
    def _check_urgency(self, subject: str, body: str) -> float:
        """Check for social engineering urgency tactics"""
        score = 0.0
        combined_text = (subject + ' ' + body).lower()
        
        urgency_indicators = [
            'immediately', 'urgent', 'limited time', 'act now',
            'verify immediately', 'confirm now', 'asap'
        ]
        
        for indicator in urgency_indicators:
            if indicator in combined_text:
                score += 0.15

        if any(keyword in combined_text for keyword in self.secrecy_keywords):
            score += 0.08
        
        return min(score, 1.0)
    
    def _check_common_misspellings(self, body: str) -> bool:
        """Check for common misspellings typical in phishing emails"""
        misspellings = [
            'occured', 'recieve', 'occassion', 'seperate',
            'adress', 'wich', 'thier', 'becuase'
        ]
        return any(misspell in body.lower() for misspell in misspellings)

    def _score_with_phase2_models(self, parsed_sender: Dict[str, str], subject: str, body: str) -> Dict[str, float]:
        """Score the message with the trained Phase 2 models when artifacts are available."""
        if not self.phase2_models.is_ready:
            return {
                'content_score': 0.0,
                'url_score': 0.0,
                'intel_exact_match_count': 0,
                'intel_domain_match_count': 0,
                'intel_matched_urls': [],
                'intel_matched_domains': [],
            }

        extracted_urls = self._extract_urls(body)
        content_score = self.phase2_models.predict_content_score(
            parsed_sender['raw'],
            subject,
            body,
            extracted_urls,
        )
        url_score = self.phase2_models.predict_url_score(body, extracted_urls)
        intel_summary = self.phase2_models.inspect_url_intel(extracted_urls)

        return {
            'content_score': round(content_score, 3),
            'url_score': round(url_score, 3),
            'intel_exact_match_count': int(intel_summary.get('exact_match_count', 0)),
            'intel_domain_match_count': int(intel_summary.get('domain_match_count', 0)),
            'intel_matched_urls': intel_summary.get('matched_urls', []),
            'intel_matched_domains': intel_summary.get('matched_domains', []),
        }
    
    def _identify_threats(self, parsed_sender: Dict[str, str], recipient: str, subject: str, body: str, headers: Dict) -> List[str]:
        """Identify specific threats in the email"""
        threats = []

        if self._check_advance_fee_fraud(subject, body):
            threats.append('Advance Fee Fraud Pattern')

        if self._check_bec_pattern(subject, body):
            threats.append('Business Email Compromise Pattern')

        if self._check_credential_harvesting(body):
            threats.append('Credential Harvesting Detected')

        if self._check_urgency_tactics(subject + ' ' + body):
            threats.append('Social Engineering - Urgency Tactic')

        if self._check_suspicious_attachments(body):
            threats.append('Suspicious Attachment References')

        if self._check_sender_impersonation(parsed_sender, subject, body):
            threats.append('Sender Impersonation Detected')

        if self._check_header_mismatch(parsed_sender, headers):
            threats.append('Sender Authentication Mismatch')

        if self._has_unicode_or_punycode_spoofing(parsed_sender['domain']):
            threats.append('Unicode Lookalike Domain Detected')

        if threats and self._check_sender_history(parsed_sender['email'], recipient) > 0:
            threats.append('First Contact Sender')

        if self._check_urls(body) > 0.45:
            threats.append('Suspicious URL Patterns')

        if self._check_malware_indicators(body):
            threats.append('Potential Malware Indicators')

        return threats if threats else ['No immediate threats detected']
    
    def _check_credential_harvesting(self, body: str) -> bool:
        """Check for credential harvesting attempts"""
        keywords = [
            'password', 'login', 'confirm identity', 'verify account',
            'authenticate', 'ssn', 'credit card', 'bank account'
        ]
        return any(keyword in body.lower() for keyword in keywords)
    
    def _check_urgency_tactics(self, text: str) -> bool:
        """Check for social engineering urgency tactics"""
        keywords = [
            'immediately', 'urgent', 'limited time', 'act now',
            'suspended', 'locked', 'unusual activity'
        ]
        return sum(1 for keyword in keywords if keyword in text.lower()) >= 2
    
    def _check_suspicious_attachments(self, body: str) -> bool:
        """Check for references to suspicious attachments"""
        suspicious_extensions = [
            '.exe', '.zip', '.scr', '.bat', '.cmd', '.vbs',
            '.jar', '.ps1', '.msi', '.dmg'
        ]
        return any(ext in body.lower() for ext in suspicious_extensions)

    def _check_sender_impersonation(self, parsed_sender: Dict[str, str], subject: str, body: str) -> bool:
        """Check for sender impersonation and lookalike-domain indicators."""
        subject_lower = subject.lower()
        sender_domain = parsed_sender['domain']
        display_name = parsed_sender['display_name']

        if self._display_name_impersonates_brand(display_name, sender_domain):
            return True

        if self._looks_like_brand_domain(sender_domain):
            return True

        for brand in self.brand_keywords:
            if brand in subject_lower and brand not in sender_domain:
                return True

        return False

    def _check_header_mismatch(self, parsed_sender: Dict[str, str], headers: Dict) -> bool:
        """Check for header-level sender mismatches when headers are available."""
        normalized_headers = {
            key.lower(): value
            for key, value in headers.items()
            if isinstance(key, str)
        }
        from_header = normalized_headers.get('from', '')
        reply_to = normalized_headers.get('reply-to', '')
        return_path = normalized_headers.get('return-path', '')

        header_email = self._parse_sender(from_header).get('email') if from_header else ''
        if header_email and parsed_sender['email'] and header_email != parsed_sender['email']:
            return True

        reply_to_domain = self._parse_sender(reply_to).get('domain') if reply_to else ''
        return_path_domain = self._parse_sender(return_path).get('domain') if return_path else ''
        sender_domain = parsed_sender['domain']

        if reply_to_domain and sender_domain and reply_to_domain != sender_domain:
            return True

        if return_path_domain and sender_domain and return_path_domain != sender_domain:
            return True

        return False
    
    def _check_malware_indicators(self, body: str) -> bool:
        """Check for malware-related indicators"""
        indicators = [
            'download now', 'enable macros', 'enable content',
            'run this script', 'execute file'
        ]
        body_lower = body.lower()
        return sum(1 for indicator in indicators if indicator in body_lower) >= 1

    def _check_impersonation(self, parsed_sender: Dict[str, str], subject: str, body: str) -> float:
        """Score user/domain impersonation and lookalike sender signals."""
        score = 0.0

        if self._check_sender_impersonation(parsed_sender, subject, body):
            score += 0.45

        if self._has_unicode_or_punycode_spoofing(parsed_sender['domain']):
            score += 0.25

        if self._display_name_impersonates_brand(parsed_sender['display_name'], parsed_sender['domain']):
            score += 0.2

        return min(score, 1.0)

    def _analyze_headers(self, parsed_sender: Dict[str, str], headers: Dict) -> float:
        """Assign score for From/Reply-To/Return-Path mismatches when headers exist."""
        if not headers:
            return 0.0

        score = 0.0
        normalized_headers = {
            key.lower(): value
            for key, value in headers.items()
            if isinstance(key, str)
        }

        from_header = normalized_headers.get('from', '')
        reply_to = normalized_headers.get('reply-to', '')
        return_path = normalized_headers.get('return-path', '')

        header_email = self._parse_sender(from_header).get('email') if from_header else ''
        if header_email and parsed_sender['email'] and header_email != parsed_sender['email']:
            score += 0.45

        reply_to_domain = self._parse_sender(reply_to).get('domain') if reply_to else ''
        if reply_to_domain and parsed_sender['domain'] and reply_to_domain != parsed_sender['domain']:
            score += 0.3

        return_path_domain = self._parse_sender(return_path).get('domain') if return_path else ''
        if return_path_domain and parsed_sender['domain'] and return_path_domain != parsed_sender['domain']:
            score += 0.25

        return min(score, 1.0)

    def _check_sender_history(self, sender_email: str, recipient: str) -> float:
        """Approximate first-contact risk using prior sender-recipient history."""
        if not sender_email or not recipient:
            return 0.0

        try:
            prior_messages = Email.query.filter_by(
                sender=sender_email.lower(),
                recipient=recipient.lower()
            ).count()
        except Exception:
            return 0.0

        if prior_messages == 0:
            return 0.12

        if prior_messages < 3:
            return 0.05

        return 0.0

    def _check_advance_fee_fraud(self, subject: str, body: str) -> bool:
        """Detect common 419 / advance-fee fraud language patterns."""
        combined_text = f"{subject} {body}".lower()
        keyword_hits = sum(1 for keyword in self.advance_fee_keywords if keyword in combined_text)
        mentions_large_amount = bool(
            re.search(r'(?:us\$|usd|\$)\s?[\d,]+', combined_text)
            or re.search(r'\b\d+\s*(million|billion)\b', combined_text)
        )
        return keyword_hits >= 3 or (keyword_hits >= 2 and mentions_large_amount)

    def _check_bec_pattern(self, subject: str, body: str) -> bool:
        """Detect BEC-style payment, invoice, and funds-transfer language."""
        combined_text = f"{subject} {body}".lower()
        keyword_hits = sum(1 for keyword in self.bec_keywords if keyword in combined_text)
        return keyword_hits >= 2

    def _determine_verdict(self, risk_score: float, threats: List[str]) -> str:
        """Classify the message into safe, suspicious, or phishing."""
        real_threats = [threat for threat in threats if threat != 'No immediate threats detected']

        if any(threat in self.high_confidence_threats for threat in real_threats):
            return 'phishing'

        if risk_score >= 0.58 or (risk_score >= 0.45 and len(real_threats) >= 2):
            return 'phishing'

        if risk_score >= 0.25 or real_threats:
            return 'suspicious'

        return 'safe'

    def _calculate_confidence(self, risk_score: float, threats: List[str]) -> str:
        """Return a confidence label for the verdict."""
        real_threats = [threat for threat in threats if threat != 'No immediate threats detected']

        if risk_score >= 0.75 or len(real_threats) >= 4:
            return 'very high'

        if risk_score >= 0.55 or len(real_threats) >= 2:
            return 'high'

        if risk_score >= 0.3 or len(real_threats) == 1:
            return 'medium'

        return 'low'

    def _generate_recommendations(self, verdict: str, risk_score: float, threats: List[str]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        if verdict == 'phishing':
            recommendations.append('Delete this email immediately')
            recommendations.append('Report as phishing to your email provider')
            recommendations.append('Do not reply, transfer funds, or share personal information')
        elif verdict == 'suspicious':
            recommendations.append('Do not click any links in this email')
            recommendations.append('Verify sender through official channels')
        elif risk_score > 0.3:
            recommendations.append('Exercise caution - be suspicious of requests')
            recommendations.append('Verify links before clicking')

        if 'Credential Harvesting' in str(threats):
            recommendations.append('Never provide password or personal information via email')

        if 'Advance Fee Fraud Pattern' in str(threats):
            recommendations.append('Do not provide bank account details or agree to receive transferred funds')

        if 'Business Email Compromise Pattern' in str(threats):
            recommendations.append('Confirm payment or bank-change requests with a known contact before acting')

        if 'Malware Indicators' in str(threats):
            recommendations.append('Do not download or execute files from this email')

        return recommendations if recommendations else ['Email appears safe']

    def _parse_sender(self, sender: str) -> Dict[str, str]:
        """Normalize sender input into display name and email parts."""
        raw_sender = (sender or '').strip()
        display_name, email_address = parseaddr(raw_sender)
        normalized_email = email_address.strip().lower()

        if not normalized_email and '@' in raw_sender and '<' not in raw_sender:
            normalized_email = raw_sender.lower()

        local_part = ''
        domain = ''
        if '@' in normalized_email:
            local_part, domain = normalized_email.rsplit('@', 1)

        return {
            'raw': raw_sender,
            'display_name': display_name.strip(),
            'email': normalized_email,
            'local_part': local_part,
            'domain': domain,
        }

    def _is_valid_email(self, email_address: str) -> bool:
        """Validate a normalized email address."""
        if not email_address:
            return False

        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_address))

    def _has_malformed_from_address(self, raw_sender: str, email_address: str) -> bool:
        """Flag From values that violate common RFC-style formatting expectations."""
        if not raw_sender:
            return True

        if '<' in raw_sender or '>' in raw_sender:
            _, parsed_email = parseaddr(raw_sender)
            if not parsed_email:
                return True

            if '>' in raw_sender:
                trailing_text = raw_sender.split('>', 1)[1].strip()
                if trailing_text:
                    return True

        if raw_sender.count('@') > 1 and '<' not in raw_sender:
            return True

        return not self._is_valid_email(email_address)

    def _display_name_impersonates_brand(self, display_name: str, sender_domain: str) -> bool:
        """Detect display names that claim a brand the domain does not support."""
        display_name_lower = (display_name or '').lower()
        if not display_name_lower:
            return False

        return any(
            brand in display_name_lower and brand not in sender_domain
            for brand in self.brand_keywords
        )

    def _has_unicode_or_punycode_spoofing(self, domain: str) -> bool:
        """Detect suspicious Unicode, punycode, or mixed-script sender domains."""
        if not domain:
            return False

        if domain.startswith('xn--') or '.xn--' in domain:
            return True

        if any(ord(char) > 127 for char in domain):
            return True

        return self._has_mixed_script(domain)

    def _has_mixed_script(self, value: str) -> bool:
        """Detect suspicious mixing of Latin, Cyrillic, or Greek characters."""
        scripts = set()
        for char in value:
            if not char.isalpha():
                continue

            name = unicodedata.name(char, '')
            if 'CYRILLIC' in name:
                scripts.add('CYRILLIC')
            elif 'GREEK' in name:
                scripts.add('GREEK')
            elif 'LATIN' in name:
                scripts.add('LATIN')
            else:
                scripts.add('OTHER')

        return len(scripts) > 1

    def _looks_like_brand_domain(self, domain: str) -> bool:
        """Detect simple lookalike or typosquatted brand domains."""
        if not domain:
            return False

        second_level = domain.split('.')[0]
        normalized_label = (
            second_level.replace('0', 'o')
            .replace('1', 'l')
            .replace('3', 'e')
            .replace('5', 's')
        )

        for brand in self.brand_keywords:
            if normalized_label == brand:
                continue

            if self._edit_distance(normalized_label, brand) == 1:
                return True

        return False

    def _extract_urls(self, body: str) -> List[str]:
        """Extract HTTP(S) and www-style URLs from body text."""
        url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
        return re.findall(url_pattern, body)

    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain portion from a URL-like string."""
        normalized_url = url.strip()
        normalized_url = re.sub(r'^https?://', '', normalized_url)
        normalized_url = re.sub(r'^www\.', '', normalized_url)
        return normalized_url.split('/')[0].split(':')[0].lower()

    def _edit_distance(self, source: str, target: str) -> int:
        """Compute a small edit distance for brand lookalike detection."""
        if source == target:
            return 0

        if not source:
            return len(target)

        if not target:
            return len(source)

        previous_row = list(range(len(target) + 1))
        for source_index, source_char in enumerate(source, start=1):
            current_row = [source_index]
            for target_index, target_char in enumerate(target, start=1):
                insertions = previous_row[target_index] + 1
                deletions = current_row[target_index - 1] + 1
                substitutions = previous_row[target_index - 1] + (source_char != target_char)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]
