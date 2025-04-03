import streamlit as st
from models import ScheduleEntry
from visualization import render_gantt_chart

def main():
    st.title("Doctor Schedule Management System")

    # Load schedule from the database
    schedule = ScheduleEntry.query.all()

    # Display schedule
    st.subheader("Schedule")
    for entry in schedule:
        st.write(f"{entry.day} | {entry.room} | {entry.shift.assigned_doctor.name} "
                 f"({entry.shift.start_time}-{entry.shift.end_time})")

    # Render Gantt chart
    st.subheader("Gantt Chart")
    render_gantt_chart(schedule)
    st.image("gantt_chart.png")

if __name__ == "__main__":
    main()
