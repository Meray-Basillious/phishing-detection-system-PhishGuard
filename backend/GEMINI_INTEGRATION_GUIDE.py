"""
INTEGRATION GUIDE: Updating phishing_detector.py for Gemini Hybrid Analysis

This shows how to modify the existing phishing_detector.py to use the Gemini hybrid approach.
"""

# =====================================================================
# STEP 1: Add import at top of phishing_detector.py
# =====================================================================

"""
Add to imports section:
"""

from services.gemini_analyzer import GeminiPhishingAnalyzer, create_hybrid_score


# =====================================================================
# STEP 2: Modify __init__ method of PhishingDetector class
# =====================================================================

"""
In the __init__ method, add:
"""

def __init__(self):
    # ... existing code ...
    
    self.phase2_models = Phase2ModelBundle()
    
    # NEW: Initialize Gemini analyzer
    try:
        self.gemini_analyzer = GeminiPhishingAnalyzer()
        self.use_gemini = True
        self.gemini_enabled = True
    except Exception as e:
        # Graceful fallback if Gemini not available
        self.gemini_analyzer = None
        self.use_gemini = False
        self.gemini_enabled = False
        print(f"Gemini analyzer initialization failed: {e}")
        print("Falling back to ML-only analysis")


# =====================================================================
# STEP 3: Modify analyze_email method (MAIN CHANGE)
# =====================================================================

"""
Replace the current analyze_email return section with this:
"""

def analyze_email(self, sender: str, recipient: str, subject: str, 
                  body: str, headers: Dict = None, use_gemini: Optional[bool] = None) -> Dict:
    """
    Main analysis function - now with optional Gemini semantic analysis.
    
    Args:
        sender: Email sender address
        recipient: Email recipient address
        subject: Email subject line
        body: Email body content
        headers: Optional email headers
        use_gemini: Force Gemini on/off (default: smart routing)
    
    Returns:
        Comprehensive phishing analysis with ML + optional semantic insights
    """
    
    headers = headers or {}
    parsed_sender = self._parse_sender(sender)

    # ===== LAYER 1: Fast ML Baseline =====
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
    
    # ===== LAYER 2: Smart Gemini Routing =====
    # Decide whether to use Gemini for semantic analysis
    use_gemini_analysis = use_gemini
    if use_gemini_analysis is None:
        # Smart routing based on ML confidence
        if overall_risk < 0.25:
            use_gemini_analysis = False  # Obviously safe
        elif overall_risk > 0.80:
            use_gemini_analysis = True   # Confirm phishing + get explanation
        else:
            use_gemini_analysis = True   # Ambiguous - refine with Gemini
    
    # ===== LAYER 3: Gemini Semantic Analysis (optional) =====
    gemini_analysis = {}
    hybrid_explanation = None
    final_risk = overall_risk
    analysis_type = "ML_ONLY"
    
    if use_gemini_analysis and self.use_gemini:
        try:
            # Get semantic analysis from Gemini
            gemini_analysis = self.gemini_analyzer.analyze_email_semantics(
                sender=sender,
                subject=subject,
                body=body,
                urls=self._extract_urls(body),
                ml_scores=scores
            )
            
            # Blend ML and Gemini scores intelligently
            ml_confidence = self._calculate_confidence(overall_risk, threats)
            gemini_confidence = gemini_analysis.get('threat_confidence', 0.5)
            
            final_risk = create_hybrid_score(
                overall_risk,
                gemini_confidence,
                ml_confidence
            )
            
            # Update verdict based on hybrid score
            hybrid_threats = threats + gemini_analysis.get('tactics_detected', [])
            verdict = self._determine_verdict(final_risk, hybrid_threats)
            
            # Generate hybrid explanation
            hybrid_explanation = self.gemini_analyzer.generate_hybrid_explanation(
                sender=sender,
                ml_scores=scores,
                gemini_analysis=gemini_analysis
            )
            
            analysis_type = "HYBRID_ML_GEMINI"
            
        except Exception as e:
            # Fallback to ML-only if Gemini fails
            print(f"Gemini analysis failed: {e}")
            gemini_analysis = {'error': str(e)}
            analysis_type = "ML_ONLY_GEMINI_FAILED"
    
    # ===== LAYER 4: Add Gemini-specific threats =====
    if gemini_analysis and not gemini_analysis.get('error'):
        threat_type = gemini_analysis.get('threat_type', '')
        if threat_type and threat_type not in threats:
            threats.append(f"Gemini Detected: {threat_type}")
        
        # Add contextual issues as threats
        contextual_issues = gemini_analysis.get('contextual_issues', [])
        for issue in contextual_issues[:3]:  # Limit to 3
            if 'Contextual Issue' not in threats:
                threats.append(f"Contextual Issue: {issue}")
    
    # ===== LAYER 5: Generate Final Response =====
    response = {
        'overall_risk_score': round(final_risk, 3),
        'verdict': verdict,
        'is_phishing': verdict == 'phishing',
        'confidence': self._calculate_confidence(final_risk, threats),
        'analysis_type': analysis_type,  # NEW: Shows which models used
        
        # ML Analysis (structured, numerical)
        'ml_analysis': {
            'component_scores': scores,
            'ml_scores': ml_scores,
        },
        
        # Gemini Analysis (semantic, contextual)
        'gemini_analysis': gemini_analysis if gemini_analysis else None,
        
        # Combined Results
        'threats': threats,
        'recommendations': self._generate_recommendations(verdict, final_risk, threats),
        'normalized_sender': parsed_sender['email'] or parsed_sender['raw'],
        'raw_sender': parsed_sender['raw'],
        
        # Model Information
        'phase2_models_enabled': self.phase2_models.is_ready,
        'gemini_enabled': self.gemini_enabled,
        'phase2_data_sources': self.phase2_models.metadata.get('data_sources', []),
        
        # Enhanced Explanation (NEW)
        'explanation': hybrid_explanation or self._generate_explanation(verdict, scores, threats),
    }
    
    # Store in database
    try:
        email = Email(
            sender=sender,
            recipient=recipient,
            subject=subject,
            content=body,
            phishing_score=int(response['overall_risk_score'] * 100),
            is_phishing=response['is_phishing'],
            analysis_details=json.dumps(response)
        )
        db.session.add(email)
        db.session.commit()
    except Exception as e:
        print(f"Database error: {e}")
    
    return response


# =====================================================================
# STEP 4: Add helper method for Gemini-enhanced explanations
# =====================================================================

def _generate_explanation(self, verdict: str, scores: Dict, threats: List[str]) -> str:
    """
    Generate explanation using component scores if Gemini not available.
    
    Fallback for when Gemini analysis isn't used.
    """
    
    if verdict == 'phishing':
        main_issue = 'likely phishing'
        action = 'Do not click links or reply with personal information'
    elif verdict == 'suspicious':
        main_issue = 'suspicious indicators'
        action = 'Exercise caution before clicking links or downloading attachments'
    else:
        main_issue = 'appears safe'
        action = 'You can safely interact with this email'
    
    # Find highest scoring component
    highest_component = max(scores.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
    
    explanation = (
        f"This email {main_issue} based on analysis of sender reputation, "
        f"content, and URLs. The main concern is {highest_component[0].replace('_', ' ')} "
        f"({highest_component[1]:.1%} suspicious). {action}."
    )
    
    return explanation


# =====================================================================
# STEP 5: Update requirements.txt
# =====================================================================

"""
Add to backend/requirements.txt:
"""

# google-generativeai==0.4.1


# =====================================================================
# STEP 6: Add to .env file
# =====================================================================

"""
Add to backend/.env:
"""

# Gemini API Configuration
GEMINI_API_KEY=AIzaSyB9jAxAKVJkenTGwe9rZtYTDmAy0G744QA
USE_GEMINI=true
GEMINI_MODEL=gemini-2.0-flash-exp


# =====================================================================
# STEP 7: Update API Response Format (email_routes.py)
# =====================================================================

"""
Modify the response in email_routes.py analyze_email endpoint:
"""

@email_bp.route('/api/email/analyze', methods=['POST'])
def analyze_email():
    """Analyze email for phishing."""
    
    data = request.get_json()
    
    # Validate input
    required_fields = ['sender', 'recipient', 'subject', 'content']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Run analysis WITH Gemini hybrid approach
    detector = PhishingDetector()
    result = detector.analyze_email(
        sender=data['sender'],
        recipient=data['recipient'],
        subject=data['subject'],
        body=data['content'],
        headers=data.get('headers'),
        use_gemini=True  # Enable Gemini
    )
    
    # Return enhanced response
    return jsonify({
        'phishing_score': int(result['overall_risk_score'] * 100),
        'verdict': result['verdict'],
        'is_phishing': result['is_phishing'],
        'confidence': round(result['confidence'], 2),
        'analysis_type': result['analysis_type'],
        
        # Detailed Analysis
        'details': {
            'ml_scores': result['ml_analysis']['component_scores'],
            'gemini_threats': result['gemini_analysis'].get('tactics_detected', []) if result['gemini_analysis'] else [],
            'all_threats': result['threats'],
        },
        
        # explanations
        'explanation': result.get('explanation', ''),
        'recommendations': result['recommendations'],
        
        # Model Info
        'analysis_info': {
            'ml_models_used': 'Random Forest (URL) + Logistic Regression (Content)',
            'gemini_enabled': result['gemini_enabled'],
            'analysis_type': result['analysis_type'],
        }
    })


# =====================================================================
# INSTALLATION INSTRUCTIONS
# =====================================================================

"""
1. Copy gemini_analyzer.py to backend/services/

2. Install package:
   pip install google-generativeai

3. Update backend/.env with GEMINI_API_KEY

4. Apply changes to phishing_detector.py:
   - Add import at top
   - Add gemini_analyzer initialization in __init__
   - Replace analyze_email method with hybrid version
   - Add _generate_explanation helper

5. Update email_routes.py with enhanced response format

6. Test:
   cd backend
   python app.py

7. Test endpoint:
   curl -X POST http://127.0.0.1:5000/api/email/analyze \\
     -H "Content-Type: application/json" \\
     -d '{
       "sender": "ceo@company.com",
       "recipient": "finance@company.com",
       "subject": "Invoice Payment - URGENT",
       "content": "Please process payment to new vendor account..."
     }'

Expected response will include:
- ML scores (structured numeric analysis)
- Gemini analysis (semantic threat classification)
- Hybrid score (combined confidence)
- Detailed explanation
- Specific recommendations
"""
