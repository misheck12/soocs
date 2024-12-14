import datetime
from bson.objectid import ObjectId

class Results:
    def __init__(self, db):
        self.collection = db['results']

    def add_result(self, fixture_id, home_score, away_score, submitted_by):
        result = {
            'fixture_id': ObjectId(fixture_id),
            'home_score': home_score,
            'away_score': away_score,
            'submitted_by': submitted_by,
            'status': 'Pending',  # Results start as pending approval
            'submitted_at': datetime.datetime.now()
        }
        self.collection.insert_one(result)

    def update_result(self, result_id, home_score, away_score):
        self.collection.update_one(
            {'_id': ObjectId(result_id)},
            {'$set': {
                'home_score': home_score,
                'away_score': away_score,
                'status': 'Pending',  # Reset status to pending approval
                'updated_at': datetime.datetime.now()
            }}
        )

    def delete_result(self, result_id):
        self.collection.delete_one({'_id': ObjectId(result_id)})

    def get_result(self, result_id):
        return self.collection.find_one({'_id': ObjectId(result_id)})

    def get_all_results(self):
        return list(self.collection.find())