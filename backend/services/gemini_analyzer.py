"""
Gemini-powered semantic phishing analysis.

Uses Google's Generative AI to provide context-aware, dynamic phishing detection
that goes beyond static rules.
"""

import json
import os
import re
from typing import Dict, List, Optional
import google.generativeai as genai


class GeminiPhishingAnalyzer:
    """
    Semantic analysis of emails using Google Gemini.
    
    Provides:
    - Social engineering intent classification
    - Contextual contradiction detection
    - Threat type identification
    - Dynamic risk factor discovery
    - Human-readable explanations
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini analyzer."""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Configuration
        self.generation_config = {
            'temperature': 0.3,  # Low temp for consistency
            'top_p': 0.8,
            'max_output_tokens': 1000,
        }
    
    def analyze_email_semantics(self, sender: str, subject: str, body: str, 
                                urls: List[str], ml_scores: Dict) -> Dict:
        """
        Perform semantic analysis of email for phishing indicators.
        
        Analyzes:
        1. Social engineering tactics used
        2. Authority and legitimacy signals
        3. Contextual contradictions
        4. Threat intent classification
        5. Dynamic risk factors
        
        Args:
            sender: Email sender address
            subject: Email subject line
            body: Email body text
            urls: List of URLs in email
            ml_scores: Machine learning component scores from Random Forest
        
        Returns:
            {
                'threat_type': str,
                'threat_confidence': float 0-1,
                'tactics_detected': [str],
                'contextual_issues': [str],
                'social_engineering_score': float 0-1,
                'explanation': str,
                'recommendation': str,
                'dynamic_factors': [str]
            }
        """
        
        # Build context for Gemini
        body_preview = body[:1000] + ("..." if len(body) > 1000 else "")
        urls_str = ", ".join(urls) if urls else "No URLs"
        
        # ML context (what the statistical models found)
        ml_context = f"""
Machine Learning Analysis (Random Forest + Logistic Regression):
- Sender suspicion score: {ml_scores.get('sender_score', 0):.1%}
- Subject suspicion score: {ml_scores.get('subject_score', 0):.1%}
- Body suspicion score: {ml_scores.get('body_score', 0):.1%}
- URL suspicion score: {ml_scores.get('url_score', 0):.1%}
- Urgency detected: {ml_scores.get('urgency_score', 0):.1%}
- Impersonation score: {ml_scores.get('impersonation_score', 0):.1%}
"""
        
        prompt = f"""
Analyze this email for phishing using semantic understanding and contextual analysis.
Go BEYOND simple pattern matching. Focus on:

1. INTENT & SOCIAL ENGINEERING
   - What action does sender want? (wire money, click link, reveal credentials?)
   - What psychological tactics are used? (urgency, authority, fear, scarcity?)
   - Is this targeted social engineering or mass phishing?

2. CONTEXTUAL ANALYSIS
   - Do all parts of email align? (sender + subject + body + URLs)
   - Are there contradictions between claimed identity and request?
   - Would a legitimate organization make this request via email?
   - Does language/tone match the claimed organization?

3. THREAT CLASSIFICATION
   - What specific type of phishing attempt is this?
   - Credential harvesting? Business Email Compromise? Advance fee fraud?
   - Software/malware distribution? Brand reputation damage?

4. DYNAMIC FACTORS (Not pre-defined rules)
   - What unusual combinations of elements suggest fraud?
   - What implicit requests hide beneath surface requests?
   - What behavioral anomalies indicate phishing?

5. CONFIDENCE ASSESSMENT
   - How certain are you this is phishing?
   - What would make you more certain?
   - Any legitimate explanations?

{ml_context}

EMAIL TO ANALYZE:
─────────────────────────────────────────────────────────────
From: {sender}
Subject: {subject}
Body: {body_preview}
URLs: {urls_str}
─────────────────────────────────────────────────────────────

Provide analysis in JSON format ONLY (no markdown or explanation):
{{
    "is_phishing": boolean,
    "threat_type": "string - specific threat category",
    "phishing_confidence": 0.0-1.0,
    "tactics_detected": ["tactic1", "tactic2"],
    "contextual_issues": ["issue1", "issue2"],
    "social_engineering_score": 0.0-1.0,
    "dynamic_risk_factors": ["factor1 - explanation", "factor2 - explanation"],
    "contradictions": ["contradiction1", "contradiction2"],
    "explanation": "2-3 sentences explaining semantic findings",
    "reasoning": "deeper analysis of why this is/isn't phishing",
    "recommendation": "specific action user should take"
}}
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            # Extract JSON from response
            response_text = response.text
            
            # Find JSON block
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            json_str = json_match.group(0)
            analysis = json.loads(json_str)
            
            # Ensure required fields
            return {
                'is_phishing': analysis.get('is_phishing', True),
                'threat_type': analysis.get('threat_type', 'Unknown Phishing'),
                'threat_confidence': float(analysis.get('phishing_confidence', 0.5)),
                'tactics_detected': analysis.get('tactics_detected', []),
                'contextual_issues': analysis.get('contextual_issues', []),
                'social_engineering_score': float(analysis.get('social_engineering_score', 0.5)),
                'dynamic_risk_factors': analysis.get('dynamic_risk_factors', []),
                'contradictions': analysis.get('contradictions', []),
                'explanation': analysis.get('explanation', ''),
                'reasoning': analysis.get('reasoning', ''),
                'recommendation': analysis.get('recommendation', ''),
            }
        
        except Exception as e:
            # Fallback on error
            return {
                'is_phishing': True,
                'threat_type': 'Analysis Error',
                'threat_confidence': 0.0,
                'tactics_detected': [],
                'contextual_issues': [f'Analysis error: {str(e)}'],
                'social_engineering_score': 0.0,
                'dynamic_risk_factors': [],
                'contradictions': [],
                'explanation': 'Gemini analysis failed',
                'reasoning': str(e),
                'recommendation': 'Manual review recommended',
            }
    
    def generate_hybrid_explanation(self, sender: str, ml_scores: Dict, 
                                   gemini_analysis: Dict) -> str:
        """
        Generate user-friendly explanation combining ML and Gemini insights.
        
        Explains WHY something is phishing in natural language.
        """
        
        prompt = f"""
Generate a 2-3 sentence explanation for a non-technical user about why their email 
is flagged as phishing. Combine statistical analysis with semantic understanding.

Machine Learning Analysis:
- Sender suspicious: {ml_scores.get('sender_score', 0):.0%}
- URL suspicious: {ml_scores.get('url_score', 0):.0%}
- Body suspicious: {ml_scores.get('body_score', 0):.0%}

Semantic Analysis by AI:
- Threat Type: {gemini_analysis.get('threat_type', 'Unknown')}
- Main Tactics: {', '.join(gemini_analysis.get('tactics_detected', [])[:3])}
- Key Issues: {', '.join(gemini_analysis.get('contextual_issues', [])[:2])}

Write explanation that:
1. Explains the specific threat (not generic "phishing detected")
2. Mentions key warning signs
3. Tells user what action to take
4. Uses simple language

Keep it 2-3 sentences, engaging, non-technical.
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            return response.text.strip()
        
        except Exception as e:
            return (f"This email is flagged as likely {gemini_analysis.get('threat_type', 'phishing')}. "
                   f"Do not click links or reply with personal information. "
                   f"Contact the sender through known channels if unsure.")
    
    def classify_threat_intent(self, sender: str, subject: str, body: str) -> Dict:
        """
        Classify the specific intent/threat type of the email.
        
        Returns detailed threat classification beyond binary phishing/safe.
        """
        
        prompt = f"""
Classify the threat intent of this email. Determine WHAT TYPE of phishing/fraud attempt 
this is, not just WHETHER it's phishing.

Possible threat types:
- Credential Harvesting: Stealing login credentials
- Business Email Compromise (BEC): CEO/authority fraud for wire transfer
- Advance Fee Fraud: "Nigerian prince" style advance payment scams
- Malware Distribution: Links/attachments containing malware
- Invoice Fraud: Fake invoices or vendor account changes
- Tech Support Scam: Fake tech support requests
- Brand Impersonation: Spoofing legitimate companies
- Social Engineering: Manipulating user through psychology alone
- Phishing (Generic): Other phishing attempts
- Not Phishing: Legitimate email

Email:
From: {sender}
Subject: {subject}
Body: {body[:500]}

Respond ONLY with JSON:
{{
    "primary_threat": "threat type string",
    "confidence": 0.0-1.0,
    "secondary_threats": ["threat2", "threat3"],
    "indicators": ["indicator1", "indicator2"],
    "organizational_risk": "high|medium|low",
    "financial_risk": "high|medium|low"
}}
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if not json_match:
                return {'primary_threat': 'Unknown', 'confidence': 0.5}
            
            return json.loads(json_match.group(0))
        
        except Exception as e:
            return {
                'primary_threat': 'Analysis Failed',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def detect_novel_patterns(self, sender: str, subject: str, body: str) -> List[str]:
        """
        Detect phishing patterns that aren't in standard rulebooks.
        
        Finds suspicious combinations and novel techniques.
        """
        
        prompt = f"""
Identify NOVEL or UNUSUAL phishing patterns in this email that might bypass 
standard antiphishing systems.

Focus on:
1. Unusual combinations of legitimate and suspicious elements
2. Techniques not commonly seen (novel methods)
3. Sophisticated social engineering
4. Contradictions between different parts of email
5. Implicit requests hidden in explicit requests

Email:
From: {sender}
Subject: {subject}
Body: {body[:1000]}

List 3-5 novel or unusual patterns detected (or empty list if none):
Return JSON ONLY:
{{
    "novel_patterns": ["pattern1 - why unusual", "pattern2 - why unusual"],
    "sophistication_level": "low|medium|high",
    "likely_attacker_skill": "amateur|intermediate|professional"
}}
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if not json_match:
                return []
            
            data = json.loads(json_match.group(0))
            return data.get('novel_patterns', [])
        
        except Exception:
            return []


def create_hybrid_score(ml_score: float, gemini_confidence: float, 
                       ml_confidence: float) -> float:
    """
    Intelligently blend ML and Gemini scores based on confidence.
    
    Uses weighted average where weights depend on confidence levels.
    """
    
    if gemini_confidence > 0.95:
        # High confidence from semantic analysis - trust it more
        return 0.4 * ml_score + 0.6 * gemini_confidence
    
    elif ml_confidence > gemini_confidence:
        # ML statistically more confident
        return 0.6 * ml_score + 0.4 * gemini_confidence
    
    else:
        # Default balanced approach
        return 0.5 * ml_score + 0.5 * gemini_confidence
