from flask import Blueprint, request, jsonify
from models import db, Email, ThreatAlert, AnalysisLog
from services.phishing_detector import PhishingDetector
from datetime import datetime

email_bp = Blueprint('emails', __name__, url_prefix='/api/emails')
detector = PhishingDetector()


@email_bp.route('/analyze', methods=['POST'])
def analyze_email():
    """
    Analyze email for phishing
    
    Request body:
    {
        "sender": "sender@example.com",
        "recipient": "recipient@example.com",
        "subject": "Email Subject",
        "body": "Email body content",
        "headers": {} (optional)
    }
    """
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['sender', 'recipient', 'subject', 'body']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields: sender, recipient, subject, body'}), 400
    
    sender = data.get('sender', '').strip()
    recipient = data.get('recipient', '').strip().lower()
    subject = data.get('subject', '').strip()
    body = data.get('body', '').strip()
    headers = data.get('headers', {})
    
    try:
        # Run AI analysis
        analysis_result = detector.analyze_email(sender, recipient, subject, body, headers)

        normalized_sender = analysis_result.get('normalized_sender') or sender
        
        # Save email to database
        email = Email(
            sender=normalized_sender.lower(),
            recipient=recipient,
            subject=subject,
            body=body,
            headers=headers,
            risk_score=analysis_result['overall_risk_score'],
            is_phishing=analysis_result['is_phishing'],
            analysis_details=analysis_result
        )
        db.session.add(email)
        db.session.flush()  # Get the email ID without committing
        
        # Create threat alerts if needed
        if analysis_result['threats'] and analysis_result['threats'][0] != 'No immediate threats detected':
            for threat in analysis_result['threats']:
                if analysis_result.get('verdict') == 'phishing':
                    severity = 'critical'
                elif analysis_result.get('verdict') == 'suspicious':
                    severity = 'high'
                else:
                    severity = 'medium'
                alert = ThreatAlert(
                    email_id=email.id,
                    threat_type=threat,
                    threat_description=f"Detected threat: {threat}",
                    severity=severity,
                    threat_details={'detection_method': 'AI Analysis'}
                )
                db.session.add(alert)
        
        # Log the analysis
        log = AnalysisLog(
            email_id=email.id,
            action='EMAIL_ANALYZED',
            details={
                'risk_score': analysis_result['overall_risk_score'],
                'is_phishing': analysis_result['is_phishing']
            }
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'email_id': email.id,
            'analysis': analysis_result,
            'message': 'Email analyzed successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@email_bp.route('/history', methods=['GET'])
def get_email_history():
    """
    Get email analysis history
    
    Query parameters:
    - limit: number of records to return (default: 50)
    - offset: pagination offset (default: 0)
    - is_phishing: filter by phishing status (true/false)
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        is_phishing = request.args.get('is_phishing', None)
        
        # Build query
        query = Email.query
        
        if is_phishing is not None:
            is_phishing_bool = is_phishing.lower() == 'true'
            query = query.filter_by(is_phishing=is_phishing_bool)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        emails = query.order_by(Email.analyzed_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'emails': [{
                'id': email.id,
                'sender': email.sender,
                'recipient': email.recipient,
                'subject': email.subject,
                'risk_score': email.risk_score,
                'is_phishing': email.is_phishing,
                'threat_count': len(email.threats),
                'analyzed_at': email.analyzed_at.isoformat()
            } for email in emails]
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_bp.route('/<int:email_id>', methods=['GET'])
def get_email_details(email_id):
    """Get detailed analysis for a specific email"""
    try:
        email = Email.query.get(email_id)
        
        if not email:
            return jsonify({'error': 'Email not found'}), 404
        
        threats = [
            {
                'id': threat.id,
                'type': threat.threat_type,
                'description': threat.threat_description,
                'severity': threat.severity,
                'details': threat.threat_details
            } for threat in email.threats
        ]
        
        return jsonify({
            'id': email.id,
            'sender': email.sender,
            'recipient': email.recipient,
            'subject': email.subject,
            'body': email.body,
            'risk_score': email.risk_score,
            'is_phishing': email.is_phishing,
            'analysis_details': email.analysis_details,
            'threats': threats,
            'analyzed_at': email.analyzed_at.isoformat(),
            'created_at': email.created_at.isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get phishing detection statistics"""
    try:
        total_emails = Email.query.count()
        phishing_detected = Email.query.filter_by(is_phishing=True).count()
        safe_emails = Email.query.filter_by(is_phishing=False).count()
        
        # Calculate average risk score
        avg_risk = db.session.query(db.func.avg(Email.risk_score)).scalar() or 0.0
        
        # Get threat types
        threats = db.session.query(
            ThreatAlert.threat_type,
            db.func.count(ThreatAlert.id)
        ).group_by(ThreatAlert.threat_type).all()
        
        threat_distribution = {threat_type: count for threat_type, count in threats}

        phase2_metrics = detector.phase2_models.metadata if detector.phase2_models else {}
        
        return jsonify({
            'total_emails': total_emails,
            'phishing_detected': phishing_detected,
            'safe_emails': safe_emails,
            'average_risk_score': round(avg_risk, 3),
            'phishing_percentage': round((phishing_detected / total_emails * 100) if total_emails > 0 else 0, 2),
            'threat_distribution': threat_distribution,
            'phase2_metrics': phase2_metrics,
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_bp.route('/phase2-metrics', methods=['GET'])
def get_phase2_metrics():
    """Get Phase 2 training metrics and model metadata."""
    try:
        metadata = detector.phase2_models.metadata if detector.phase2_models else {}

        return jsonify({
            'phase2_enabled': detector.phase2_models.is_ready if detector.phase2_models else False,
            'trained_at': metadata.get('trained_at'),
            'artifact_dir': metadata.get('artifact_dir'),
            'content_metrics': metadata.get('content_metrics', {}),
            'url_metrics': metadata.get('url_metrics', {}),
            'data_sources': metadata.get('data_sources', []),
            'notes': metadata.get('notes', []),
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_bp.route('/<int:email_id>/mark-phishing', methods=['POST'])
def mark_as_phishing(email_id):
    """Mark an email as phishing (user feedback)"""
    try:
        email = Email.query.get(email_id)
        
        if not email:
            return jsonify({'error': 'Email not found'}), 404
        
        email.is_phishing = True
        db.session.commit()
        
        # Log user feedback
        log = AnalysisLog(
            email_id=email.id,
            action='USER_MARKED_PHISHING',
            details={'user_feedback': True}
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'message': 'Email marked as phishing'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@email_bp.route('/<int:email_id>/mark-safe', methods=['POST'])
def mark_as_safe(email_id):
    """Mark an email as safe (user feedback)"""
    try:
        email = Email.query.get(email_id)
        
        if not email:
            return jsonify({'error': 'Email not found'}), 404
        
        email.is_phishing = False
        db.session.commit()
        
        # Log user feedback
        log = AnalysisLog(
            email_id=email.id,
            action='USER_MARKED_SAFE',
            details={'user_feedback': True}
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'message': 'Email marked as safe'}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
