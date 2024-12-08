class Team:
    def __init__(self, name, logo, points=0, matches_played=0, wins=0, draws=0, losses=0, goals_for=0, goals_against=0, goal_diff=0):
        self.name = name
        self.logo = logo
        self.points = points
        self.matches_played = matches_played
        self.wins = wins
        self.draws = draws
        self.losses = losses
        self.goals_for = goals_for
        self.goals_against = goals_against
        self.goal_diff = goal_diff

    def update_stats(self, goals_for, goals_against):
        """Update team stats based on match results."""
        self.matches_played += 1
        self.goals_for += goals_for
        self.goals_against += goals_against
        self.goal_diff = self.goals_for - self.goals_against
        
        if goals_for > goals_against:  # Win
            self.wins += 1
            self.points += 3
        elif goals_for == goals_against:  # Draw
            self.draws += 1
            self.points += 1
        else:  # Loss
            self.losses += 1

    def to_dict(self):
        """Convert team object to dictionary format."""
        return {
            'name': self.name,
            'logo': self.logo,
            'points': self.points,
            'matches_played': self.matches_played,
            'wins': self.wins,
            'draws': self.draws,
            'losses': self.losses,
            'goal_diff': self.goal_diff,
            'goals_for': self.goals_for,
            'goals_against': self.goals_against
        }
