import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from models.team import Team
from models.settings import Settings
from models.results import Results
from models.fixture import Fixture
from flask_wtf.csrf import CSRFProtect, generate_csrf
from utils.db import get_db
from datetime import datetime, timedelta
from config import Config
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = '5eeac454effdfb2917705251fa543a88'  # Replace with a strong, random key
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

client = MongoClient(app.config['MONGODB_URI'])
db = client.get_database()
teams_collection = db.teams
fixtures_collection = db.fixtures
users_collection = db.users
standings_collection = db.standings  # Ensure this collection exists

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@app.route('/')
def index():
    return render_template('index.html')

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    return User(str(user_data["_id"]), user_data["username"], user_data["password"]) if user_data else None

# Initialize Models
settings_model = Settings(db)
results_model = Results(db)

def compute_standings():
    try:
        teams = list(teams_collection.find())
        standings = []

        for team in teams:
            team_id = team['_id']
            team_name = team['name']

            # Initialize stats
            played = won = drawn = lost = goals_for = goals_against = 0

            # Fetch completed matches involving the team
            matches = fixtures_collection.find({
                'status': 'Completed',
                '$or': [
                    {'home_team_id': team_id},
                    {'away_team_id': team_id}
                ]
            })

            for match in matches:
                home_team = match['home_team_id'] == team_id
                home_score = match.get('home_score', 0)
                away_score = match.get('away_score', 0)
                played += 1

                if home_team:
                    goals_for += home_score
                    goals_against += away_score
                    if home_score > away_score:
                        won += 1
                    elif home_score == away_score:
                        drawn += 1
                    else:
                        lost += 1
                else:
                    goals_for += away_score
                    goals_against += home_score
                    if away_score > home_score:
                        won += 1
                    elif away_score == home_score:
                        drawn += 1
                    else:
                        lost += 1

            points = won * 3 + drawn
            goal_difference = goals_for - goals_against

            standings.append({
                'team_name': team_name,
                'played': played,
                'won': won,
                'drawn': drawn,
                'lost': lost,
                'goals_for': goals_for,
                'goals_against': goals_against,
                'goal_difference': goal_difference,
                'points': points
            })

        # Sort the standings by points, then goal difference
        standings.sort(key=lambda x: (x['points'], x['goal_difference']), reverse=True)
        return standings
    except Exception as e:
        logger.error(f"Error computing standings: {e}")
        return []

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = users_collection.find_one({"username": username})
        
        if user_data and check_password_hash(user_data['password'], password):
            user = User(str(user_data['_id']), user_data['username'], user_data['password'])
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')
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
        # Compute analytics data
        total_teams = teams_collection.count_documents({})
        upcoming_fixtures = fixtures_collection.count_documents({'status': 'Scheduled'})
        pending_approvals = fixtures_collection.count_documents({'status': 'Pending'})

        analytics = {
            'total_teams': total_teams,
            'upcoming_fixtures': upcoming_fixtures,
            'pending_approvals': pending_approvals
        }

        # Fetch required data for the dashboard
        teams = list(teams_collection.find())
        fixtures = list(fixtures_collection.find())
        results = results_model.get_all_results()  # Use the Results model
        admin_users = list(users_collection.find({'role': 'admin'}))
        standings = compute_standings()
        settings = settings_model.get_settings()  # Use the Settings model

        return render_template(
            'admin.html',
            analytics=analytics,
            teams=teams,
            fixtures=fixtures,
            results=results,
            admin_users=admin_users,
            standings=standings,
            settings=settings
        )
    except Exception as e:
        logger.error(f"Error in admin_dashboard: {e}")
        return jsonify({'message': 'Error loading admin dashboard.'}), 500
        
@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    try:
        league_name = request.form.get('league_name')
        season_start_date = request.form.get('season_start_date')

        if not league_name or not season_start_date:
            return jsonify({'success': False, 'message': 'All fields are required.'})

        season_start_date = datetime.strptime(season_start_date, '%Y-%m-%d')

        settings_model.update_settings({
            'league_name': league_name,
            'season_start_date': season_start_date
        })

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({'success': False, 'message': 'Error updating settings.'})

@app.route('/add-team', methods=['POST'])
@login_required
def add_team():
    """Add a new team."""
    team_name = request.form.get('team_name')
    logo_file = request.files.get('team_logo')

    if not team_name or not logo_file:
        return jsonify({'message': 'Team name and logo are required.'}), 400

    if not allowed_file(logo_file.filename):
        return jsonify({'message': 'Invalid file type for logo.'}), 400

    filename = secure_filename(logo_file.filename)
    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    logo_file.save(logo_path)
    logo_url = url_for('static', filename='uploads/' + filename)

    new_team = {
        "name": team_name,
        "logo_url": logo_url,
        # Initialize other fields if necessary
        "points": 0,
        "matches_played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_diff": 0
    }

    try:
        teams_collection.insert_one(new_team)
        return jsonify({'message': 'Team added successfully'}), 201
    except Exception as e:
        logger.error(f"Error adding team: {e}")
        return jsonify({'message': f'Error adding team: {e}'}), 500

@app.route('/generate-fixtures', methods=['POST'])
@login_required
def generate_fixtures_endpoint():
    teams = list(teams_collection.find())
    team_ids = [team['_id'] for team in teams]
    generate_fixtures(team_ids)
    return jsonify({'message': 'Fixtures generated successfully'})

@app.route('/get_all_fixtures', methods=['GET'])
@login_required
def get_all_fixtures():
    """Fetch and return all fixtures."""
    try :
        fixtures_cursor = fixtures_collection.find()
        fixtures = []
        for fixture_data in fixtures_cursor:
            home_team = teams_collection.find_one({"_id": fixture_data["home_team_id"]})
            away_team = teams_collection.find_one({"_id": fixture_data["away_team_id"]})
            if home_team and away_team:
                fixture = Fixture(
                    home_team_id=fixture_data["home_team_id"],
                    away_team_id=fixture_data["away_team_id"],
                    match_date=fixture_data["match_date"],
                    home_score=fixture_data.get("home_score"),
                    away_score=fixture_data.get("away_score"),
                    status=fixture_data.get("status", FixtureStatus.SCHEDULED.value),
                    rejection_reason=fixture_data.get("rejection_reason")
                )
                fixtures.append({
                    "id": str(fixture_data["_id"]),
                    "home_team": home_team["name"],
                    "away_team": away_team["name"],
                    "match_date": fixture.match_date.strftime("%Y-%m-%d"),
                    "status": fixture.status,
                    "home_score": fixture.home_score if fixture.home_score is not None else "N/A",
                    "away_score": fixture.away_score if fixture.away_score is not None else "N/A",
                    "rejection_reason": fixture.rejection_reason or "N/A"
                })
            else:
                logger.warning(f"Fixture {fixture_data['_id']} has invalid team references.")
        return jsonify({"fixtures": fixtures}), 200
    except Exception as e:
        logger.error(f"Error occurred in get_all_fixtures: {e}")
        return jsonify({'message': 'Failed to fetch fixtures.'}), 500

@app.route('/get_fixture/<fixture_id>', methods=['GET'])
@login_required
def get_fixture(fixture_id):
    """Fetch and return a specific fixture by ID."""
    try:
        fixture = fixtures_collection.find_one({"_id": ObjectId(fixture_id)})
        if fixture:
            fixture_id_str = str(fixture.pop('_id'))
            fixture_obj = Fixture(**fixture)  # Ensure Fixture model excludes 'logo'
            fixture_dict = fixture_obj.to_dict()
            fixture_dict['_id'] = fixture_id_str
            return jsonify({'fixture': fixture_dict}), 200
        return jsonify({'message': 'Fixture not found'}), 404
    except Exception as e:
        logger.error(f"Error occurred in get_fixture: {e}")
        return jsonify({'message': 'An error occurred'}), 500

@app.route('/update_fixture/<fixture_id>', methods=['POST'])
@login_required
def update_fixture(fixture_id):
    """Update a fixture's details."""
    try:
        fixture = fixtures_collection.find_one({"_id": ObjectId(fixture_id)})
        if not fixture:
            return jsonify({'message': 'Fixture not found'}), 404

        home_team_id = request.form.get('home_team_id')
        away_team_id = request.form.get('away_team_id')
        match_date = request.form.get('match_date')
        status = request.form.get('status')
        update_data = {}

        if home_team_id:
            update_data['home_team_id'] = ObjectId(home_team_id)
        if away_team_id:
            update_data['away_team_id'] = ObjectId(away_team_id)
        if match_date:
            update_data['match_date'] = datetime.strptime(match_date, '%Y-%m-%d')
        if status:
            update_data['status'] = status

        if update_data:
            fixtures_collection.update_one({"_id": ObjectId(fixture_id)}, {"$set": update_data})
            return jsonify({'message': 'Fixture updated successfully'}), 200
        else:
            return jsonify({'message': 'No valid fields provided for update'}), 400
    except Exception as e:
        logger.error(f"Error occurred in update_fixture: {e}")
        return jsonify({'message': 'An error occurred'}), 500

@app.route('/delete_fixture/<fixture_id>', methods=['DELETE'])
@login_required
def delete_fixture(fixture_id):
    """Delete a fixture by ID."""
    try:
        result = fixtures_collection.delete_one({"_id": ObjectId(fixture_id)})
        if result.deleted_count:
            return jsonify({'message': 'Fixture deleted successfully'}), 200
        return jsonify({'message': 'Fixture not found'}), 404
    except Exception as e:
        logger.error(f"Error occurred in delete_fixture: {e}")
        return jsonify({'message': 'An error occurred'}), 500

@app.route('/edit_team/<team_id>', methods=['POST'])
@login_required
def edit_team(team_id):
    try:
        team_name = request.form.get('team_name')
        team_logo = request.files.get('team_logo')
        
        if not team_name:
            return jsonify({'success': False, 'message': 'Team name is required.'})
        
        update_data = {'name': team_name}
        
        if team_logo:
            # Save new logo
            logo_filename = secure_filename(team_logo.filename)
            logo_path = os.path.join('static/uploads', logo_filename)
            team_logo.save(logo_path)
            update_data['logo_url'] = url_for('static', filename='uploads/' + logo_filename)
        
        teams_collection.update_one({'_id': ObjectId(team_id)}, {'$set': update_data})
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error editing team: {e}")
        return jsonify({'success': False, 'message': 'Error editing team.'})

# Route for creating a fixture
@app.route('/create_fixture', methods=['POST'])
@login_required
def create_fixture():
    try:
        data = request.get_json()
        home_team_id = data.get('home_team_id')
        away_team_id = data.get('away_team_id')
        match_date = data.get('match_date')
        
        # Validate inputs
        if not home_team_id or not away_team_id or not match_date:
            return jsonify({'success': False, 'message': 'Missing required fields.'})
        
        # Convert match_date to datetime object
        match_date = datetime.strptime(match_date, '%Y-%m-%d')
        
        # Create fixture object
        fixture = {
            'home_team_id': ObjectId(home_team_id),
            'away_team_id': ObjectId(away_team_id),
            'match_date': match_date,
            'status': 'Scheduled'
        }
        fixtures_collection.insert_one(fixture)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error creating fixture: {e}")
        return jsonify({'success': False, 'message': 'Error creating fixture.'})

# Route for approving a result
@app.route('/approve_result/<result_id>', methods=['POST'])
@login_required
def approve_result(result_id):
    try:
        # Update result status to 'Approved'
        fixtures_collection.update_one({'_id': ObjectId(result_id)}, {'$set': {'status': 'Approved'}})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error approving result: {e}")
        return jsonify({'success': False, 'message': 'Error approving result.'})

# Route for rejecting a result
@app.route('/reject_result/<result_id>', methods=['POST'])
@login_required
def reject_result(result_id):
    try:
        # Update result status to 'Rejected'
        fixtures_collection.update_one({'_id': ObjectId(result_id)}, {'$set': {'status': 'Rejected'}})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error rejecting result: {e}")
        return jsonify({'success': False, 'message': 'Error rejecting result.'})

# Route for adding a user
@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required.'})
        
        hashed_password = generate_password_hash(password)
        
        user = {
            'username': username,
            'password': hashed_password,
            'role': 'admin'
        }
        users_collection.insert_one(user)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        return jsonify({'success': False, 'message': 'Error adding user.'})

# Route for deleting a user
@app.route('/delete_user/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    try:
        users_collection.delete_one({'_id': ObjectId(user_id)})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({'success': False, 'message': 'Error deleting user.'})

# Route for changing password
@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': 'All fields are required.'})
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'New passwords do not match.'})
        
        user = users_collection.find_one({'username': session.get('username')})
        if not user or not check_password_hash(user['password'], current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect.'})
        
        hashed_password = generate_password_hash(new_password)
        users_collection.update_one({'_id': user['_id']}, {'$set': {'password': hashed_password}})
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({'success': False, 'message': 'Error changing password.'})

# Route for generating reports
@app.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
    try:
        data = request.get_json()
        report_type = data.get('report_type')
        
        if not report_type:
            return jsonify({'success': False, 'message': 'Report type is required.'})
        
        # Generate report based on report_type
        if report_type == 'match_statistics':
            report_html = generate_match_statistics_report()
        elif report_type == 'team_performance':
            report_html = generate_team_performance_report()
        elif report_type == 'league_progress':
            report_html = generate_league_progress_report()
        else:
            return jsonify({'success': False, 'message': 'Invalid report type.'})
        
        return jsonify({'success': True, 'report_html': report_html})
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({'success': False, 'message': 'Error generating report.'})

def generate_match_statistics_report():
    """Generate match statistics report."""
    try:
        # Fetch all completed fixtures
        completed_fixtures = fixtures_collection.find({'status': 'Completed'})

        total_matches = completed_fixtures.count()
        total_goals = 0

        for fixture in completed_fixtures:
            home_score = fixture.get('home_score', 0)
            away_score = fixture.get('away_score', 0)
            total_goals += home_score + away_score

        average_goals = total_goals / total_matches if total_matches > 0 else 0

        report_html = f"""
        <h3>Match Statistics Report</h3>
        <p><strong>Total Matches Played:</strong> {total_matches}</p>
        <p><strong>Total Goals Scored:</strong> {total_goals}</p>
        <p><strong>Average Goals per Match:</strong> {average_goals:.2f}</p>
        """
        return report_html
    except Exception as e:
        logger.error(f"Error generating match statistics report: {e}")
        return '<p>Error generating match statistics report.</p>'

def generate_team_performance_report():
    """Generate team performance report."""
    try:
        teams = teams_collection.find()
        report_rows = ""

        for team in teams:
            team_id = team['_id']
            team_name = team['name']

            # Matches where the team is involved
            matches = fixtures_collection.find({
                'status': 'Completed',
                '$or': [
                    {'home_team_id': team_id},
                    {'away_team_id': team_id}
                ]
            })

            played = matches.count()
            won = drawn = lost = goals_for = goals_against = 0

            for match in matches:
                home_team = match['home_team_id'] == team_id
                home_score = match.get('home_score', 0)
                away_score = match.get('away_score', 0)

                if home_team:
                    goals_for += home_score
                    goals_against += away_score
                    if home_score > away_score:
                        won += 1
                    elif home_score == away_score:
                        drawn += 1
                    else:
                        lost += 1
                else:
                    goals_for += away_score
                    goals_against += home_score
                    if away_score > home_score:
                        won += 1
                    elif away_score == home_score:
                        drawn += 1
                    else:
                        lost += 1

            report_rows += f"""
            <tr>
                <td>{team_name}</td>
                <td>{played}</td>
                <td>{won}</td>
                <td>{drawn}</td>
                <td>{lost}</td>
                <td>{goals_for}</td>
                <td>{goals_against}</td>
                <td>{goals_for - goals_against}</td>
                <td>{(won * 3) + drawn}</td>
            </tr>
            """

        report_html = f"""
        <h3>Team Performance Report</h3>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Team</th>
                    <th>Played</th>
                    <th>Won</th>
                    <th>Drawn</th>
                    <th>Lost</th>
                    <th>GF</th>
                    <th>GA</th>
                    <th>GD</th>
                    <th>Points</th>
                </tr>
            </thead>
            <tbody>
                {report_rows}
            </tbody>
        </table>
        """
        return report_html
    except Exception as e:
        logger.error(f"Error generating team performance report: {e}")
        return '<p>Error generating team performance report.</p>'

def generate_league_progress_report():
    """Generate league progress report."""
    try:
        total_fixtures = fixtures_collection.count_documents({})
        completed_matches = fixtures_collection.count_documents({'status': 'Completed'})
        scheduled_matches = fixtures_collection.count_documents({'status': 'Scheduled'})

        completion_percentage = (completed_matches / total_fixtures * 100) if total_fixtures > 0 else 0

        report_html = f"""
        <h3>League Progress Report</h3>
        <p><strong>Total Fixtures:</strong> {total_fixtures}</p>
        <p><strong>Completed Matches:</strong> {completed_matches}</p>
        <p><strong>Scheduled Matches:</strong> {scheduled_matches}</p>
        <p><strong>League Completion:</strong> {completion_percentage:.2f}%</p>
        """
        return report_html
    except Exception as e:
        logger.error(f"Error generating league progress report: {e}")
        return '<p>Error generating league progress report.</p>'

@app.route('/submit-game', methods=['POST'])
@login_required  # Ensure only authorized users can submit game results
def submit_game():
    """Submit game results and update team statistics."""
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    fixture_id = data.get('fixture_id')
    home_score = data.get('home_score')
    away_score = data.get('away_score')

    # Input validation
    if not fixture_id or home_score is None or away_score is None:
        return jsonify({'message': 'Missing required fields'}), 400

    try:
        home_score = int(home_score)
        away_score = int(away_score)
    except ValueError:
        return jsonify({'message': 'Scores must be integers'}), 400

    try:
        fixture = fixtures_collection.find_one({"_id": ObjectId(fixture_id)})
    except Exception as e:
        return jsonify({'message': f'Invalid fixture_id format: {e}'}), 400

    if not fixture:
        return jsonify({'message': 'Fixture not found'}), 404

    try:
        home_team = teams_collection.find_one({"_id": ObjectId(fixture['home_team_id'])})
        away_team = teams_collection.find_one({"_id": ObjectId(fixture['away_team_id'])})
    except Exception as e:
        return jsonify({'message': f'Error fetching teams: {e}'}), 500

    if not home_team or not away_team:
        return jsonify({'message': 'One or both teams not found'}), 404

    try:
        # Initialize Team objects
        home_team_obj = Team(**home_team)
        away_team_obj = Team(**away_team)

        # Update stats for both teams
        home_team_obj.update_stats(goals_for=home_score, goals_against=away_score)
        away_team_obj.update_stats(goals_for=away_score, goals_against=home_score)

        # Save updated stats to the database
        teams_collection.update_one(
            {"_id": ObjectId(home_team['_id'])},
            {"$set": home_team_obj.to_dict()}
        )
        teams_collection.update_one(
            {"_id": ObjectId(away_team['_id'])},
            {"$set": away_team_obj.to_dict()}
        )

        # Update fixture status to pending
        fixtures_collection.update_one(
            {"_id": ObjectId(fixture_id)},
            {"$set": {
                "home_score": home_score,
                "away_score": away_score,
                "status": "pending"
            }}
        )

        return jsonify({'message': 'Game results submitted successfully'}), 200

    except Exception as e:
        logger.error(f"Error submitting game results: {e}")
        return jsonify({'message': 'Failed to submit game results'}), 500

@app.route('/approve-game/<fixture_id>', methods=['POST'])
@login_required
def approve_game(fixture_id):
    """Approve a pending fixture."""
    try:
        result = fixtures_collection.update_one(
            {"_id": ObjectId(fixture_id), "status": "Scheduled"},
            {"$set": {"status": "Approved"}}
        )
        if result.modified_count:
            flash('Fixture approved successfully.', 'success')
        else:
            flash('Fixture not found or already approved/rejected.', 'warning')
    except Exception as e:
        flash(f'Error approving fixture: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/reject-game/<fixture_id>', methods=['POST'])
@login_required
def reject_game(fixture_id):
    """Reject a pending fixture."""
    try:
        result = fixtures_collection.update_one(
            {"_id": ObjectId(fixture_id), "status": "Scheduled"},
            {"$set": {"status": "Rejected"}}
        )
        if result.modified_count:
            flash('Fixture rejected successfully.', 'success')
        else:
            flash('Fixture not found or already approved/rejected.', 'warning')
    except Exception as e:
        flash(f'Error rejecting fixture: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

def generate_fixtures(team_ids):
    """Generate a round-robin schedule for all teams and store fixtures in the database."""
    try:
        teams = team_ids

        if len(teams) < 2:
            flash("Not enough teams to generate fixtures.", 'warning')
            return

        # If odd number of teams, add a dummy team with ID None
        if len(teams) % 2 != 0:
            teams.append(None)  # Add a dummy team to make it even

        fixtures = []
        num_rounds = len(teams) - 1

        teams_ids = teams.copy()

        for round_num in range(num_rounds):
            round_matches = []
            for i in range(len(teams) // 2):
                home = teams_ids[i]
                away = teams_ids[-i-1]
                if home is not None and away is not None:
                    # Define match date (customize scheduling logic as needed)
                    match_date = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0) + \
                                 timedelta(days=round_num*7 + i)
                    store_fixture(home, away, match_date)
                    round_matches.append((home, away))
            teams_ids.insert(1, teams_ids.pop())  # Rotate teams
            fixtures.append(round_matches)

        # Reverse fixtures for the second half of the season (home and away)
        reversed_fixtures = [[(away, home) for home, away in round_fixtures] for round_fixtures in fixtures]
        for round_fixtures in reversed_fixtures:
            for home, away in round_fixtures:
                match_date = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0) + \
                             timedelta(days=(fixtures.index(round_fixtures) + 1)*7)
                store_fixture(home, away, match_date)
        flash("All fixtures generated and stored successfully.", 'success')
    except Exception as e:
        flash(f'Error generating fixtures: {e}', 'danger')

def store_fixture(home_team_id, away_team_id, match_date):
    """Store a single fixture in the database."""
    try:
        fixtures_collection.insert_one({
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'match_date': match_date,
            'status': 'Scheduled'
        })
        logger.info(f"Fixture scheduled: {home_team_id} vs {away_team_id} on {match_date}")
    except Exception as e:
        logger.error(f"Error storing fixture: {e}")
        flash(f'Error storing fixture: {e}', 'danger')

def increment_date(date_str):
    """Increment a date string by one week."""
    date_format = "%Y-%m-%d"
    try:
        current_date = datetime.strptime(date_str, date_format)
        new_date = current_date + timedelta(days=7)  # Weekly matches
        return new_date.strftime(date_format)
    except ValueError as ve:
        logger.error(f"Invalid date format: {date_str}. Error: {ve}")
        flash('Invalid date format.', 'danger')
        return date_str

@app.route('/fixtures')
def fixtures():
    return render_template('fixtures.html')

@app.route('/standings')
def standings():
    teams = list(teams_collection.find().sort([("points", -1), ("goal_diff", -1), ("goals_for", -1)]))
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
            'GoalDifference': team.get('goal_diff', 0),
            'Points': team.get('points', 0)
        })
        position += 1
    return render_template('standings.html', standings=standings)

@app.route('/fixtures', methods=['GET'])
@login_required
def get_fixtures():
    """Fetch and return fixtures based on query parameters."""
    status = request.args.get('status')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    team_id = request.args.get('team_id')

    query = {}
    if status:
        query['status'] = status
    if from_date or to_date:
        query['match_date'] = {}
        if from_date:
            try:
                query['match_date']['$gte'] = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({'message': "Invalid 'from_date' format. Use YYYY-MM-DD."}), 400
        if to_date:
            try:
                query['match_date']['$lte'] = datetime.strptime(to_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({'message': "Invalid 'to_date' format. Use YYYY-MM-DD."}), 400
    if team_id:
        try:
            obj_id = ObjectId(team_id)
            query['$or'] = [
                {"home_team_id": obj_id},
                {"away_team_id": obj_id}
            ]
        except Exception as e:
            return jsonify({'message': f"Invalid 'team_id': {e}"}), 400

    try:
        fixtures = list(fixtures_collection.find(query))

        for fixture in fixtures:
            home_team_doc = teams_collection.find_one({"_id": fixture['home_team_id']})
            away_team_doc = teams_collection.find_one({"_id": fixture['away_team_id']})
            fixture['home_team'] = home_team_doc['name'] if home_team_doc else "Unknown"
            fixture['away_team'] = away_team_doc['name'] if away_team_doc else "Unknown"

        # Serialize fixtures
        serialized_fixtures = serialize_fixtures(fixtures)

        return jsonify({"fixtures": serialized_fixtures}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to fetch fixtures.'}), 500

@app.route('/standings', methods=['GET'])
@login_required
def get_standings():
    """Fetch and return standings."""
    try:
        standings = list(standings_collection.find({}).sort("points", -1))  # Sort by points descending
        serialized_standings = serialize_standings(standings)
        return jsonify({"standings": serialized_standings}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Failed to fetch standings.'}), 500

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

@app.route('/fixtures_page')
@login_required
def fixtures_page():
    """Render the Fixtures page."""
    return render_template('fixtures.html')

@app.route('/standings_page')
@login_required
def standings_page():
    """Render the Standings page."""
    return render_template('standings.html')  # Ensure your template is named 'standings.html'

@app.route('/get-teams', methods=['GET'])
@login_required
def get_teams():
    try:
        teams = list(teams_collection.find())
        team_list = []
        for team in teams:
            # Extract only the required fields for the Team class
            team_data = {
                'name': team.get('name', 'Unknown Team'),
                'logo_url': team.get('logo_url', '/static/uploads/default-logo.png'),
                'points': team.get('points', 0),
                'matches_played': team.get('matches_played', 0),
                'wins': team.get('wins', 0),
                'draws': team.get('draws', 0),
                'losses': team.get('losses', 0),
                'goals_for': team.get('goals_for', 0),
                'goals_against': team.get('goals_against', 0),
                'goal_diff': team.get('goal_diff', 0)
            }
            
            # Instantiate the Team object with the correct arguments
            team_obj = Team(**team_data)
            team_dict = team_obj.to_dict()
            team_dict['_id'] = str(team['_id'])
            team_list.append(team_dict)
        return jsonify({'teams': team_list}), 200
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return jsonify({'message': 'An error occurred'}), 500

@app.route('/get-team/<team_id>', methods=['GET'])
@login_required
def get_team(team_id):
    """Fetch and return a specific team by ID."""
    try:
        team = teams_collection.find_one({"_id": ObjectId(team_id)})
    except Exception as e:
        return jsonify({'message': f'Invalid team_id: {e}'}), 400

    if team:
        # Exclude the 'logo' field to prevent unexpected keyword argument
        team_data = {
            'name': team.get('name', 'Unknown Team'),
            'logo_url': team.get('logo_url', '/static/uploads/default-logo.png'),
            'points': team.get('points', 0),
            'matches_played': team.get('matches_played', 0),
            'wins': team.get('wins', 0),
            'draws': team.get('draws', 0),
            'losses': team.get('losses', 0),
            'goals_for': team.get('goals_for', 0),
            'goals_against': team.get('goals_against', 0),
            'goal_diff': team.get('goal_diff', 0)
        }
        
        team_obj = Team(**team_data)
        team_dict = team_obj.to_dict()
        team_dict['_id'] = str(team['_id'])
        return jsonify({'team': team_dict}), 200
    return jsonify({'message': 'Team not found'}), 404

@app.route('/update-team/<team_id>', methods=['POST'])
@login_required
def update_team(team_id):
    """Update a team's details."""
    try:
        team = teams_collection.find_one({"_id": ObjectId(team_id)})
    except Exception as e:
        return jsonify({'message': f'Invalid team_id: {e}'}), 400

    if not team:
        return jsonify({'message': 'Team not found'}), 404

    name = request.form.get('team_name')
    logo_file = request.files.get('team_logo')
    update_data = {}

    if name:
        update_data['name'] = name

    if logo_file and allowed_file(logo_file.filename):
        filename = secure_filename(logo_file.filename)
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logo_file.save(logo_path)
        update_data['logo_url'] = url_for('static', filename='uploads/' + filename)

    if update_data:
        teams_collection.update_one({"_id": ObjectId(team_id)}, {"$set": update_data})
        return jsonify({'message': 'Team updated successfully'}), 200
    else:
        return jsonify({'message': 'No valid fields provided for update'}), 400

@app.route('/delete-team/<team_id>', methods=['DELETE'])
@login_required
def delete_team(team_id):
    """Delete a team by ID."""
    try:
        result = teams_collection.delete_one({"_id": ObjectId(team_id)})
    except Exception as e:
        return jsonify({'message': f'Invalid team_id: {e}'}), 400

    if result.deleted_count:
        return jsonify({'message': 'Team deleted successfully'}), 200
    return jsonify({'message': 'Team not found'}), 404

def serialize_fixtures(fixtures):
    """Serialize fixture data for JSON response."""
    serialized = []
    for fixture in fixtures:
        serialized_fixture = {
            "_id": str(fixture["_id"]),
            "home_team_id": str(fixture["home_team_id"]),
            "away_team_id": str(fixture["away_team_id"]),
            "match_date": fixture["match_date"].strftime("%Y-%m-%d") if fixture.get("match_date") else "",
            "status": fixture.get("status", ""),
            "home_team": fixture.get("home_team", "Unknown"),
            "away_team": fixture.get("away_team", "Unknown"),
            # Add other fields as necessary
        }
        serialized.append(serialized_fixture)
    return serialized

def serialize_standings(standings):
    """Serialize standings data for JSON response."""
    serialized = []
    for team in standings:
        serialized_team = {
            "Position": team.get("position", ""),
            "TeamLogo": team.get("logo_url", ""),  # Ensure this field exists in your DB
            "TeamName": team.get("team_name", ""),
            "MatchesPlayed": team.get("matches_played", 0),
            "Wins": team.get("wins", 0),
            "Draws": team.get("draws", 0),
            "Losses": team.get("losses", 0),
            "GoalsFor": team.get("goals_for", 0),
            "GoalsAgainst": team.get("goals_against", 0),
            "GoalDifference": team.get("goal_difference", 0),
            "Points": team.get("points", 0)
        }
        serialized.append(serialized_team)
    return serialized

if __name__ == '__main__':
    app.run(debug=True)
