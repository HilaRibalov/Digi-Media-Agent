import requests
import time
import os
import sys
from google.cloud import firestore

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_client import FirestoreSaver

def run_final_logic_test():
    url = "http://127.0.0.1:8000/webhook"
    
    # We use "אירוע חדש:" to trigger the correct route in server.py
    payload = {
        "update_id": 100002,
        "message": {
            "message_id": 3,
            "chat": {"id": 8621732852, "type": "private"},
            "text": "אירוע חדש: בדיקה 1 ותוסיף אליה את כולם."
        }
    }
    
    print("⏳ Sending 'Everyone' logic test request to webhook...")
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload)
        elapsed = time.time() - start_time
        
        print(f"Response Status: {response.status_code}")
        print(f"Time taken: {elapsed:.4f} seconds")
        
        assert response.status_code == 200, "Expected 200 OK"
        
        print("✅ Webhook responded. Sleeping for 15s to allow LLM processing and DB writes...")
        time.sleep(15)  # 8s might be a bit too tight for an LLM call + tools
        
        print("🔍 Connecting to Firestore to retrieve state...")
        db = firestore.Client(database="digi-media-db")
        
        # We need the most recent thread ID. We can scan the collection for the latest one.
        # But wait, in server.py, it generates a new UUID for "אירוע חדש:"!
        # ACTIVE_THREAD_ID = str(uuid.uuid4())
        # How do we get the thread ID?
        # We can fetch the most recently created document in checkpoints!
        
        docs = db.collection("checkpoints").order_by("checkpoint_id", direction=firestore.Query.DESCENDING).limit(1).stream()
        latest_doc = None
        for doc in docs:
            latest_doc = doc
            break
            
        if not latest_doc:
            print("❌ No checkpoints found in Firestore.")
            return
            
        data = latest_doc.to_dict()
        thread_id = data.get("thread_id")
        checkpoint_ns = data.get("checkpoint_ns", "")
        
        print(f"✅ Found latest thread: {thread_id}")
        
        saver = FirestoreSaver()
        tuple_result = saver.get_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}})
        
        if tuple_result and tuple_result.checkpoint:
            channel_values = tuple_result.checkpoint.get("channel_values", {})
            
            # Print missing attendees
            missing = channel_values.get("missing_attendees", [])
            print("\n📋 Extracted Attendees (missing_attendees list):")
            for m in missing:
                print(f"  - {m}")
                
            # Print latest AI response
            messages = channel_values.get("messages", [])
            print(f"\n💬 Extracted Messages (count: {len(messages)}):")
            for msg in messages[-3:]:
                if hasattr(msg, 'content'):
                    print(f"  [Message]: {msg.content}")
                elif isinstance(msg, dict) and 'kwargs' in msg:
                    print(f"  [{msg.get('id', 'Message')}]: {msg['kwargs'].get('content', '')}")
                else:
                    print(f"  [Raw]: {msg}")
                    
        else:
            print("❌ Failed to decode checkpoint state.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server. Make sure FastAPI is running.")
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")

if __name__ == "__main__":
    run_final_logic_test()
