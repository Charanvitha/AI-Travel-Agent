from datetime import datetime, timezone
from uuid import uuid4
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc)

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    preferred_language = db.Column(db.String(20), default="English")
    created_at = db.Column(db.DateTime(timezone=True), default=now)
    trips = db.relationship("Trip", backref="user", cascade="all, delete-orphan")
    family_profile = db.relationship("FamilyProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class FamilyProfile(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    user_id = db.Column(db.String(36), db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    adults_count = db.Column(db.Integer, default=2)
    children_age_ranges = db.Column(db.JSON, default=list)
    dietary_preferences = db.Column(db.JSON, default=list)
    accessibility_needs = db.Column(db.JSON, default=list)
    travel_pace = db.Column(db.String(20), default="balanced")
    interests = db.Column(db.JSON, default=list)

class Trip(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    user_id = db.Column(db.String(36), db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    origin = db.Column(db.String(160), nullable=False)
    destination = db.Column(db.String(160), nullable=False)
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10), nullable=False)
    total_budget = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="INR")
    travel_mode = db.Column(db.String(40), default="Car")
    status = db.Column(db.String(24), default="planning")
    current_version = db.Column(db.Integer, default=0)
    itinerary = db.Column(db.JSON, default=dict)
    checklist = db.Column(db.JSON, default=list)
    messages = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=now)
    versions = db.relationship("TripVersion", backref="trip", cascade="all, delete-orphan", passive_deletes=True)

class TripVersion(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=uid)
    trip_id = db.Column(db.String(36), db.ForeignKey("trip.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    itinerary_snapshot = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now)
    __table_args__ = (db.UniqueConstraint("trip_id", "version_number"),)
