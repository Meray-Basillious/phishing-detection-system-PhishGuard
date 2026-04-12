from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# This will be initialized in app.py
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, analyst, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Email(db.Model):
    __tablename__ = 'emails'
    
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(120), nullable=False)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    headers = db.Column(db.JSON, nullable=True)
    risk_score = db.Column(db.Float, default=0.0)
    is_phishing = db.Column(db.Boolean, default=False)
    analysis_details = db.Column(db.JSON, nullable=True)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    threats = db.relationship('ThreatAlert', backref='email', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Email {self.subject[:50]}...>'


class ThreatAlert(db.Model):
    __tablename__ = 'threat_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)
    threat_type = db.Column(db.String(100), nullable=False)
    threat_description = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    threat_details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ThreatAlert {self.threat_type}>'


class AnalysisLog(db.Model):
    __tablename__ = 'analysis_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisLog {self.action}>'
