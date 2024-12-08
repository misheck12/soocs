import os

# Define the folder structure
folders = [
    "static",
    "static/css",
    "static/js",
    "static/images",
    "templates",
    "utils",
    "models"
]

# Define the files to create
files = {
    "app.py": "",
    "requirements.txt": "",
    "static/css/style.css": "",
    "static/js/script.js": "",
    "static/images/logo.png": "",  # Placeholder for the logo image
    "templates/base.html": """
<!DOCTYPE html>
<html>
<head>
    <title>Football League App</title>
    <link rel="stylesheet" type="text/css" href="/static/css/style.css">
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
""",
    "templates/index.html": """
{% extends "base.html" %}
{% block content %}
<h1>Welcome to the Football League App</h1>
<a href="/admin">Go to Admin Dashboard</a>
{% endblock %}
""",
    "templates/admin.html": """
{% extends "base.html" %}
{% block content %}
<h1>Admin Dashboard</h1>
<form id="add-team-form">
    <label for="team-name">Team Name:</label>
    <input type="text" id="team-name" name="team_name" required>
    <label for="team-logo">Team Logo URL:</label>
    <input type="url" id="team-logo" name="team_logo" required>
    <button type="submit">Add Team</button>
</form>
<button id="generate-fixtures-button">Generate Fixtures</button>
<table>
    <thead>
        <tr>
            <th>Home Team</th>
            <th>Away Team</th>
            <th>Match Date</th>
        </tr>
    </thead>
    <tbody>
        <!-- Fixtures will be dynamically populated here -->
    </tbody>
</table>
{% endblock %}
""",
    "templates/standings.html": """
{% extends "base.html" %}
{% block content %}
<h1>League Standings</h1>
<table>
    <thead>
        <tr>
            <th>Logo</th>
            <th>Team</th>
            <th>Points</th>
            <th>Wins</th>
            <th>Draws</th>
            <th>Losses</th>
            <th>Goal Difference</th>
            <th>Goals Scored</th>
        </tr>
    </thead>
    <tbody id="standings-table-body">
        <!-- Standings will be dynamically populated here -->
    </tbody>
</table>
{% endblock %}
""",
    "utils/__init__.py": "",
    "utils/db.py": """
from pymongo import MongoClient

def get_db():
    client = MongoClient('localhost', 27017)
    db = client.football_league
    return db
""",
    "models/__init__.py": "",
    "models/team.py": """
class Team:
    def __init__(self, name, logo, points=0, wins=0, draws=0, losses=0, goal_diff=0, goals_scored=0):
        self.name = name
        self.logo = logo
        self.points = points
        self.wins = wins
        self.draws = draws
        self.losses = losses
        self.goal_diff = goal_diff
        self.goals_scored = goals_scored

    def to_dict(self):
        return {
            'name': self.name,
            'logo': self.logo,
            'points': self.points,
            'wins': self.wins,
            'draws': self.draws,
            'losses': self.losses,
            'goal_diff': self.goal_diff,
            'goals_scored': self.goals_scored
        }
""",
    "config.py": """
class Config:
    SECRET_KEY = 'your_secret_key'
    MONGODB_URI = 'mongodb://localhost:27017/football_league'
"""
}

# Create the folders
for folder in folders:
    os.makedirs(folder, exist_ok=True)

# Create the files
for file_path, content in files.items():
    with open(file_path, "w") as file:
        file.write(content.strip())
        
print("Folder structure and files created successfully!")
