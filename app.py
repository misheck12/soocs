from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from models.team import Team
from utils.db import get_db
from datetime import datetime, timedelta
from config import Config
from werkzeug.security import check_password_hash
from bson.objectid import ObjectId  # Import ObjectId

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = '5eeac454effdfb2917705251fa543a88'  # Replace with a strong, random key

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

client = MongoClient(app.config['MONGODB_URI'])
db = client.get_database()
teams_collection = db.teams
fixtures_collection = db.fixtures
users_collection = db.users

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = str(id)  # Convert ObjectId to string
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = users_collection.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_data["_id"], user_data["username"], user_data["password"])
    except Exception as e:
        print(f"Error loading user: {e}")
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username') or request.form['username']
        password = request.form.get('password') or request.form['password']
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return redirect(url_for('login'))
        
        user_data = users_collection.find_one({"username": username})
        
        if user_data:
            print(f"User found: {user_data['username']}")
            if check_password_hash(user_data['password'], password):
                user = User(user_data['_id'], user_data['username'], user_data['password'])
                login_user(user)
                return redirect(url_for('admin_dashboard'))
            else:
                print("Password does not match.")
                flash('Invalid username or password. Please try again.', 'error')
                return redirect(url_for('login'))
        else:
            print("User not found.")
            flash('Invalid username or password. Please try again.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    try:
        # Fetch scheduled fixtures
        fixtures = list(fixtures_collection.find({"status": "scheduled"}))

        # Extract unique team IDs
        team_ids = set()
        for fixture in fixtures:
            team_ids.add(fixture['home_team_id'])
            team_ids.add(fixture['away_team_id'])

        # Fetch all teams in a single query
        teams = teams_collection.find({"_id": {"$in": list(team_ids)}})
        team_mapping = {team['_id']: team['name'] for team in teams}

        # Process fixtures using the mapping
        processed_fixtures = []
        for fixture in fixtures:
            home_team_name = team_mapping.get(fixture['home_team_id'], 'Unknown')
            away_team_name = team_mapping.get(fixture['away_team_id'], 'Unknown')
            match_date = fixture['match_date'].strftime('%Y-%m-%d') if 'match_date' in fixture else 'TBD'

            processed_fixture = {
                'home_team_name': home_team_name,
                'away_team_name': away_team_name,
                'match_date': match_date,
                'fixture_id': str(fixture['_id'])
            }
            processed_fixtures.append(processed_fixture)

        return render_template('admin.html', fixtures=processed_fixtures)
    except Exception as e:
        print(f"Error loading admin dashboard: {e}")
        flash('Failed to load admin dashboard.', 'error')
        return redirect(url_for('index'))

@app.route('/add-team', methods=['POST'])
@login_required
def add_team():
    data = request.json
    team = Team(
        name=data['team_name'],
        logo=data['team_logo']
    )
    try:
        teams_collection.insert_one(team.to_dict())
        return jsonify({'message': 'Team added successfully'}), 201
    except Exception as e:
        print(f"Error adding team: {e}")
        return jsonify({'message': 'Failed to add team'}), 500

@app.route('/generate-fixtures', methods=['POST'])
@login_required
def generate_fixtures_endpoint():
    try:
        teams = list(teams_collection.find())
        team_ids = [team['_id'] for team in teams]
        fixtures = generate_fixtures(team_ids)
        match_date = '2024-01-01'  # Example starting date
        for round_num, round_fixtures in enumerate(fixtures):
            for match in round_fixtures:
                store_fixture(match[0], match[1], match_date)
                match_date = increment_date(match_date)  # Increment match date as needed
        return jsonify({'message': 'Fixtures generated successfully'}), 201
    except Exception as e:
        print(f"Error generating fixtures: {e}")
        return jsonify({'message': 'Failed to generate fixtures'}), 500

@app.route('/fixtures', methods=['GET'])
def get_fixtures():
    # Get query parameters
    status = request.args.get('status')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    team_id = request.args.get('team_id')

    # Build the query
    query = {}
    if status:
        query['status'] = status
    if from_date or to_date:
        query['match_date'] = {}
        if from_date:
            try:
                query['match_date']['$gte'] = datetime.strptime(from_date, '%Y-%m-%d')
            except ValueError:
                flash('Invalid from_date format. Use YYYY-MM-DD.', 'error')
                return redirect(url_for('index'))
        if to_date:
            try:
                query['match_date']['$lte'] = datetime.strptime(to_date, '%Y-%m-%d')
            except ValueError:
                flash('Invalid to_date format. Use YYYY-MM-DD.', 'error')
                return redirect(url_for('index'))
    if team_id:
        try:
            team_oid = ObjectId(team_id)
            query['$or'] = [
                {'home_team_id': team_oid},
                {'away_team_id': team_oid}
            ]
        except Exception as e:
            flash('Invalid team_id.', 'error')
            return redirect(url_for('index'))

    try:
        # Fetch fixtures based on the query
        fixtures = list(fixtures_collection.find(query))

        # Process fixtures to include team names and format data
        for fixture in fixtures:
            home_team = teams_collection.find_one({'_id': ObjectId(fixture['home_team_id'])})
            away_team = teams_collection.find_one({'_id': ObjectId(fixture['away_team_id'])})

            fixture['home_team_name'] = home_team['name'] if home_team else 'Unknown'
            fixture['away_team_name'] = away_team['name'] if away_team else 'Unknown'

            # Convert ObjectId to string for JSON serialization
            fixture['_id'] = str(fixture['_id'])
            fixture['home_team_id'] = str(fixture['home_team_id'])
            fixture['away_team_id'] = str(fixture['away_team_id'])
            # Format date
            fixture['match_date'] = fixture['match_date'].strftime('%Y-%m-%d')

        return jsonify({'fixtures': fixtures}), 200
    except Exception as e:
        print(f"Error fetching fixtures: {e}")
        return jsonify({'message': 'Failed to fetch fixtures'}), 500

@app.route('/standings')
def standings():
    standings_data = get_standings_data()
    return render_template('standings.html', standings=standings_data)

def get_standings_data():
    try:
        teams = list(teams_collection.find().sort([
            ("points", -1),
            ("goal_difference", -1),
            ("goals_for", -1)
        ]))
        standings = []
        position = 1
        for team in teams:
            standings.append({
                'Position': position,
                'TeamLogo': team.get('logo', ''),
                'TeamName': team.get('name', 'Unknown'),
                'MatchesPlayed': team.get('matches_played', 0),
                'Wins': team.get('wins', 0),
                'Draws': team.get('draws', 0),
                'Losses': team.get('losses', 0),
                'GoalsFor': team.get('goals_for', 0),
                'GoalsAgainst': team.get('goals_against', 0),
                'GoalDifference': team.get('goal_difference', 0),
                'Points': team.get('points', 0)
            })
            position += 1
        return standings
    except Exception as e:
        print(f"Error getting standings data: {e}")
        return []

@app.route('/approve-game/<fixture_id>', methods=['POST'])
@login_required
def approve_game(fixture_id):
    try:
        fixtures_collection.update_one(
            {"_id": ObjectId(fixture_id)},
            {"$set": {"status": "approved"}}
        )
        flash('Game approved successfully.', 'success')
    except Exception as e:
        print(f"Error approving game: {e}")
        flash('Failed to approve game.', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/approved-fixtures')
@login_required
def approved_fixtures():
    try:
        # Fetch approved fixtures
        fixtures = list(fixtures_collection.find({"status": "approved"}))

        # Extract unique team IDs
        team_ids = set()
        for fixture in fixtures:
            team_ids.add(fixture['home_team_id'])
            team_ids.add(fixture['away_team_id'])

        # Fetch all teams in a single query
        teams = teams_collection.find({"_id": {"$in": list(team_ids)}})
        team_mapping = {team['_id']: team['name'] for team in teams}

        # Process fixtures using the mapping
        processed_fixtures = []
        for fixture in fixtures:
            home_team_name = team_mapping.get(fixture['home_team_id'], 'Unknown')
            away_team_name = team_mapping.get(fixture['away_team_id'], 'Unknown')
            match_date = fixture.get('match_date')
            if match_date:
                match_date = match_date.strftime('%Y-%m-%d')
            else:
                match_date = 'TBD'

            processed_fixture = {
                'home_team_name': home_team_name,
                'away_team_name': away_team_name,
                'match_date': match_date
            }
            processed_fixtures.append(processed_fixture)

        return render_template('approved_fixtures.html', fixtures=processed_fixtures)
    except Exception as e:
        print(f"Error loading approved fixtures: {e}")
        flash('Failed to load approved fixtures.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/rejected-fixtures')
@login_required
def rejected_fixtures():
    try:
        # Fetch rejected fixtures
        fixtures = list(fixtures_collection.find({"status": "rejected"}))

        # Extract unique team IDs
        team_ids = set()
        for fixture in fixtures:
            team_ids.add(fixture['home_team_id'])
            team_ids.add(fixture['away_team_id'])

        # Fetch all teams in a single query
        teams = teams_collection.find({"_id": {"$in": list(team_ids)}})
        team_mapping = {team['_id']: team['name'] for team in teams}

        # Process fixtures using the mapping
        processed_fixtures = []
        for fixture in fixtures:
            home_team_name = team_mapping.get(fixture['home_team_id'], 'Unknown')
            away_team_name = team_mapping.get(fixture['away_team_id'], 'Unknown')
            match_date = fixture.get('match_date')
            if match_date:
                match_date = match_date.strftime('%Y-%m-%d')
            else:
                match_date = 'TBD'
            rejection_reason = fixture.get('rejection_reason', 'No reason provided')

            processed_fixture = {
                'home_team_name': home_team_name,
                'away_team_name': away_team_name,
                'match_date': match_date,
                'rejection_reason': rejection_reason
            }
            processed_fixtures.append(processed_fixture)

        return render_template('rejected_fixtures.html', fixtures=processed_fixtures)
    except Exception as e:
        print(f"Error loading rejected fixtures: {e}")
        flash('Failed to load rejected fixtures.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/reject-game/<fixture_id>', methods=['POST'])
@login_required
def reject_game(fixture_id):
    try:
        rejection_reason = request.form.get('rejection_reason', 'No reason provided')

        # Update the fixture's status and add the rejection reason
        fixtures_collection.update_one(
            {'_id': ObjectId(fixture_id)},
            {'$set': {'status': 'rejected', 'rejection_reason': rejection_reason}}
        )
        flash('Fixture rejected successfully.', 'success')
    except Exception as e:
        print(f"Error rejecting fixture: {e}")
        flash('Failed to reject fixture.', 'error')
    return redirect(url_for('rejected_fixtures'))

@app.route('/submit-game', methods=['GET', 'POST'])
@login_required
def submit_game():
    if request.method == 'POST':
        data = request.form
        fixture_id = data.get('fixture_id')
        home_score = int(data.get('home_score', 0))
        away_score = int(data.get('away_score', 0))
        
        try:
            # Update fixture with submitted results
            fixtures_collection.update_one(
                {"_id": ObjectId(fixture_id)},
                {
                    "$set": {
                        "home_score": home_score,
                        "away_score": away_score,
                        "status": "pending"
                    }
                }
            )
            flash('Game results submitted successfully.', 'success')
            return jsonify({'message': 'Game results submitted successfully'}), 200
        except Exception as e:
            print(f"Error submitting game results: {e}")
            flash('Failed to submit game results.', 'error')
            return jsonify({'message': 'Failed to submit game results'}), 500
    
    try:
        fixtures = list(fixtures_collection.find({"status": "scheduled"}))
        return render_template('submit_game.html', fixtures=fixtures)
    except Exception as e:
        print(f"Error fetching scheduled fixtures: {e}")
        flash('Failed to load fixtures.', 'error')
        return redirect(url_for('admin_dashboard'))

def increment_date(date_str):
    date_format = "%Y-%m-%d"
    current_date = datetime.strptime(date_str, date_format)
    new_date = current_date + timedelta(days=7)  # Weekly matches
    return new_date.strftime(date_format)

def generate_fixtures(teams):
    num_teams = len(teams)
    if num_teams % 2 != 0:
        teams.append(None)  # Add a dummy team if odd number of teams

    fixtures = []
    num_rounds = len(teams) - 1

    for round_num in range(num_rounds):
        round_fixtures = []
        for i in range(len(teams) // 2):
            home = teams[i]
            away = teams[-i-1]
            if home is not None and away is not None:
                round_fixtures.append((home, away))
        teams.insert(1, teams.pop())  # Rotate teams
        fixtures.append(round_fixtures)

    # Reverse fixtures for the second half of the season (home and away)
    reversed_fixtures = [[(away, home) for home, away in round_fixtures] for round_fixtures in fixtures]
    fixtures.extend(reversed_fixtures)

    return fixtures

def store_fixture(home_team_id, away_team_id, match_date):
    try:
        fixtures_collection.insert_one({
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'match_date': datetime.strptime(match_date, "%Y-%m-%d"),
            'status': 'scheduled'
        })
    except Exception as e:
        print(f"Error storing fixture: {e}")

if __name__ == '__main__':
    app.run(debug=True)
