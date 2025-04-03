"""
Data Handling for Doctor Schedule Management System.
"""

from models import Doctor, Room, Shift, ScheduleEntry
from models import db  # Ensure the database is imported correctly

def get_schedule_entries(day=None, room=None, department=None):
    """
    Retrieve schedule entries, optionally filtered by day, room, or department.
    """
    query = ScheduleEntry.query.join(Shift).join(Doctor)
    if day:
        query = query.filter(ScheduleEntry.day == day)
    if room:
        query = query.filter(ScheduleEntry.room == room)
    if department:
        query = query.filter(Doctor.department == department)
    return query.all()
