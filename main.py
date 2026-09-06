from agent import app
from langgraph.types import Command


def run_agent():
    config = {"configurable": {"thread_id": "test_event_1"}}

    initial_state = {
        "event_id": "evt_123",
        "event_name": "סדנת\ חברה",
        "event_date": "2026-10-15",
        "missing_attendees": ["dani@example.com", "yossi@example.com"],
        #"missing_attendees": [],
        "reminder_count": 0,
        "wakeup_reason": "timer",  # הריצה הראשונה מתנהגת כמו טיימר כדי לשלוח את הקישור הראשוני
        "messages": []
    }

    print("--- Starting the Agent (Run 1) ---")
    print(f"📋 Current missing attendees: {initial_state['missing_attendees']}")

    for event in app.stream(initial_state, config):
        pass

    state = app.get_state(config)

    while state.next:
        print("\n--- AGENT PAUSED: Awaiting Manager Approval ---")
        current_path = state.values.get("suggested_folder_path")
        print(f"Suggested Path: {current_path}")

        user_input = input("Enter feedback to change path, or press Enter to approve: ")

        if user_input.strip():
            app.update_state(config, {"user_feedback": user_input})
            for event in app.stream(Command(resume=True), config):
                pass
            state = app.get_state(config)
        else:
            print("\n--- Path approved! Resuming ---")
            app.update_state(config, {"approved_folder_path": current_path, "user_feedback": ""})

            for event in app.stream(Command(resume=True), config):
                for node_name, updates in event.items():
                    print(f"[Finished Node: {node_name}]")
            break

    print("\n--- Initial Setup Complete ---")

    # ==========================================
    # הסימולציה האינטראקטיבית עם תפריט הטריגרים
    # ==========================================
    while True:
        current_state = app.get_state(config)
        missing_now = current_state.values.get("missing_attendees", [])
        print(f"\n📋 Currently missing attendees: {missing_now}")

        print("\n[Simulation] How would you like to wake up the agent?")
        print("1. Simulate incoming message (Webhook)")
        print("2. Simulate daily timer (Cron)")
        print("3. Exit")
        choice = input("Enter 1, 2, or 3: ")

        if choice == '1':
            wakeup_reason = "message"
        elif choice == '2':
            wakeup_reason = "timer"
        else:
            print("Shutting down simulation.")
            break

        print(f"\n--- Waking up agent (Trigger: {wakeup_reason}) ---")

        # מעבירים לסוכן את סיבת ההתעוררות כדי שהראוטר יידע מה לעשות
        for event in app.stream({"wakeup_reason": wakeup_reason}, config):
            for node_name, updates in event.items():
                print(f"[Finished Node: {node_name}]")

    print("\n--- Run Complete ---")


if __name__ == "__main__":
    run_agent()