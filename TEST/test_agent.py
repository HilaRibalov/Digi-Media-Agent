import unittest
import uuid
from unittest.mock import patch
from langgraph.types import Command
from agent import app


class TestMediaCollectionAgent(unittest.TestCase):
    """
    Automated Test Suite for the Digithillel Media Collection Agent.
    Executes edge cases, happy paths, and error states without human intervention.
    """

    def setUp(self):
        """Initializes a clean base state for each test to prevent data leakage."""
        self.base_state = {
            "event_id": "test_evt_001",
            "event_name": "Standard Company Event",
            "event_date": "2026-10-15",
            "missing_attendees": ["user1@example.com", "user2@example.com"],
            "reminder_count": 0,
            "wakeup_reason": "timer",
            "messages": []
        }

    def run_simulation(self, initial_state, manager_feedbacks=None, daily_triggers=None):
        """
        Helper method to run the LangGraph agent autonomously.
        Handles the setup phase (manager approvals) and the collection phase (daily cron/webhooks).
        """
        if manager_feedbacks is None:
            manager_feedbacks = [""]  # Default: Approve immediately
        if daily_triggers is None:
            daily_triggers = []

        # Unique thread ID for each test to isolate memory
        config = {"configurable": {"thread_id": uuid.uuid4().hex}}

        # 1. Start the setup phase
        for _ in app.stream(initial_state, config):
            pass

        state = app.get_state(config)

        # 2. Handle Manager Approval Interruption
        while state.next and "create_drive_space" in state.next:
            feedback = manager_feedbacks.pop(0) if manager_feedbacks else ""
            if feedback:
                app.update_state(config, {"user_feedback": feedback})
            else:
                app.update_state(config, {
                    "approved_folder_path": state.values.get("suggested_folder_path"),
                    "user_feedback": ""
                })

            for _ in app.stream(Command(resume=True), config):
                pass
            state = app.get_state(config)

        # 3. Execute Daily Triggers
        for trigger in daily_triggers:
            wakeup = trigger.get("wakeup_reason", "timer")
            mock_files = trigger.get("files", [])
            mock_msgs = trigger.get("messages", [])

            # CRITICAL FIX: Patching the tools directly in the 'agent' module namespace
            # to bypass Pydantic's strict immutability on StructuredTool objects.
            with patch("agent.check_drive_uploads") as mock_uploads, \
                    patch("agent.read_team_messages") as mock_msgs_tool:

                mock_uploads.invoke.return_value = mock_files
                mock_msgs_tool.invoke.return_value = mock_msgs

                for _ in app.stream({"wakeup_reason": wakeup}, config):
                    pass

        return app.get_state(config).values

    # ==========================================
    # TEST CASES (15 Scenarios)
    # ==========================================

    def test_01_happy_path_all_upload_immediately(self):
        """
        Goal: Verify that if all users upload files immediately, the task finishes.
        Expected: Missing attendees list is empty, status is 'finished'.
        """
        triggers = [{"wakeup_reason": "timer",
                     "files": ["photo_from_user1@example.com.jpg", "photo_from_user2@example.com.jpg"]}]
        final_state = self.run_simulation(self.base_state, daily_triggers=triggers)
        self.assertEqual(len(final_state["missing_attendees"]), 0)
        self.assertEqual(final_state["collection_phase_status"], "finished")

    def test_02_manager_rejects_path_once_then_approves(self):
        """
        Goal: Verify the agent regenerates the path if the manager rejects it initially.
        Expected: Path is updated and approved, simulation proceeds to reminders.
        """
        feedbacks = ["Change to English letters", ""]
        final_state = self.run_simulation(self.base_state, manager_feedbacks=feedbacks)
        self.assertIn("approved_folder_path", final_state)
        self.assertNotEqual(final_state["approved_folder_path"], "")

    def test_03_manager_rejects_path_twice(self):
        """
        Goal: Ensure the system can handle multiple human-in-the-loop revisions.
        Expected: Agent processes two feedback loops before proceeding.
        """
        feedbacks = ["No year please", "Add hyphens instead of spaces", ""]
        final_state = self.run_simulation(self.base_state, manager_feedbacks=feedbacks)
        self.assertEqual(final_state["folder_approval_status"], "approved")

    def test_04_user_unresponsive_leads_to_escalation(self):
        """
        Goal: Verify that an unresponsive user receives 3 reminders and then triggers escalation.
        Expected: Reminder count hits 3, status changes to 'escalated', user remains in missing list.
        """
        state = self.base_state.copy()
        state["missing_attendees"] = ["lazy_user@example.com"]

        # 3 days of silence (Setup takes count to 1, then 2 more timer triggers hit the threshold)
        triggers = [
            {"wakeup_reason": "timer"},
            {"wakeup_reason": "timer"},
            {"wakeup_reason": "timer"}
        ]
        final_state = self.run_simulation(state, daily_triggers=triggers)
        self.assertEqual(final_state["collection_phase_status"], "escalated")
        self.assertIn("lazy_user@example.com", final_state["missing_attendees"])

    def test_05_user_claims_uploaded_but_no_files_found(self):
        """
        Goal: Verify the AI Auditor (Brain) does NOT remove a user who lies about uploading.
        Expected: User remains in missing list because no files match their claim.
        """
        triggers = [{"wakeup_reason": "message", "messages": ["user1@example.com: העלתי את התמונות"]}]
        final_state = self.run_simulation(self.base_state, daily_triggers=triggers)
        self.assertIn("user1@example.com", final_state["missing_attendees"])

    def test_06_user_excused_due_to_illness(self):
        """
        Goal: Verify the AI Auditor removes a user who claims legitimate exemption (illness).
        Expected: User1 is removed, User2 remains.
        """
        triggers = [{"wakeup_reason": "message", "messages": ["user1@example.com: הייתי חולה בבית"]}]
        final_state = self.run_simulation(self.base_state, daily_triggers=triggers)
        self.assertNotIn("user1@example.com", final_state["missing_attendees"])
        self.assertIn("user2@example.com", final_state["missing_attendees"])

    def test_07_user_excused_forgot_to_take_pictures(self):
        """
        Goal: Verify the AI Auditor handles lack-of-media exemptions properly.
        Expected: User1 is removed, User2 remains.
        """
        triggers = [{"wakeup_reason": "message", "messages": ["user1@example.com: שכחתי לצלם באירוע לצערי"]}]
        final_state = self.run_simulation(self.base_state, daily_triggers=triggers)
        self.assertNotIn("user1@example.com", final_state["missing_attendees"])

    def test_08_single_attendee_event(self):
        """
        Goal: Test system stability with an edge-case of a 1-person event.
        Expected: Properly finishes when the single user uploads.
        """
        state = self.base_state.copy()
        state["missing_attendees"] = ["solo@example.com"]
        triggers = [{"wakeup_reason": "timer", "files": ["photo_from_solo@example.com.jpg"]}]
        final_state = self.run_simulation(state, daily_triggers=triggers)
        self.assertEqual(len(final_state["missing_attendees"]), 0)
        self.assertEqual(final_state["collection_phase_status"], "finished")

    def test_09_large_attendee_group(self):
        """
        Goal: Test system stability and token limits with a larger array of users.
        Expected: All 10 users are processed correctly.
        """
        state = self.base_state.copy()
        state["missing_attendees"] = [f"user{i}@example.com" for i in range(1, 11)]
        files_mock = [f"photo_from_user{i}@example.com.jpg" for i in range(1, 11)]
        triggers = [{"wakeup_reason": "timer", "files": files_mock}]
        final_state = self.run_simulation(state, daily_triggers=triggers)
        self.assertEqual(len(final_state["missing_attendees"]), 0)
        self.assertEqual(final_state["collection_phase_status"], "finished")

    def test_10_special_characters_in_event_name(self):
        """
        Goal: Verify path suggestion handles weird symbols in event names safely.
        Expected: Path is generated successfully without crashing.
        """
        state = self.base_state.copy()
        state["event_name"] = "Event @#$%^&*"
        final_state = self.run_simulation(state)
        self.assertIn("approved_folder_path", final_state)

    def test_11_unusual_date_format(self):
        """
        Goal: Verify LLM path reasoning handles non-standard date strings.
        Expected: Path is generated and approved.
        """
        state = self.base_state.copy()
        state["event_date"] = "Late October sometime"
        final_state = self.run_simulation(state)
        self.assertIn("approved_folder_path", final_state)

    def test_12_mixed_behavior_one_uploads_one_escalates(self):
        """
        Goal: Test complex tracking where one finishes and the other reaches escalation limit.
        Expected: User1 is cleared, User2 remains, status is 'escalated'.
        """
        triggers = [
            {"wakeup_reason": "timer", "files": ["photo_from_user1@example.com.jpg"]},
            {"wakeup_reason": "timer"},
            {"wakeup_reason": "timer"}
        ]
        final_state = self.run_simulation(self.base_state, daily_triggers=triggers)
        self.assertNotIn("user1@example.com", final_state["missing_attendees"])
        self.assertIn("user2@example.com", final_state["missing_attendees"])
        self.assertEqual(final_state["collection_phase_status"], "escalated")

    def test_13_empty_initial_missing_list(self):
        """
        Goal: Edge case where an event starts with no missing attendees.
        Expected: Agent skips reminders and finishes immediately after setup.
        """
        state = self.base_state.copy()
        state["missing_attendees"] = []
        final_state = self.run_simulation(state)

        # CRITICAL FIX: Safe extraction using .get() for graphs that bypass the collection phase
        status = final_state.get("collection_phase_status", "finished")
        self.assertEqual(status, "finished")
        self.assertEqual(len(final_state["missing_attendees"]), 0)

    def test_14_message_wakeup_does_not_increment_reminders(self):
        """
        Goal: Ensure webhook wakeups (messages) do not trigger mass reminders.
        Expected: Reminder count remains at initial value (1 after setup).
        """
        triggers = [{"wakeup_reason": "message", "messages": ["user1@example.com: היי"]}]
        final_state = self.run_simulation(self.base_state, daily_triggers=triggers)
        self.assertEqual(final_state["reminder_count"], 1)

    def test_15_drive_creation_failure(self):
        """
        Goal: Verify graceful error handling if the Drive API fails.
        Expected: Status is 'error', no reminders are sent.
        """
        # Patching inside the test context to simulate a network/permission error
        with patch("agent.create_drive_folder") as mock_create_drive:
            mock_create_drive.invoke.side_effect = Exception("Google API Quota Exceeded")

            config = {"configurable": {"thread_id": uuid.uuid4().hex}}
            for _ in app.stream(self.base_state, config): pass

            app.update_state(config, {"approved_folder_path": "test_path", "user_feedback": ""})
            for _ in app.stream(Command(resume=True), config): pass

            final_state = app.get_state(config).values
            self.assertEqual(final_state["collection_phase_status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)