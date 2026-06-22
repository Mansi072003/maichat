import asyncio
from typing import List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# --- Minimal Hardcoded MongoDBService Class ---
class HardcodedMongoDBService:
    """A self-contained MongoDB service for one-off seeding."""
    
    def __init__(self):
        # Hardcoded connection details for local testing
        self.mongodb_url = "mongodb://localhost:27017"
        self.database_name = "rag_medical_db"
        self.client = None
        self.db = None
    
    async def initialize(self):
        """Initializes the MongoDB connection."""
        try:
            print(f"Connecting to MongoDB at {self.mongodb_url}...")
            self.client = AsyncIOMotorClient(self.mongodb_url)
            self.db = self.client[self.database_name]
            await self.client.admin.command('ping')
            print("Successfully connected to MongoDB.")
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    async def set_practitioner_patients(
        self, 
        practitioner_id: str, 
        patients: List[str]
    ) -> bool:
        """Sets or updates a practitioner's patient list using upsert."""
        try:
            await self.db.practitioners.update_one(
                {"practitioner_id": practitioner_id},
                {"$set": {"patients": patients, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"❌ Error setting practitioner patients: {e}")
            return False
            
    async def close(self):
        """Closes the MongoDB connection."""
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")

# --- Seeding Script ---
async def seed_practitioner_data():
    """Main function to seed the database with a practitioner and patients."""
    db_service = HardcodedMongoDBService()
    try:
        await db_service.initialize()

        # Define the practitioner and a list of patient IDs
        practitioner_id = "pract-456"
        patient_ids = ["patient-101", "patient-102", "patient-103"]

        print(f"Attempting to add practitioner '{practitioner_id}' with patients: {patient_ids}...")
        
        # Use upsert to insert or update the record
        success = await db_service.set_practitioner_patients(
            practitioner_id=practitioner_id,
            patients=patient_ids
        )

        if success:
            print("🎉 Successfully seeded practitioner and patient data!")
        else:
            print("❌ Failed to seed data.")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
    finally:
        await db_service.close()

if __name__ == "__main__":
    asyncio.run(seed_practitioner_data())