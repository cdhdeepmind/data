from pymongo import MongoClient
from pymongo.errors import BulkWriteError, ServerSelectionTimeoutError
from datetime import datetime, timedelta, timezone

import requests
import time 




class MongoHandler: 
    def __init__(self, uri, db_name): 
        self.uri = uri
        self.db_name = db_name
        self.client = None 
        self.db = None 


    def connect(self): 
        try: 
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
        except ServerSelectionTimeoutError as e: 
            print('Server selection time out error occured!')
            raise
        except Exception as e: 
            print('Another error occured!')
            raise


    def close(self): 
        self.client.close()
          

    def get_candle_collection(self, interval: str): 
        # when connect() has not been called first
        if self.client is None: 
            raise ConnectionError('MongoDB is not connected')
        return self.db[f'BTCUSDT_{interval}']
    

    # last updated time infomation collection, (interval, end_time, start_time)
    def get_last_updated_collection(self):
        # when connect() has not been called first
        if self.client is None: 
            raise ConnectionError('MongoDB is not connected')
        return self.db['last_updated']


    # get next_start_time(milliseconds) from last_updated_collection
    def get_next_start_time(self, interval: str): 
        collection = self.get_last_updated_collection()
        doc = collection.find_one({"interval": interval})
        start_time = doc['start_time']  # start_time : milliseconds
        return start_time


    # get last_updated_time(milliseconds) from last_updated_collection
    def get_last_updated_time(self, interval: str): 
        pass 


    





class DataCollector: 
    def __init__(self, mongo=None): 
        self.mongo = mongo 


    def run(self, start=None, end=None, interval=None): 

        # when used with collection data (last_updated_time)
        if start is None:        
            default_start = datetime(2020, 1, 1)
            default_start_utc = self.make_dt_utc(default_start)
            default_start_millis = self.make_millis_from_dt(default_start_utc)
            start_millis = self.mongo.get_start_time(interval)             
            start_millis = start_millis or default_start_millis
        
        # when the run method is used individually
        else: 
            start_utc = self.make_utc(start)
            start_millis = self.make_millis_from_dt(start)

        end_utc = self.make_utc(end)
        end_millis = self.make_millis_from_dt(end_utc)
        
        while start_millis < end_millis: 
            response = self.request_to_binance(start_millis, end_millis, interval)
            data = self.response_to_dict(response)
            self.save_to_mongo(data, interval)

            start_millis = self.mongo.get_start_time(interval)

            time.sleep(2)


    def run_all(self, start=None, end=None, intervals=None): 
        pass


    def request_to_binance(self, start_millis, end_millis, interval): 
        URL = 'https://fapi.binance.com/fapi/v1/klines'
        params = {
            'symbol': 'BTCUSDT', 
            'interval': interval, 
            'limit': 1500, 
            'startTime': start_millis, 
            'endTime': end_millis
        }

        try: 
            response = requests.get(URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()  # json -> list

        # requests failurer
        except requests.exceptions.RequestException as e: 
            raise RuntimeError(f"requests failure: {e}")
        
        # jason parsing error 
        except ValueError as e: 
            raise RuntimeError(f"jason parsing failure: {e}")
        
        if not data: 
            raise ValueError(f"data is empty")
        
        return data

   
    def save_to_mongo(self, data: list, interval: str): 
        collection = self.mongo.get_candle_collection(interval)

        try: 
            collection.insert_many(data, ordered=True)
            print('Document insertion was successfully!')
            print('-' * 20)
        except BulkWriteError as e: 
            pass 


    # update last_updated collection
    # sample -> {'interval': '1d', 'last_updated_time': 150027000, 'next_start_time': 159034000}
    def refresh_last_updated(self, interval, last_millis): 
        collection = self.mongo.get_last_updated_collection()
        next_start_millis = self.make_start_millis(interval, last_millis)
        collection.update_one(
            {'interval': interval}, 
            {
                '$set': {
                    'last_updated_time': last_millis, 
                    'next_start_time': next_start_millis
                }, 
            }, 
            upsert=True
        )
    

    ### utility methods ###
    def response_to_dict(self, data: list) -> dict:
        data_dict_list = [
            {
            'open_time': item[0], 
            'open': item[1], 
            'high': item[2], 
            'low': item[3], 
            'close': item[4], 
            'volume': item[5], 
            'quote_volume': item[6], 
            'count': item[8], 
            'taker_buy_volume': item[9], 
            'taker_buy_quote_volume': item[10], 
            'ignore': item[11]
            } 
        for item in data
        ]

        return data_dict_list
     

    def make_start_millis(self, interval, last_millis): 
        if interval == '1d': 
            delta_millis = int(timedelta(days=1).total_seconds() * 1000)
        elif interval == '12h': 
            delta_millis = int(timedelta(hours=12).total_seconds() * 1000)
        elif interval == '6h': 
            delta_millis = int(timedelta(hours=6).total_seconds() * 1000)
        elif interval == '4h': 
            delta_millis = int(timedelta(hours=4).total_seconds() * 1000)
        elif interval == '1h': 
            delta_millis = int(timedelta(hours=1).total_seconds() * 1000)
        elif interval == '15m': 
            delta_millis = int(timedelta(minutes=15).total_seconds() * 1000)
        elif interval == '5m': 
            delta_millis = int(timedelta(minutes=5).total_seconds() * 1000)

        next_millis = last_millis + delta_millis 


    def make_utc(self, dt): 
        dt_utc = dt.replace(tzinfo=timezone.utc)
        return dt_utc 


    def make_millis_from_dt(self, dt):
        millis = int(dt.timestamp() * 1000)
        return millis 


  



if __name__ == "__main__": 

    mongo = MongoHandler('test_db')

    try: 
        collector = DataCollector()
        collector.run_all()
    except Exception as e: 
        print('error occured')
    finally: 
        mongo.close()






