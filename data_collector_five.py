from pymongo import MongoClient 
from pymongo.errors import BulkWriteError, ServerSelectionTimeoutError 
from datetime import datetime, timedelta, timezone

import requests
import time 



class MongoHandler: 
    def __init__(self): 
        pass 

    def connect(self):
        pass 

    def disconnect(self): 
        pass 

    def get_candle_collection(self): 
        pass 

    def get_last_updated_collection(self): 
        pass 

    def get_next_start_time(self): 
        pass 

    def get_last_updated_time(self): 
        pass 



class DataCollector: 
    def __init__(self): 
        pass 

    def run(self): 
        pass 

    def run_all(self): 
        pass 

    def request_to_binance(self): 
        pass 

    def save_to_mongo(self): 
        pass 

    def refresh_last_updated(self): 
        pass 

    ### utility methods ###
    @staticmethod
    def _response_to_dict(): 
        pass 

    @staticmethod
    def _make_start_millis(): 
        pass 

    @staticmethod
    def _make_utc():
        pass 

    @staticmethod
    def _make_millis_from_dt(): 
        pass 


if __name__ == "__main__": 
    mongo = MongoHandler()