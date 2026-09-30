import numpy as np 
import pandas as pd 
import time
import requests
import re

from datetime import datetime, timedelta, timezone
from pymongo import MongoClient 
from pymongo.errors import BulkWriteError
from pymongo.errors import ServerSelectionTimeoutError


class DataCollector:
    def __init__(self, symbol, start, end, interval, limit=1500): 
        self.symbol = symbol
        self.start = start
        self.end = end 
        self.interval = interval
        self.limit = limit
        self.client = None
        self.collection = None
    

    def str_millis(self, time_string):
        dt = datetime.strptime(time_string, '%Y-%m-%d %H:%M')
        millis = int(dt.timestamp() * 1000)
        return millis 
    
    # millis -> 
    def millis_str(self, millis): 
        seconds = int(millis / 1000)
        dt = datetime.fromtimestamp(seconds)
        string = dt.strftime('%Y-%m-%d %H:%M')
        return string 
    

    def next_start_millis(self, last_millis, interval): 
        interval_type = interval[-1]
        if interval_type == 'd':
            delta_millis = int(timedelta(days=1).total_seconds() * 1000)
        elif interval_type == 'h': 
            interval_num = int(interval[:-1])
            if interval_num == 1:
                delta_millis = int(timedelta(hours=1).total_seconds() * 1000)
            elif interval_num == 6: 
                delta_millis = int(timedelta(hours=6).total_seconds() * 1000)
        else: 
            time_num = int(interval[:-1])
            delta_millis = int(timedelta(minutes=time_num).total_seconds() * 1000)
        next_millis = last_millis + delta_millis
        return next_millis


    def collection_maker(self, symbol, interval): 
        # connect mongodb
        try: 
            self.client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=1000) 
            connected = self.client.is_primary
            print('mongodb connection succeeded!')
        except ServerSelectionTimeoutError: 
            print('mongodb connection failed....')
        
        db = self.client[symbol]
        collection = db[f'{symbol}_{interval}']

        return collection
    

    def remove_duplicate(self, start, end, collection):
        field_to_remove_duplicates = 'open_time'
        query = {'open_time': {'$gte': start, '$lte': end}}
        distinct_values = collection.distinct(field_to_remove_duplicates, query)
        delete_count = 0 
        for value in distinct_values: 
            duplicate_documents = list(collection.find({field_to_remove_duplicates: value}).skip(1))
            for doc in duplicate_documents: 
                collection.delete_one({"_id": doc["_id"]})
                delete_count += 1

        print(f'Removed duplicate document: total {delete_count}')


    def run(self):
        print(f'request start! --- {self.interval}')
        print(f'total start: {self.start} ~ total end: {self.end}')
        print('=' * 20)
        start_millis = self.str_millis(self.start)
        end_millis = self.str_millis(self.end)
        
        # request ohlcv
        URL = 'https://fapi.binance.com/fapi/v1/klines'
       
        # make collection
        self.collection = self.collection_maker(self.symbol, self.interval)
        
        # request data and insert data to mongodb
        while start_millis < end_millis: 
            params = {
                'symbol': self.symbol, 
                'interval': self.interval, 
                'limit': self.limit, 
                'startTime': start_millis,
                'endTime': end_millis
            }
            response = requests.get(URL, params=params)
            data = response.json()
            
            if not data: 
                print('response has no data...')
                print('data collection stopped...')
                break
            
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
            first_open_time_str = self.millis_str(first_open_time_millis)
            last_open_time_str = self.millis_str(last_open_time_millis)
            
            print(f'start: {first_open_time_str} ~ end: {last_open_time_str}')
            
            # save request data to mongodb
            try: 
                self.collection.insert_many(data_dict_list, ordered=False)
            except Exception as e: 
                print('Mongodb insert error occured...')
                print(e)
            else:
                print('insert many ok!')
                print('remove duplicate start!')   
                # remove duplicate document from field(open_time)
                # self.remove_duplicate(first_open_time_millis, last_open_time_millis, self.collection)
                print('=' * 10)
            # nest start milliseconds
            start_millis = self.next_start_millis(last_open_time_millis, self.interval)
            
            # when the start time and end time of the data request became identical, 
            # the response from binance server will be an error message
            if start_millis >= end_millis: 
                print('request over...')
                break
            else:
                time.sleep(2)
        
        # mongodb disconnect
        self.client.close()


if __name__ == "__main__": 
    symbol = 'BTCUSDT'
    start = '2024-04-01 09:00'
    end = '2024-05-31 23:00'
    interval = '1h'

    # 1d, 1h, 15m last collection period => 2024-04-01 

    data_collector = DataCollector(symbol, start, end, interval)
    start = time.time()
    data_collector.run()
    end = time.time()
    total_minutes = (end - start) / 60
    print(f'total cost minutes: {round(total_minutes,2)}m')

   