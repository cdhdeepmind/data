from data_collector_psql import PostgresHandler, DataCollector, Utility, DataLoader, GraphLoader, PreProcessor, DataFrameTransformer, Report
from datetime import datetime, date, timedelta

import streamlit as st 
import pandas as pd 
import importlib
import time
import data_collector_psql 

importlib.reload(data_collector_psql)

st.title('volatility')
st.divider()

if st.session_state.posdb:
    st.write('postgresql is ready to use')

    col1, col2 = st.columns(2)
    start = col1.date_input('start_date', date(2025, 1, 1))
    end = col2.date_input('end_date', date(2025, 1, 31))
    threshold = st.number_input(
        'threshold', 
        min_value = 0.004, 
        max_value = 0.021, 
        step = 0.001, 
        format = '%.3f', 
        value = 0.012
    )

    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day)

    rarry_on = st.toggle('rarry', value=True)

    if rarry_on: 
        start_dt = start_dt - timedelta(days=1)

    btn_click = st.button('analysis')
    st.divider()

    if btn_click: 
        if start_dt is not None and end_dt is not None: 
            if start_dt > end_dt: 
                st.warning('start date must be less than date') 
            else: 
                st.session_state.posdb.connect()
                loader = DataLoader(st.session_state.posdb)
                df_1d = loader.make_df(
                    '1d', start_dt, end_dt, 
                    open_time_dt=True, volume=False, ohlc_type='float'                   
                )
                
                graph = GraphLoader()
                report = Report()

                graph.candle_sequence_month(df_1d, '1d', threshold)
                graph.candle_volatility_mixed_sort(df_1d.copy(), threshold, rarry=rarry_on, percent_line='on', sort='no')
                
                graph.candle_volatility_mixed_sort(df_1d.copy(), threshold, sort='low')
                graph.candle_volatility_mixed_sort(df_1d.copy(), threshold, sort='high', percent_line='on')

               
                graph.candle_volatility_mixed_sort(df_1d, threshold, sort='no')
                
                graph.candle_volatility_mixed_sort_one(df_1d.copy(), threshold, sort='no')
                # head / tail ratio 
                st.write('head tail ratio ========')

               
                # rarry threshold
                start_k_dt = start_dt - timedelta(days=1)
                end_k_dt = end_dt 
                df_k_1d = loader.make_df(
                    '1d', start_k_dt, end_k_dt, 
                    open_time_dt = True, volume=False, ohlc_type='float'
                )
                df_k_1d = loader.volatility_transfer_df(df_k_1d, k=0.35)
                df_k_1d.dropna(inplace=True)
                df_k_1d = loader._volatility_way_direction_maker(df_k_1d)
                df_k_1d = loader._volatility_max_profit_pct_maker(df_k_1d)
                result_df, _ = report.way_report(df_k_1d, breakout='rarry')
                st.write('Rarry Breakout Report')
                

                # fixed threshold
                df_1d_origin = loader.make_df(
                    '1d', start_dt, end_dt, 
                    open_time_dt = True, volume=False, ohlc_type='float'                   
                )

                df_1d = loader.transfer_df(df_1d_origin, threshold)
                result_df, _ = report.way_report(df_1d, breakout='fixed')
                st.write('Fixed Breakout Report')
                # st.dataframe(result_df)


                # volatility distribution & histogram
                # month 
                df_1d_month = loader.transfer_df(df_1d_origin, threshold=threshold)
                df_1d_month = loader._volatility_maker(df_1d_month)
                
                graph.make_df_histogram(df_1d_month, bins=10)


                # year
                start_dt_year = datetime(start.year, 1, 1)
                end_dt_year = datetime(start.year, 12, 31)
                df_1d_year = loader.make_df(
                    '1d', start_dt_year, end_dt_year, 
                    open_time_dt=True, volume=False, ohlc_type='float'
                )

                df_1d_year = loader.make_df(
                    '1d', start_dt, end_dt,
                    open_time_dt=True, volume=False, ohlc_type='float'
                )
                df_1d_year = loader.transfer_df(df_1d_year, threshold=threshold)
                df_1d_year = loader._volatility_maker(df_1d_year)
                
                report = Report()
                report.pandl_report(df_1d_year, threshold)
                report.pandl_report(df_1d_year, threshold, times=5)
                report.pandl_report(df_1d_year, threshold, times=10)
                report.max_profit_report(df_1d_year)
               
                graph.make_df_histogram(df_1d_year, bins=50)

                st.session_state.posdb.disconnect() 

        else: 
            st.warning('You should input date')

else: 
    st.warning('postgresql is not readyh to use...')

st.session_state.posdb.connect()

loader = DataLoader(st.session_state.posdb)


#===========
# corelation

df_1d = loader.make_df(
    '1d', datetime(2025, 6, 1), datetime(2025, 11, 30), 
    open_time_dt=True, volume=False, ohlc_type='float'
)

df_1d['volatility'] = df_1d['high'] - df_1d['low']
df_1d['pre_volatility'] = df_1d['volatility'].shift(2)
df_1d = df_1d.dropna()
top_2_indices = df_1d['pre_volatility'].nlargest(10).index
df_1d = df_1d.drop(top_2_indices)



df_1d['volatility_squared'] = df_1d['volatility'] ** 2
df_1d['pre_volatility_squared'] = df_1d['pre_volatility'] ** 2
correlation = df_1d['pre_volatility'].corr(df_1d['volatility'])
correlation = round(correlation, 2)

correlation_two = df_1d['pre_volatility_squared'].corr(df_1d['volatility_squared'])
correlation_two = round(correlation, 2)
# st.dataframe(df_1d)

graph = GraphLoader()
graph.volatility(df_1d)
st.write(f'correlation: {correlation}')
st.write(f'correlation_square: {correlation_two}')

df_1d_one = loader.make_df(
    '1d', datetime(2025,1, 1), datetime(2025,3, 31), 
    open_time_dt=True, volume=False, ohlc_type='float'
)
df_1d_two = loader.make_df(
    '1d', datetime(2025, 7, 1), datetime(2025, 7, 31), 
    open_time_dt=True, volume=False, ohlc_type='float'
)
df_1d_three = loader.make_df(
    '1d', datetime(2025, 1, 1), datetime(2025, 12, 31), 
    open_time_dt=True, volume=False, ohlc_type='float'
)

df_1d_four = loader.make_df(
    '1d', datetime(2024, 1, 1), datetime(2024, 3, 31), 
    open_time_dt=True, volume=False, ohlc_type='float'
)

df_1d_five = loader.make_df(
    '1d', datetime(2023, 1, 1), datetime(2023, 7, 31), 
    open_time_dt=True, volume=False, ohlc_type='float'
)
st.session_state.posdb.disconnect()

graph = GraphLoader()



graph.candle_volatility_mixed_sort(df_1d_one, threshold, sort=True)
graph.candle_volatility_mixed_sort(df_1d_two, threshold, sort=True)

graph.candle_volatility_mixed_sort(df_1d_three, threshold, sort=True)
graph.candle_volatility_mixed_sort(df_1d_four, threshold, sort=True)
graph.candle_volatility_mixed_sort(df_1d_five, threshold, sort=True)