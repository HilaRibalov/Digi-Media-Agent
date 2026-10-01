from google.cloud import firestore

def test_firestore_connection():
    try:
        # אתחול הקליינט - כאן פייתון שואב אוטומטית את ההרשאות מה-CLI
        #db = firestore.Client()
        db = firestore.Client(database='digi-media-db')

        # ניסיון כתיבה לאוסף זמני
        doc_ref = db.collection('test_connection').document('ping')
        doc_ref.set({'status': 'OK', 'message': 'Hello from local ADC!'})
        print("✅ Connection successful! Wrote document to Firestore.")

        # ניקוי מסמך הבדיקה
        doc_ref.delete()
        print("🧹 Test document deleted successfully.")

    except Exception as e:
        print(f"❌ Connection failed. Error: {e}")

if __name__ == "__main__":
    test_firestore_connection()