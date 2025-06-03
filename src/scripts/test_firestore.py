import os
import sys
from dotenv import load_dotenv
from google.cloud import firestore

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import COLLECTIONS

def test_firestore_connection():
    """Test Firestore connection and create test data"""
    try:
        # Initialize Firestore client
        db = firestore.Client()
        
        # Test write
        test_collection = db.collection('test')
        test_doc = test_collection.document('connection_test')
        test_doc.set({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'status': 'connected'
        })
        
        # Test read
        doc = test_doc.get()
        if doc.exists:
            print("✅ Successfully connected to Firestore!")
            print(f"Test document data: {doc.to_dict()}")
            
            # Clean up test data
            test_doc.delete()
            print("✅ Test data cleaned up")
        else:
            print("❌ Failed to read test document")
            
    except Exception as e:
        print(f"❌ Error connecting to Firestore: {str(e)}")
        return False
    
    return True

def create_collections():
    """Create the required collections"""
    try:
        db = firestore.Client()
        
        # Create collections
        collections = [
            COLLECTIONS["MESSAGES"],
            COLLECTIONS["USERS"],
            COLLECTIONS["INTERESTS"],
            COLLECTIONS["ROLES"]
        ]
        
        for collection in collections:
            # Create a test document in each collection
            db.collection(collection).document('test').set({
                'created_at': firestore.SERVER_TIMESTAMP
            })
            print(f"✅ Created collection: {collection}")
            
            # Clean up test document
            db.collection(collection).document('test').delete()
            
        print("✅ All collections created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error creating collections: {str(e)}")
        return False

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    print("Testing Firestore connection...")
    if test_firestore_connection():
        print("\nCreating required collections...")
        create_collections() 