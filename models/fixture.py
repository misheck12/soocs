# models/fixture.py
class Fixture:
    def __init__(self, home_team_id, away_team_id, match_date, home_score=None, away_score=None, status='scheduled'):
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id
        self.match_date = match_date
        self.home_score = home_score
        self.away_score = away_score
        self.status = status

    def to_dict(self):
        return {
            'home_team_id': self.home_team_id,
            'away_team_id': self.away_team_id,
            'match_date': self.match_date,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'status': self.status
        }
