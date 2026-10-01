import requests
import time

def test_async_webhook():
    url = "http://127.0.0.1:8000/webhook" 
    
    payload = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "chat": {"id": 8621732852, "type": "private"},
            "text": "Hello Async Webhook!"
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
        
        if response.status_code == 200 and elapsed < 0.5:
            print("✅ Test Passed: Webhook returned 200 OK immediately!")
        else:
            print("❌ Warning: Response took too long or failed. Sync logic might still be blocking.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server. Make sure your FastAPI server is running.")

if __name__ == "__main__":
    test_async_webhook()
