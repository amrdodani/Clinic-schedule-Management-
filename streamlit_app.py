import streamlit as st
from models import db, Doctor, Room, Department, ScheduleEntry, Shift
from visualization import render_gantt_chart
from shift_optimizer import optimize_shifts, is_schedule_optimized
import pandas as pd
import os

# Initialize Streamlit app
st.set_page_config(page_title="Doctor Schedule Management System", layout="wide")

# Helper function to load data
def load_data():
    doctors = Doctor.query.all()
    rooms = Room.query.all()
    departments = Department.query.all()
    schedule = ScheduleEntry.query.all()
    return doctors, rooms, departments, schedule

# Home Page
def home():
    st.title("Doctor Schedule Management System")
    st.write("Welcome to the Doctor Schedule Management System!")
    st.write("Use the sidebar to navigate through the application.")

# Manage Departments
def manage_departments():
    st.header("Manage Departments")
    departments = Department.query.all()

    # Add Department
    with st.form("add_department"):
        st.subheader("Add Department")
        department_name = st.text_input("Department Name")
        location = st.text_input("Location")
        branch = st.radio("Branch", ["SASH", "SAHH"])
        submitted = st.form_submit_button("Add Department")
        if submitted:
            try:
                department_id = f"{branch}-{department_name[:2].upper()}{len(departments) + 1:02d}"
                department = Department(department_id=department_id, department_name=department_name, location=location, branch=branch)
                db.session.add(department)
                db.session.commit()
                st.success("Department added successfully!")
            except Exception as e:
                st.error(f"Error: {e}")

    # Display Departments
    st.subheader("Existing Departments")
    for department in departments:
        st.write(f"**{department.department_name}** - {department.location} ({department.branch})")

# View Schedule
def view_schedule():
    st.header("Doctor Schedule")
    doctors, rooms, departments, schedule = load_data()

    # Filters
    st.sidebar.subheader("Filters")
    filter_day = st.sidebar.selectbox("Filter by Day", ["All"] + ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
    filter_room = st.sidebar.selectbox("Filter by Room", ["All"] + [room.room_name for room in rooms])
    filter_doctor = st.sidebar.selectbox("Filter by Doctor", ["All"] + [doctor.name for doctor in doctors])

    # Apply Filters
    filtered_schedule = schedule
    if filter_day != "All":
        filtered_schedule = [entry for entry in filtered_schedule if entry.day == filter_day]
    if filter_room != "All":
        filtered_schedule = [entry for entry in filtered_schedule if entry.room == filter_room]
    if filter_doctor != "All":
        filtered_schedule = [entry for entry in filtered_schedule if entry.shift.assigned_doctor.name == filter_doctor]

    # Display Schedule
    st.subheader("Schedule")
    if filtered_schedule:
        for entry in filtered_schedule:
            st.write(f"{entry.day} | {entry.room} | {entry.shift.assigned_doctor.name} ({entry.shift.start_time}-{entry.shift.end_time})")
    else:
        st.info("No schedule entries available.")

# Render Gantt Chart
def render_gantt():
    st.header("Gantt Chart")
    _, _, departments, schedule = load_data()

    # Department Filter
    selected_department = st.selectbox("Select Department", ["All"] + [dept.department_name for dept in departments])
    if selected_department != "All":
        schedule = [entry for entry in schedule if entry.shift.assigned_doctor.department == selected_department]

    # Generate Gantt Chart
    if schedule:
        file_path = "static/gantt_chart.png"
        render_gantt_chart(schedule, file_path, department_name=selected_department)
        st.image(file_path)
    else:
        st.info("No schedule data available to render the Gantt chart.")

# Optimize Shifts
def optimize_shifts_ui():
    st.header("Optimize Shifts")
    _, rooms, departments, _ = load_data()

    # Optimization Form
    with st.form("optimize_shifts"):
        department_name = st.selectbox("Select Department", [dept.department_name for dept in departments])
        days = st.multiselect("Select Days", ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"])
        time_slots = st.multiselect("Select Time Slots", ["08:00-12:00", "12:00-16:00", "16:00-20:00"])
        submitted = st.form_submit_button("Optimize")
        if submitted:
            try:
                proposed_schedule = optimize_shifts(department_name, days, [room.room_name for room in rooms], time_slots, dry_run=True)
                if proposed_schedule:
                    st.success("Optimization successful! Proposed schedule:")
                    for entry in proposed_schedule:
                        st.write(f"{entry['day']} | {entry['room']} | {entry['doctor']} ({entry['time_slot']})")
                else:
                    st.warning("No feasible solution found.")
            except Exception as e:
                st.error(f"Error: {e}")

# Sidebar Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Manage Departments", "View Schedule", "Gantt Chart", "Optimize Shifts"])

# Page Routing
if page == "Home":
    home()
elif page == "Manage Departments":
    manage_departments()
elif page == "View Schedule":
    view_schedule()
elif page == "Gantt Chart":
    render_gantt()
elif page == "Optimize Shifts":
    optimize_shifts_ui()
