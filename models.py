"""
Data Models for Doctor Schedule Management System.
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from datetime import datetime

db = SQLAlchemy()  # Initialize SQLAlchemy

class Doctor(db.Model):
    """
    Represents a doctor with a name, department, and additional details.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    room = db.Column(db.String(100))
    designation = db.Column(db.String(50))
    contract_type = db.Column(db.String(50))
    note = db.Column(db.Text)
    attachment = db.Column(db.String(200))
    shifts = db.relationship('Shift', backref='assigned_doctor', cascade="all, delete", lazy=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "department": self.department,
            "room": self.room,
            "designation": self.designation,
            "contract_type": self.contract_type,
            "note": self.note,
            "attachment": self.attachment,
        }

    def is_available(self, day, time):
        overlapping_shift = ScheduleEntry.query.join(Shift).filter(
            Shift.doctor_id == self.id,
            ScheduleEntry.day == day,
            Shift.start_time <= time,
            Shift.end_time >= time
        ).first()
        return overlapping_shift is None

class Room(db.Model):
    """
    Represents a room where doctors are assigned.
    """
    id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(100), nullable=False)
    department_name = db.Column(db.String(100), nullable=False)

class Department(db.Model):
    """
    Represents a department to which doctors belong.
    """
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.String(50), unique=True, nullable=False)
    department_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100))
    branch = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Shift(db.Model):
    """
    Represents a shift with start time, end time, shift type, and assigned doctor.
    """
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    shift_type = db.Column(db.String(50), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id', ondelete="CASCADE"), nullable=False)
    schedule_entries = db.relationship('ScheduleEntry', backref='linked_shift', cascade="all, delete", lazy=True)

class ScheduleEntry(db.Model):
    """
    Represents a single entry in the schedule, combining doctor, room, and shift.
    """
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(20), nullable=False)
    room = db.Column(db.String(100), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    shift = db.relationship('Shift', overlaps="linked_shift,schedule_entries")  # Added overlaps parameter
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnowledgeBase(db.Model):
    """
    Represents a knowledge base entry for FAQs or structured knowledge.
    """
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False, unique=True)
    answer = db.Column(db.Text, nullable=False)

# Automatically update `last_updated` for related models
def update_last_updated(mapper, connection, target):
    target.last_updated = datetime.utcnow()

event.listen(Doctor, 'before_update', update_last_updated)
event.listen(Department, 'before_update', update_last_updated)
event.listen(ScheduleEntry, 'before_update', update_last_updated)
