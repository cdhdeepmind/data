import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

from datetime import datetime, date
from data_collector_psql import (
    DataLoader, DataAnalyzer, PreProcessor, 
    PullbackAnalyzer, Report, GraphLoader, DataFrameTransformer, 
    IndicatorBuilder
    )

importlib.reload(data_collector_psql)

st.title('Sequence_12h')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready!')

    col1, col2 = st.columns(2)
    start = col1.date_input('start_date', date(2025, 1, 1))
    end = col2.date_input('end_date', date(2025, 1, 31))
    threshold = st.number_input(
        'threshold', 
        min_value = 0.007, 
        max_value = 0.021, 
        step = 0.001, 
        format = '%.3f', 
        value = 0.012
    )

    way = st.segmented_control('way', ['all', 'one_way', 'two_way', 'no_way'], default='all')
    candle_type = st.segmented_control('candle_type', ['all', 'plus', 'minus'], default='all')
    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day)

    btn_click = st.button('analysis')
    st.divider()

    if btn_click: 
        if start_dt is not None and end_dt is not None: 
            if start_dt > end_dt: 
                st.warning('start date must be less than end date')
            else: 
                st.session_state.posdb.connect()
                loader = DataLoader(st.session_state.posdb)
                df_12h = loader.make_df('12h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
                
                # transform dataframe 
                transformer = DataFrameTransformer()
                df_12h = transformer.make_close_type(df_12h)
                df_12h['date'] = df_12h['open_time'].dt.date
                df_12h = transformer.make_ohlc_pct(df_12h, '12h')

                # make way from 1d and merge 12h, 1d 
                df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float') 
                df_1d = transformer.make_date(df_1d)
                df_1d = transformer.make_close_type(df_1d)
                df_1d = transformer.make_ohlc_pct(df_1d, interval='1d')
                df_1d = transformer.make_way(df_1d, threshold)
                df_1d = df_1d[['date', 'way', 'close_type']]
                st.write('1d')
                st.dataframe(df_1d)

                if candle_type == 'plus': 
                    df_1d = df_1d[df_1d['close_type'] == 'p']
                elif candle_type == 'minus': 
                    df_1d = df_1d[df_1d['close_type'] == 'm']

                st.write(df_1d)

                if way == 'one_way': 
                    df_1d = df_1d[df_1d['way'] == 'one_way']
                elif way == 'two_way': 
                    df_1d = df_1d[df_1d['way'] == 'two_way']        
                elif way == 'no_way': 
                    df_1d = df_1d [df_1d['way'] == 'no_way']            

                df_12h = pd.merge(df_12h, df_1d, on='date', how='right' )
                # mm_days = df_12h.groupby('date').filter(lambda x: list(x['close_type']) == ['m', 'm'])
                        
                st.dataframe(df_12h)
                graph = GraphLoader()
                graph.candle_sequence_pct(df_12h, threshold)
                st.dataframe(df_12h)

                st.session_state.posdb.disconnect()


        else: 
            st.warning('You should input date') 

else: 
    st.warning('postgresql is not ready to use ...')