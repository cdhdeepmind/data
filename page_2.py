from bokeh.plotting import figure 
from bokeh.io import curdoc
from bokeh.models import BoxAnnotation
from bokeh.models import DatetimeTicker, SingleIntervalTicker
from datetime import datetime, date, timedelta

from data_collector_psql import DataCollector, DataLoader, DataAnalyzer, GraphLoader

import streamlit as st
import time
import pandas as pd
import numpy as np
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)

if 'year_df' not in st.session_state: 
    st.session_state.year_df = None 

if 'year_df_graph' not in st.session_state: 
    st.session_state.year_df_graph = None

if 'first' not in st.session_state: 
    st.session_state.first = None 


st.title('threshold analysis')
st.divider()

if st.session_state.posdb:
    st.write('postgresql instance is ready to use') 

########## main process ##########

start = st.date_input('start', date(2024, 11, 1))
end = st.date_input('end', date(2024, 11, 30))

start_dt = datetime(start.year, start.month, start.day)
end_dt = datetime(end.year, end.month, end.day)
threshold = st.number_input(
    'threshold',
    min_value = 0.005, 
    max_value = 0.021, 
    step = 0.001, 
    format = '%.3f'
    )

btn_click = st.button('analysis')

if btn_click: 
    if start_dt is not None and end_dt is not None: 
        # make dataframe and store to session 
        if start_dt > end_dt: 
            st.warning('start date must be less than end date')
        else: 
            st.session_state.posdb.connect()

            with st.spinner('Data analysing ...'): 
                loader = DataLoader(st.session_state.posdb)
                df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=True, ohlc_type='float')
                df_1d = loader.transfer_df(df_1d, threshold=threshold)
             
                total = len(df_1d)
                no_way = (df_1d['way'] == 'no_way').sum()
                one_way = (df_1d['way'] == 'one_way').sum()
                two_way = (df_1d['way'] == 'two_way').sum()

                total_in = one_way + two_way

                no_way_pct = round(no_way/total * 100, 2)
                one_way_pct = round(one_way/total * 100, 2)
                two_way_pct = round(two_way/total * 100, 2)

                in_one_way_pct = round(one_way/total_in * 100, 2)
                in_two_way_pct = round(two_way/total_in * 100, 2)
          
                data = {
                    'no_way': [no_way, f'{no_way_pct}%', f'#'], 
                    'one_way': [one_way, f'{one_way_pct}%', f'{in_one_way_pct}%'],
                    'two_way': [two_way, f'{two_way_pct}%', f'{in_two_way_pct}%']
                }

                analysis_df = pd.DataFrame(data=data)
                st.dataframe(analysis_df)

                # Calculate monthly statistics for one_way and two_way 
                start_dt = datetime(start.year, 1, 1)
                end_dt = datetime(start.year, 12, 31)
                df_year_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=True, ohlc_type='float')
                df_year_1d = loader.transfer_df(df_year_1d, threshold=threshold)
                df_year_1d['month'] = df_year_1d['open_time'].dt.month

                st.write(start_dt, end_dt)
                
                def way_report(group): 
                    total = len(group)
                    no_way = (group['way'] == 'no_way').sum()
                    one_way = (group['way'] == 'one_way').sum()
                    two_way = (group['way'] == 'two_way').sum()

                    total_in = one_way + two_way

                    no_way_pct = round(no_way/total * 100, 2)
                    one_way_pct = round(one_way/total * 100, 2)
                    two_way_pct = round(two_way/total * 100, 2)
                    one_way_in_pct = round(one_way/total_in * 100, 2)
                    two_way_in_pct = round(two_way/total_in * 100, 2)

                    data = {
                        'one_way': one_way_pct, 
                        'two_way': two_way_pct, 
                        'no_way': no_way_pct, 
                        'one_way_in': one_way_in_pct,
                        'two_way_in': two_way_in_pct
                    }

                    return pd.Series(data)

                
                result = df_year_1d.groupby('month').apply(way_report)
                st.dataframe(result)

                corr = result['one_way'].corr(result['no_way'])
                corr = round(corr, 2)
                st.write(f'correlation: {corr}')
                stats = result['one_way'].agg(['mean', 'std', 'min', 'max'])
                st.dataframe(stats)
                stats = result['two_way'].agg(['mean', 'std', 'min', 'max'])
                st.dataframe(stats)

            st.session_state.posdb.disconnect()
                
    else: 
        st.warning('You shoud input date')
        pass



###### threshold analysis ######
st.divider()

# if st.session_state.year_df is None or st.session_state.year_df_graph is None:
if st.session_state.first is None: 
    st.write('first session')
    st.session_state.posdb.connect()    

    start = date
    start_dt = datetime(2020, 1, 1)
    end_dt = datetime(2025, 12, 31)

    st.write(start_dt)
    st.write(end_dt)

    loader = DataLoader(st.session_state.posdb)
    analyzer = DataAnalyzer()
    df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
    df_1d['year'] = df_1d['open_time'].dt.year
    result = df_1d.groupby('year').apply(lambda g: analyzer.report(g, loader))
    result.reset_index(level=1, drop=True, inplace=True)

    result_two = df_1d.groupby('year').apply(lambda g: analyzer.report(g, loader, way_type='one'))
    result_two.reset_index(level=1, drop=True, inplace=True)

    st.session_state.year_df = result 
    st.session_state.year_df_graph = result_two

    st.session_state.first = 'seconds'

    st.session_state.posdb.disconnect()

st.write(st.session_state.year_df)
st.write(st.session_state.year_df_graph)

one_df = st.session_state.year_df_graph

st.divider()
graph = GraphLoader()
graph.threshold_sequence(one_df)





