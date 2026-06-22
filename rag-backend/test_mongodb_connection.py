import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

async def test():
    try:
        mongodb_url = os.getenv('MONGODB_URL').strip().strip('"').strip("'")
        print(f'Testing MongoDB connection...')
        print(f'URL: {mongodb_url[:60]}...')
        print('-' * 50)
        
        client = AsyncIOMotorClient(
            mongodb_url,
            serverSelectionTimeoutMS=30000,
            tls=True,
            retryWrites=True
        )
        
        await client.admin.command('ping')
        print(' MongoDB connection successful!')
        
        db_list = await client.list_database_names()
        print(f' Available databases: {db_list}')
        
        client.close()
        print('\n All tests passed!')
        
    except Exception as e:
        print(f' Connection failed: {e}')

if __name__ == "__main__":
    asyncio.run(test())
