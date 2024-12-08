# create_admin.py

import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from bson.objectid import ObjectId

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "misheck1720@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "6474325m")  # It's better to set this in .env

if not MONGODB_URI:
    print("Error: MONGODB_URI not found in environment variables.")
    exit(1)

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client.get_default_database()
users_collection = db["users"]
teams_collection = db["teams"]

# ---------------------------
# Admin User Creation
# ---------------------------

# Check if admin user already exists
existing_admin = users_collection.find_one({"email": ADMIN_EMAIL})
if existing_admin:
    print("Admin user already exists.")
else:
    # Create admin user
    admin_user = {
        "username": ADMIN_USERNAME,
        "email": ADMIN_EMAIL,
        "password": generate_password_hash(
            ADMIN_PASSWORD, method="pbkdf2:sha256", salt_length=16
        ),
        "role": "admin",  # Optional: Assign a role if your application uses roles
    }

    users_collection.insert_one(admin_user)
    print("Admin user created successfully!")

# ---------------------------
# Teams Initialization
# ---------------------------

# Define teams to be added
teams = [
    {"name": "Chamba Valley", "logo": "default-logo.png"},
    {"name": "Corpus Harvest", "logo": "default-logo.png"},
    {"name": "SIA", "logo": "default-logo.png"},
    {"name": "Sirago", "logo": "default-logo.png"},
    {"name": "Elite", "logo": "default-logo.png"},
    {"name": "NYHSA", "logo": "default-logo.png"},
    {"name": "Young Gribs SA", "logo": "default-logo.png"},
    {"name": "Chudleigh United", "logo": "default-logo.png"},
    {"name": "Obama Rangers", "logo": "default-logo.png"},
    {"name": "LYKHFA", "logo": "default-logo.png"},
    {"name": "DA Sport Academy", "logo": "default-logo.png"},
    {"name": "Kamps FC", "logo": "default-logo.png"},
    {"name": "Shemimack", "logo": "default-logo.png"},
    {"name": "Lusaka Wanderers", "logo": "default-logo.png"},
    {"name": "Michael AC", "logo": "default-logo.png"},
    {"name": "Tabesha FC", "logo": "default-logo.png"},
    {"name": "Christian Academy", "logo": "default-logo.png"},
]

# Function to add teams
def add_teams(teams_list):
    added_count = 0
    for team in teams_list:
        existing_team = teams_collection.find_one({"name": team["name"]})
        if existing_team:
            print(f"Team '{team['name']}' already exists. Skipping.")
        else:
            teams_collection.insert_one(team)
            print(f"Team '{team['name']}' added successfully!")
            added_count += 1
    if added_count == 0:
        print("No new teams were added.")
    else:
        print(f"Total teams added: {added_count}")

# Add teams to the database
add_teams(teams)