from __future__ import annotations

import re
import unicodedata
from email.utils import parseaddr
from typing import Dict, List

from models import Email
from services.phase2_models import Phase2ModelBundle


class PhishingDetector:
    """Enhanced phishing detection engine with stronger impersonation and urgency scoring."""

    def __init__(self):
        self.phishing_keywords = [
            'verify', 'confirm', 'update', 'validate', 'urgent', 'act now', 'click here',
            'suspended', 'limited time', 'reactivate', 'confirm identity', 'authenticate',
            'sign in', 'invoice', 'payment', 'wire transfer', 'beneficiary', 'bank account',
            'security notice', 'payroll', 'gift card', 'send money', 'bank transfer',
            'remittance', 'purchase order', 'confidential payment'
        ]

        self.suspicion_phrases = [
            'click here immediately', 'verify your account', 'confirm your identity',
            'update your information', 'account suspended', 'unusual activity',
            'action required', 'strictly confidential', 'keep this matter secret',
            'urgent response', 'next of kin', 'security company', 'foreign partner',
            'beneficiary of the fund', 'risk free transaction', 'reply urgently',
            'send funds today', 'wire the money', 'do not tell anyone'
        ]

        self.suspicious_domains = [
            'gmail-security', 'paypal-verify', 'amazon-account',
            'apple-support', 'microsoft-account', 'bank-secure'
        ]

        self.generic_mail_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'live.com', 'mail.com', 'aol.com', 'proton.me', 'protonmail.com'
        }

        self.brand_keywords = [
            'paypal', 'amazon', 'apple', 'microsoft', 'google',
            'office365', 'outlook', 'docusign', 'dropbox'
        ]

        self.advance_fee_keywords = [
            'beneficiary', 'next of kin', 'foreign partner', 'security company',
            'consignment', 'diplomatic box', 'transfer the fund',
            'million united states dollars', 'inheritance',
            'strictly confidential', 'confidential business proposal',
            'urgent assistance', 'percentage for you', 'risk free transaction',
            'bank account', 'compensate you', 'trusted foreign',
            'await your urgent response'
        ]

        self.bec_keywords = [
            'wire transfer', 'gift card', 'invoice', 'accounts payable',
            'payment', 'purchase order', 'payroll', 'remittance',
            'bank details', 'vendor update', 'approve this transfer',
            'send funds', 'process payment', 'make the transfer'
        ]

        self.secrecy_keywords = [
            'confidential', 'secret', 'do not disclose', 'keep this matter',
            'private', 'strictly to yourself', 'do not tell anyone',
            'between us', 'only you'
        ]

        self.urgency_patterns = [
            r'\burgent\b', r'\basap\b', r'\bimmediately\b', r'\bright now\b',
            r'\btoday\b', r'\bwithin\s+\d+\s+(hours?|minutes?)\b',
            r'\baction required\b', r'\brespond now\b', r'\bwithout delay\b',
            r'\bcritical\b', r'\bfinal notice\b', r'\bimmediate action\b'
        ]

        self.money_patterns = [
            r'\bsend\s+(me\s+)?money\b',
            r'\bwire\s+(the\s+)?(money|funds|transfer)\b',
            r'\btransfer\s+(the\s+)?(money|funds)\b',
            r'\bpayment\b',
            r'\bremittance\b',
            r'\bbank account\b',
            r'\bgift cards?\b',
            r'\busd\s?[\d,]+\b',
            r'\$\s?[\d,]+\b'
        ]

        self.identity_claim_patterns = [
            r'\bi am\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b',
            r'\bthis is\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b',
            r'\bi\'m\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b',
            r'\bmy name is\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b'
        ]

        self.vip_names = {
            'brad pitt', 'elon musk', 'bill gates', 'jeff bezos', 'mark zuckerberg',
            'tim cook', 'sundar pichai', 'satya nadella', 'warren buffett',
            'taylor swift', 'donald trump', 'barack obama', 'oprah winfrey'
        }

        self.role_impersonation_terms = {
            'ceo', 'chief executive officer', 'cfo', 'chief financial officer',
            'finance director', 'hr director', 'payroll manager', 'accounts payable',
            'vendor', 'attorney', 'lawyer', 'executive assistant'
        }

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
            'sender_score': 0.16,
            'subject_score': 0.12,
            'body_score': 0.22,
            'url_score': 0.14,
            'urgency_score': 0.12,
            'impersonation_score': 0.14,
            'history_score': 0.05,
            'header_score': 0.05,
        }

        self.phase2_models = Phase2ModelBundle()

    def analyze_email(self, sender: str, recipient: str, subject: str, body: str, headers: Dict = None) -> Dict:
        headers = headers or {}
        parsed_sender = self._parse_sender(sender)

        scores = {
            'sender_score': self._analyze_sender(parsed_sender, subject, body),
            'subject_score': self._analyze_subject(subject),
            'body_score': self._analyze_body(body),
            'url_score': self._check_urls(body),
            'urgency_score': self._analyze_urgency(subject, body),
            'impersonation_score': self._analyze_impersonation(parsed_sender, subject, body),
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
                (risk_scores['body_score'] * 0.50) + (ml_scores['content_score'] * 0.50)
            )

        if ml_scores['url_score'] > 0:
            risk_scores['url_score'] = max(
                risk_scores['url_score'],
                (risk_scores['url_score'] * 0.35) + (ml_scores['url_score'] * 0.65)
            )

        # Cross-component escalation for obvious social engineering
        if risk_scores['impersonation_score'] >= 0.55 and risk_scores['urgency_score'] >= 0.45:
            risk_scores['body_score'] = min(1.0, max(risk_scores['body_score'], 0.72))

        if risk_scores['impersonation_score'] >= 0.60:
            risk_scores['sender_score'] = min(1.0, max(risk_scores['sender_score'], 0.55))

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

        threats = list(dict.fromkeys(threats))
        verdict = self._determine_verdict(overall_risk, threats)

        return {
            'overall_risk_score': round(overall_risk, 3),
            'verdict': verdict,
            'is_phishing': verdict == 'phishing',
            'confidence': self._calculate_confidence(overall_risk, threats),
            'component_scores': {
                k: round(v, 3) for k, v in risk_scores.items()
                if k in self.score_weights
            },
            'threats': threats or ['No immediate threats detected'],
            'ml_scores': ml_scores,
            'recommendations': self._generate_recommendations(verdict, overall_risk, threats),
            'normalized_sender': parsed_sender['email'] or parsed_sender['raw'],
            'raw_sender': parsed_sender['raw'],
            'phase2_models_enabled': self.phase2_models.is_ready,
            'phase2_data_sources': self.phase2_models.metadata.get('data_sources', []),
        }

    def _parse_sender(self, sender: str) -> Dict[str, str]:
        display_name, email_addr = parseaddr(sender or '')
        raw = sender or ''
        email_addr = (email_addr or '').strip().lower()
        display_name = (display_name or '').strip()
        return {
            'raw': raw,
            'display_name': display_name,
            'email': email_addr,
            'domain': email_addr.split('@')[-1] if '@' in email_addr else '',
        }

    def _normalize_text(self, text: str) -> str:
        return unicodedata.normalize("NFKC", (text or "")).strip()

    def _analyze_sender(self, parsed_sender: Dict[str, str], subject: str, body: str) -> float:
        score = 0.0
        display_name = self._normalize_text(parsed_sender.get('display_name', '')).lower()
        email_addr = parsed_sender.get('email', '').lower()
        domain = parsed_sender.get('domain', '').lower()
        combined = f"{subject} {body}".lower()

        if domain in self.generic_mail_domains:
            score += 0.12

        if any(susp in domain for susp in self.suspicious_domains):
            score += 0.40

        if display_name:
            if any(vip in display_name for vip in self.vip_names):
                score += 0.45
            if any(role in display_name for role in self.role_impersonation_terms):
                score += 0.25
            if domain in self.generic_mail_domains and (any(vip in display_name for vip in self.vip_names) or any(role in display_name for role in self.role_impersonation_terms)):
                score += 0.20

        # Display name claims identity not reflected by domain
        if display_name and domain:
            if any(vip in display_name for vip in self.vip_names) and domain not in {'planbproduction.com'}:
                score += 0.20

        # Fake identity request from generic mailbox
        if domain in self.generic_mail_domains and any(
            re.search(pattern, body or '') for pattern in self.identity_claim_patterns
        ):
            score += 0.18

        # Unicode lookalike or odd sender tokens
        if any(ord(ch) > 127 for ch in (display_name + email_addr)):
            score += 0.08

        if re.search(r'(support|security|billing|payroll|finance|accounts)[._-]?\d*@', email_addr):
            score += 0.10

        # Sender-body mismatch: famous or executive claim appears in body but sender domain is generic
        if domain in self.generic_mail_domains and (
            any(vip in combined for vip in self.vip_names) or
            any(role in combined for role in self.role_impersonation_terms)
        ):
            score += 0.15

        return min(score, 1.0)

    def _analyze_subject(self, subject: str) -> float:
        score = 0.0
        subject_lower = (subject or '').lower()

        for keyword in self.phishing_keywords:
            if keyword in subject_lower:
                score += 0.08

        urgency_words = ['urgent', '!!', 'asap', 'immediate', 'alert', 'critical', 'today', 'reply now']
        for word in urgency_words:
            if word in subject_lower:
                score += 0.12

        if any(word in subject_lower for word in ['account', 'password', 'security', 'payment', 'transfer']):
            score += 0.10

        if any(keyword in subject_lower for keyword in self.bec_keywords):
            score += 0.18

        if any(keyword in subject_lower for keyword in self.advance_fee_keywords[:8]):
            score += 0.18

        # New: impersonation and money-pressure patterns in subject
        if any(vip in subject_lower for vip in self.vip_names):
            score += 0.20

        if any(role in subject_lower for role in self.role_impersonation_terms):
            score += 0.16

        if re.search(r'\b(send|wire|transfer|pay)\b', subject_lower) and re.search(r'\b(money|funds|payment|invoice)\b', subject_lower):
            score += 0.22

        if re.search(r'\bconfidential\b|\bprivate\b|\bsecret\b', subject_lower):
            score += 0.12

        return min(score, 1.0)

    def _analyze_body(self, body: str) -> float:
        score = 0.0
        body_lower = (body or '').lower()

        for phrase in self.suspicion_phrases:
            if phrase in body_lower:
                score += 0.15

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

        if self._check_common_misspellings(body or ''):
            score += 0.08

        # New: explicit money request / coercion
        money_hits = sum(1 for pattern in self.money_patterns if re.search(pattern, body_lower))
        score += min(money_hits * 0.10, 0.30)

        # New: direct identity claim
        if any(re.search(pattern, body or '') for pattern in self.identity_claim_patterns):
            score += 0.15

        # New: celebrity or role claim in body
        if any(vip in body_lower for vip in self.vip_names):
            score += 0.18

        if any(role in body_lower for role in self.role_impersonation_terms):
            score += 0.12

        return min(score, 1.0)

    def _analyze_urgency(self, subject: str, body: str) -> float:
        score = 0.0
        combined = f"{subject} {body}".lower()

        hits = sum(1 for pattern in self.urgency_patterns if re.search(pattern, combined))
        score += min(hits * 0.14, 0.50)

        if any(word in combined for word in ['confidential', 'secret', 'private', 'do not tell anyone']):
            score += 0.18

        if re.search(r'\b(today|now|immediately|right away)\b', combined) and re.search(r'\b(send|wire|transfer|pay)\b', combined):
            score += 0.22

        if combined.count('!') >= 2:
            score += 0.08

        return min(score, 1.0)

    def _analyze_impersonation(self, parsed_sender: Dict[str, str], subject: str, body: str) -> float:
        score = 0.0
        display_name = self._normalize_text(parsed_sender.get('display_name', '')).lower()
        domain = parsed_sender.get('domain', '').lower()
        combined = f"{subject} {body}".lower()

        if any(re.search(pattern, body or '') for pattern in self.identity_claim_patterns):
            score += 0.20

        if any(vip in combined for vip in self.vip_names):
            score += 0.45

        if any(role in combined for role in self.role_impersonation_terms):
            score += 0.20

        if domain in self.generic_mail_domains and (
            any(vip in combined for vip in self.vip_names) or
            any(role in combined for role in self.role_impersonation_terms)
        ):
            score += 0.20

        if display_name and any(vip in display_name for vip in self.vip_names):
            score += 0.30

        if display_name and any(role in display_name for role in self.role_impersonation_terms):
            score += 0.18

        if re.search(r'\bi am\b|\bthis is\b|\bmy name is\b|\bi\'m\b', body.lower()):
            score += 0.10

        # Strong escalation for identity + money ask
        if (
            any(vip in combined for vip in self.vip_names) or
            any(role in combined for role in self.role_impersonation_terms)
        ) and any(re.search(pattern, combined) for pattern in self.money_patterns):
            score += 0.25

        return min(score, 1.0)

    def _check_urls(self, body: str) -> float:
        body_lower = (body or '').lower()
        score = 0.0

        urls = re.findall(r'https?://[^\s<>"\']+|www\.[^\s<>"\']+', body_lower)
        if urls:
            score += min(len(urls) * 0.10, 0.30)

        for url in urls:
            if '@' in url:
                score += 0.18
            if re.search(r'(bit\.ly|tinyurl|t\.co|goo\.gl)', url):
                score += 0.18
            if re.search(r'(login|verify|secure|update|signin|password)', url):
                score += 0.14

        return min(score, 1.0)

    def _identify_threats(self, parsed_sender: Dict[str, str], recipient: str, subject: str, body: str, headers: Dict) -> List[str]:
        threats = []
        combined = f"{subject} {body}".lower()
        domain = parsed_sender.get('domain', '').lower()
        display_name = parsed_sender.get('display_name', '').lower()

        if self._analyze_impersonation(parsed_sender, subject, body) >= 0.55:
            threats.append('Sender Impersonation Detected')

        if self._check_advance_fee_pattern(subject, body):
            threats.append('Advance Fee Fraud Pattern')

        if self._check_bec_pattern(subject, body):
            threats.append('Business Email Compromise Pattern')

        if domain in self.generic_mail_domains and (
            any(vip in combined for vip in self.vip_names) or
            any(role in combined for role in self.role_impersonation_terms)
        ):
            threats.append('Identity Claim from Generic Mailbox')

        if any(re.search(pattern, combined) for pattern in self.money_patterns):
            threats.append('Financial Request Pattern')

        return threats

    def _determine_verdict(self, overall_risk: float, threats: List[str]) -> str:
        if any(t in self.high_confidence_threats for t in threats):
            return 'phishing'
        if overall_risk >= 0.75:
            return 'phishing'
        if overall_risk >= 0.45:
            return 'suspicious'
        return 'safe'

    def _calculate_confidence(self, overall_risk: float, threats: List[str]) -> str:
        if overall_risk >= 0.85 or len(threats) >= 3:
            return 'very high'
        if overall_risk >= 0.65 or len(threats) >= 2:
            return 'high'
        if overall_risk >= 0.35:
            return 'medium'
        return 'low'

    def _generate_recommendations(self, verdict: str, overall_risk: float, threats: List[str]) -> List[str]:
        if verdict == 'phishing':
            return [
                'Do not reply or send money.',
                'Do not click any links or open attachments.',
                'Report the message to security immediately.',
                'Verify the sender through an independent trusted channel.'
            ]
        if verdict == 'suspicious':
            return [
                'Verify the sender identity independently.',
                'Do not take financial action until confirmed.',
                'Treat any links, invoices, or requests with caution.'
            ]
        return [
            'No strong phishing indicators were found, but stay cautious with unexpected requests.'
        ]

    def _score_with_phase2_models(self, parsed_sender: Dict[str, str], subject: str, body: str) -> Dict:
        try:
            return self.phase2_models.predict_scores(
                sender=parsed_sender.get('email', ''),
                subject=subject,
                body=body,
            )
        except Exception:
            return {
                'content_score': 0.0,
                'url_score': 0.0,
                'intel_exact_match_count': 0,
                'intel_domain_match_count': 0,
            }

    def _check_sender_history(self, sender_email: str, recipient: str) -> float:
        try:
            if not sender_email or not recipient:
                return 0.0
            historical = Email.query.filter_by(sender=sender_email.lower(), recipient=recipient.lower()).count()
            if historical == 0:
                return 0.10
            if historical <= 2:
                return 0.04
            return 0.0
        except Exception:
            return 0.0

    def _analyze_headers(self, parsed_sender: Dict[str, str], headers: Dict) -> float:
        if not headers:
            return 0.0
        score = 0.0
        sender_domain = parsed_sender.get('domain', '').lower()

        reply_to = (headers.get('Reply-To') or headers.get('reply-to') or '').lower()
        from_header = (headers.get('From') or headers.get('from') or '').lower()

        if reply_to and sender_domain and sender_domain not in reply_to:
            score += 0.25

        if from_header and parsed_sender.get('email', '').lower() and parsed_sender['email'].lower() not in from_header:
            score += 0.10

        return min(score, 1.0)

    def _check_common_misspellings(self, text: str) -> bool:
        patterns = [
            r'\bacc0unt\b', r'\bverlfy\b', r'\bsecur1ty\b', r'\bpassw0rd\b',
            r'\bpaypa1\b', r'\bm1crosoft\b'
        ]
        text_lower = (text or '').lower()
        return any(re.search(pattern, text_lower) for pattern in patterns)

    def _check_advance_fee_pattern(self, subject: str, body: str) -> bool:
        combined_text = f"{subject} {body}".lower()
        keyword_hits = sum(1 for keyword in self.advance_fee_keywords if keyword in combined_text)
        mentions_large_amount = bool(
            re.search(r'(?:us\$|usd|\$)\s?[\d,]+', combined_text) or
            re.search(r'\b\d+\s*(million|billion)\b', combined_text)
        )
        return keyword_hits >= 3 or (keyword_hits >= 2 and mentions_large_amount)

    def _check_bec_pattern(self, subject: str, body: str) -> bool:
        combined_text = f"{subject} {body}".lower()
        keyword_hits = sum(1 for keyword in self.bec_keywords if keyword in combined_text)
        return keyword_hits >= 2