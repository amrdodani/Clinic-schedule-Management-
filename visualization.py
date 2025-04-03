"""
Visualization Module for Doctor Schedule Management System.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to suppress GUI warnings
import matplotlib.pyplot as plt
from datetime import datetime
import os
import re  # Import regex module for extracting numeric parts

def render_gantt_chart(schedule, file_path, department_name="", last_updated=None):
    """
    Render a Gantt chart for the given schedule using matplotlib.
    """
    if not schedule:
        print("No schedule data available to render the Gantt chart.")
        raise ValueError("Schedule data is empty.")

    try:
        # Debugging: Log the schedule data being rendered
        print("Rendering Gantt Chart with the following data:")
        for entry in schedule:
            print(entry)

        # Ensure the directory for the file path exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Set the figure size to match the required dimensions (1768x622 pixels)
        fig, ax = plt.subplots(figsize=(17.68, 6.22))

        # Parse schedule and collect unique tasks (rooms | days)
        y_labels = []  # Track unique tasks for proper alignment
        for entry in schedule:
            # Abbreviate the day (e.g., "Saturday" -> "Sat")
            day_abbr = entry["Task"].split(" | ")[1][:3]
            y_label = f"{entry['Task'].split(' | ')[0]} | {day_abbr}"  # Task format: "Room | Day Abbreviation"
            if y_label not in y_labels:
                y_labels.append(y_label)

        # Debugging: Log the unsorted Y-axis labels
        print("Unsorted Y-axis labels:", y_labels)

        # Sort the Y-axis labels by room number (ascending order) and then by day abbreviation
        def extract_room_and_day(label):
            room_match = re.search(r'\d+', label.split(" | ")[0])  # Extract numeric part from "Room X"
            room_number = int(room_match.group()) if room_match else float('inf')  # Use infinity for non-numeric rooms
            day_order = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]  # Define day order
            day_abbr = label.split(" | ")[1]
            day_index = day_order.index(day_abbr) if day_abbr in day_order else float('inf')
            return room_number, day_index

        try:
            y_labels.sort(key=extract_room_and_day)
        except Exception as e:
            print(f"Error while sorting Y-axis labels: {e}")
            raise

        # Reverse the Y-axis labels to display in descending order
        y_labels.reverse()

        # Debugging: Log the reversed Y-axis labels
        print("Reversed Y-axis labels:", y_labels)

        # Plot bars for each schedule entry
        for entry in schedule:
            # Parse the start and end times without the placeholder date
            start_time = datetime.strptime(entry["Start"].split("T")[1], "%H:%M:%S")
            end_time = datetime.strptime(entry["Finish"].split("T")[1], "%H:%M:%S")
            duration = (end_time - start_time).seconds / 3600

            # Determine bar color based on contract type and shift type
            bar_color = "lightblue" if entry["ContractType"] == "Full-Time" else "orange"
            if "Split" in entry["ShiftDetails"]:
                bar_color = "green"  # Highlight split shifts

            # Calculate the Y position based on the reversed index of the task
            day_abbr = entry["Task"].split(" | ")[1][:3]
            y_label = f"{entry['Task'].split(' | ')[0]} | {day_abbr}"
            y_pos = y_labels.index(y_label)

            # Plot the bar for the shift
            ax.barh(
                y_pos,
                duration,
                left=start_time.hour + start_time.minute / 60,
                color=bar_color,
                edgecolor="black",
            )

            # Include doctor name and shift details inside the bar
            text_x = start_time.hour + start_time.minute / 60 + duration / 2
            ax.text(
                text_x,
                y_pos,
                f"{entry['Doctor']} ({entry['ShiftDetails']})",
                ha="center",
                va="center",
                fontsize=8,
                color="black",
            )

        # Configure chart
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels)
        ax.set_xlabel("Time")
        ax.set_ylabel(department_name)  # Replace "Task" with the department name
        ax.set_xticks(range(8, 24))  # Extend X-axis to 11:00 PM
        ax.set_xticklabels([f"{hour}:00" for hour in range(8, 24)])
        ax.xaxis.set_label_position("top")  # Move X-axis to the top
        ax.xaxis.tick_top()

        # Add last update date and time above the X-axis with proper spacing
        last_update_text = f"Last Updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}" if last_updated else "Last Updated: N/A"
        ax.text(
            16,  # Centered horizontally (adjust as needed)
            len(y_labels) + 1.5,  # Increased spacing above the top of the chart
            last_update_text,
            ha="center",
            va="center",
            fontsize=10,
            color="black",
        )

        # Adjust the layout to ensure no overlap
        plt.tight_layout(rect=[0, 0, 1, 0.95])  # Add extra space at the top
        plt.savefig(file_path)  # Save to the specified file path
        plt.close()

        # Debugging: Confirm successful rendering
        print(f"Gantt chart successfully saved to {file_path}")

    except Exception as e:
        print(f"Error while rendering Gantt chart: {e}")
        raise
