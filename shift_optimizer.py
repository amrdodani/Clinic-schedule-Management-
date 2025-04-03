"""
Shift Optimization Module for Doctor Schedule Management System.
"""

from ortools.sat.python import cp_model
from models import Doctor, Shift, ScheduleEntry, db

def optimize_shifts(department_name, days, rooms, time_slots, dry_run=False):
    """
    Optimize shift assignments for a given department.
    If dry_run is True, return the proposed schedule without applying changes.
    """
    # Fetch doctors in the department
    doctors = Doctor.query.filter_by(department=department_name).all()
    if not doctors:
        raise ValueError(f"No doctors found in department: {department_name}")

    # Check if the existing schedule is already optimized
    if is_schedule_optimized(department_name, days, rooms, time_slots):
        print("The existing schedule is already optimized and valid. No optimization needed.")
        return []

    # Create the CP-SAT model
    model = cp_model.CpModel()

    # Variables: Assignments (doctor, day, room, time_slot)
    assignments = {}
    for doctor in doctors:
        for day in days:
            for room in rooms:
                for time_slot in time_slots:
                    assignments[(doctor.id, day, room, time_slot)] = model.NewBoolVar(
                        f"assign_d{doctor.id}_day{day}_room{room}_time{time_slot}"
                    )

    # Constraints
    # 1. Each room can have at most one doctor per time slot
    for day in days:
        for room in rooms:
            for time_slot in time_slots:
                model.Add(
                    sum(assignments[(doctor.id, day, room, time_slot)] for doctor in doctors) <= 1
                )

    # 2. Each doctor can have at most one shift per time slot
    for doctor in doctors:
        for day in days:
            for time_slot in time_slots:
                model.Add(
                    sum(assignments[(doctor.id, day, room, time_slot)] for room in rooms) <= 1
                )

    # 3. Full-time doctors must work exactly 8 hours per day
    for doctor in doctors:
        if doctor.contract_type == "Full-Time":
            for day in days:
                # Full-time doctors can work either a straight shift or a split shift
                straight_shift = sum(assignments[(doctor.id, day, room, time_slot)] * 4 for room in rooms for time_slot in ["08:00-12:00", "12:00-16:00"])
                split_shift = sum(assignments[(doctor.id, day, room, time_slot)] * 4 for room in rooms for time_slot in ["08:00-12:00", "16:00-20:00"])
                model.Add(straight_shift + split_shift == 8)

                # Thursday-specific constraints
                if day == "Thursday":
                    valid_morning_shifts = ["08:00-12:00"]  # Only valid morning shift for Thursday
                    valid_afternoon_shifts = ["18:00-22:00"]  # Valid afternoon shift for Thursday
                    morning_shift = sum(assignments[(doctor.id, day, room, time_slot)] * 4 for room in rooms for time_slot in valid_morning_shifts)
                    afternoon_shift = sum(assignments[(doctor.id, day, room, time_slot)] * 4 for room in rooms for time_slot in valid_afternoon_shifts)
                    model.Add(morning_shift + afternoon_shift == 8)

    # 4. Part-time doctors must work exactly 4 or 5 hours per day and only after 2:00 PM
    for doctor in doctors:
        if doctor.contract_type == "Part-Time":
            for day in days:
                part_time_hours = sum(assignments[(doctor.id, day, room, time_slot)] * 4 for room in rooms for time_slot in ["14:00-18:00", "18:00-22:00"])
                model.Add(part_time_hours >= 4)
                model.Add(part_time_hours <= 5)

                # Ensure part-time doctors only work after 2:00 PM
                for time_slot in ["08:00-12:00", "12:00-16:00"]:
                    model.Add(
                        sum(assignments[(doctor.id, day, room, time_slot)] for room in rooms) == 0
                    )

    # 5. Clinic capacity rules
    for day in days:
        for room in rooms:
            # Ensure no more than one full-time doctor per shift
            full_time_shifts = sum(assignments[(doctor.id, day, room, time_slot)] for doctor in doctors if doctor.contract_type == "Full-Time" for time_slot in ["08:00-12:00", "12:00-16:00", "16:00-20:00"])
            model.Add(full_time_shifts <= 1)

            # Ensure no more than two part-time doctors per day
            part_time_shifts = sum(assignments[(doctor.id, day, room, time_slot)] for doctor in doctors if doctor.contract_type == "Part-Time" for time_slot in ["14:00-18:00", "18:00-22:00"])
            model.Add(part_time_shifts <= 2)

    # Objective: Distribute shifts evenly among doctors
    total_shifts = sum(assignments[(doctor.id, day, room, time_slot)] for doctor in doctors for day in days for room in rooms for time_slot in time_slots)
    model.Maximize(total_shifts)

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Debugging: Log solver status
    if status == cp_model.OPTIMAL:
        print("Solver found an optimal solution.")
    elif status == cp_model.FEASIBLE:
        print("Solver found a feasible solution.")
    elif status == cp_model.INFEASIBLE:
        print("Solver found the problem to be infeasible.")
        print("Debugging constraints and variables:")
        for doctor in doctors:
            for day in days:
                for room in rooms:
                    for time_slot in time_slots:
                        print(f"Doctor {doctor.name}, Day {day}, Room {room}, Time Slot {time_slot}: {solver.BooleanValue(assignments[(doctor.id, day, room, time_slot)])}")
    elif status == cp_model.MODEL_INVALID:
        print("The model is invalid.")
    else:
        print("Solver returned an unknown status.")

    # Debugging: Log invalid assignments
    for doctor in doctors:
        for day in days:
            for room in rooms:
                for time_slot in time_slots:
                    if day == "Thursday" and time_slot not in ["08:00-12:00", "18:00-22:00"]:
                        print(f"Invalid assignment detected: ({doctor.id}, '{day}', '{room}', '{time_slot}')")

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("Optimal solution found!")
        proposed_schedule = []
        for doctor in doctors:
            for day in days:
                for room in rooms:
                    for time_slot in time_slots:
                        if solver.BooleanValue(assignments[(doctor.id, day, room, time_slot)]):
                            proposed_schedule.append({
                                "doctor": doctor.name,
                                "day": day,
                                "room": room,
                                "time_slot": time_slot,
                            })
                            if not dry_run:
                                # Create a new shift and schedule entry
                                shift = Shift(
                                    start_time=time_slot.split("-")[0],
                                    end_time=time_slot.split("-")[1],
                                    shift_type="Optimized",
                                    doctor_id=doctor.id,
                                )
                                db.session.add(shift)
                                db.session.commit()

                                schedule_entry = ScheduleEntry(
                                    day=day,
                                    room=room,
                                    shift_id=shift.id,
                                )
                                db.session.add(schedule_entry)
                                db.session.commit()
        return proposed_schedule
    else:
        print("No feasible solution found.")
        return []

def is_schedule_optimized(department_name, days, rooms, time_slots):
    """
    Check if the existing schedule is already optimized and valid.
    """
    schedule_entries = ScheduleEntry.query.join(Shift).join(Doctor).filter(Doctor.department == department_name).all()

    # Validate each schedule entry
    for entry in schedule_entries:
        doctor = entry.shift.assigned_doctor
        day = entry.day
        room = entry.room
        start_time = entry.shift.start_time
        end_time = entry.shift.end_time

        # Check for overlapping shifts in the same room
        overlapping_shifts = ScheduleEntry.query.join(Shift).filter(
            ScheduleEntry.day == day,
            ScheduleEntry.room == room,
            Shift.start_time < end_time,
            Shift.end_time > start_time,
            Shift.id != entry.shift_id
        ).count()
        if overlapping_shifts > 0:
            return False

        # Validate full-time doctor rules
        if doctor.contract_type == "Full-Time":
            shift_duration = (int(end_time.split(":")[0]) - int(start_time.split(":")[0])) * 60 + \
                             (int(end_time.split(":")[1]) - int(start_time.split(":")[1]))
            if shift_duration != 480:  # 8 hours = 480 minutes
                return False
            if day == "Thursday" and start_time not in ["08:00", "09:00"] and end_time not in ["12:00", "13:00", "18:00", "22:00"]:
                return False

        # Validate part-time doctor rules
        if doctor.contract_type == "Part-Time":
            if int(start_time.split(":")[0]) < 14:  # Must start after 2:00 PM
                return False
            shift_duration = (int(end_time.split(":")[0]) - int(start_time.split(":")[0])) * 60 + \
                             (int(end_time.split(":")[1]) - int(start_time.split(":")[1]))
            if shift_duration not in [240, 300]:  # 4 or 5 hours
                return False

    return True

def recommend_shifts(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    available_shifts = []
    for day in ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]:
        for time_slot in ["08:00-12:00", "12:00-16:00", "16:00-20:00"]:
            if doctor.is_available(day, time_slot.split("-")[0]):
                available_shifts.append({"day": day, "time_slot": time_slot})
    return available_shifts
