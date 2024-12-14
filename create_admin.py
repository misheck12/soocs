import os
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

# Load environment variables from the .env file
load_dotenv()

class Config:
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/football_league")

# Initialize MongoDB client
client = MongoClient(Config.MONGODB_URI)
db = client.get_database()
users_collection = db.users

# Check if admin user already exists
if not users_collection.find_one({"email": "misheck1720@gmail.com"}):
    admin_user = {
        "username": "admin",
        "email": "misheck1720@gmail.com",
        "password": generate_password_hash("6474325m", method='pbkdf2:sha256')
    }
    users_collection.insert_one(admin_user)
    print("Admin user created successfully!")
else:
    print("Admin user already exists.")
