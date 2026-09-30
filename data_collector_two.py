import numpy as np 
import pandas as pd 
import time
import requests
import re

from datetime import datetime, timedelta, timezone
from pymongo import MongoClient 
from pymongo.errors import BulkWriteError
from pymongo.errors import ServerSelectionTimeoutError


# 2023. 1. 1 ~ 2023. 1. 31
# input type => datetime object : ex) datetime(2033, 1, 1)
# base timezone => utc
# self.start: milliseconds, self.end: milliseconds 
class DataCollector: 
    def __init__(self, start, end, interval, symbol='BTCUSDT', limit=1500): 
        self.symbol = symbol 
        self.start = start
        self.end = end  
        self.interval = interval 
        self.limit = limit
        self.client = None 
        self.collection = None 
        self.make_millis_from_dt()
        pass


    def make_dt_from_millis(self, millis: int) -> datetime: 
        seconds = int(millis / 1000)
        # utcfromtimestamp is no longer recommended
        # instead use fromtimestamp() included tz=timezone.utc
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt


    def make_millis_from_dt(self) -> None: 
        start_dt = self.start
        end_dt = self.end

        if self.interval == '1d': 
            pass 
        elif self.interval == '12h': 
            end_dt = end_dt + timedelta(hours=12)
        elif self.interval == '6h': 
            end_dt = end_dt + timedelta(hours=18)
        elif self.interval == '4h': 
            end_dt = end_dt + timedelta(hours=20)
        elif self.interval == '1h': 
            end_dt = end_dt + timedelta(hours=23)
        elif self.interval == '15m': 
            end_dt = end_dt + timedelta(hours=23, minutes=45)
        elif self.interval == '5m':
            end_dt = end_dt + timedelta(hours=23, minutes=55)
   
        start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = end_dt.replace(tzinfo=timezone.utc)
        self.start = int(start_dt.timestamp() * 1000)
        self.end = int(end_dt.timestamp() * 1000)


    def make_collection(self): 
        # connect mongodb
        try: 
            self.client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=1000)
            connected = self.client.is_primary
        except ServerSelectionTimeoutError:
            print('MongoDB connection failed ...')

        db = self.client[self.symbol]
        collection = db[f'{self.symbol}_{self.interval}']
        return collection


    def request_to_binance(self, start_millis: int, end_millis: int) -> list: 
        # request url 
        URL = 'https://fapi.binance.com/fapi/v1/klines'
        params = {
            'symbol': self.symbol, 
            'interval': self.interval,
            'limit': self.limit, 
            'startTime': start_millis, 
            'endTime': end_millis
        }
        try: 
            response = requests.get(URL, params=params, timeout=10)
            response.raise_for_status()  # 4xx, 5xx error raise
        except requests.Timeout: 
            print('Timeout error occured')
            return None 
        except requests.RequestException as e:
            print(f'An error occurred during the request.') 
            return None 
        else: 
            # json -> list
            return response.json()


    def data_to_dict(self, data: list) -> dict: 
        if not data: 
            print('response has no data ...')
            return None 
        else: 
            data_dict_list = [
                {
                'open_time': item[0], 
                'open': item[1],
                'high': item[2], 
                'low': item[3], 
                'close': item[4],
                'volume': item[5], 
                'close_time': item[6], 
                'quote_volume': item[7], 
                'count': item[8], 
                'taker_buy_volume': item[9], 
                'taker_buy_quote_vloume': item[10], 
                'ignore': item[11]  
                }
            for item in data
            ]

            # print start time, end time
            first_open_time_millis = data_dict_list[0]['open_time']
            last_open_time_millis = data_dict_list[-1]['open_time'] 
            #first_open_time_dt = self.make_dt_from_millis(first_open_time_millis)
            #last_open_time_dt = self.make_dt_from_millis(last_open_time_millis)            
            
            return data_dict_list, last_open_time_millis 
        

    def data_to_mongo(self, data: list) -> None: 
        first_open_time_millis = data[0]['open_time']
        last_open_time_millis = data[-1]['open_time']
        first_open_time_dt = self.make_dt_from_millis(first_open_time_millis)
        last_open_time_dt = self.make_dt_from_millis(last_open_time_millis)
        print(f'{first_open_time_dt} ~ {last_open_time_dt}')

        # save data to mongodb
        try: 
            self.collection.insert_many(data, ordered=True)
            print('Document insertion was successful !')
            print('-' * 20)
            return 'success'
        
        except BulkWriteError as e:
            print('MongoDB insert Error occured ...')
            write_errors = e.details.get('writeErrors', [])   # 'writeErrors': [{}, {}]
            if write_errors: 
                error_index = write_errors[0].get('index')
                retry_data = data[error_index:]
                print(f'retry data num is {len(retry_data)}')
                print('Retring to insert document into MongoDB ...')

                try: 
                    result = self.collection.insert_many(retry_data, ordered=True)
                    print('Document insertion was successful !')
                    print('-' * 20)
                    return 'success'
                except BulkWriteError as e: 
                    # fail to retring to insert document 
                    # need to logic
                    print('Error occured too ...')
                    print('Retry program ...')
                    write_errors = e.details.get('writeErrors', [])
                    if write_errors:
                        error_index = write_errors[0].get('index')
                        error_open_time_millis = retry_data[error_index].open_time
                        error_dt = self.make_dt_from_millis(error_open_time_millis)
                        print(f'error datetime: {error_dt}')
                        return 'partial success', data[error_index - 1].open_time


    def retry_insert(self, data, error): 
        pass        

        



    def next_start_millis(self, last_millis) -> int: 
        if self.interval == '1d': 
            delta_millis = int(timedelta(days=1).total_seconds() * 1000)
        elif self.interval == '12h': 
            delta_millis = int(timedelta(hours=12).total_seconds() * 1000)
        elif self.interval == '6h': 
            delta_millis = int(timedelta(hours=6).total_seconds() * 1000)
        elif self.interval == '4h': 
            delta_millis = int(timedelta(hours=4).total_seconds() * 1000)
        elif self.interval == '1h':          
            delta_millis = int(timedelta(hours=1).total_seconds() * 1000)
        elif self.interval == '15m': 
            delta_millis = int(timedelta(minutes=15).total_seconds() * 1000) 
        elif self.interval == '5m': 
            delta_millis = int(timedelta(minutes=5).total_seconds() * 1000)
        next_millis = last_millis + delta_millis
        return next_millis
    

    def update_last_open_time(): 
        pass 


    def run(self): 
        start_millis = self.start
        end_millis = self.end 

        print('=' * 30)
        print(f'{self.interval} data collecting start')
        print(f'{self.make_dt_from_millis(start_millis)} ~ {self.make_dt_from_millis(end_millis)}')
        print('=' * 30)

        self.collection = self.make_collection()

        while start_millis < end_millis: 
            data = self.request_to_binance(start_millis, end_millis)
            if not data: 
                return 
            data_dict_list, last_open_time_millis = self.data_to_dict(data)
            result = self.data_to_mongo(data_dict_list)
            # if failed to insert document twice, then break program
            if not result: 
                break

            # update last open time
            self.update_last_open_time()
            start_millis = self.next_start_millis(last_open_time_millis)
            
            time.sleep(2)

        # mongodb disconnect
        self.client.close()


if __name__ == '__main__': 
    start = datetime(2025, 2, 1)
    end = datetime(2025, 2, 28)
    collector = DataCollector(start, end, '5m')
    collector.run()


    
    
    # 1d last collector periods => datetime(2025. 2, 1) ~ datetime(2025, 2, 28)

    # 12h last collector periods => datetime(2025. 2, 1) ~ datetime(2025, 2, 28)

    # 6h last collector periods => datetime(2025. 2, 1) ~ datetime(2025, 2, 28)

    # 4h last collector periods => datetime(2020, 1, 1) ~ datetime(2025, 2, 28 )
   
    # 1h last collector periods => datetime(2025. 2, 1) ~ datetime(2025, 2, 28)

   
    # 15m last collector periods => datetime(2025. 2, 1) ~ datetime(2025, 2, 28)


    # 5m last collector periods => datetime(2025. 2, 1) ~ datetime(2025, 2, 28)

    

    # print(end_dt)

