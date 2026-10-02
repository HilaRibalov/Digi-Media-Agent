import requests
import time
from google.cloud import firestore

def run_integration_test():
    url = "http://127.0.0.1:8000/webhook"
    
    payload = {
        "update_id": 100001,
        "message": {
            "message_id": 2,
            "chat": {"id": 8621732852, "type": "private"},
            "text": "Integration Test Message"
        }
    }
    
    print("⏳ Sending request to webhook...")
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload)
        elapsed = time.time() - start_time
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        print(f"Time taken: {elapsed:.4f} seconds")
        
        assert response.status_code == 200, "Expected 200 OK"
        assert elapsed < 0.5, "Expected elapsed time to be less than 0.5s"
        
        print("✅ Webhook responded immediately. Sleeping for 5s to allow background processing...")
        time.sleep(5)
        
        print("🔍 Connecting to Firestore to verify checkpoint persistence...")
        db = firestore.Client(database="digi-media-db")
        
        # In server.py, thread_id defaults to "default_1"
        thread_id = "default_1"
        checkpoint_ns = ""
        doc_id = f"{thread_id}_{checkpoint_ns}"
        
        doc_ref = db.collection("checkpoints").document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            print(f"✅ Checkpoint found for thread: {thread_id}")
            data = doc.to_dict()
            
            # The checkpoint_bytes contains the state. Let's see if we can decode it via the saver
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from db_client import FirestoreSaver
            
            saver = FirestoreSaver()
            tuple_result = saver.get_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}})
            
            if tuple_result and tuple_result.checkpoint:
                print(f"Checkpoint keys: {tuple_result.checkpoint.keys()}")
                messages = tuple_result.checkpoint.get("channel_values", {}).get("messages", [])
                print(f"✅ State persisted successfully! Current number of messages in state: {len(messages)}")
            else:
                print("❌ Warning: Checkpoint document found, but could not decode state messages.")
                
        else:
            print(f"❌ Error: Checkpoint document '{doc_id}' not found in Firestore.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server. Make sure your FastAPI server is running.")
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")

if __name__ == "__main__":
    run_integration_test()
