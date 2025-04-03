"""
Application Entrypoint for Doctor Schedule Management System using Flask.
"""

from flask import Flask, request, send_file, render_template, redirect, url_for, Response, jsonify
from models import db, Doctor, Shift, ScheduleEntry, Department, Room, KnowledgeBase
from visualization import render_gantt_chart
from io import BytesIO
from reportlab.pdfgen import canvas
from flask_migrate import Migrate
from shift_optimizer import optimize_shifts, is_schedule_optimized
from transformers import pipeline
from reportlab.lib.pagesizes import letter
import os
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

migrate = Migrate(app, db)

# Initialize the NLP model
chatbot_model = pipeline("text-generation", model="gpt2", pad_token_id=50256)


@app.route("/")
def home():
    departments = Department.query.all()
    return render_template("home.html", departments=departments)


@app.route("/departments", methods=["GET", "POST"])
def manage_departments():
    if request.method == "POST":
        try:
            department_name = request.form["department_name"]
            location = request.form["location"]
            branch = request.form["branch"]
            department_id = f"{branch}-{department_name[:2].upper()}{len(Department.query.filter_by(branch=branch).all()) + 1:02d}"
            department = Department(department_id=department_id, department_name=department_name, location=location, branch=branch)
            db.session.add(department)
            db.session.commit()
            return redirect(url_for("manage_departments"))
        except Exception as e:
            return render_template("departments.html", departments=Department.query.all(), message=f"Error: {e}")

    departments = Department.query.all()
    return render_template("departments.html", departments=departments)


@app.route("/edit-department/<string:department_id>", methods=["GET", "POST"])
def edit_department(department_id):
    department = Department.query.filter_by(department_id=department_id).first()
    if not department:
        return redirect(url_for("manage_departments"))

    if request.method == "POST":
        try:
            department.department_name = request.form["department_name"]
            department.location = request.form["location"]
            db.session.commit()
            return redirect(url_for("manage_departments"))
        except Exception as e:
            return render_template("edit_department.html", department=department, message=f"Error: {e}")

    return render_template("edit_department.html", department=department)


@app.route("/delete-department/<string:department_id>", methods=["POST"])
def delete_department(department_id):
    department = Department.query.filter_by(department_id=department_id).first()
    if department:
        try:
            db.session.delete(department)
            db.session.commit()
        except Exception as e:
            return redirect(url_for("manage_departments", message=f"Error: {e}"))
    return redirect(url_for("manage_departments"))


@app.route("/rooms", methods=["GET", "POST"])
def manage_rooms():
    if request.method == "POST":
        try:
            room_name = request.form["room_name"]
            department_name = request.form["department_name"]
            branch = request.form["branch"]
            room_name_with_branch = f"{room_name} - {branch}"

            if Room.query.filter_by(room_name=room_name_with_branch, department_name=department_name).first():
                return render_template("rooms.html", rooms=Room.query.all(), departments=Department.query.all(), message="Room already exists.")

            room = Room(room_name=room_name_with_branch, department_name=department_name)
            db.session.add(room)
            db.session.commit()
            return redirect(url_for("manage_rooms"))
        except Exception as e:
            return render_template("rooms.html", rooms=Room.query.all(), departments=Department.query.all(), message=f"Error: {e}")

    return render_template("rooms.html", rooms=Room.query.all(), departments=Department.query.all())


@app.route("/edit-room/<string:room_name>", methods=["GET", "POST"])
def edit_room(room_name):
    room = Room.query.filter_by(room_name=room_name).first()
    if not room:
        return redirect(url_for("manage_rooms"))

    if request.method == "POST":
        try:
            room.room_name = request.form["room_name"]
            room.department_name = request.form["department_name"]
            branch = request.form["branch"]
            room.room_name = f"{room.room_name.split(' - ')[0]} - {branch}"
            db.session.commit()
            return redirect(url_for("manage_rooms"))
        except Exception as e:
            return render_template("edit_room.html", room=room, departments=Department.query.all(), message=f"Error: {e}")

    return render_template("edit_room.html", room=room, departments=Department.query.all())


@app.route("/delete-room/<string:room_name>", methods=["POST"])
def delete_room(room_name):
    room = Room.query.filter_by(room_name=room_name).first()
    if room:
        try:
            db.session.delete(room)
            db.session.commit()
        except Exception as e:
            return redirect(url_for("manage_rooms", message=f"Error: {e}"))
    return redirect(url_for("manage_rooms"))


@app.route("/doctors", methods=["GET", "POST"])
def manage_doctors():
    if request.method == "POST":
        try:
            doctor = Doctor(
                name=request.form["doctor_name"],
                department=request.form["department_name"],
                designation=request.form["designation"],
                contract_type=request.form["contract_type"],
                note=request.form["note"],
                attachment=request.files["attachment"].filename if request.files["attachment"] else None
            )
            db.session.add(doctor)
            db.session.commit()
            return redirect(url_for("manage_doctors"))
        except Exception as e:
            return render_template("doctors.html", doctors=Doctor.query.all(), departments=Department.query.all(), message=f"Error: {e}")

    doctors = Doctor.query.all()
    departments = Department.query.all()
    return render_template("doctors.html", doctors=doctors, departments=departments)


@app.route("/delete-doctor/<int:doctor_id>", methods=["POST"])
def delete_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if doctor:
        try:
            db.session.delete(doctor)
            db.session.commit()
        except Exception as e:
            return redirect(url_for("manage_doctors", message=f"Error: {e}"))
    return redirect(url_for("manage_doctors"))


@app.route("/edit-doctor/<int:doctor_id>", methods=["GET", "POST"])
def edit_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return redirect(url_for("manage_doctors"))

    if request.method == "POST":
        try:
            doctor.name = request.form["doctor_name"]
            doctor.department = request.form["department_name"]
            doctor.designation = request.form["designation"]
            doctor.contract_type = request.form["contract_type"]
            doctor.note = request.form["note"]

            attachment = request.files["attachment"]
            if attachment and attachment.filename:
                attachment_path = f"attachments/{doctor.name}_{attachment.filename}"
                os.makedirs("attachments", exist_ok=True)
                attachment.save(attachment_path)
                doctor.attachment = attachment_path

            db.session.commit()
            return redirect(url_for("manage_doctors"))
        except Exception as e:
            return render_template("edit_doctor.html", doctor=doctor, departments=Department.query.all(), message=f"Error: {e}")

    return render_template("edit_doctor.html", doctor=doctor, departments=Department.query.all())


@app.route("/schedule", methods=["GET", "POST"])
def view_schedule():
    if request.method == "POST":
        try:
            selected_entries = request.form.getlist("selected_entries")
            if selected_entries:
                for entry_id in selected_entries:
                    entry = ScheduleEntry.query.get(entry_id)
                    if entry:
                        db.session.delete(entry)
                db.session.commit()
                return redirect(url_for("view_schedule"))
        except Exception as e:
            return render_template("schedule.html", schedule=[], rooms=Room.query.all(), doctors=Doctor.query.all(), departments=Department.query.all(), message=f"Error: {e}")

    filter_day = request.args.get("filter_day")
    filter_room = request.args.get("filter_room")
    filter_doctor = request.args.get("filter_doctor")

    query = ScheduleEntry.query.join(Shift).join(Doctor)
    if filter_day:
        query = query.filter(ScheduleEntry.day == filter_day)
    if filter_room:
        query = query.filter(ScheduleEntry.room == filter_room)
    if filter_doctor:
        query = query.filter(Doctor.name == filter_doctor)

    schedule = query.all()
    rooms = Room.query.all()
    doctors = Doctor.query.all()
    departments = Department.query.all()
    return render_template("schedule.html", schedule=schedule, rooms=rooms, doctors=doctors, departments=departments)


@app.route("/render-gantt", methods=["GET", "POST"])
def render_gantt():
    selected_department = request.form.get("department_filter", None)

    try:
        if (selected_department):
            query = ScheduleEntry.query.join(Shift).join(Doctor).filter(Doctor.department == selected_department)
            schedule = query.all()

            if not schedule:
                message = f"No schedule found for the selected department: {selected_department}."
                return render_template("gantt.html", message=message, departments=Department.query.all(), selected_department=selected_department)

            gantt_data = []
            seen_entries = set()
            for entry in schedule:
                key = (entry.room, entry.day, entry.shift.start_time, entry.shift.end_time, entry.shift.assigned_doctor.name)
                if key not in seen_entries:
                    gantt_data.append({
                        "Task": f"{entry.room} | {entry.day}",
                        "Start": f"2023-01-01T{entry.shift.start_time}:00",
                        "Finish": f"2023-01-01T{entry.shift.end_time}:00",
                        "Doctor": entry.shift.assigned_doctor.name,
                        "ShiftDetails": f"{entry.shift.start_time} - {entry.shift.end_time}",
                        "ContractType": entry.shift.assigned_doctor.contract_type,
                    })
                    seen_entries.add(key)

            # Fetch the latest update timestamps for each table
            schedule_last_updated = db.session.query(db.func.max(ScheduleEntry.last_updated)).scalar()
            doctor_last_updated = db.session.query(db.func.max(Doctor.last_updated)).scalar()
            department_last_updated = db.session.query(db.func.max(Department.last_updated)).scalar()

            # Determine the latest timestamp programmatically
            last_updated = max(filter(None, [schedule_last_updated, doctor_last_updated, department_last_updated]))

            file_path = "static/gantt_chart.png"
            try:
                render_gantt_chart(gantt_data, file_path, department_name=selected_department, last_updated=last_updated)
            except Exception as e:
                print(f"Error while generating the Gantt chart: {e}")  # Debugging log
                message = f"An error occurred while generating the Gantt chart: {e}"
                return render_template("gantt.html", message=message, departments=Department.query.all(), selected_department=selected_department)

            return render_template(
                "gantt.html",
                departments=Department.query.all(),
                selected_department=selected_department,
                gantt_image=file_path,
            )
        else:
            message = "Please select a department to view the Gantt chart."
            return render_template("gantt.html", message=message, departments=Department.query.all())
    except Exception as e:
        print(f"Unexpected error in /render-gantt: {e}")  # Debugging log
        return render_template("gantt.html", message="An unexpected error occurred. Please try again later.", departments=Department.query.all())


@app.route("/add-shift", methods=["GET", "POST"])
def add_shift():
    if request.method == "POST":
        try:
            day = request.form["day"]
            room = request.form["room"]
            doctor_name = request.form["doctor_name"]
            department = request.form["department"]
            start_time = request.form["start_time"]
            end_time = request.form["end_time"]
            shift_type = request.form["shift_type"]

            doctor = Doctor.query.filter_by(name=doctor_name).first()
            if not doctor:
                return render_template("add_shift.html", message="Doctor not found.", doctors=Doctor.query.all(), rooms=Room.query.all(), departments=Department.query.all())

            overlapping_shift = ScheduleEntry.query.join(Shift).filter(
                ScheduleEntry.day == day,
                Shift.doctor_id == doctor.id,
                Shift.start_time < end_time,
                Shift.end_time > start_time
            ).first()
            if overlapping_shift:
                return render_template("add_shift.html", message="Shift overlaps with an existing shift.", doctors=Doctor.query.all(), rooms=Room.query.all(), departments=Department.query.all())

            shift = Shift(
                start_time=start_time,
                end_time=end_time,
                shift_type=shift_type,
                doctor_id=doctor.id
            )
            db.session.add(shift)
            db.session.commit()

            entry = ScheduleEntry(day=day, room=room, shift_id=shift.id)
            db.session.add(entry)
            db.session.commit()

            return redirect(url_for("view_schedule"))
        except Exception as e:
            return render_template("add_shift.html", message=f"Error: {e}", doctors=Doctor.query.all(), rooms=Room.query.all(), departments=Department.query.all())

    return render_template("add_shift.html", doctors=Doctor.query.all(), rooms=Room.query.all(), departments=Department.query.all())


@app.route("/edit-schedule/<int:entry_index>", methods=["GET", "POST"])
def edit_schedule(entry_index):
    entry = ScheduleEntry.query.get(entry_index)
    if not entry:
        return redirect(url_for("view_schedule"))

    if request.method == "POST":
        try:
            doctor_name = request.form["doctor_name"]
            start_time = request.form["start_time"]
            end_time = request.form["end_time"]
            shift_type = request.form["shift_type"]

            doctor = Doctor.query.filter_by(name=doctor_name).first()
            if not doctor:
                return render_template(
                    "edit_schedule.html",
                    entry=entry,
                    entry_index=entry_index,
                    doctors=Doctor.query.all(),
                    rooms=Room.query.filter_by(department_name=entry.shift.assigned_doctor.department).all(),
                    departments=Department.query.all(),
                    message=["Doctor not found."]
                )

            overlapping_shift = ScheduleEntry.query.join(Shift).filter(
                ScheduleEntry.day == entry.day,
                Shift.doctor_id == doctor.id,
                Shift.start_time < end_time,
                Shift.end_time > start_time,
                ScheduleEntry.id != entry.id
            ).first()
            if overlapping_shift:
                return render_template(
                    "edit_schedule.html",
                    entry=entry,
                    entry_index=entry_index,
                    doctors=Doctor.query.all(),
                    rooms=Room.query.filter_by(department_name=entry.shift.assigned_doctor.department).all(),
                    departments=Department.query.all(),
                    message=["Shift overlaps with an existing shift."]
                )

            room_conflict = ScheduleEntry.query.join(Shift).filter(
                ScheduleEntry.day == entry.day,
                ScheduleEntry.room == entry.room,
                Shift.start_time < end_time,
                Shift.end_time > start_time,
                ScheduleEntry.id != entry.id
            ).first()
            if room_conflict:
                return render_template(
                    "edit_schedule.html",
                    entry=entry,
                    entry_index=entry_index,
                    doctors=Doctor.query.all(),
                    rooms=Room.query.filter_by(department_name=entry.shift.assigned_doctor.department).all(),
                    departments=Department.query.all(),
                    message=["Room is already occupied during the selected time."]
                )

            entry.shift.start_time = start_time
            entry.shift.end_time = end_time
            entry.shift.shift_type = shift_type
            entry.shift.doctor_id = doctor.id
            db.session.commit()

            return redirect(url_for("view_schedule"))
        except Exception as e:
            return render_template(
                "edit_schedule.html",
                entry=entry,
                entry_index=entry_index,
                doctors=Doctor.query.all(),
                rooms=Room.query.filter_by(department_name=entry.shift.assigned_doctor.department).all(),
                departments=Department.query.all(),
                message=[f"Error: {e}"]
            )

    return render_template(
        "edit_schedule.html",
        entry=entry,
        entry_index=entry_index,
        doctors=Doctor.query.all(),
        rooms=Room.query.filter_by(department_name=entry.shift.assigned_doctor.department).all(),
        departments=Department.query.all(),
    )


@app.route("/delete-schedule/<int:entry_index>", methods=["POST"])
def delete_schedule(entry_index):
    entry = ScheduleEntry.query.get(entry_index)
    if entry:
        shift = entry.shift
        db.session.delete(entry)
        db.session.commit()
        if not ScheduleEntry.query.filter_by(shift_id=shift.id).first():
            db.session.delete(shift)
            db.session.commit()
    return redirect(url_for("view_schedule"))


@app.route("/copy-shift/<int:entry_index>", methods=["GET", "POST"])
def copy_shift(entry_index):
    entry = ScheduleEntry.query.get(entry_index)
    if not entry:
        return redirect(url_for("view_schedule"))

    if request.method == "POST":
        selected_days = request.form.getlist("days")
        for day in selected_days:
            overlapping_shift = ScheduleEntry.query.join(Shift).filter(
                ScheduleEntry.day == day,
                Shift.doctor_id == entry.shift.doctor_id,
                Shift.start_time == entry.shift.start_time,
                Shift.end_time == entry.shift.end_time,
            ).first()
            if not overlapping_shift:
                new_entry = ScheduleEntry(
                    day=day,
                    room=entry.room,
                    shift_id=entry.shift_id
                )
                db.session.add(new_entry)
        db.session.commit()
        return redirect(url_for("view_schedule"))
    return render_template("copy_shift.html", entry=entry, entry_index=entry_index, doctors=Doctor.query.all(), rooms=Room.query.all(), departments=Department.query.all())


@app.route("/attachments/<path:filename>")
def serve_attachment(filename):
    return send_file(os.path.join("attachments", filename))


@app.route("/statistics", methods=["GET", "POST"])
def statistics():
    selected_department = request.form.get("department_filter", None)
    query_doctors = Doctor.query
    query_shifts = Shift.query
    query_schedule_entries = ScheduleEntry.query
    if selected_department:
        query_doctors = query_doctors.filter(Doctor.department == selected_department)
        query_shifts = query_shifts.join(Doctor).filter(Doctor.department == selected_department)
        query_schedule_entries = query_schedule_entries.join(Shift).join(Doctor).filter(Doctor.department == selected_department)
    total_doctors = query_doctors.count()
    total_shifts = query_shifts.count()
    total_schedule_entries = query_schedule_entries.count()
    total_departments = Department.query.count()
    total_rooms = Room.query.filter(Room.department_name == selected_department).count() if selected_department else Room.query.count()
    part_time_shifts = query_shifts.filter(Shift.shift_type == "Part-Time").count()
    full_time_shifts = query_shifts.filter(Shift.shift_type == "Full-Time").count()
    doctor_workload = db.session.query(
        Doctor.name, db.func.count(ScheduleEntry.id)
    ).join(Shift, Shift.doctor_id == Doctor.id).join(ScheduleEntry, ScheduleEntry.shift_id == Shift.id)
    if selected_department:
        doctor_workload = doctor_workload.filter(Doctor.department == selected_department)
    doctor_workload = doctor_workload.group_by(Doctor.name).all()
    department_workload = db.session.query(
        Department.department_name, db.func.count(ScheduleEntry.id)
    ).join(Doctor, Doctor.department == Department.department_name).join(Shift, Shift.doctor_id == Doctor.id).join(ScheduleEntry, ScheduleEntry.shift_id == Shift.id)
    if selected_department:
        department_workload = department_workload.filter(Department.department_name == selected_department)
    department_workload = department_workload.group_by(Department.department_name).all()
    time_slots = [f"{hour}:00" for hour in range(8, 24)]
    workload_distribution = {slot: 0 for slot in time_slots}
    for entry in query_schedule_entries.all():
        start_time = int(entry.shift.start_time.split(":")[0])
        end_time = int(entry.shift.end_time.split(":")[0])
        for hour in range(start_time, end_time):
            slot = f"{hour}:00"
            if slot in workload_distribution:
                workload_distribution[slot] += 1
    full_time_doctors = db.session.query(
        Department.department_name, db.func.count(Doctor.id)
    ).join(Doctor, Doctor.department == Department.department_name)  # Add explicit join condition
    if selected_department:
        full_time_doctors = full_time_doctors.filter(Doctor.department == selected_department)
    full_time_doctors = full_time_doctors.group_by(Department.department_name).all()
    part_time_doctors = db.session.query(
        Department.department_name, db.func.count(Doctor.id)
    ).join(Doctor, Doctor.department == Department.department_name)  # Add explicit join condition
    if selected_department:
        part_time_doctors = part_time_doctors.filter(Doctor.department == selected_department)
    part_time_doctors = part_time_doctors.group_by(Department.department_name).all()
    return render_template(
        "statistics.html",
        total_doctors=total_doctors,
        total_shifts=total_shifts,
        total_schedule_entries=total_schedule_entries,
        total_departments=total_departments,
        total_rooms=total_rooms,
        full_time_shifts=full_time_shifts,
        part_time_shifts=part_time_shifts,
        doctor_workload=doctor_workload,
        department_workload=department_workload,
        workload_distribution=workload_distribution,
        full_time_doctors=full_time_doctors,
        part_time_doctors=part_time_doctors,
        selected_department=selected_department,
        departments=Department.query.all(),
    )


@app.route("/export-statistics/excel")
def export_statistics_excel():
    doctor_workload = db.session.query(
        Doctor.name, db.func.count(ScheduleEntry.id)
    ).join(Shift, Shift.doctor_id == Doctor.id).join(ScheduleEntry, ScheduleEntry.shift_id == Shift.id).group_by(Doctor.name).all()
    department_workload = db.session.query(
        Department.department_name, db.func.count(ScheduleEntry.id)
    ).join(Doctor, Doctor.department == Department.department_name).join(Shift, Shift.doctor_id == Doctor.id).join(ScheduleEntry, ScheduleEntry.shift_id == Shift.id).group_by(Department.department_name).all()
    doctor_df = pd.DataFrame(doctor_workload, columns=["Doctor", "Number of Shifts"])
    department_df = pd.DataFrame(department_workload, columns=["Department", "Number of Shifts"])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        doctor_df.to_excel(writer, sheet_name="Doctor Workload", index=False)
        department_df.to_excel(writer, sheet_name="Department Workload", index=False)
    output.seek(0)
    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=statistics.xlsx"}
    )


@app.route("/export-statistics/pdf")
def export_statistics_pdf():
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    pdf.drawString(100, 800, "Doctor Schedule Management System - Statistics")
    pdf.drawString(100, 780, "Doctor Workload:")
    y = 760
    doctor_workload = db.session.query(
        Doctor.name, db.func.count(ScheduleEntry.id)
    ).join(Shift, Shift.doctor_id == Doctor.id).join(ScheduleEntry, ScheduleEntry.shift_id == Shift.id).group_by(Doctor.name).all()
    for doctor, count in doctor_workload:
        pdf.drawString(100, y, f"{doctor}: {count} shifts")
        y -= 20
    pdf.drawString(100, y - 20, "Department Workload:")
    y -= 40
    department_workload = db.session.query(
        Department.department_name, db.func.count(ScheduleEntry.id)
    ).join(Doctor, Doctor.department == Department.department_name).join(Shift, Shift.doctor_id == Doctor.id).join(ScheduleEntry, ScheduleEntry.shift_id == Shift.id).group_by(Department.department_name).all()
    for department, count in department_workload:
        pdf.drawString(100, y, f"{department}: {count} shifts")
        y -= 20
    pdf.save()
    output.seek(0)
    return Response(
        output,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment;filename=statistics.pdf"}
    )


@app.route("/optimize-shifts", methods=["POST"])
def optimize_shifts_route():
    department_name = request.form.get("department_name")
    days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    rooms = [room.room_name for room in Room.query.filter_by(department_name=department_name).all()]
    time_slots = ["08:00-12:00", "12:00-16:00", "16:00-20:00"]
    if not department_name or not rooms:
        return render_template("home.html", message="Invalid department or no rooms available.", departments=Department.query.all())
    if is_schedule_optimized(department_name, days, rooms, time_slots):
        return render_template(
            "home.html",
            message="The current schedule is already optimized. No changes are necessary.",
            departments=Department.query.all(),
        )
    try:
        proposed_schedule = optimize_shifts(department_name, days, rooms, time_slots, dry_run=True)
        if not proposed_schedule:
            return render_template(
                "home.html",
                message="No feasible solution found for the given constraints.",
                departments=Department.query.all(),
            )
        gantt_data = []
        for entry in proposed_schedule:
            gantt_data.append({
                "Task": f"{entry['room']} | {entry['day']}",
                "Start": f"2023-01-01T{entry['time_slot'].split('-')[0]}:00",
                "Finish": f"2023-01-01T{entry['time_slot'].split('-')[1]}:00",
                "Doctor": entry["doctor"],
                "ShiftDetails": entry["time_slot"],
                "ContractType": "Full-Time" if "Full-Time" in entry["time_slot"] else "Part-Time",
            })
        file_path = "static/optimized_gantt_chart.png"
        render_gantt_chart(gantt_data, file_path, department_name=department_name)
        return render_template(
            "confirm_optimization.html",
            department_name=department_name,
            proposed_schedule=proposed_schedule,
            gantt_image=file_path,
        )
    except Exception as e:
        return render_template("home.html", message="Error during shift optimization.", departments=Department.query.all())


@app.route("/apply-optimization", methods=["POST"])
def apply_optimization():
    department_name = request.form.get("department_name")
    days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    rooms = [room.room_name for room in Room.query.filter_by(department_name=department_name).all()]
    time_slots = ["08:00-12:00", "12:00-16:00", "16:00-20:00"]
    try:
        optimize_shifts(department_name, days, rooms, time_slots, dry_run=False)
        return render_template("home.html", message="Shift optimization applied successfully!", departments=Department.query.all())
    except Exception as e:
        print(f"Error during optimization: {e}")
        return render_template("home.html", message="Error applying shift optimization. Please check the logs.", departments=Department.query.all())


@app.route("/scenarios", methods=["GET"])
def scenarios():
    scenarios = [
        {"name": "Scenario No.1", "description": "Clinic No.1: Full-time doctor (8:00 AM - 4:00 PM), Part-time doctor (4:00 PM - 8:00 PM)."},
        {"name": "Scenario No.2", "description": "Clinic No.2: Full-time doctor on split shift (8:00 AM - 12:00 PM, 6:00 PM - 10:00 PM)."},
    ]
    return render_template("scenarios.html", scenarios=scenarios)


@app.route("/export-schedule", methods=["POST"])
def export_schedule():
    export_type = request.form.get("export_type")
    filter_department = request.form.get("export_filter_department")
    filter_doctor = request.form.get("export_filter_doctor")
    filter_day = request.form.get("export_filter_day")
    filter_room = request.form.get("export_filter_room")

    query = ScheduleEntry.query.join(Shift).join(Doctor)
    if filter_department:
        query = query.filter(Doctor.department == filter_department)
    if filter_doctor:
        query = query.filter(Doctor.name == filter_doctor)
    if filter_day:
        query = query.filter(ScheduleEntry.day == filter_day)
    if filter_room:
        query = query.filter(ScheduleEntry.room == filter_room)
    schedule = query.all()

    if export_type == "excel":
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            data = [
                {
                    "Day": entry.day,
                    "Room": entry.room,
                    "Doctor": entry.shift.assigned_doctor.name,
                    "Department": entry.shift.assigned_doctor.department,
                    "Start Time": entry.shift.start_time,
                    "End Time": entry.shift.end_time,
                    "Shift Type": entry.shift.shift_type,
                }
                for entry in schedule
            ]
            df = pd.DataFrame(data)
            df.to_excel(writer, index=False, sheet_name="Schedule")
        output.seek(0)
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment;filename=schedule.xlsx"}
        )
    elif export_type == "pdf":
        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=letter)
        pdf.drawString(100, 750, "Doctor Schedule")
        y = 730
        for entry in schedule:
            pdf.drawString(
                100,
                y,
                f"{entry.day} | {entry.room} | {entry.shift.assigned_doctor.name} | {entry.shift.start_time}-{entry.shift.end_time}",
            )
            y -= 20
            if y < 50:
                pdf.showPage()
                y = 750
        pdf.save()
        output.seek(0)
        return Response(
            output,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=schedule.pdf"}
        )
    else:
        return redirect(url_for("view_schedule"))


@app.route("/export-schedule/json")
def export_schedule_json():
    schedule = ScheduleEntry.query.all()
    schedule_data = [
        {
            "day": entry.day,
            "room": entry.room,
            "doctor": entry.shift.assigned_doctor.name,
            "start_time": entry.shift.start_time,
            "end_time": entry.shift.end_time
        }
        for entry in schedule
    ]
    return jsonify(schedule_data)


@app.route("/knowledge-base", methods=["GET", "POST"])
def manage_knowledge_base():
    if request.method == "POST":
        question = request.form["question"]
        answer = request.form["answer"]
        entry = KnowledgeBase(question=question, answer=answer)
        db.session.add(entry)
        db.session.commit()
        return redirect(url_for("manage_knowledge_base"))
    entries = KnowledgeBase.query.all()
    return render_template("knowledge_base.html", entries=entries)


@app.route("/delete-knowledge/<int:entry_id>", methods=["POST"])
def delete_knowledge(entry_id):
    entry = KnowledgeBase.query.get(entry_id)
    if entry:
        try:
            db.session.delete(entry)
            db.session.commit()
        except Exception as e:
            return redirect(url_for("manage_knowledge_base", message=f"Error: {e}"))
    return redirect(url_for("manage_knowledge_base"))


@app.route("/bulk-delete-schedule", methods=["POST"])
def bulk_delete_schedule():
    try:
        selected_entries = request.form.getlist("selected_entries")
        if not selected_entries:
            return redirect(url_for("view_schedule", message="No entries selected for deletion."))

        for entry_id in selected_entries:
            entry = ScheduleEntry.query.get(entry_id)
            if entry:
                shift = entry.shift
                db.session.delete(entry)
                db.session.commit()
                # Delete the shift if no other schedule entries are linked to it
                if not ScheduleEntry.query.filter_by(shift_id=shift.id).first():
                    db.session.delete(shift)
                    db.session.commit()

        return redirect(url_for("view_schedule", message="Selected entries deleted successfully."))
    except Exception as e:
        print(f"Error during bulk deletion: {e}")
        return redirect(url_for("view_schedule", message="An error occurred during bulk deletion."))


@app.route("/check-conflicts", methods=["GET"])
def check_conflicts():
    conflicts = []
    schedule_entries = ScheduleEntry.query.all()
    for entry in schedule_entries:
        overlapping = ScheduleEntry.query.join(Shift).filter(
            ScheduleEntry.day == entry.day,
            ScheduleEntry.room == entry.room,
            Shift.start_time < entry.shift.end_time,
            Shift.end_time > entry.shift.start_time,
            ScheduleEntry.id != entry.id
        ).all()
        if overlapping:
            conflicts.append({
                "entry": entry,
                "conflicts": overlapping
            })
    return render_template("conflicts.html", conflicts=conflicts)


@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        user_query = request.json.get("query")
        response = handle_chatbot_query(user_query)
        return jsonify({"response": response})
    return render_template("chatbot.html")


def handle_chatbot_query(query):
    """
    Process the chatbot query and return a response.
    """
    query = query.lower()

    # Example responses for specific queries
    if "how many departments" in query or "number of departments" in query:
        department_count = Department.query.count()
        return f"There are {department_count} departments in the system."
    elif "how many doctors" in query:
        doctor_count = Doctor.query.count()
        return f"There are {doctor_count} doctors in the system."
    elif "how many rooms" in query:
        room_count = Room.query.count()
        return f"There are {room_count} rooms in the system."
    elif "schedule" in query:
        schedule_entries = ScheduleEntry.query.all()
        if not schedule_entries:
            return "No schedule entries found in the system."
        response = "<table class='table table-bordered'><thead><tr><th>#</th><th>Day</th><th>Room</th><th>Doctor</th><th>Start Time</th><th>End Time></th></tr></thead><tbody>"
        for index, entry in enumerate(schedule_entries, start=1):
            response += f"<tr><td>{index}</td><td>{entry.day}</td><td>{entry.room}</td><td>{entry.shift.assigned_doctor.name}</td><td>{entry.shift.start_time}</td><td>{entry.shift.end_time}</td></tr>"
        response += "</tbody></table>"
        return response

    # Default response using the chatbot model
    response = chatbot_model(query, max_length=150, num_return_sequences=1)[0]["generated_text"]
    return response


if __name__ == "__main__":
    from waitress import serve
    with app.app_context():
        db.create_all()
    serve(app, host="127.0.0.1", port=5000)