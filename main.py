import os
from agent import app
from langgraph.types import Command


def run_agent():
    # Setup configuration and initial thread state
    config = {"configurable": {"thread_id": "demo_event_1"}}

    initial_state = {
        "event_id": "evt_123",
        "event_name": "סדנת חברה",
        "event_date": "2026-10-15",
        "missing_attendees": ["dani@example.com", "yossi@example.com"],
        "reminder_count": 0,
        "wakeup_reason": "timer",
        "messages": []
    }

    print("\n" + "=" * 50)
    print("Starting the Digithillel Media Agent Demo")
    print("=" * 50)

    # Disable interactive mock prompts during the initial setup phase
    os.environ["MOCK_PROMPT_TYPE"] = "none"

    # Run the graph until it hits the defined interrupt
    for event in app.stream(initial_state, config):
        pass

    state = app.get_state(config)

    # Handle Human-in-the-loop interruption for folder path approval
    while state.next:
        print("\n" + "-" * 50)
        print("AGENT PAUSED: Awaiting Manager Approval")
        current_path = state.values.get("suggested_folder_path")
        print(f"Suggested Path: {current_path}")

        user_input = input("Enter feedback to change path, or press Enter to approve: ")

        if user_input.strip():
            # Manager provided feedback; update state and resume to regenerate path
            app.update_state(config, {"user_feedback": user_input})
            for event in app.stream(Command(resume=True), config):
                pass
            state = app.get_state(config)
        else:
            # Manager approved the path; proceed to folder creation and initial reminders
            print("\nPath approved! Resuming...")
            app.update_state(config, {"approved_folder_path": current_path, "user_feedback": ""})

            for event in app.stream(Command(resume=True), config):
                pass
            break

    print("\nInitial Setup Complete! Folder is ready and first reminders sent.")

    # ==========================================
    # Interactive Simulation Loop
    # ==========================================
    while True:
        current_state = app.get_state(config)
        missing_now = current_state.values.get("missing_attendees", [])

        # Graceful exit when the list is empty
        if not missing_now:
            print("\n" + "=" * 50)
            print("SUCCESS: All attendees have uploaded their media!")
            print("The agent's task is complete. Exiting simulation.")
            print("=" * 50 + "\n")
            break

        print(f"\nCurrently missing: {missing_now}")
        print("\n[Simulation] Select next trigger:")
        print("1. Simulate incoming text message (Webhook)")
        print("2. Simulate silent file upload (Checked on next Cron timer)")
        print("3. Simulate daily timer (Cron - no new updates)")
        print("4. Exit Simulation")

        choice = input("Enter 1, 2, 3, or 4: ")

        # Route the specific trigger behavior to the tools using an environment variable
        if choice == '1':
            wakeup_reason = "message"
            os.environ["MOCK_PROMPT_TYPE"] = "chat"
        elif choice == '2':
            wakeup_reason = "timer"  # <--- תוקן: הסוכן מתעורר מטיימר כדי למצוא את הקובץ שעלה בשקט
            os.environ["MOCK_PROMPT_TYPE"] = "upload"
        elif choice == '3':
            wakeup_reason = "timer"
            os.environ["MOCK_PROMPT_TYPE"] = "none"
        elif choice == '4':
            print("\nShutting down simulation. Goodbye!")
            break
        else:
            print("Invalid choice, try again.")
            continue

        print(f"\n--- Waking up agent (Trigger: {wakeup_reason}) ---")

        # Stream the graph execution based on the selected wakeup reason
        for event in app.stream({"wakeup_reason": wakeup_reason}, config):
            pass


if __name__ == "__main__":
    run_agent()