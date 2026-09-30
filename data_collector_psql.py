from datetime import datetime, timedelta, timezone
from psycopg2 import extras, sql
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource, Span, Arrow, NormalHead, LabelSet, NumeralTickFormatter, Range1d
from bokeh.palettes import Category10

from bokeh.models import (Arrow, NormalHead, LabelSet)
from bokeh.models import Range1d, WheelZoomTool, NumeralTickFormatter, DatetimeTickFormatter, BoxAnnotation, FixedTicker
from scipy.stats import gaussian_kde

from math import floor, ceil

import psycopg2
import requests
import time 
import streamlit as st
import pandas as pd 
import numpy as np 



class PostgresHandler: 
    def __init__(self, dbname): 
        self.dbname = dbname
        self.conn = None 
        pass 


    @staticmethod
    def calculate_start_millis(interval, last_millis): 
        if interval == '1d': 
            delta_millis = int(timedelta(days=1).total_seconds())
        elif interval == '12h':
            delta_millis = int(timedelta(hours=12).total_seconds() * 1000)
        elif interval == '6h':
            delta_millis = int(timedelta(hours=6).total_seconds() * 1000)
        elif interval == '4h': 
            delta_millis = int(timedelta(hours=4).total_seconds() * 1000)
        elif interval == '2h': 
            delta_millis = int(timedelta(hours=2).total_seconds() * 1000)
        elif interval == '1h': 
            delta_millis = int(timedelta(hours=1).total_seconds() * 1000)
        elif interval == '30m': 
            delta_millis = int(timedelta(minutes=30).total_seconds() * 1000)
        elif interval == '15m': 
            delta_millis = int(timedelta(minutes=15).total_seconds() * 1000)
        elif interval == '5m': 
            delta_millis = int(timedelta(minutes=5).total_seconds() * 1000)

        start_millis = last_millis + delta_millis 
        return start_millis 


    def connect(self):
        try: 
            self.conn = psycopg2.connect(
                host = '127.0.0.1',
                port = 5432,
                dbname = self.dbname, 
                user = 'chododa', 
                password = '3705'
            )
        except Exception as e: 
            print('conn error occured')
            self.conn.close()
        else: 
            print('DB connection succeed !')
    

    def disconnect(self): 
        self.conn.close()
        self.conn = None
        print('DB disconnected .....')


    def get_update_info(self): 
        if not self.conn: 
            raise ConnectionError("No active postgresql connection. Please call connect()")    
        cur = self.conn.cursor()
        cur.execute("SELECT interval, last_millis, start_millis FROM update_info ORDER BY id ASC;")
        result = cur.fetchall() 
        cur.close() 

        return result
     

    def update_update_info(self, interval, last_millis): 
        if not self.conn: 
            raise ConnectionError("No active postgresql connection. Please call connect()")
        
        with self.conn.cursor() as cur: 
            sql = '''
            UPDATE update_info 
            SET last_millis = %s, start_millis = %s
            WHERE interval = %s
            '''

            start_millis = self.calculate_start_millis(interval, last_millis)
            data = (last_millis, start_millis, interval)
            cur.execute(sql, data)
        
        self.conn.commit()

   
    def fetch_candles(self, interval, start_millis, end_millis): 
        if not self.conn: 
            raise ConnectionError("No active postgresql connection. Please call connect()")
        
        table = f"btcusdt_{interval}"
        query = f"SELECT * FROM {table} WHERE open_time >= %s AND open_time <= %s ORDER BY open_time ASC"

        with self.conn.cursor() as cur:
            cur.execute(query, (start_millis, end_millis))
            result = cur.fetchall()
            return result


    def _make_utc(self, dt): 
        utc_dt = dt.replace(tzinfo=timezone.utc)
        return utc_dt 


    def _make_millis_from_dt(self, dt): 
        utc_dt = self._make_utc(dt)
        millis = int(utc_dt.timestamp() * 1000)
        
        return millis 
    

    def _make_dt_from_millis(self, millis): 
        seconds = int(millis / 1000)
        utc_dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return utc_dt


    # hello 



class DataCollector: 
    def __init__(self, dbhandler): 
        self.dbhandler = dbhandler
        self.conn = dbhandler.conn
        pass 
          
    
    def run(self, interval, end_dt): 
        with self.conn.cursor() as cur:        
            cur.execute("SELECT start_millis FROM update_info WHERE interval= %s", (interval,))
            result = cur.fetchone()

            start_millis = result[0]        
            end_millis = self._make_millis_from_dt(end_dt)
            
        print(f'=== Start {interval} data collection ===')
        
        while start_millis < end_millis: 
            # bring candle data from Binance API
            data = self._request_to_binance(interval, start_millis, end_millis)
        
            # save to Postgres the Data from Binance 
            success, last_millis = self._save_to_postgres(interval, data)

            if success: 
                self.dbhandler.update_update_info(interval, last_millis)
                last_dt = self._make_dt_from_millis(last_millis)
                print(f'Successfully "{interval}" saved to PostgreSQL!')
                print(last_dt)
                print('-' * 20)
            
            start_millis = self._get_start_millis(interval)

            time.sleep(2)
        
        # process the data and then print the relevant details
        print(f'Completed {interval} candle collecting!')
        print(f'=' * 30)
            

    def run_all(self, end_dt): 
        intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d']

        for interval in intervals: 
            self.run(interval, end_dt)
            print('wait ....... ')
            time.sleep(2)
            
        print('All interval is collected!')


    def run_all_iter(self, end_dt): 
        intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d']

        progress_end = st.empty() 

        for interval in intervals: 
            progress_end.write(f'{interval} start!')
            with st.spinner("Please wait..."):
                self.run(interval, end_dt)
            yield interval
            print('wait ....... ')
            time.sleep(2)

        progress_end.empty()
            
        print('All interval is collected!')
     

    def _request_to_binance(self, interval, start_millis, end_millis): 
        URL = 'https://fapi.binance.com/fapi/v1/klines'
        params = {
            'symbol': 'BTCUSDT', 
            'interval': interval, 
            'limit': 1000, 
            'startTime': start_millis, 
            'endTime': end_millis
        }

        try: 
            response = requests.get(URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        # requests failure
        except requests.exceptions.RequestException as e: 
            raise RuntimeError(f'requests failure: {e}')

        # json parsing error
        except ValueError as e: 
            raise RuntimeError(f'response data is empty!')

        if not data: 
            raise ValueError('data is empty')
     
        return data 
    

    def _save_to_postgres(self, interval, data: list):
        table_name = f"btcusdt_{interval}"

        query = sql.SQL("""
            INSERT INTO {table} (
                open_time, open, high, low, close, volume, 
                close_time, quote_volume, trade_count, 
                taker_buy_volume, taker_buy_quote, ignore
            ) VALUES %s
            """).format(table=sql.Identifier(table_name))
        
        try: 
            with self.conn.cursor() as cur: 
                extras.execute_values(cur, query, data)
            self.conn.commit()        
        
        except Exception as e: 
            self.conn.rollback()
            print('DB Error:', e)

        # if the data is successfully saved to DB, it returns the
        # interval and last_millis 
        else: 
            last_millis = data[-1][0]
            success = True
            return success, last_millis 
     

    def _make_utc(self, dt): 
        utc_dt = dt.replace(tzinfo=timezone.utc)
        return utc_dt 


    def _make_millis_from_dt(self, dt): 
        utc_dt = self._make_utc(dt)
        millis = int(utc_dt.timestamp() * 1000)
        return millis 
    

    def _make_dt_from_millis(self, millis): 
        seconds = int(millis / 1000)
        utc_dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return utc_dt
    

    def _get_start_millis(self, interval): 
        with self.conn.cursor() as cur: 
            cur.execute("SELECT start_millis FROM update_info WHERE interval= %s", (interval,))
            result = cur.fetchone()
            return result[0]





class DataLoader: 
    def __init__(self, dbhandler):
        self.dbhandler = dbhandler
        self.df = None


    @staticmethod
    def calc_interval_end_dt(interval, end_dt): 
        if interval == '1d': 
            new_end_dt = end_dt
        elif interval == '12h': 
            new_end_dt = end_dt + timedelta(hours=12)
        elif interval == '6h':
            new_end_dt = end_dt + timedelta(hours=18)
        elif interval == '4h': 
            new_end_dt = end_dt + timedelta(hours=20)
        elif interval == '2h': 
            new_end_dt = end_dt + timedelta(hours=22)
        elif interval == '1h': 
            new_end_dt = end_dt + timedelta(hours=23)
        elif interval == '30m': 
            new_end_dt = end_dt + timedelta(hours=23, minutes=30)
        elif interval == '15m': 
            new_end_dt = end_dt + timedelta(hours=23, minutes=45)
        elif interval == '5m': 
            new_end_dt = end_dt + timedelta(hours=23, minutes=55)

        return new_end_dt


    def make_df(self, interval, start_dt, end_dt, open_time_dt=False, volume=True, ohlc_type=None):
        start_millis = self.dbhandler._make_millis_from_dt(start_dt)
        end_dt = self.calc_interval_end_dt(interval, end_dt)
        end_millis = self.dbhandler._make_millis_from_dt(end_dt)
        
        query_data = self.dbhandler.fetch_candles(interval, start_millis, end_millis)
        query_df = pd.DataFrame(query_data).copy()
        
        # volume option
        if volume: 
            query_df = query_df.iloc[:, 0:6]
            query_df.rename(columns={
                0: 'open_time', 
                1: 'open', 
                2: 'high', 
                3: 'low', 
                4: 'close', 
                5: 'volume'
            }, inplace=True)

        else: 
            query_df = query_df.iloc[:, 0:5]
            query_df.rename(columns={
                0: 'open_time', 
                1: 'open', 
                2: 'high', 
                3: 'low', 
                4: 'close'
            }, inplace=True)

        # ohlc_type option
        if ohlc_type == 'float': 
            query_df[['open', 'high', 'low', 'close']] = query_df[['open', 'high', 'low', 'close']].astype(float)

        # open_time: millis => pd.to_datetime
        if open_time_dt: 
            query_df['open_time'] = pd.to_datetime(query_df['open_time'], unit='ms')

        return query_df
        

    # df = o_t,o,h,l,c 
    # transfer_df = 
    def transfer_df(self, df, threshold=0.01): 
        df = df.copy()
        df = self._type_maker(df)
        df = self._pct_maker(df)
        

        # reverse low, high. close in minus 
        df['new_high_pct'] = np.where(df['type'] == 'minus', -df['low_pct'], df['high_pct'])
        df['new_low_pct'] = np.where(df['type'] == 'minus', -df['high_pct'], df['low_pct'])
        df['new_close_pct'] = np.where(df['type'] == 'minus', -df['close_pct'], df['close_pct'])

        df = self._way_maker(df, threshold)
        df = self._way_direction_maker(df, threshold)
        df = self._mfe_maker(df, threshold)
        df = self._mfe_label_maker(df)
        df = self._close_profit_maker(df, threshold)
        df = self._date_maker(df)
        
        return df

    
    def transfer_pct_df(self, df, threshold=0.01, indicator=True): 
        df = df.copy()
        df['date'] = df['open_time'].dt.date
        
        def inner(group):
            open_prc = group.iat[0, 1]

            # ohlc pct 
            group['open_pct'] = (group['open'] - open_prc) / open_prc
            group['high_pct'] = (group['high'] - open_prc) / open_prc
            group['low_pct'] = (group['low'] - open_prc) / open_prc
            group['close_pct'] = (group['close'] - open_prc) / open_prc

            if indicator:
            # indicator pct 
                group['ma7_pct'] = (group['ma7'] - open_prc) / open_prc
                group['ma20_pct'] = (group['ma20'] - open_prc) / open_prc
                group['bb_upper_pct'] = (group['bb_upper'] - open_prc) / open_prc
                group['bb_lower_pct'] = (group['bb_lower'] - open_prc) / open_prc

            round_num = 3

            group['open_pct'] = (group['open_pct'] * 100).round(round_num)
            group['high_pct'] = (group['high_pct'] * 100).round(round_num)
            group['low_pct'] = (group['low_pct'] * 100).round(round_num)
            group['close_pct'] = (group['close_pct'] * 100).round(round_num)

            if indicator:
                group['ma7_pct'] = (group['ma7_pct'] * 100).round(round_num)
                group['ma20_pct'] = (group['ma20_pct'] * 100).round(round_num)
                group['bb_upper_pct'] = (group['bb_upper_pct'] * 100).round(round_num)
                group['bb_lower_pct'] = (group['bb_lower_pct'] * 100).round(round_num)

            return group
            st.write(open_prc)
            st.dataframe(group.head())
            

        result_df = df.groupby('date', group_keys=False).apply(inner)
        
        return result_df









        return df
    

    def volatility_transfer_df(self, df, k=0.5):
        df = df.copy()
        df['type'] = np.where(df['close'] > df['open'], 'plus', 'minus')
        df['open_pct'] = 0
        df['high_pct'] = (df['high'] - df['open']) / df['open']
        df['low_pct'] = (df['low'] - df['open']) / df['open']
        df['close_pct'] = (df['close'] - df['open']) / df['open']

        df['pre_high'] = df['high'].shift(1)
        df['pre_low'] = df['low'].shift(1)

        df['k_threshold'] = (df['pre_high'] - df['pre_low']) * k / df['open']
        df['k_threshold'] = df['k_threshold'].round(3)

        df = self._volatility_way_maker(df)

        return df
    

    # parameter: 1d_candle dataframe
    def calculate_profit_dist(self, df, threshold, times=1) -> np.ndarray: 

        # df : open_time, o, h, l, c, type, h_pct, l_pct, c_pct, way, max_type, max
        way_dict = df['way'].value_counts().to_dict()
        max_values = df.loc[df['way']=='one_way', 'max'].to_numpy()

        ## one way random array ##
        n_cases = 10000
        n_vars = len(max_values)

        random_cases = np.random.rand(n_cases, n_vars) * max_values * times
        # st.write(random_cases)
        plus_arr = (random_cases / 100) + 1
        # st.write(plus_arr)

        ## two way array
        loss_cut = threshold * times
        two_way_cases = np.full((n_cases, way_dict['two_way']), loss_cut)
        minus_arr = 1 - (two_way_cases / 100)
        # st.write(minus_arr)


        ## concatenate
        profit_arr = np.concatenate([plus_arr, minus_arr], axis=1)
        st.write(profit_arr)
        product_arr = np.prod(profit_arr, axis=1)
        max_value = product_arr.max() * 100 
        min_value = product_arr.min() * 100
        st.write(product_arr)
        st.write(way_dict)
        st.write(f'times: {times}')
        st.write(f'threshold: {threshold}')
        st.write(f'max_profit: {max_value.round(2)}%')
        st.write(f'min_profit: {min_value.round(2)}%')

        return product_arr
        
    
    def _pct_maker(self, df): 
        df['open_pct'] = 0 
        df['high_pct'] = (df['high'] - df['open']) / df['open']
        df['low_pct'] = (df['low'] - df['open']) / df['open']
        df['close_pct'] = (df['close'] - df['open']) / df['open']

        return df
    

    def _way_maker(self, df, threshold): 
        df['way'] = np.where(
            (-threshold < df['low_pct']) & (df['high_pct'] < threshold), 
            'no_way', 
            np.where(
                (df['low_pct'] <= -threshold) & (threshold <= df['high_pct']), 
                'two_way', 
                'one_way'
            )
        )
        return df

    def _volatility_way_maker(self, df): 
        st.write('volatility_way_maker')
        df['volatility_way'] = np.where(
            (-df['k_threshold'] < df['low_pct']) & (df['high_pct'] < df['k_threshold']), 
            'no_way', 
            np.where(
                (df['low_pct'] <= -df['k_threshold']) & (df['k_threshold'] <= df['high_pct']), 
                'two_way', 
                'one_way'
            )
        )
        return df

    def _volatility_way_direction_maker(self, df):
        df['way_direction'] = np.where(
            (df['volatility_way'] == 'one_way') & (df['high_pct'] >= df['k_threshold']), 
            'high',
            np.where(
                (df['volatility_way'] == 'one_way') & (df['low_pct'] <= -df['k_threshold']), 
                'low', 'no'
            )
        )
        return df

    def _way_direction_maker(self, df, threshold):
        df['way_direction'] = np.where(
            (df['way'] == 'one_way') & (df['high_pct'] >= threshold), 
            'high', 
            np.where(
                (df['way'] == 'one_way') & (df['low_pct'] <=  -threshold), 
                'low', 'no'
            )
        )
        return df 


    def _mfe_maker(self, df, threshold): 
        df['mfe'] = np.where(
            df['way_direction'] == 'high', 
            (df['high_pct'] - threshold) / (1 + threshold), 
            np.where(
                df['way_direction'] == 'low', 
                (-threshold - df['low_pct']) / (1 - threshold), 0
            )
        )

        df['mfe'] = df['mfe'].round(3)
        return df


    def _mfe_label_maker(self, df): 
        # before _mfe_maker() called
        conditions = [
            (df['mfe'] > 0) & (df['mfe'] < 0.01), 
            (df['mfe'] >= 0.01) & (df['mfe'] < 0.02), 
            (df['mfe'] >= 0.02) & (df['mfe'] < 0.03), 
            (df['mfe'] >= 0.03)
        ]

        choices = [0, 1, 2, 3]

        df['mfe_label'] = np.select(conditions, choices, default=-1)
        return df 

    
    def _close_profit_maker(self, df, threshold): 
        # before _way_direction_maker(), _mfe_label_maker()
        # st.write('_close_profit_maker')
        # st.dataframe(df)
        
        df['close_profit'] = np.where(
            df['way_direction'] == 'high', 
            (df['close_pct'] - threshold) / (1 + threshold), 
            np.where(
                df['way_direction'] == 'low', 
                (-threshold - df['close_pct']) / (1 - threshold), 0
            )
        )

        df['close_profit'] = df['close_profit'].round(8)


        return df


    def _volatility_max_profit_pct_maker(self, df): 
        df['mfe'] = np.where(
            df['way_direction'] == 'high', 
            (df['high_pct'] - df['k_threshold']) / (1 + df['k_threshold']), 
            np.where(
                df['way_direction'] == 'low', 
                (-df['k_threshold'] - df['low_pct']) / (1 - df['k_threshold']), 0
            )
        )
    
        df['mfe'] = df['mfe'].round(3)
        return df


    def _volatility_maker(self, df): 
        df['volatility_pct'] = (df['high'] - df['low']) / df['open']
        df['volatility_pct'] = df['volatility_pct'].round(3)
        return df   
    

    def _date_maker(self, df): 
        df['date'] = df['open_time'].dt.date
        return df


    def _type_maker(self, df): 
        df['type'] = np.where(df['close'] > df['open'], 'plus', 'minus')
        return df


    

class DataAnalyzer: 
    def __init__(self): 
        pass 

    def pull_back_data(self, df_1d, df_1h):   
        df_1d['open_time'] = pd.to_datetime(df_1d['open_time'], unit='ms')
        df_1h['open_time'] = pd.to_datetime(df_1h['open_time'], unit='ms')

        original_1d = df_1d
       
        df_1d = df_1d[df_1d['way'] == 'one_way']
        
        filtered_1d = df_1d[
            ['open_time', 'type', 'way', 'way_direction', 'max_profit_pct']
        ]
        
        filtered_1d['date'] = filtered_1d['open_time'].dt.date
        one_way_date = set(df_1d['open_time'].dt.date)
  
        filtered_1h = df_1h[df_1h['open_time'].dt.date.isin(one_way_date)]
        filtered_1h['date'] = filtered_1h['open_time'].dt.date

        # filtered_1h['high_pct'] = (filtered_1h['high'] - filtered_1h['open']) / filtered_1h['open']
        # filtered_1h['low_pct'] = (filtered_1h['low'] - filtered_1h['open']) / filtered_1h['open']
        # filtered_1h['close_pct'] = (filtered_1h['close'] - filtered_1h['open']) / filtered_1h['open']

        filtered_1h = filtered_1h.merge(filtered_1d[['date', 'way_direction']], on='date', how='left')

        return filtered_1d, filtered_1h, original_1d
        


    # df_1d: one_way, df_1h: one_way
    def pull_back(self, df_1d, df_1h, original_1d, threshold=0.01): 

        def inner(group): 
            # make high_pct, low_pct, close_pct
            first_open = group.iat[0, 1]
            group = group.reset_index(drop=True)
            group['high_pct'] = (group['high'] - first_open) / first_open
            group['low_pct'] = (group['low'] - first_open) / first_open
            group['close_pct'] = (group['close'] - first_open) / first_open
        
            # way_direction
            if group.iat[0, 6] == 'high': 
                mask = group['high_pct'] >= threshold
                touch_idx = mask.to_numpy().argmax()
                # st.write('+++++ touch_idx', touch_idx)
                min_max_idx = group['high_pct'].to_numpy().argmax()
                # st.write('+++++ min_max_idx: ', min_max_idx)
                min_max_pct = group['high_pct'].to_numpy()[min_max_idx].round(4)
                # st.write('+++++ min_max_pct: ', min_max_pct)
                group_sub = group['low_pct'].iloc[touch_idx+1:min_max_idx+1]
                # st.write('+++++ group_sub: ', group_sub)

                if group_sub.empty: 
                    pull_back_idx = touch_idx
                    pull_back_pct = group['low_pct'][touch_idx]
                else: 
                    pull_back_idx = group_sub.to_numpy().argmin()                
                    pull_back_pct = group_sub.to_numpy()[pull_back_idx].round(4)
            

            elif group.iat[0, 6] == 'low': 
                mask = group['low_pct'] <= -threshold
                touch_idx = mask.to_numpy().argmax()
                min_max_idx = group['low_pct'].to_numpy().argmin()
                min_max_pct = group['low_pct'].to_numpy()[min_max_idx].round(4)

                group_sub = group['high_pct'].iloc[touch_idx+1:min_max_idx+1]

                if group_sub.empty: 
                    pull_back_idx = touch_idx
                    pull_back_pct = group['high_pct'][touch_idx]
                else: 
                    pull_back_idx = group_sub.to_numpy().argmax()
                    pull_back_pct = group_sub.to_numpy()[pull_back_idx].round(4)
            
            # st.write(group)
            # st.write(touch_idx, min_max_idx)
            # st.write(first_open)
            # st.write(group.iat[0, 6])
            # st.write(touch_idx, min_max_idx, min_max_pct, pull_back_idx, pull_back_pct)
            return pd.Series({
                'touch_idx': touch_idx, 
                'min_max_pct': min_max_pct, 
                'pull_back_pct': pull_back_pct
            })

        result = df_1h.groupby('date').apply(inner)
        result = df_1d.merge(result, on='date', how='left')

        total_df = original_1d[['open_time', 'open_pct', 'high_pct', 'low_pct', 'close_pct', 'type']]
        total_df['date'] = total_df['open_time'].dt.date

        result_two = result[['date', 'min_max_pct', 'pull_back_pct']]
        total_df = total_df.merge(result_two, on='date', how='left')
        total_df.fillna(0, inplace=True)
    
        return result, total_df
    


    # df_1d: from DataLoader.transfer_df, pull_back_df_1d: from pull_back
    def pre_calc_profit(self, df_1d, pull_back_df_1d, threshold, loss_cut, times=1): 
        two_way_num = (df_1d['way'] == 'two_way').sum()
        no_way_num = (df_1d['way'] == 'no_way').sum()
        one_way_num = len(pull_back_df_1d)
        total_num = len(df_1d)
        total_no_num = total_num - no_way_num 

        st.write(two_way_num, no_way_num, one_way_num)
        way_df = pd.DataFrame({
            'one_way': [one_way_num], 
            'two_way': [two_way_num], 
            'no_way': [no_way_num]
        })
        
        # one_way analysis
        loss = -loss_cut * times
        limit_high = threshold - loss_cut
        limit_low = -threshold + loss_cut


        pull_back_df_1d['profit'] = np.where(
            (pull_back_df_1d['way_direction'] == 'high') & (pull_back_df_1d['pull_back_pct'] <= limit_high), 
            'minus', 
            np.where(
                (pull_back_df_1d['way_direction'] == 'low') & (pull_back_df_1d['pull_back_pct'] >= limit_low), 
                'minus', 'plus'
            )
        )

        
        one_way_minus_num = (pull_back_df_1d['profit'] == 'minus').sum()
        one_way_plus_num = (pull_back_df_1d['profit'] == 'plus').sum()
        
        loss_num = two_way_num + one_way_minus_num

        total_loss = (1 + loss)**(loss_num)

        # threshold ~ (low or high) => max_profit
        max_profit_sr = pull_back_df_1d.loc[pull_back_df_1d['profit'] == 'plus', 'max_profit_pct']
        max_profit_arr = max_profit_sr.to_numpy()

        no_way_pct = round(no_way_num / total_num * 100, 2)
        one_way_plus_pct = round(one_way_plus_num / total_num * 100, 2)
        one_way_minus_pct = round(one_way_minus_num / total_num * 100, 2)
        two_way_pct = round(two_way_num / total_num * 100, 2)

        one_way_plus_no_pct = round(one_way_plus_num / total_no_num * 100, 2)
        one_way_minus_no_pct = round(one_way_minus_num / total_no_num * 100, 2)
        two_way_no_pct = round(two_way_num / total_no_num * 100, 2)

        



        report_dict = {
            'no_way': [no_way_num, f'{no_way_pct}%', 'except'], 
            'one_plus_way': [one_way_plus_num, f'{one_way_plus_pct}%', f'{one_way_plus_no_pct}%'], 
            'one_minus_way': [one_way_minus_num, f'{one_way_minus_pct}%', f'{one_way_minus_no_pct}%'], 
            'two_way': [two_way_num, f'{two_way_pct}%', f'{two_way_no_pct}%']
        }
        
        return max_profit_arr, total_loss, report_dict

    

    def calc_profit(self, max_profit_arr, total_loss, times=1):
        n_cases = 100_000
        n_vars = len(max_profit_arr)

        random_cases = (np.random.rand(n_cases, n_vars) * max_profit_arr * times) + 1
        loss_cases = np.full((n_cases, 1), total_loss)

        profit_arr = np.concatenate([random_cases, loss_cases], axis=1)
        product_arr = np.prod(profit_arr, axis=1)

        max_revenue = product_arr.max()
        min_revenue = product_arr.min()

        st.write(f'n_cases: {n_cases:,}')
        st.write(f'max: {round(max_revenue, 3)}')
        st.write(f'min: {round(min_revenue, 3)}')

        return product_arr
       
    
               
    def report(self, df, loader, way_type=None): 
        thresholds = [round(i * 0.001, 3) for i in range(5, 31)]
        year_arr = []

        for threshold in thresholds: 
            trans_df = loader.transfer_df(df, threshold)

            total = len(trans_df)
            no = (trans_df['way'] == 'no_way').sum()
            one = (trans_df['way'] == 'one_way').sum()
            two = (trans_df['way'] == 'two_way').sum()

            no_pct = round(no / total * 100, 2)
            one_pct = round(one / total * 100, 2)
            two_pct = round(two / total * 100, 2)

            if way_type is None: 
                result = f'{no} ({no_pct}%), {one} ({one_pct}%), {two} ({two_pct}%)'
                year_arr.append(result)
            elif way_type == 'one':
                result = one_pct
                year_arr.append(result) 
        
        result = pd.DataFrame(data=[year_arr], columns=thresholds)
        
        return result


    # df : loader.make_df -> loader.transfer_df -> df(month)
    def report_way(self, df):
        result = self._calculate_way(df)

        data = {
            'no_way': [result['no'], result['no_pct'], 0], 
            'one_way': [result['one'], result['one_pct'], result['one_sub_pct']], 
            'two_way': [result['two'], result['two_pct'], result['two_sub_pct']]
        }

        report_df = pd.DataFrame(data=data)
        st.dataframe(report_df)



    def _calculate_way(self, df) -> dict: 
        no = (df['way'] == 'no_way').sum()
        one = (df['way'] == 'one_way').sum()
        two = (df['way'] == 'two_way').sum()

        total = len(df)
        total_sub = total - no

        no_pct = round(no / total * 100, 2)
        one_pct = round(one / total * 100, 2)
        two_pct = round(two / total * 100, 2)

        one_sub_pct = round(one / total_sub * 100, 2)
        two_sub_pct = round(two / total_sub * 100, 2)

        return {
            'no': no, 
            'one': one, 
            'two': two, 
            'no_pct': no_pct, 
            'one_pct': one_pct, 
            'two_pct': two_pct, 
            'one_sub_pct': one_sub_pct, 
            'two_sub_pct': two_sub_pct
        }
    


class Transform: 
    def transfer_df(self, df, threshold=0.01): 
        df = df.copy()
        # decimal -> float
        # df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)

        df['type'] = np.where(df['close'] > df['open'], 'plus', 'minus')
        df['open_pct'] = 0
        df['high_pct'] = (df['high'] - df['open']) / df['open'] 
        df['low_pct'] = (df['low'] - df['open']) / df['open'] 
        df['close_pct'] = (df['close'] - df['open']) / df['open'] 

        # reverse low, high. close in minus 
        df['new_high_pct'] = np.where(df['type'] == 'minus', -df['low_pct'], df['high_pct'])
        df['new_low_pct'] = np.where(df['type'] == 'minus', -df['high_pct'], df['low_pct'])
        df['new_close_pct'] = np.where(df['type'] == 'minus', -df['close_pct'], df['close_pct'])

        df = self._way_maker(df, threshold)
        df = self._way_direction_maker(df, threshold)
        df = self._mfe_maker(df, threshold)
        
        return df


    def _way_maker(self, df, threshold): 
        df['way'] = np.where(
            (-threshold < df['low_pct']) & (df['high_pct'] < threshold), 
            'no_way', 
            np.where(
                (df['low_pct'] <= -threshold) & (threshold <= df['high_pct']), 
                'two_way', 
                'one_way'
            )
        )
        return df


    def _way_direction_maker(self, df, threshold):
        df['way_direction'] = np.where(
            (df['way'] == 'one_way') & (df['high_pct'] >= threshold), 
            'high', 
            np.where(
                (df['way'] == 'one_way') & (df['low_pct'] <=  -threshold), 
                'low', 'no'
            )
        )
        return df 


    def _mfe_maker(self, df, threshold): 
        df['mfe'] = np.where(
            df['way_direction'] == 'high', 
            (df['high_pct'] - threshold) / (1 + threshold), 
            np.where(
                df['way_direction'] == 'low', 
                (-threshold - df['low_pct']) / (1 - threshold), 0
            )
        )

        df['mfe'] = df['mfe'].round(3)
        return df
    

    
    def _mfe_label_maker(): 
    # before called _mfe_maker() 
        pass 
    
    def _pct_maker(self, df):
        pass 




class DataFrameTransformer: 
    def __init__(self): 
        pass  

    def make_way(self, df_1d, threshold): 
        #  ohlc_pct_maker() method must be called before this method
        conditions = [
            (df_1d['high_pct'] < threshold) & (df_1d['low_pct'] > -threshold), 
            (df_1d['high_pct'] >= threshold) & (df_1d['low_pct'] <= -threshold)
        ]
        choices = ['no_way', 'two_way']
        df_1d['way'] = np.select(conditions, choices, default='one_way')
        return df_1d
    

    def make_way_direction(self, df_1d, threshold): 
        # way_maker() method must be called before this method
        if 'way' in df_1d.columns: 
            conditions = [
                (df_1d['way'] == 'one_way') & (df_1d['high_pct'] > threshold), 
                (df_1d['way'] == 'one_way') & (df_1d['low_pct'] < -threshold), 
                (df_1d['way'] == 'two_way')
            ]
            choices = ['high', 'low', 'both']
            df_1d['way_direction'] = np.select(conditions, choices, default='no')
            return df_1d 
        else: 
            raise KeyError("The DataFrame must contain a 'way' column!")
        

    def make_max_profit_pct(self, df_1d, threshold): 
        # way_direction_maker() method must be called before this method
        if 'way_direction' in df_1d.columns: 
            conditions = [
                (df_1d['way_direction'] == 'high'), 
                (df_1d['way_direction'] == 'low')
            ]
            choices = [
                (df_1d['high_pct'] - threshold) / (1 + threshold), 
                (-df_1d['low_pct'] - threshold) / (1 - threshold)
            ]
            df_1d['max_profit_pct'] = np.select(conditions, choices, default=0)
            df_1d['max_profit_pct'] = df_1d['max_profit_pct'].round(4)
            return df_1d
        else: 
            raise KeyError("The DataFrame must contain a 'way_direction' column!")


    def make_ohlc_pct(self, df, interval: str): 
        # make_date() method must be called before
        def inner(group): 
            open = group.iat[0, 1]
            group['open_pct'] = (group['open'] - open) / open
            group['high_pct'] = (group['high'] - open) / open
            group['low_pct'] = (group['low'] - open) / open 
            group['close_pct'] = (group['close'] - open) / open 
            return group
        
        #-----interval: 1d------#
        if interval == '1d': 
            df['open_pct'] = 0
            df['high_pct'] = (df['high'] - df['open']) / df['open']
            df['low_pct'] = (df['low'] - df['open']) / df['open']
            df['close_pct'] = (df['close'] - df['open']) / df['open']
        
        #-----interval: 1h------#
        else: 
            if 'date' in df.columns: 
                df = df.groupby('date', group_keys=False).apply(inner)
            else: 
                raise KeyError("The DataFrame must contain a 'date' column!")
        
        df = df.round({
            'open': 5,
            'high': 5, 
            'low': 5, 
            'close': 5
        })

        return df 


    def make_date(self, df): 
        if isinstance(df['open_time'].iloc[0], pd.Timestamp): 
            df['date'] = df['open_time'].dt.date
            return df
        
        else: 
            raise TypeError("Convert df['open_time'] to datetime format using pd.to_datetime()")
            
        
    def make_ht_ratio(self, df_1d): 
        # make_close_type() method must be called before this method
        df_1d['head_tail_ratio'] = np.where(
            df_1d['close_type'] == 'plus', 
            (df_1d['high'] - df_1d['open']) / (df_1d['open'] - df_1d['low']),
            (df_1d['open'] - df_1d['low']) / (df_1d['high'] - df_1d['open'])
        )
        df_1d['head_tail_ratio'] = df_1d['head_tail_ratio'].round(2)
        return df_1d


    def make_close_type(self, df_1d): 
        df_1d['close_type'] = np.where(df_1d['close'] > df_1d['open'], 'p', 'm')
        return df_1d
    
    def make_base_direction(self, group): 
        # make_date() method must be called before this method
        # groupby.apply : inner method
        base = 0
        pass 


    def make_atr(self, df): 
        df['tr'] = df['high'] - df['low']
        df['atr'] = df['tr'].rolling(14).mean()
        df.dropna(inplace=True)
        df['atr'] = df['atr'].round(0)
        df['atr_upper'] = df['open'] + 1.5 * df['atr']
        df['atr_lower'] = df['open'] - 1.5 * df['atr']
        return df 


    def invert_bearish_ohlc_pct(self, df_1d, scale=1): 
        # ohlc_pct_maker() method must be called before this method
        df_1d['inverse_high_pct'] = np.where(df_1d['close_type'] == 'p', df_1d['high_pct'], df_1d['low_pct'] * -1)
        df_1d['inverse_low_pct'] = np.where(df_1d['close_type'] == 'p', df_1d['low_pct'], df_1d['high_pct'] * -1)
        df_1d['inverse_close_pct'] = np.where(df_1d['close_type'] == 'p', df_1d['close_pct'], df_1d['close_pct'] * -1)

        df_1d['inverse_high_pct'] = df_1d['inverse_high_pct'] * scale
        df_1d['inverse_low_pct'] = df_1d['inverse_low_pct'] * scale
        df_1d['inverse_close_pct'] = df_1d['inverse_close_pct'] * scale

        # df_1d = df_1d[['open_time', 'open', 'high', 'low', 'close', 'close_type', 'open_pct', 'inverse_high_pct', 'inverse_low_pct', 'inverse_close_pct']]
        
        # df_1d.rename(columns={
        #     'inverse_high_pct': 'high_pct', 
        #     'inverse_low_pct': 'low_pct', 
        #     'inverse_close_pct': 'close_pct'
        # }, inplace=True)
        return df_1d
    

    def sort_values(self, df_1d):
        # invert_bearish_ohlc_pct() method must be called before this method
        df_1d = df_1d.sort_values(by='inverse_low_pct', ascending=True)
        df_1d.reset_index(drop=True, inplace=True)
        return df_1d


    def make_rarry_way(self, df_1d, k=0.3): 
        df_1d['pre_high'] = df_1d['high'].shift(1)
        df_1d['pre_low'] = df_1d['low'].shift(1)

        df_1d['k_threshold'] = (df_1d['pre_high'] - df_1d['pre_low']) * k / df_1d['open']
        df_1d['k_threshold'] = df_1d['k_threshold'].round(3)
        
        df_1d['volatility_way'] = np.where(
            (-df_1d['k_threshold'] < df_1d['low_pct']) & (df_1d['high_pct'] < df_1d['k_threshold']), 
            'no_way', 
            np.where(
                (df_1d['low_pct'] <= -df_1d['k_threshold']) & (df_1d['k_threshold'] <= df_1d['high_pct']), 
                'two_way', 
                'one_way'
            )
        )
        df_1d.dropna(inplace=True)
        df_1d.reset_index(drop=True, inplace=True)
        return df_1d 


    def make_fixed_way(self, df_1d, threshold):
        df_1d['fixed_way'] = np.where(
            (-threshold < df_1d['low_pct']) & (df_1d['high_pct'] < threshold), 
            'no_way',
            np.where(
                (df_1d['low_pct'] <= -threshold) & (threshold <= df_1d['high_pct']), 
                'two_way', 
                'one_way'
            )
        ) 
        return df_1d



class IndicatorBuilder: 
    @staticmethod
    def add_ma7(df): 
        df['ma7'] = df['close'].rolling(window=7).mean()
        return df 

    @staticmethod
    def add_ma20(df): 
        df['ma20'] = df['close'].rolling(window=20).mean()
        return df

    @staticmethod
    def add_bollinger_bands(df): 
        ma = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()

        df['bb_mid'] = ma
        df['bb_upper'] = ma + 2*std
        df['bb_lower'] = ma - 2*std
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        return df

    @staticmethod
    def add_adr(df): 
        df['adr'] = df['high_pct'] - df['low_pct']
        return df  
    
    @staticmethod
    def add_madr(df, period): 
        df[f'madr_{str(period)}'] = df['adr'].rolling(window=period).mean()
        df[f'madr_{str(period)}'] = df[f'madr_{str(period)}'].shift(period)
        return df

    
        


class PreProcessor(Transform):
    def __init__(self): 
        pass 
    

    def transform_df(self, df_1d, threshold): 
        # df_1d transform 
        trans_df_1d = self.transfer_df(df_1d, threshold)
        trans_df_1d['date'] = trans_df_1d['open_time'].dt.date
        trans_df_1d = trans_df_1d[['date', 'way', 'way_direction', 'max_profit_pct']].copy()

        return trans_df_1d
        
        

    def split_way_df(self, df_1d):
        one_df_1d = df_1d[df_1d['way'] == 'one_way'].copy()
        two_df_1d = df_1d[df_1d['way'] != 'one_way'].copy()
        # st.write(one_df_1d.head())
        # st.write(two_df_1d.head())
        
        return one_df_1d, two_df_1d
        


    def merge_df(self, df_1d, df_1h): 
        df_1h['date'] = df_1h['open_time'].dt.date
        merged_df_1h = df_1h.merge(df_1d, on='date', how='right')
        # st.write(merged_df_1h.head())
        return merged_df_1h
      


    def pullback_run(self, df_1d, df_1h, threshold): 

        trans_df_1d = self.transform_df(df_1d, threshold)
        one_df_1d, two_df_1d = self.split_way_df(trans_df_1d)
        merged_df_1h = self.merge_df(one_df_1d, df_1h)
        
        return two_df_1d, merged_df_1h



    def run_pullback(self, df_1d, df_1h):
        pass


    def run_htratio(self, df_1d):
        pass 


class TestPreProcessor(DataFrameTransformer): 
    # DataLoader().make_df() method must be called before this method
    # The DataFrame returned by make_df() must be used as a parameter for methods below

    def run_pullback(self, df_1d, df_sub): 
        #------ transform df_1d ------#
        # df_1d: (date, way, way_direction, high_low_pct, max_profit_pct)


        #------ transform df_1h ------# 
        # df_sub: (open_time, open_pct, high_pct, low_pct, close_pct, date)

        pass 

    def run_htratio(self, df_1d): 
        pass 




    
# 1d, 1h -> 
class PullbackAnalyzer: 
    def _transform(self, df_1h): 
        # df_1h transform, should adjust groupby 1h 
        df_1h.reset_index(drop=True, inplace=True)
        open_price = df_1h.iat[0, 1]
        df_1h['high_pct'] = (df_1h['high'] - open_price) / open_price
        df_1h['low_pct'] = (df_1h['low'] - open_price) / open_price
        df_1h['close_pct'] = (df_1h['close'] - open_price) / open_price

        return df_1h



    def pullback_compute(self, df_1h, threshold): 
        # grouped 1h one_way 
        def inner_func(group):
            group = self._transform(group)
      
            if group.iat[0, 7] == 'high': 
                mask = group['high_pct'] >= threshold
                touch_idx = mask.to_numpy().argmax()
                min_max_idx = group['high_pct'].to_numpy().argmax()
                min_max_pct = group['high_pct'].to_numpy()[min_max_idx]
                group_sub = group['low_pct'].iloc[touch_idx+1:min_max_idx+1]

                if touch_idx == min_max_idx: 
                    pull_back_pct = 0
                else: 
                    pull_back_idx = group_sub.to_numpy().argmin()
                    pull_back_pct = group_sub.to_numpy()[pull_back_idx].round(4)

            elif group.iat[0, 7] == 'low': 
                mask = group['low_pct'] <= -threshold
                touch_idx = mask.to_numpy().argmax()
                min_max_idx = group['low_pct'].to_numpy().argmin()
                min_max_pct = group['low_pct'].to_numpy()[min_max_idx]
                group_sub = group['high_pct'].iloc[touch_idx+1:min_max_idx+1]

                if touch_idx == min_max_idx: 
                    pull_back_pct = 0
                else: 
                    pull_back_idx = group_sub.to_numpy().argmax()
                    pull_back_pct = group_sub.to_numpy()[pull_back_idx].round(4)
                
            date = group.iat[0, 5]
            way = group.iat[0, 6]
            way_direction = group.iat[0, 7]
            max_profit_pct = group.iat[0, 8]

            return pd.Series({
                'date': date, 
                'way': way, 
                'way_direction': way_direction, 
                'max_profit_pct': max_profit_pct,            
                'pull_back_pct': pull_back_pct, 
                'min_max_pct': min_max_pct,                 
            })
           

        result_1d = df_1h.groupby('date').apply(inner_func)
        result_1d.reset_index(drop=True, inplace=True)
       
        return result_1d
    


    def pullback_type_compute(self, combine_df_1d, threshold, losscut):
        base_losscut = threshold - losscut

        conditions_one = [
            combine_df_1d['way'] == 'no_way', 
            combine_df_1d['way'] == 'two_way', 
            (combine_df_1d['way'] == 'one_way') & (combine_df_1d['pull_back_pct'] == 0),
            (combine_df_1d['way'] == 'one_way') & (combine_df_1d['way_direction'] == 'high') & (combine_df_1d['pull_back_pct'] <= base_losscut), 
            (combine_df_1d['way'] == 'one_way') & (combine_df_1d['way_direction'] == 'low') & (combine_df_1d['pull_back_pct'] >= -base_losscut)
        ]
        choices_one = ['none', 'b', 'amd', 'amp', 'amp']
        combine_df_1d['pullback_type'] = np.select(conditions_one, choices_one, default='ap')
        
        return combine_df_1d
    


    def combine(self, one_df_1d, two_df_1d): 
        two_df_1d['pull_back_pct'] = 0
        two_df_1d['min_max_pct'] = 0
        result_df = pd.concat([one_df_1d, two_df_1d], axis=0)
        result_df = result_df.sort_values(by='date', ascending=True)

        return result_df



    def run(self, df_1d, df_1h, threshold, losscut): 
        result_one_df_1d = self.pullback_compute(df_1h, threshold)
        combine_df_1d = self.combine(result_one_df_1d, df_1d)
        result_df = self.pullback_type_compute(combine_df_1d, threshold, losscut)

        return result_df




class CdhMath: 
    @staticmethod
    def max_profit_geo_return(max_profit_arr: np.array): 
        geo_return = np.prod(1 + max_profit_arr)**(1/len(max_profit_arr)) -1
        geo_return = round(geo_return, 3)
        return geo_return 


    @staticmethod
    def max_profit_avg_return(max_profit_arr: np.array): 
        avg_return = np.mean(max_profit_arr, axis=0)
        avg_return = round(avg_return, 3)


    @staticmethod
    def min_geo_margin(beta, alpha, losscut): 
        min_margin = (1 / (1 - losscut))**(beta / alpha) - 1
        min_margin = round(min_margin, 3)
        return min_margin
   
    



class Report: 
    def pullback_report(self, df_1d, losscut): 
        total = len(df_1d)
        sub_total = (df_1d['way'] != 'no_way').sum()    

        no_way = (df_1d['way'] == 'no_way').sum()
        one_way = (df_1d['way'] == 'one_way').sum()
        two_way = (df_1d['way'] == 'two_way').sum()
        one_way_plus = (df_1d['pullback_type'] == 'ap').sum()
        one_way_minus_direct = (df_1d['pullback_type'] == 'amd').sum()
        one_way_minus_pullback = (df_1d['pullback_type'] == 'amp').sum()

        # calculate_pct
        no_way_pct = round(no_way/total * 100, 2)
        one_way_pct = round(one_way/total * 100, 2)
        two_way_pct = round(two_way/total * 100, 2)

        sub_one_way_pct = round(one_way/sub_total * 100, 2)
        sub_two_way_pct = round(two_way/sub_total * 100, 2)

        alpha = one_way_plus
        beta = two_way + one_way_minus_direct + one_way_minus_pullback
        alpha_beta_div = round(beta / alpha, 2)

        # Compute the geometric mean return for rows where type is 'ap'
        max_profit_arr = df_1d[df_1d['pullback_type'] == 'ap']['max_profit_pct'].values
        geo_return = np.prod(1 + max_profit_arr)**(1/len(max_profit_arr)) - 1
        geo_return = round(geo_return, 3)
        
        # compute min_margin
        min_margin = (1 / (1 - losscut)**(beta / alpha)) - 1
        min_margin = round(min_margin, 3)

        # make max_profit_pct arr & graph 
        max_arr = df_1d[df_1d['pullback_type'] == 'ap']['max_profit_pct'].to_list()


        result_dict_a = { 
            'no_way': [no_way, f'{no_way_pct}%', '#'], 
            'one_way': [one_way, f'{one_way_pct}%', f'{sub_one_way_pct}%'], 
            'two_way': [two_way, f'{two_way_pct}%', f'{sub_two_way_pct}%']            
            }
        
        result_dict_b = {
            'one_way_plus': [one_way_plus], 
            'one_way_minus_direct': [one_way_minus_direct], 
            'one_way_minus_pullback': [one_way_minus_pullback]
        }
        
        result_df_a = pd.DataFrame(data=result_dict_a).astype('string')
        result_df_b = pd.DataFrame(data=result_dict_b).astype('string')

        st.dataframe(df_1d)
        st.dataframe(result_df_a, hide_index=True)
        st.dataframe(result_df_b, hide_index=True)
        st.markdown(rf"$ {{\alpha}} = {alpha} $")
        st.markdown(rf"$ {{\beta}} = {beta} $")
        st.markdown(rf"$ \frac{{\beta}}{{\alpha}}={alpha_beta_div} $")

        st.markdown(rf"$ max\ return = {geo_return} $")
        st.markdown(rf"$ min\ margin = {min_margin} $")

        graph = GraphLoader()
        graph.max_profit_pct_sequence(max_arr, geo_return, min_margin)


    def pullback_dist_report(self, df_1d, threshold, max_mean, min_margin): 
        df_1d_original = df_1d
        df_1d = df_1d[df_1d['pullback_type'] != 'amd']
        # boolean method
        T_high = ((df_1d['way_direction'] == 'high') & (df_1d['pull_back_pct'] > threshold)).sum()
        T_low  = ((df_1d['way_direction'] == 'low') & (df_1d['pull_back_pct'] < -threshold)).sum()
        T_m = (df_1d_original['pullback_type'] == 'amd').sum()
        # qeury method
        A_high = df_1d.query("way_direction == 'high' and 0.5 * @threshold < pull_back_pct <= @threshold").shape[0]
        A_low  = df_1d.query("way_direction == 'low' and -@threshold <= pull_back_pct < -0.5 * @threshold").shape[0]
        B_high = df_1d.query("way_direction == 'high' and 0 < pull_back_pct <= 0.5 * @threshold").shape[0]
        B_low  = df_1d.query("way_direction == 'low' and -0.5 * @threshold <= pull_back_pct < 0").shape[0]
        C_high = df_1d.query("way_direction == 'high' and -0.5 * @threshold < pull_back_pct <= 0").shape[0]
        C_low  = df_1d.query("way_direction == 'low' and 0 <= pull_back_pct < 0.5 * @threshold").shape[0]
        D_high = df_1d.query("way_direction == 'high' and -@threshold < pull_back_pct <= -0.5 * @threshold").shape[0]
        D_low  = df_1d.query("way_direction == 'low' and 0.5 * @threshold <= pull_back_pct < @threshold").shape[0]

        # pullback and straight
        T_up = T_high + T_low 
        A    = A_high + A_low
        B    = B_high + B_low 
        C    = C_high + C_low
        D    = D_high + D_low

        # state number 
        St_up   = (df_1d_original['way'] != 'no_way').sum()
        Sa      = St_up - T_up -T_m
        Sb      = Sa - A
        Sc      = Sb - B 
        Sd      = Sc - C 
        St_down = (df_1d_original['way'] == 'two_way').sum()

        # pullback and straight_pct 
        T_up_pct = round(T_up / St_up * 100, 2)
        A_pct    = round(A / Sa * 100, 2)
        B_pct    = round(B / Sb * 100, 2)
        C_pct    = round(C / Sc * 100, 2)
        D_pct    = round(D / Sc * 100, 2)

        return {
            'St_up': St_up, 
            'Sa': Sa, 
            'Sb': Sb, 
            'Sc': Sc, 
            'Sd': Sd, 
            'St_down': St_down, 
            'T_up': T_up, 
            'A': A, 
            'B': B, 
            'C': C, 
            'D': D, 
            'T_up_pct': T_up_pct, 
            'A_pct': A_pct, 
            'B_pct': B_pct, 
            'C_pct': C_pct, 
            'D_pct': D_pct
        }
        
      
     
    def pullback_high_report(self, df_1d, threshold): 
        df_1d_ap = df_1d[df_1d['pullback_type'] == 'ap'].copy()
        st.write(df_1d_ap)

        conditions = [
            # high direction
            (df_1d_ap['way_direction'] == 'high') & (df_1d_ap['pull_back_pct'] > threshold), 
            (df_1d_ap['way_direction'] == 'high') & (df_1d_ap['pull_back_pct'] <= threshold) & (df_1d_ap['pull_back_pct'] > 0.5*threshold), 
            (df_1d_ap['way_direction'] == 'high') & (df_1d_ap['pull_back_pct'] <= 0.5*threshold) & (df_1d_ap['pull_back_pct'] > 0*threshold), 
            (df_1d_ap['way_direction'] == 'high') & (df_1d_ap['pull_back_pct'] <= 0*threshold) & (df_1d_ap['pull_back_pct'] > -0.5*threshold), 
            (df_1d_ap['way_direction'] == 'high') & (df_1d_ap['pull_back_pct'] <= -0.5*threshold) & (df_1d_ap['pull_back_pct'] > -threshold), 
            # low direction
            (df_1d_ap['way_direction'] == 'low') & (df_1d_ap['pull_back_pct'] < -threshold), 
            (df_1d_ap['way_direction'] == 'low') & (df_1d_ap['pull_back_pct'] >= -threshold) & (df_1d_ap['pull_back_pct'] < -0.5*threshold), 
            (df_1d_ap['way_direction'] == 'low') & (df_1d_ap['pull_back_pct'] >= -0.5*threshold) & (df_1d_ap['pull_back_pct'] < 0*threshold), 
            (df_1d_ap['way_direction'] == 'low') & (df_1d_ap['pull_back_pct'] >= 0*threshold) & (df_1d_ap['pull_back_pct'] < 0.5*threshold), 
            (df_1d_ap['way_direction'] == 'low') & (df_1d_ap['pull_back_pct'] >= 0.5*threshold) & (df_1d_ap['pull_back_pct'] < threshold)
        ]

        choices = ['apt', 'apa', 'apb', 'apc', 'apd', 'apt', 'apa', 'apb', 'apc', 'apd']
        df_1d_ap['detail_type'] = np.select(conditions, choices, default='none')
        st.write(df_1d_ap)

        def inner(g): 
            pull_back_type = g.iloc[0, 7]
            g_mean = g['max_profit_pct'].mean()

            return pd.Series({
                'pull_back_type': pull_back_type, 
                'max_profit_pct_mean': g_mean
            })

        result_df = df_1d_ap.groupby('detail_type').apply(inner)
        st.dataframe(result_df)

        return df_1d_ap
    


    def pullback_step_max_profit(self, df_1d_ap): 
        apt_max_arr = df_1d_ap[df_1d_ap['detail_type'] == 'apt']['max_profit_pct'].to_list()
        apa_max_arr = df_1d_ap[df_1d_ap['detail_type'] == 'apa']['max_profit_pct'].to_list()
        apb_max_arr = df_1d_ap[df_1d_ap['detail_type'] == 'apb']['max_profit_pct'].to_list()
        apc_max_arr = df_1d_ap[df_1d_ap['detail_type'] == 'apc']['max_profit_pct'].to_list()
        apd_max_arr = df_1d_ap[df_1d_ap['detail_type'] == 'apd']['max_profit_pct'].to_list()

        graph = GraphLoader()

        if len(apt_max_arr) != 0:  
            st.write('apt')
            graph.max_profit_pct_sequence(apt_max_arr)
        else:
            st.write(f'apt is None')

        if len(apa_max_arr) != 0:
            st.write('apa')
            graph.max_profit_pct_sequence(apa_max_arr)
        else: 
            st.write(f'apa is None')
                
        if len(apb_max_arr) != 0:
            st.write('apb')
            graph.max_profit_pct_sequence(apb_max_arr)
        else: 
            st.write(f'apb is None')

        if len(apc_max_arr) != 0:
            st.write('apc')
            graph.max_profit_pct_sequence(apc_max_arr)
        else: 
            st.write(f'apc is None')

        if len(apd_max_arr) != 0:
            st.write('apd')
            graph.max_profit_pct_sequence(apd_max_arr)
        else: 
            st.write(f'apd is None')

       
    
    def pullback_step_total_profit(self, df_1d_ap, df_1d): 
        pass 



    def way_report(self, df_1d, breakout): 
        
        if breakout == 'fixed':
            one_way = (df_1d['way'] == 'one_way').sum()
            two_way = (df_1d['way'] == 'two_way').sum()
            no_way = (df_1d['way'] == 'no_way').sum()

        elif breakout == 'rarry': 
            one_way = (df_1d['volatility_way'] == 'one_way').sum()
            two_way = (df_1d['volatility_way'] == 'two_way').sum()
            no_way = (df_1d['volatility_way'] == 'no_way').sum()

        total = len(df_1d)
        total_in = one_way + two_way

    

        one_way_pct = round(one_way/total * 100, 2)
        two_way_pct = round(two_way/total * 100, 2)
        no_way_pct = round(no_way/total * 100, 2)

        in_one_way_pct = round(one_way/total_in * 100, 2)
        in_two_way_pct = round(two_way/total_in * 100, 2)

        data = {
            'one_way': [f'{one_way_pct} ({one_way})'], 
            'two_way': [f'{two_way_pct} ({two_way})'], 
            'no_way': [f'{no_way_pct} ({no_way})'], 
            'one_way_in': [in_one_way_pct], 
            'two_way_in': [in_two_way_pct]
        }

        df = pd.DataFrame(data, index=[f'{breakout}'])

        st.dataframe(df)

        return df, two_way
    

    def mfe_report(self, df):     
        # mfe_label number
        zero_num = (df['mfe_label'] == 0).sum()
        one_num = (df['mfe_label'] == 1).sum()
        two_num = (df['mfe_label'] == 2).sum()
        three_num = (df['mfe_label'] == 3).sum()
        total_num = zero_num + one_num + two_num + three_num 

        # mfe_label pct 
        zero_pct = round((zero_num / total_num) * 100, 2)
        one_pct = round((one_num / total_num) * 100, 2)
        two_pct = round((two_num / total_num) * 100, 2)
        three_pct = round((three_num / total_num) * 100, 2)

        # plus, minus number
        zero_plus_num = ((df['mfe_label'] == 0) & (df['profit'] >= 1)).sum()
        zero_minus_num = zero_num - zero_plus_num
        one_plus_num = ((df['mfe_label'] == 1) & (df['profit'] >= 1)).sum()
        one_minus_num = one_num - one_plus_num
        two_plus_num = ((df['mfe_label'] == 2) & (df['profit'] >= 1)).sum()
        two_minus_num = two_num - two_plus_num 
        three_plus_num = ((df['mfe_label'] == 3) & (df['profit'] >= 1)).sum()

        # plus_pct 
        zero_plus_pct = round(zero_plus_num / zero_num * 100, 2)
        one_plus_pct = round(one_plus_num / one_num * 100, 2)
        two_plus_pct = round(two_plus_num / two_num * 100, 2)
        three_plus_pct = round(three_plus_num / three_num * 100, 2)

        # profit from mfe
        condition = (df['mfe_label'] == 0)
        zero_profit_sr = df.loc[condition, 'profit']
        zero_profit = zero_profit_sr.cumprod().iat[-1]
        zero_profit = round(zero_profit, 2) 

        condition = (df['mfe_label'] == 1)
        one_profit_sr = df.loc[condition, 'profit']
        one_profit = one_profit_sr.cumprod().iat[-1]
        one_profit = round(one_profit, 2)

        condition = (df['mfe_label'] == 2)
        two_profit_sr = df.loc[condition, 'profit']
        two_profit = two_profit_sr.cumprod().iat[-1]
        two_profit = round(two_profit, 2)

        condition = (df['mfe_label'] == 3)
        three_profit_sr = df.loc[condition, 'profit']
        three_profit = three_profit_sr.cumprod().iat[-1]
        three_profit = round(three_profit, 3)

        data = {
            'total': [
                f'{zero_num} ({zero_pct}%)',
                f'{one_num} ({one_pct}%)', 
                f'{two_num} ({two_pct}%)', 
                f'{three_num} ({three_pct}%)'
            ], 
            'plus': [
                f'{zero_plus_num} ({zero_plus_pct}%)', 
                f'{one_plus_num} ({one_plus_pct}%)',
                f'{two_plus_num} ({two_plus_pct}%)',
                f'{three_plus_num} ({three_plus_pct}%)'
            ],
            'profit': [
                zero_profit, 
                one_profit,
                two_profit, 
                three_profit
            ]
        }

        result = pd.DataFrame(data, index=['0% ~ 1%', '1% ~ 2%', '2% ~ 3%', '3% ~'])
        st.dataframe(result)


    def pandl_report(self, df, threshold, times=1): 
        
        Loss_cut = -threshold
        Loss_cut_profit = 1 + round(Loss_cut * times, 5)

        def profit(row): 
            if row['way'] == 'one_way': 
                if row['way_direction'] == 'high':
                    profit = (row['close_pct'] - threshold) / (1 + threshold)
                    profit = round(profit * times, 5)
                elif row['way_direction'] == 'low': 
                    profit = (-row['close_pct'] - threshold) / (1 - threshold)
                    profit = round(profit * times, 5)
                
                profit = 1 + profit 

                if profit < Loss_cut_profit:
                    profit = Loss_cut_profit

                return profit
            
            elif row['way'] == 'two_way': 
                profit = Loss_cut_profit
                return profit 

            elif row['way'] == 'no_way': 
                profit = 1 
                return profit
        

        df['profit'] = df.apply(profit, axis=1)

        # plus_profit
        condition = (df['way'] == 'one_way') & (df['profit'] > 1)
        plus_profit = df.loc[condition, 'profit'].cumprod().iat[-1]
        plus_profit = round(plus_profit, 3)
        
        # last_profit 
        df['cum_profit'] = df['profit'].cumprod()
        last_profit = df['cum_profit'].iat[-1]
        last_profit = round(last_profit, 3)

        # improved_profit: MFE 0 ~ 1% make profit to 1
        new_df = df.copy()
        st.write('pandl_report')
        st.dataframe(new_df.head())
        condition = (new_df['mfe_label'] == 0)
        # condition = (new_df['way'] == 'one_way') & (new_df['mfe'] < 0.01)
        new_df.loc[condition, 'profit'] = 1
        improved_profit = new_df['profit'].cumprod().iat[-1]
        improved_profit = round(improved_profit, 3)

        # fct_filtered_profit: fct > 13
        new_df = df.copy()
        condition = (new_df['fct'] >= 13)
        new_df.loc[condition, 'profit'] = 1
        fct_filtered_profit = new_df['profit'].cumprod().iat[-1]
        fct_filtered_profit = round(fct_filtered_profit, 3)

        # num: mfe_label = 0 & profit +
        zero_label_num = (df['mfe_label'] == 0).sum()
        plus_num = ((df['mfe_label'] == 0) & (df['close_profit'] > 0)).sum()
        plus_ratio = plus_num / zero_label_num * 100 
        plus_ratio = round(plus_ratio, 2)

        data = {
            'plus_profit': [plus_profit], 
            'last_profit': [last_profit],
            'improved_profit': [improved_profit], 
            'fct_profit': [fct_filtered_profit]
        }

        result_df = pd.DataFrame(data)
        st.dataframe(result_df)

        return df



    def close_profit_report(self, df): 
        total = len(df)
        minus = (df['close_profit'] <= 0).sum()
        minus_ratio = (minus / total) * 100 
        minus_ratio = round(minus_ratio, 2)

        data = {
            'total': [total], 
            'minus': [minus], 
            'minus_ratio': [f'{minus_ratio}%']
        }

        report_df = pd.DataFrame(data)
        st.dataframe(report_df)

        mean_plus = df[df['close_profit'] > 0]['close_profit'].mean()
        mean_minus = df[df['close_profit'] <= 0]['close_profit'].mean()
        mean_plus = round(mean_plus, 5)
        mean_minus = round(mean_minus, 5)
        st.write(mean_plus)
        st.write(mean_minus)


    def adr_report(self, df): 
        mfe_one_madr_one = df.loc[(df['mfe_label'] == 0), 'madr_3'].mean()
        mfe_three_madr_one = df.loc[(df['mfe_label'] == 3), 'madr_3'].mean()
        mfe_one_sadr_one = df.loc[(df['mfe_label'] == 0), 'madr_3'].std()
        mfe_three_sadr_one = df.loc[(df['mfe_label'] == 3), 'madr_3'].std()

        data = {
            'madr_1': [mfe_one_madr_one, mfe_three_madr_one], 
            'sadr_1': [mfe_one_sadr_one, mfe_three_sadr_one]
        }

        report_df = pd.DataFrame(data, index=['mfe_0', 'mfe_3'])
        st.dataframe(report_df)

        mfe_one_madr_one_sr = df.loc[(df['mfe_label'] == 0), 'madr_1']

        return df, mfe_one_madr_one_sr
    






class GraphLoader(DataFrameTransformer): 
    def __init__(self): 
        pass 


    def make_histogram(self, arr: np.ndarray, bins): 
        profit_pct_arr = arr
        hist, edges = np.histogram(profit_pct_arr, bins=bins)

        p = figure(title="profit histogram", 
                   x_axis_label = 'Value', 
                   y_axis_label = 'frequency', 
                   height = 350, 
                   toolbar_location = None)
                   
        source = ColumnDataSource(data=dict(
            left = edges[:-1], 
            right = edges[1:], 
            top = hist
        ))

        p.quad(
            top='top', bottom=0,
            left='left', right='right',
            source=source,
            fill_color="#57c55d", line_color="white", line_width=10
       )
        
        # vertical line
        vline = Span(
            location=1, 
            dimension='height', 
            line_color='purple', 
            line_dash='dashed', 
            line_width=2
        )

        p.add_layout(vline)

        st.bokeh_chart(p, use_container_width=True)



    def make_df_histogram(self, df, bins, scale=100): 
        filtered_df = df[df['way'] == 'two_way']
        df['volatility_pct'] = df['volatility_pct'] * scale
        # 2. 히스토그램 데이터 계산 (Numpy 활용)
       
        start = floor(df['volatility_pct'].min())
        end = ceil(df['volatility_pct'].max())
        st.write('bin is ', start, end)
        measured_bins = list(range(start, end+1))
        hist_all, edges_all = np.histogram(df['volatility_pct'], bins=measured_bins)
        if not filtered_df.empty:
            hist_filter, edges_filter = np.histogram(filtered_df['volatility_pct'], bins=bins)

        # 3. Bokeh Figure 객체 생성
        p = figure(
            title="데이터 분포 (Histogram)",
            tools="pan,wheel_zoom,box_zoom,reset,save",
            background_fill_color="#fafafa",
            height=300,
            x_axis_label='Value',
            y_axis_label='Count'
        )

        # 4. quad 글리프를 사용하여 히스토그램 그리기
        p.quad(
            top=hist_all,bottom=0,left=edges_all[:-1], right=edges_all[1:], 
            fill_color="navy", line_color="white", alpha=0.3
        )

        if not filtered_df.empty: 
            p.quad(
                top=hist_filter, bottom=0, left=edges_all[:-1], right=edges_all[1:],
                fill_color="tomato", line_color="white", alpha=0.7, legend_label="Filtered (> 0)"
            )
        # 5. Streamlit에 렌더링
        st.bokeh_chart(p, use_container_width=True)

       


    def candle_sequence_month(self, df, interval, threshold, max_profit=False, max_profit_line=False, rarry_line=False, bollinger=False, atr_line=False, indicator=None):
        df = df.copy()
        
        date = df.iloc[0, 0]
        open_prc = df.iloc[0, 1]
        # prev_open = df.iat[0, 8]
        # prev_high = df.iat[0, 9]
        # prev_low = df.iat[0, 10]
        # prev_type = df.iat[0, 11]

        threshold_up = open_prc * (1 + threshold)
        threshold_down = open_prc * (1 - threshold)

        inc = df.close > df.open
        dec = df.close < df.open

        if interval == '1d':
            w = 12 * 60 * 60 * 600
        elif interval == '6h': 
            w = 12 * 60 * 60 * 260
        elif interval == '1h': 
            w = 12 * 60 * 60 * 30
        elif interval == '30m': 
            w = 12 * 60 * 60 * 20
        elif interval == '15m': 
            w = 12 * 60 * 60 * 10

        p = figure(
            title = f'sequence candle: {date}', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = 'right', 
            height = 300
        )
        
        p.segment(df.open_time[inc], df.high[inc], df.open_time[inc], df.low[inc], color='#089981')
        p.segment(df.open_time[dec], df.high[dec], df.open_time[dec], df.low[dec], color='#f23645')
        p.vbar(df.open_time[inc], w, df.open[inc], df.close[inc], fill_color='#089981', line_color='#089981')
        p.vbar(df.open_time[dec], w, df.open[dec], df.close[dec], fill_color='#f23645', line_color='#f23645')
        # p.line(df.open_time, df.ma9, line_width=2, line_color='skyblue')
        # p.line(df.open_time, df.ma20, line_width=2, line_color='orange')
        
        # scatter_dates = df[df['way'] == 'two_way']['open_time'].values
        # scatter_prices = df[df['way'] == 'two_way']['high'].values + 1000
        # p.scatter(scatter_dates, scatter_prices, size=7, color='violet', marker='x')

        # ma7, ma20
        if indicator == 'ma': 
            p.line(df['open_time'], df['ma7'], line_width=2, color='skyblue')
            p.line(df['open_time'], df['ma20'], line_width=2, color='orange')

        if bollinger: 
            p.line(df['open_time'], df['bb_upper'], line_width=0.6, color='purple')
            p.line(df['open_time'], df['bb_lower'], line_width=0.6, color='purple')

        if atr_line: 
            p.line(df['open_time'], df['atr_upper'], line_width=0.6, color='green')
            p.line(df['open_time'], df['atr_lower'], line_width=0.6, color='green')
     
        # bolinger band

        p.xaxis.ticker.desired_num_ticks = 9
        p.yaxis.formatter = NumeralTickFormatter(format="0")


        hline1 = Span(location=threshold_up, dimension='width', line_color='blue', line_width=1)
        hline2 = Span(location=threshold_down, dimension='width', line_color='blue', line_width=1)
        hline3 = Span(location=open_prc, dimension='width', line_color='gray', line_width=2)

        if rarry_line: 
            st.write('rarry_line in')
            k_threshold_up = int(open_prc * (1 + df.iat[0, 12]))
            st.write(k_threshold_up)
            k_threshold_down = int(open_prc * (1 - df.iat[0, 12]))
            hline4 = Span(location=k_threshold_up, dimension='width', line_color='green', line_width=1)
            hline5 = Span(location=k_threshold_down, dimension='width', line_color='green', line_width=1)
            p.add_layout(hline4)
            p.add_layout(hline5)
        #hline4 = Span(location=prev_open, dimension='width', line_color='violet', line_width=2)
        
        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)
        #p.add_layout(hline4)

        if max_profit_line: 
            st.write(threshold, open_prc)
            one_pct_up_price = int((1 + (threshold + (1+threshold)*0.01)) * open_prc)
            one_pct_down_price = int((1 - (threshold + (1+threshold)*0.01)) * open_prc)
            two_pct_up_price = int((1 + (threshold + (1+threshold)*0.02)) * open_prc)
            two_pct_down_price = int((1 - (threshold + (1+threshold)*0.02)) * open_prc)
            three_pct_up_price = int((1 + (threshold + (1+threshold)*0.03)) * open_prc)
            three_pct_down_price = int((1 - (threshold + (1+threshold)*0.03)) * open_prc)

            one_pct_up_line = Span(location=one_pct_up_price, dimension='width', line_color='green', line_width=1)
            one_pct_down_line = Span(location=one_pct_down_price, dimension='width', line_color='green', line_width=1)
            two_pct_up_line = Span(location=two_pct_up_price, dimension='width', line_color='green', line_width=1)
            two_pct_down_line = Span(location=two_pct_down_price, dimension='width', line_color='green', line_width=1)
            three_pct_up_line = Span(location=three_pct_up_price, dimension='width', line_color='green', line_width=1)
            three_pct_down_line = Span(location=three_pct_down_price, dimension='width', line_color='green', line_width=1)

            if max_profit == '~1%': 
                p.add_layout(one_pct_up_line)
                p.add_layout(one_pct_down_line) 
            elif max_profit== '1%~3%': 
                p.add_layout(one_pct_up_line)
                p.add_layout(one_pct_down_line) 
                p.add_layout(two_pct_up_line)
                p.add_layout(two_pct_down_line) 
            elif max_profit == '3%~': 
                p.add_layout(one_pct_up_line)
                p.add_layout(one_pct_down_line) 
                p.add_layout(two_pct_up_line)
                p.add_layout(two_pct_down_line)
                p.add_layout(three_pct_up_line)
                p.add_layout(three_pct_down_line) 
              



    

        # price_box = BoxAnnotation(
        #     bottom=prev_low, 
        #     top=prev_high, 
        #     fill_alpha=0.15, 
        #     fill_color='green', 
        #     level='underlay'
        # )

        # p.add_layout(price_box)
        st.bokeh_chart(p)



    def candle_sequence_month_pct(self, df, interval, threshold, candle, 
                                  ma, bollinger, velocity_line, 
                                  max_profit_line, trigger_line):
        df = df.copy()
    
        open_prc = df.iat[0, 1]
        threshold_up = threshold * 100 
        threshold_down = -threshold * 100
        base_threshold_up = 0.01 * 100
        base_threshold_down = - 0.01 * 100 
        date = df.iat[0, 11]
        candle_type = df['type'].iat[0]
        way_direction = df.iat[0, 22]
        st.write(way_direction)

        data_low = df['low_pct'].min()
        data_high = df['high_pct'].max()

        lower = min(-5, data_low)
        upper = max(5, data_high)
        
        inc = df.close > df.open
        dec = df.close < df.open

        if interval == '1d':
            w = 12 * 60 * 60 * 600
        elif interval == '6h': 
            w = 12 * 60 * 60 * 260
        elif interval == '1h': 
            w = 12 * 60 * 60 * 30
        elif interval == '30m': 
            w = 12 * 60 * 60 * 20
        elif interval == '15m': 
            w = 12 * 60 * 60 * 10

        p = figure(
            title = f'sequence candle: {date}', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = 'right', 
            height = 300
        )
        
        if candle: 
            p.segment(df.open_time[inc], df.high_pct[inc], df.open_time[inc], df.low_pct[inc], color='#089981')
            p.segment(df.open_time[dec], df.high_pct[dec], df.open_time[dec], df.low_pct[dec], color='#f23645')
            p.vbar(df.open_time[inc], w, df.open_pct[inc], df.close_pct[inc], fill_color='#089981', line_color='#089981')
            p.vbar(df.open_time[dec], w, df.open_pct[dec], df.close_pct[dec], fill_color='#f23645', line_color='#f23645')
        
        if ma: 
            p.line(df['open_time'], df['ma7_pct'], line_width=2, color='skyblue')
            p.line(df['open_time'], df['ma20_pct'], line_width=2, color='orange')

        if bollinger:   
            p.line(df['open_time'], df['bb_upper_pct'], line_width=0.6, color='purple')
            p.line(df['open_time'], df['bb_lower_pct'], line_width=0.6, color='purple')






        p.xaxis.ticker.desired_num_ticks = 9
        p.yaxis.formatter = NumeralTickFormatter(format="0")

        hline1 = Span(location=threshold_up, dimension='width', line_color='blue', line_width=1)
        hline2 = Span(location=threshold_down, dimension='width', line_color='blue', line_width=1)
        hline3 = Span(location=0, dimension='width', line_color='gray', line_width=2)

        if trigger_line:
            hline4 = Span(location=base_threshold_up, dimension='width', line_color='purple', line_width=1)
            hline5 = Span(location=base_threshold_down, dimension='width', line_color='purple', line_width=1)


        one_pct_up = (100 + threshold_up) * 0.01 + threshold_up
        one_pct_down = -(100 - threshold_down) * 0.01 + threshold_down 
        two_pct_up = (100 + threshold_up) * 0.02 + threshold_up
        two_pct_down = -(100 - threshold_down) * 0.02 + threshold_down
        three_pct_up = (100 + threshold_up) * 0.03 + threshold_up
        three_pct_down = -(100 - threshold_down) * 0.03 + threshold_down


        one_pct_up_line = Span(location=one_pct_up, dimension='width', line_color='green', line_width=1)
        two_pct_up_line = Span(location=two_pct_up, dimension='width', line_color='green', line_width=1)
        three_pct_up_line = Span(location=three_pct_up, dimension='width', line_color='green', line_width=1)
    
        one_pct_down_line = Span(location=one_pct_down, dimension='width', line_color='green', line_width=1)
        two_pct_down_line = Span(location=two_pct_down, dimension='width', line_color='green', line_width=1)
        three_pct_down_line = Span(location=three_pct_down, dimension='width', line_color='green', line_width=1)

        
        

        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)

        if trigger_line: 
            p.add_layout(hline4)
            p.add_layout(hline5)



        if max_profit_line:

            if way_direction == 'high': 
                p.add_layout(one_pct_up_line)
                p.add_layout(two_pct_up_line)                
                p.add_layout(three_pct_up_line)
                
            if way_direction == 'low':
                p.add_layout(one_pct_down_line) 
                p.add_layout(two_pct_down_line)
                p.add_layout(three_pct_down_line) 
                


        p.y_range = Range1d(start=lower, end=upper)

        start_time = df['open_time'].iloc[0]
        end_time = df['open_time'].iloc[-1]

        open_pct = df['open_pct'].iloc[0]

    

        if way_direction == 'high': 
            three_pct = three_pct_up
            two_pct = two_pct_up
            one_pct = one_pct_up

        elif way_direction == 'low': 
            three_pct = three_pct_down
            two_pct = two_pct_down
            one_pct = one_pct_down

        else: 
            three_pct = three_pct_up
            two_pct = two_pct_up
            one_pct = one_pct_up


        if velocity_line:
            p.line(x = [start_time, end_time], y = [open_pct, three_pct], line_color = 'green', line_width = 1)
            p.line(x = [start_time, end_time], y = [open_pct, two_pct], line_color = 'green', line_width = 1)
            p.line(x = [start_time, end_time], y = [open_pct, one_pct], line_color = 'green', line_width = 1)

        
        st.bokeh_chart(p)


    def candle_sequence_15m(self, df, interval, threshold, max_profit=False, max_profit_line=False, rarry_line=False, bollinger=False, atr_line=False, indicator=None):
        df = df.copy()
        # st.dataframe(df)
        
        date = df.iloc[0, 0]
        open_prc = df.iloc[0, 1]
        # prev_open = df.iat[0, 8]
        # prev_high = df.iat[0, 9]
        # prev_low = df.iat[0, 10]
        # prev_type = df.iat[0, 11]

        threshold_up = open_prc * (1 + threshold)
        threshold_down = open_prc * (1 - threshold)

        inc = df.close > df.open
        dec = df.close < df.open

        if interval == '1d':
            w = 12 * 60 * 60 * 600
        elif interval == '6h': 
            w = 12 * 60 * 60 * 260
        elif interval == '1h': 
            w = 12 * 60 * 60 * 30
        elif interval == '30m': 
            w = 12 * 60 * 60 * 20
        elif interval == '15m': 
            w = 12 * 60 * 60 * 10

        p = figure(
            title = f'sequence candle: {date}', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = 'right', 
            height = 300
        )
        
        p.segment(df.open_time[inc], df.high[inc], df.open_time[inc], df.low[inc], color='#089981')
        p.segment(df.open_time[dec], df.high[dec], df.open_time[dec], df.low[dec], color='#f23645')
        p.vbar(df.open_time[inc], w, df.open[inc], df.close[inc], fill_color='#089981', line_color='#089981')
        p.vbar(df.open_time[dec], w, df.open[dec], df.close[dec], fill_color='#f23645', line_color='#f23645')
        # p.line(df.open_time, df.ma9, line_width=2, line_color='skyblue')
        # p.line(df.open_time, df.ma20, line_width=2, line_color='orange')
        
        # scatter_dates = df[df['way'] == 'two_way']['open_time'].values
        # scatter_prices = df[df['way'] == 'two_way']['high'].values + 1000
        # p.scatter(scatter_dates, scatter_prices, size=7, color='violet', marker='x')

        # ma7, ma20
        if indicator == 'ma': 
            p.line(df['open_time'], df['ma7'], line_width=2, color='skyblue')
            p.line(df['open_time'], df['ma20'], line_width=2, color='orange')

        if bollinger: 
            p.line(df['open_time'], df['bb_upper'], line_width=0.6, color='purple')
            p.line(df['open_time'], df['bb_lower'], line_width=0.6, color='purple')

        if atr_line: 
            p.line(df['open_time'], df['atr_upper'], line_width=0.6, color='green')
            p.line(df['open_time'], df['atr_lower'], line_width=0.6, color='green')
     
        # bolinger band

        p.xaxis.ticker.desired_num_ticks = 9
        p.yaxis.formatter = NumeralTickFormatter(format="0")


        hline1 = Span(location=threshold_up, dimension='width', line_color='blue', line_width=1)
        hline2 = Span(location=threshold_down, dimension='width', line_color='blue', line_width=1)
        hline3 = Span(location=open_prc, dimension='width', line_color='gray', line_width=2)

        if rarry_line: 
            st.write('rarry_line in')
            k_threshold_up = int(open_prc * (1 + df.iat[0, 12]))
            st.write(k_threshold_up)
            k_threshold_down = int(open_prc * (1 - df.iat[0, 12]))
            hline4 = Span(location=k_threshold_up, dimension='width', line_color='green', line_width=1)
            hline5 = Span(location=k_threshold_down, dimension='width', line_color='green', line_width=1)
            p.add_layout(hline4)
            p.add_layout(hline5)
        #hline4 = Span(location=prev_open, dimension='width', line_color='violet', line_width=2)
        
        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)
        #p.add_layout(hline4)

        if max_profit_line: 
            st.write(threshold, open_prc)
            one_pct_up_price = int((1 + (threshold + (1+threshold)*0.01)) * open_prc)
            one_pct_down_price = int((1 - (threshold + (1+threshold)*0.01)) * open_prc)
            two_pct_up_price = int((1 + (threshold + (1+threshold)*0.02)) * open_prc)
            two_pct_down_price = int((1 - (threshold + (1+threshold)*0.02)) * open_prc)
            three_pct_up_price = int((1 + (threshold + (1+threshold)*0.03)) * open_prc)
            three_pct_down_price = int((1 - (threshold + (1+threshold)*0.03)) * open_prc)

            one_pct_up_line = Span(location=one_pct_up_price, dimension='width', line_color='green', line_width=1)
            one_pct_down_line = Span(location=one_pct_down_price, dimension='width', line_color='green', line_width=1)
            two_pct_up_line = Span(location=two_pct_up_price, dimension='width', line_color='green', line_width=1)
            two_pct_down_line = Span(location=two_pct_down_price, dimension='width', line_color='green', line_width=1)
            three_pct_up_line = Span(location=three_pct_up_price, dimension='width', line_color='green', line_width=1)
            three_pct_down_line = Span(location=three_pct_down_price, dimension='width', line_color='green', line_width=1)

            if max_profit == '~1%': 
                p.add_layout(one_pct_up_line)
                p.add_layout(one_pct_down_line) 
            elif max_profit== '1%~3%': 
                p.add_layout(one_pct_up_line)
                p.add_layout(one_pct_down_line) 
                p.add_layout(two_pct_up_line)
                p.add_layout(two_pct_down_line) 
            elif max_profit == '3%~': 
                p.add_layout(one_pct_up_line)
                p.add_layout(one_pct_down_line) 
                p.add_layout(two_pct_up_line)
                p.add_layout(two_pct_down_line)
                p.add_layout(three_pct_up_line)
                p.add_layout(three_pct_down_line) 
              


        # -- (add 1h candle) -- #
        df_1h = df.resample('1h', on='open_time').agg({
            'open': 'first', 
            'close': 'last'
        }).reset_index()
        # st.dataframe(df_1h)
        inc_1h = df_1h.close > df_1h.open
        dec_1h = df_1h.open > df_1h.close 

        df_1h['center_time'] = df_1h['open_time'] + pd.Timedelta(minutes=22.5)
        w_1h = 60 * 60 * 1000 * 0.9

        p.vbar(df_1h.center_time[inc_1h], w_1h, df_1h.open[inc_1h], df_1h.close[inc_1h], 
               fill_color='#089981', line_color='#089981', fill_alpha=0.15, line_alpha=0.5)
        p.vbar(df_1h.center_time[dec_1h], w_1h, df_1h.open[dec_1h], df_1h.close[dec_1h], 
               fill_color='#f23645', line_color='#f23645', fill_alpha=0.15, line_alpha=0.5)


        # price_box = BoxAnnotation(
        #     bottom=prev_low, 
        #     top=prev_high, 
        #     fill_alpha=0.15, 
        #     fill_color='green', 
        #     level='underlay'
        # )

        # p.add_layout(price_box)
        st.bokeh_chart(p)


    def candle_sequence_6h(self, df):
        df = df.copy()
        
        date = df.iloc[0, 5]
        
        
        inc = df.close > df.open
        dec = df.close < df.open

        w = 12 * 60 * 60 * 260
        
        p = figure(
            title = f'sequence candle: {date}', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            height = 300,
            tools='xpan,reset', 
            toolbar_location='above'
        )
        
        p.segment(df.open_time[inc], df.high[inc], df.open_time[inc], df.low[inc], color='#089981')
        p.segment(df.open_time[dec], df.high[dec], df.open_time[dec], df.low[dec], color='#f23645')
        p.vbar(df.open_time[inc], w, df.open[inc], df.close[inc], fill_color='#089981', line_color='#089981')
        p.vbar(df.open_time[dec], w, df.open[dec], df.close[dec], fill_color='#f23645', line_color='#f23645')
        

        
        p.xaxis.ticker.desired_num_ticks = 9
        p.yaxis.formatter = NumeralTickFormatter(format="0")

        

        st.bokeh_chart(p, use_container_width=True)


    def cumprofit_line_graph(self, df): 

        p = figure(
            title = f'cumprod_profit', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = None, 
            height = 300
        )
        p.line(df['open_time'], df['cum_profit'], line_width=2, color='skyblue')

        st.bokeh_chart(p, use_container_width=True)

    
    from bokeh.plotting import figure
    from bokeh.models import NumeralTickFormatter, DatetimeTicker, DaysTicker

    
    from bokeh.plotting import figure
    from bokeh.models import NumeralTickFormatter, DatetimeTicker


    


    def candle_sequence_pct(self, df, threshold): 
        df = df.copy()
        # df : open_time, o, h, l, c, date, o_p, h_p, l_p, c_p

        open = 0
        df[['open_pct', 'high_pct', 'low_pct', 'close_pct']] = df[['open_pct', 'high_pct', 'low_pct', 'close_pct']] * 100
        label_start = df.iat[0, 5]
        label_end = df.iat[-1, 5]
        threshold_up = threshold * 100
        threshold_down = -threshold * 100
        detect_up = 2.2
        detect_down = -2.2

        inc = df.close > df.open
        dec = df.close < df.open

        if len(df) <= 32: 
            w = 12 * 60 * 60 * 300
        else: 
            w = 12 * 60 * 60 * 230
       

        p = figure(
            title = f'sequence 6h: {label_start} ~ {label_end}', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = None, 
            height = 300
        )

        p.segment(df.open_time[inc], df.high_pct[inc], df.open_time[inc], df.low_pct[inc], color='#089981')
        p.segment(df.open_time[dec], df.high_pct[dec], df.open_time[dec], df.low_pct[dec], color='#f23645')
        p.vbar(df.open_time[inc], w, df.open_pct[inc], df.close_pct[inc], fill_color='#089981', line_color='#089981')
        p.vbar(df.open_time[dec], w, df.open_pct[dec], df.close_pct[dec], fill_color='#f23645', line_color='#f23645')

        p.xaxis.ticker.desired_num_ticks = 9
        p.yaxis.formatter = NumeralTickFormatter(format="0")

        hline1 = Span(location=threshold_up, dimension='width', line_color='blue', line_width=1)
        hline2 = Span(location=threshold_down, dimension='width', line_color='blue', line_width=1)
        hline3 = Span(location=open, dimension='width', line_color='gray', line_width=2)
        hline4 = Span(location=detect_up, dimension='width', line_color='orange', line_width=1)
        hline5 = Span(location=detect_down, dimension='width', line_color='orange', line_width=1)
        
        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)
        p.add_layout(hline4)
        p.add_layout(hline5)

        st.bokeh_chart(p)



    def candle_sequence_str_pct(self, df, threshold): 
        df = df.copy()
        # df : open_time, o, h, l, c, date, o_p, h_p, l_p, c_p

        open = 0
        df[['open_pct', 'high_pct', 'low_pct', 'close_pct']] = df[['open_pct', 'high_pct', 'low_pct', 'close_pct']] * 100
        label_start = df.iat[0, 5]
        label_end = df.iat[-1, 5]
        threshold_up = threshold * 100
        threshold_down = -threshold * 100
        detect_up = 2.2
        detect_down = -2.2

        inc = df.close > df.open
        dec = df.close < df.open

        if len(df) <= 32: 
            w = 0.6
        else: 
            w = 0.5
       

        p = figure(
            title = f'sequence 6h: {label_start} ~ {label_end}', 
            x_range=list(df["time_str"]),
            sizing_mode = 'stretch_width', 
            toolbar_location = None, 
            height = 300
        )

        p.segment(df.time_str[inc], df.high_pct[inc], df.time_str[inc], df.low_pct[inc], color='#089981')
        p.segment(df.time_str[dec], df.high_pct[dec], df.time_str[dec], df.low_pct[dec], color='#f23645')
        p.vbar(df.time_str[inc], w, df.open_pct[inc], df.close_pct[inc], fill_color='#089981', line_color='#089981')
        p.vbar(df.time_str[dec], w, df.open_pct[dec], df.close_pct[dec], fill_color='#f23645', line_color='#f23645')

        
        
        
        
        
        
        
        
        
        p.yaxis.formatter = NumeralTickFormatter(format="0")
        p.xaxis.major_label_orientation = 1.0
        # p.xaxis.visible = False
        p.xaxis.major_label_text_font_size = "0pt"
        p.xaxis.major_tick_line_color = None
        p.xaxis.minor_tick_line_color = None

        hline1 = Span(location=threshold_up, dimension='width', line_color='blue', line_width=1)
        hline2 = Span(location=threshold_down, dimension='width', line_color='blue', line_width=1)
        hline3 = Span(location=open, dimension='width', line_color='gray', line_width=2)
        hline4 = Span(location=detect_up, dimension='width', line_color='orange', line_width=1)
        hline5 = Span(location=detect_down, dimension='width', line_color='orange', line_width=1)
        
        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)
        p.add_layout(hline4)
        p.add_layout(hline5)

        st.bokeh_chart(p)


    
    def candle_sequence_pct_two(self, df, threshold): 
        df = df.copy()
        # df : open_time, o, h, l, c, date, o_p, h_p, l_p, c_p

        open = 0
        df[['open_pct', 'high_pct', 'low_pct', 'close_pct']] = df[['open_pct', 'high_pct', 'low_pct', 'close_pct']] * 100
        label_start = df.iat[0, 5]
        label_end = df.iat[-1, 5]
        threshold_up = threshold * 100
        threshold_down = -threshold * 100
        inc = df.close > df.open
        dec = df.close < df.open

        w = 12 * 60 * 60 * 230

        p = figure(
            title = f'sequence 6h: {label_start} ~ {label_end}', 
            x_axis_type = None, 
            sizing_mode = 'stretch_width', 
            toolbar_location = None, 
            height = 300
        )

        # box annotation 
        

        # candle 
        p.segment(df.open_time[inc], df.high_pct[inc], df.open_time[inc], df.low_pct[inc], color='#089981')
        p.segment(df.open_time[dec], df.high_pct[dec], df.open_time[dec], df.low_pct[dec], color='#f23645')
        p.vbar(df.open_time[inc], w, df.open_pct[inc], df.close_pct[inc], fill_color='#089981', line_color='#089981')
        p.vbar(df.open_time[dec], w, df.open_pct[dec], df.close_pct[dec], fill_color='#f23645', line_color='#f23645')

        # p.xaxis.ticker.desired_num_ticks = 9
        p.yaxis.formatter = NumeralTickFormatter(format="0")

        hline1 = Span(location=threshold_up, dimension='width', line_color='blue', line_width=1)
        hline2 = Span(location=threshold_down, dimension='width', line_color='blue', line_width=1)
        hline3 = Span(location=open, dimension='width', line_color='gray', line_width=2)
        
        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)

        st.bokeh_chart(p)


    def candle_volatility_mixed(self, df_1d, threshold, sort=False): 
        #------ dataframe manuplation ------#
        # df_1d: (open_time: pd.to_datetime, open, high, low, close)
        df_1d = df_1d.copy()
        df_1d = self.make_close_type(df_1d)
        df_1d = self.make_ohlc_pct(df_1d, '1d')
        df_1d = self.invert_bearish_ohlc_pct(df_1d, scale=100)

        if sort: 
            df = self.sort_values(df_1d)
        else: 
            df = df_1d

        # #------ graph implementation ------#
        date = df.iat[0, 0]

        inc = df['close_type'] == 'p'
        dec = df['close_type'] == 'm'
        w = 12 * 60 * 60 * 1000

        p = figure(
            title = f'sequence candle: {date.year}-{date.month}', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = None, 
            height = 300
        )

        color_one = '#6B68E8'
        color_two = '#B6C5E8'

        p.segment(df.open_time[inc], df.high_pct[inc], df.open_time[inc], df.low_pct[inc], color=color_one)
        p.segment(df.open_time[dec], df.high_pct[dec], df.open_time[dec], df.low_pct[dec], color=color_two)
        p.vbar(df.open_time[inc], w, df.open_pct[inc], df.close_pct[inc], fill_color=color_one, line_color=color_one)
        p.vbar(df.open_time[dec], w, df.open_pct[dec], df.close_pct[dec], fill_color=color_two, line_color=color_two)
        p.xaxis.ticker.desired_num_ticks = 9

        
        
        # p line 
        x_min = df['open_time'].min()
        x_max = df['open_time'].max()
        threshold = threshold * 100

        p.line([x_min, x_max], [threshold, threshold], line_color='purple', line_width=2)
        p.line([x_min, x_max], [-threshold, -threshold], line_color='purple', line_width=2)

        st.bokeh_chart(p)




    def candle_volatility_mixed_sort(self, df_1d, threshold, rarry=False, percent_line='off', sort='low'): 
        #------ dataframe manuplation ------#
        # df_1d: (open_time: pd.to_datetime, open, high, low, close)
        df_1d = self.make_close_type(df_1d)
        df_1d = self.make_ohlc_pct(df_1d, '1d')
        df_1d = self.invert_bearish_ohlc_pct(df_1d, scale=100)
        if rarry: 
            df_1d = self.make_rarry_way(df_1d)
        df_1d = self.make_fixed_way(df_1d, threshold)
        
        # st.write('graphLoader --======')
        # st.dataframe(df_1d)

       
        if sort == 'low': 
            df = df_1d.sort_values('inverse_low_pct')
            df.reset_index(drop=True, inplace=True)
        elif sort == 'high': 
            df = df_1d.sort_values('inverse_high_pct')
            df.reset_index(drop=True, inplace=True)
        else: 
            df = df_1d

        

        # #------ graph implementation ------#
        date_min = df['open_time'].min()
        date_max = df['open_time'].max()

        inc = df['close_type'] == 'p'
        dec = df['close_type'] == 'm'
        w = 0.3 

        p = figure(
            title = f'sequence candle: {date_min.year}-{date_min.month}', 
            
            sizing_mode = 'stretch_width', 
            toolbar_location = 'right', 
            height = 300
        )

        color_one = '#6B68E8'
        color_two = '#93A6D4'
   
        color_two = '#B6C5E8'
        if rarry: 
            for i in range(len(df)): 
                p.vbar(df.index[i], 0.8, -df.iat[i,15]*100, df.iat[i, 15]*100, fill_color='#1DB100', alpha=0.2, line_color=None)
        # p.vbar(df.index[1], 0.8, 0.6, -0.6, fill_color='#1DB100', alpha=0.3, line_color=None)

        p.segment(df.index[inc], df.inverse_high_pct[inc], df.index[inc], df.inverse_low_pct[inc], color=color_one)
        p.segment(df.index[dec], df.inverse_high_pct[dec], df.index[dec], df.inverse_low_pct[dec], color=color_two)
        p.vbar(df.index[inc], w, df.open_pct[inc], df.inverse_close_pct[inc], fill_color=color_one, line_color=color_one)
        p.vbar(df.index[dec], w, df.open_pct[dec], df.inverse_close_pct[dec], fill_color=color_two, line_color=color_two)
        p.xaxis.ticker.desired_num_ticks = 9


       
        
        # p line 
        x_min = df.index.min()
        x_max = df.index.max()
        
        if percent_line == 'on':
            one_percent_line = ((1+threshold)*0.01 + threshold) * 100
            one_percent_line = round(one_percent_line, 2)
            two_percent_line = ((1+threshold)*0.02 + threshold) * 100
            two_percent_line = round(two_percent_line, 2)
            three_percent_line = ((1+threshold)*0.03 + threshold) * 100
            three_percent_line = round(three_percent_line, 2)

            p.line([x_min, x_max], [one_percent_line, one_percent_line], line_color='green', line_width=1)
            p.line([x_min, x_max], [-one_percent_line, -one_percent_line], line_color='green', line_width=1)
            p.line([x_min, x_max], [two_percent_line, two_percent_line], line_color='green', line_width=0.3)
            p.line([x_min, x_max], [-two_percent_line, -two_percent_line], line_color='green', line_width=0.3)
            p.line([x_min, x_max], [three_percent_line, three_percent_line], line_color='green', line_width=0.3)
            p.line([x_min, x_max], [-three_percent_line, -three_percent_line], line_color='green', line_width=0.3)

        threshold = threshold * 100

        p.line([x_min, x_max], [threshold, threshold], line_color='purple', line_width=1)
        p.line([x_min, x_max], [-threshold, -threshold], line_color='purple', line_width=1)

       
        st.bokeh_chart(p)


    def candle_volatility_mixed_sort_one(self, df_1d, threshold, rarry=False, sort='low'): 
        #------ dataframe manuplation ------#
        # df_1d: (open_time: pd.to_datetime, open, high, low, close)
        df_1d = self.make_close_type(df_1d)
        df_1d = self.make_ohlc_pct(df_1d, '1d')
        df_1d = self.invert_bearish_ohlc_pct(df_1d, scale=100)
        if rarry: 
            df_1d = self.make_rarry_way(df_1d)
        df_1d = self.make_fixed_way(df_1d, threshold)

        # st.write('graphLoader --======')
        # st.dataframe(df_1d)

        df_1d['inverse_open_pct'] = 0
        df_1d['inverse_open_pct'] = df_1d['inverse_open_pct'] - df_1d['inverse_low_pct']
        df_1d['inverse_high_pct'] = df_1d['inverse_high_pct'] - df_1d['inverse_low_pct']
        df_1d['inverse_close_pct'] = df_1d['inverse_close_pct'] - df_1d['inverse_low_pct']
        df_1d['inverse_low_pct'] = 0 

        st.write('sort_one')
        st.dataframe(df_1d)

        if sort == 'low': 
            df = df_1d.sort_values('inverse_low_pct')
            df.reset_index(drop=True, inplace=True)
        elif sort == 'high': 
            df = df_1d.sort_values('inverse_high_pct')
            df.reset_index(drop=True, inplace=True)
        else: 
            df = df_1d

        

        # #------ graph implementation ------#
        date_min = df['open_time'].min()
        date_max = df['open_time'].max()

        inc = df['close_type'] == 'p'
        dec = df['close_type'] == 'm'
        w = 0.3

        p = figure(
            title = f'sequence candle: {date_min.year}-{date_min.month}', 
            
            sizing_mode = 'stretch_width', 
            toolbar_location = 'right', 
            height = 300
        )

        color_one = '#6B68E8'
        color_two = '#93A6D4'
   
        color_two = '#B6C5E8'
        if rarry: 
            for i in range(len(df)): 
                p.vbar(df.index[i], 0.8, -df.iat[i,15]*100, df.iat[i, 15]*100, fill_color='#1DB100', alpha=0.2, line_color=None)
        # p.vbar(df.index[1], 0.8, 0.6, -0.6, fill_color='#1DB100', alpha=0.3, line_color=None)

        p.segment(df.index[inc], df.inverse_high_pct[inc], df.index[inc], df.inverse_low_pct[inc], color=color_one)
        p.segment(df.index[dec], df.inverse_high_pct[dec], df.index[dec], df.inverse_low_pct[dec], color=color_two)
        p.vbar(df.index[inc], w, df.inverse_low_pct[inc], df.inverse_high_pct[inc], fill_color=color_one, line_color=color_one)
        p.vbar(df.index[dec], w, df.inverse_low_pct[dec], df.inverse_high_pct[dec], fill_color=color_two, line_color=color_two)
        p.xaxis.ticker.desired_num_ticks = 9


       
        
        # p line 
        x_min = df.index.min()
        x_max = df.index.max()
        threshold = threshold * 100

        p.line([x_min, x_max], [threshold, threshold], line_color='purple', line_width=1)
        p.line([x_min, x_max], [-threshold, -threshold], line_color='purple', line_width=1)

        st.bokeh_chart(p)


    def pull_back_vertical(self, df, threshold=0.01): 
        st.dataframe(df)
        x = df.index.tolist()
        a = df['min_max_pct'].tolist()
        b = df['pull_back_pct'].tolist()

        p = figure(title='Vertical Lines Example', height=300, toolbar_location=None)
        p.segment(x0=x, y0=a, x1=x, y1=b, line_width=2, color="navy")

        hline1 = Span(location=threshold, dimension='width', line_color='purple', line_width=2)
        hline2 = Span(location=-threshold, dimension='width', line_color='purple', line_width=2)
        
        p.add_layout(hline1)
        p.add_layout(hline2)

        st.bokeh_chart(p)

        st.write(f'one_way: {len(df)}')


    

    def pull_back_all_vertical(self, df, threshold=0.01, loss_cut=0.01): 
        
        inc = df['type'] == 'p'
        dec = df['type'] == 'm'
        w = 12 * 60 * 60 * 600
        sequence = df.loc[0, 'date']
        loss = threshold - loss_cut

        p = figure(
            title = f'{sequence} candle', 
            x_axis_type = 'datetime', 
            sizing_mode = 'stretch_width', 
            toolbar_location = None, 
            height = 350
        )

        # color
        a = '#d1e0e0'
        b = '#7c4dfb'
        c = '#bda9f3'
       
        p.segment(df.open_time, df.min_max_pct, df.open_time, df.pull_back_pct, line_width=14, color=a)

        p.segment(df.open_time[inc], df.high_pct[inc], df.open_time[inc], df.low_pct[inc], color=b)
        p.segment(df.open_time[dec], df.high_pct[dec], df.open_time[dec], df.low_pct[dec], color=c)
        p.vbar(df.open_time[inc], w, df.open_pct[inc], df.close_pct[inc], fill_color=b, line_color=b)
        p.vbar(df.open_time[dec], w, df.open_pct[dec], df.close_pct[dec], fill_color=c, line_color=c)

        hline1 = Span(location=threshold, dimension='width', line_color='green', line_width=2)
        hline2 = Span(location=-threshold, dimension='width', line_color='green', line_width=2)

        hline3 = Span(location=loss, dimension='width', line_color='blue', line_width=1)
        hline4 = Span(location=-loss, dimension='width', line_color='red', line_width=1)

        hline5 = Span(location=2*threshold, dimension='width', line_color='#2ecc71')
        hline6 = Span(location=-2*threshold, dimension='width', line_color='#2ecc71')

        p.add_layout(hline1)
        p.add_layout(hline2)
        p.add_layout(hline3)
        p.add_layout(hline4)
        p.add_layout(hline5)
        p.add_layout(hline6)

        p.xaxis.ticker.desired_num_ticks = 9
        
        st.bokeh_chart(p)




    def threshold_sequence(self, df): 
        st.write(df)
        x = list(df.columns)

        p = figure(
            # x_range=x, 
            title="Each Row as a Line (axis=1 direction)",
            height=350, 
            width=600,
            toolbar_location=None
        )

        palette = Category10[10]

        for i, (year, row) in enumerate(df.iterrows()): 
            y = row.values
            p.line(
                x, 
                y, 
                color=palette[i % len(palette)], 
                legend_label=str(year), 
                line_width=2
            )

        p.legend.title = "Year"
        p.legend.location = "top_right"
        p.legend.click_policy = "hide" 
       
        st.bokeh_chart(p)
   
   


     


    def max_profit_pct_sequence(self, arr: list, max_mean=None, min_margin=None): 
        x_idx = list(range(len(arr)))

        source = ColumnDataSource(data=dict(x=x_idx, y=arr))

        p = figure(title='max_profit_pct_sequence', 
                   height=350)
        p.circle(x='x', y='y', size=3, source=source, color="navy", alpha=0.7)

        if max_mean is not None: 
            hline_max = Span(location=max_mean, dimension='width', line_color='red', line_width=2)
            p.add_layout(hline_max)

        if min_margin is not None: 
            hline_min = Span(location=min_margin, dimension='width', line_color='red', line_width=2)
            p.add_layout(hline_min)
        
        st.bokeh_chart(p)






    def pull_back_distribution(self, dist_values): 
        x =  [10, 20, 30, 40, 50, 60]
        factors = [75, 65, 55, 45, 35, 25]

        p = figure(title="Categorical Dot Plot", tools="", toolbar_location=None,
                y_range=[0,100], x_range=[0,100], height=500)

        #p.segment(0, factors, x, factors, line_width=2, line_color="green", )
        p.circle(x, factors, size=35, fill_color="#E9E9E9", line_color="#E9E9E9", line_width=1)

        p.segment(0, 70, 100, 70, line_width=2, line_color="gray", )
        p.segment(0, 60, 100, 60, line_width=2, line_color="gray", )
        p.segment(0, 50, 100, 50, line_width=5, line_color="#aa6ce9", )
        p.segment(0, 40, 100, 40, line_width=2, line_color="gray", )
        p.segment(0, 30, 100, 30, line_width=2, line_color="gray", )

        # add arrows
        arrow_color = '#81FF81'
        arrow_t_up = Arrow(end=NormalHead(fill_color="black", size=5),
                    x_start=10, y_start=75,
                    x_end=15, y_end=85,
                    line_color=arrow_color, line_width=1, level='underlay')
        arrow_a = Arrow(end=NormalHead(fill_color="black", size=5),
                    x_start=20, y_start=65,
                    x_end=30, y_end=85,
                    line_color=arrow_color, line_width=1, level='underlay')
        arrow_b = Arrow(end=NormalHead(fill_color="black", size=5),
                    x_start=30, y_start=55,
                    x_end=45, y_end=85,
                    line_color=arrow_color, line_width=1, level='underlay')
        arrow_c = Arrow(end=NormalHead(fill_color="black", size=5),
                    x_start=40, y_start=45,
                    x_end=60, y_end=85,
                    line_color=arrow_color, line_width=1, level='underlay')
        arrow_d = Arrow(end=NormalHead(fill_color="black", size=5),
                    x_start=50, y_start=35,
                    x_end=75, y_end=85,
                    line_color=arrow_color, line_width=1, level='underlay')

        p.add_layout(arrow_t_up)
        p.add_layout(arrow_a)
        p.add_layout(arrow_b)
        p.add_layout(arrow_c)
        p.add_layout(arrow_d)

        # state_values
        p.text(
            x=x,
            y=factors,
            text=[
                dist_values['St_up'], 
                dist_values['Sa'], 
                dist_values['Sb'], 
                dist_values['Sc'], 
                dist_values['Sd'], 
                dist_values['St_down']
            ],
            text_align='center',
            text_baseline='middle',   # 원 중심에 오게
            text_font_size="10pt"
        )

        # pull_back and straight values
        p.text(
            x=[17, 32, 47, 62, 77],
            y=90,
            text=[
                f"{dist_values['T_up']} ({dist_values['T_up_pct']}%)",
                f"{dist_values['A']} ({dist_values['A_pct']}%)",
                f"{dist_values['B']} ({dist_values['B_pct']}%)",
                f"{dist_values['C']} ({dist_values['C_pct']}%)",
                f"{dist_values['D']} ({dist_values['D_pct']}%)", 
            ],
            text_align='center',
            text_baseline='middle',   # 원 중심에 오게
            text_font_size="10pt"
        )

        st.bokeh_chart(p)



    def pull_back_high(self, df_1d):
        df = df_1d.copy()

        groups = df['detail_type'].unique()
        colors = Category10[len(groups)]

        ### --------------------------
        ###  보케 figure 생성
        ### --------------------------
        p = figure(
            title="Group-wise Smooth Line Histogram (KDE)",
            width=850, height=450,
            tools="pan,wheel_zoom,box_zoom,reset"
        )

        legend_items = []

        ### --------------------------
        ###  각 그룹별 KDE 커브 플롯
        ### --------------------------
        for (g, color) in zip(groups, colors):
            data = df.loc[df['detail_type'] == g, 'max_profit_pct'].values

            # KDE 밀도 추정
            kde = gaussian_kde(data)

            # X축 범위 생성 (데이터 전체 범위에서 촘촘히)
            xs = np.linspace(data.min(), data.max(), 400)
            ys = kde(xs)

            r = p.line(xs, ys, line_width=2, color=color)
            legend_items.append((str(g), [r]))

        ### --------------------------
        ###  범례 추가
        ### --------------------------
        from bokeh.models import Legend
        legend = Legend(items=legend_items)
        p.add_layout(legend, "right")

        ### --------------------------
        ###  Streamlit 출력
        ### --------------------------
        st.bokeh_chart(p) 


    
    def volatility(self, df_1d): 
        
        source = ColumnDataSource(df_1d)

        p = figure(
            title='Scatter Plot Example', 
            x_axis_label='X', 
            y_axis_label='Y',
            sizing_mode='stretch_width', 
            height=350            
        )

        p.circle(
            x="pre_volatility",
            y="volatility",
            source=source,
            size=3,
            alpha=0.6
        )

        st.bokeh_chart(p)











class Utility: 
    def __init__(self):
        pass 


    @staticmethod
    def make_dt_from_millis(millis): 
        seconds = int(millis / 1000)
        utc_dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return utc_dt


    @staticmethod
    def make_millis_from_dt(dt):
        utc_dt = dt.replace(tzinfo=timezone.utc) 
        millis = int(utc_dt.timestamp() * 1000)
        return millis
    

    @staticmethod
    def make_utc_dt(dt): 
        utc_dt = dt.replace(tzinfo=timezone.utc)
        return utc_dt
      


    










if __name__ == "__main__":
    pos = PostgresHandler('btcusdt')
    pos.connect() 
    
    loader = DataLoader(pos)
    transformer = DataFrameTransformer()
    df_1d = loader.make_df('1d', datetime(2024, 9, 1), datetime(2024, 9, 30), open_time_dt=True, volume=False, ohlc_type='float')
    df_1h = loader.make_df('1h', datetime(2025, 9, 1), datetime(2025, 9, 2), open_time_dt=True, volume=False, ohlc_type='float')
    # df_1h = transformer.date_maker(df_1h)
    # df_1d = transformer.ohlc_pct_maker(df_1d, '1d')
    # df_1d = transformer.way_maker(df_1d, 0.01)
    # df_1d = transformer.way_direction_maker(df_1d, 0.01)
    # df_1d = transformer.max_profit_pct_maker(df_1d, 0.01)

    df_1d = transformer.close_type_maker(df_1d)
    df_1d = transformer.htr_maker(df_1d)
    print(df_1d.head())

    pos.disconnect
  
