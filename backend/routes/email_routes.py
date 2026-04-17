from flask import Blueprint, request, jsonify
from models import db, Email, ThreatAlert, AnalysisLog
from services.hybrid_analyzer import HybridPhishingAnalyzer
from datetime import datetime
import json
from pathlib import Path

email_bp = Blueprint('emails', __name__, url_prefix='/api/emails')
detector = HybridPhishingAnalyzer()


@email_bp.route('/analyze', methods=['POST'])
def analyze_email():
    data = request.get_json()

    required_fields = ['sender', 'recipient', 'subject', 'body']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields: sender, recipient, subject, body'}), 400

    sender = data.get('sender', '').strip()
    recipient = data.get('recipient', '').strip().lower()
    subject = data.get('subject', '').strip()
    body = data.get('body', '').strip()
    headers = data.get('headers', {})

    try:
        analysis_result = detector.analyze_email(sender, recipient, subject, body, headers)
        normalized_sender = analysis_result.get('normalized_sender') or sender

        final_risk_score = analysis_result.get('overall_risk_score', 0.0)
        final_is_phishing = analysis_result.get('is_phishing', False)

        email = Email(
            sender=normalized_sender.lower(),
            recipient=recipient,
            subject=subject,
            body=body,
            headers=headers,
            risk_score=final_risk_score,
            is_phishing=final_is_phishing,
            analysis_details=analysis_result
        )
        db.session.add(email)
        db.session.flush()

        threats = analysis_result.get('threats', [])
        if threats and threats[0] != 'No immediate threats detected':
            for threat in threats:
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
                    threat_details={
                        'detection_method': analysis_result.get('decision_authority', 'hybrid'),
                        'analysis_type': analysis_result.get('analysis_type', 'unknown')
                    }
                )
                db.session.add(alert)

        log = AnalysisLog(
            email_id=email.id,
            action='EMAIL_ANALYZED',
            details={
                'risk_score': final_risk_score,
                'is_phishing': final_is_phishing,
                'decision_authority': analysis_result.get('decision_authority', 'baseline_ml')
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
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        is_phishing = request.args.get('is_phishing', None)

        query = Email.query
        if is_phishing is not None:
            is_phishing_bool = is_phishing.lower() == 'true'
            query = query.filter_by(is_phishing=is_phishing_bool)

        total = query.count()
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
            }
            for threat in email.threats
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
    try:
        total_emails = Email.query.count()
        phishing_detected = Email.query.filter_by(is_phishing=True).count()
        safe_emails = Email.query.filter_by(is_phishing=False).count()

        avg_risk = db.session.query(db.func.avg(Email.risk_score)).scalar() or 0.0

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


def _load_model_comparison_report():
    report_path = Path(__file__).resolve().parents[1] / 'artifacts' / 'model_comparison' / 'model_comparison_report.json'

    if not report_path.exists():
        return {
            'available': False,
            'report_path': str(report_path),
            'message': 'Model comparison report not found. Run backend/train_phase2_model_comparison.py first.',
            'report': None,
        }

    try:
        with report_path.open('r', encoding='utf-8') as f:
            report = json.load(f)

        return {
            'available': True,
            'report_path': str(report_path),
            'message': 'Model comparison report loaded successfully.',
            'report': report,
        }
    except Exception as exc:
        return {
            'available': False,
            'report_path': str(report_path),
            'message': f'Failed to load model comparison report: {exc}',
            'report': None,
        }


@email_bp.route('/phase2-model-comparison', methods=['GET'])
def get_phase2_model_comparison():
    try:
        metadata = detector.phase2_models.metadata if getattr(detector, "phase2_models", None) else {}
        report_path = Path(__file__).resolve().parents[1] / 'artifacts' / 'model_comparison' / 'model_comparison_report.json'

        report = None
        available = False
        message = 'Model comparison report not found.'

        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding='utf-8'))
                available = True
                message = 'Model comparison report loaded successfully.'
            except Exception as exc:
                message = f'Could not read comparison report: {exc}'

        return jsonify({
            'phase2_enabled': detector.phase2_models.is_ready if getattr(detector, "phase2_models", None) else False,
            'trained_at': metadata.get('trained_at'),
            'content_metrics': metadata.get('content_metrics', {}),
            'url_metrics': metadata.get('url_metrics', {}),
            'comparison': {
                'available': available,
                'report_path': str(report_path),
                'message': message,
                'report': report,
            },
            'current_models': {
                'url': {
                    'name': 'Random Forest',
                    'metrics': metadata.get('url_metrics', {}),
                },
                'content': {
                    'name': 'Logistic Regression',
                    'metrics': metadata.get('content_metrics', {}),
                },
            },
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@email_bp.route('/<int:email_id>/mark-phishing', methods=['POST'])
def mark_as_phishing(email_id):
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({'error': 'Email not found'}), 404

        email.is_phishing = True
        db.session.commit()

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
    try:
        email = Email.query.get(email_id)
        if not email:
            return jsonify({'error': 'Email not found'}), 404

        email.is_phishing = False
        db.session.commit()

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