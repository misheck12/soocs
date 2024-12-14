import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from the .env file
load_dotenv()

class Config:
    """
    Configuration class for Flask application.
    """
    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")

    # MongoDB settings
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/football_league")

    # Initialize MongoDB client
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()
    users_collection = db["users"]
    teams_collection = db["teams"]
    fixtures_collection = db["fixtures"]
    settings_collection = db['settings']
    results_collection = db['results']
