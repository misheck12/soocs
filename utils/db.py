from pymongo import MongoClient
from config import Config

def get_db():
    client = MongoClient(Config.MONGODB_URI)
    db = client.get_database()
    return db
