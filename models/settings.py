import datetime
from bson.objectid import ObjectId

class Settings:
    def __init__(self, db):
        self.collection = db['settings']

    def get_settings(self):
        settings = self.collection.find_one({})
        if not settings:
            # If settings do not exist, initialize with default values
            settings = {
                'league_name': 'Your League Name',
                'season_start_date': datetime.datetime.now()
            }
            self.collection.insert_one(settings)
        return settings

    def update_settings(self, data):
        self.collection.update_one({}, {'$set': data}, upsert=True)