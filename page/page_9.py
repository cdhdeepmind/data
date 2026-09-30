from datetime import datetime, date, timedelta
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)


st.title('Sequence_30m')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready to use')

    col1, col2 = st.columns(2)
    start = col1.date_input('start_date', date(2025, 1, 1))
    end = col2.date_input('end_date', date(2025, 11, 30))
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

    btn_click = st.button('analysis')
    st.divider()

    if btn_click: 
        if start_dt is not None and end_dt is not None: 
            if start_dt > end_dt: 
                st.warning('start date must be less than end date')
            else: 
                # loading 30m dataframe
                st.session_state.posdb.connect()
                loader = DataLoader(st.session_state.posdb)
                df_30m = loader.make_df('30m', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
                st.session_state.posdb.disconnect() 
                # rendering graph 
                graph = GraphLoader()
                df_30m['date'] = df_30m['open_time'].dt.date
                df_30m.groupby('date').apply(lambda g: graph.candle_sequence_month(g, '30m', threshold))
        else: 
            st.warning('You should input date')
       
else: 
    st.write('postgresql is not ready to use...')