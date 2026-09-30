from datetime import datetime, date, timedelta

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, DataFrameTransformer

st.title('Sequence_15m')
st.divider()


if st.session_state.posdb: 
    st.write('postgresql is ready to use')

    # -> transform to st.element
    col1, col2 = st.columns(2)
    start = col1.date_input('start_date', date(2024, 1, 1))
    end = col2.date_input('end_date', date(2024, 1, 31))
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
    
    atr_line = st.toggle('atr_line', value=True)
    btn_click = st.button('analysis')

    if atr_line: 
        start_dt = start_dt - timedelta(hours=3, minutes=15)
        st.write(start_dt)
    st.divider()

    if btn_click: 
        if start_dt is not None and end_dt is not None: 
            if start_dt > end_dt: 
                st.warning('start date must be less than end date')
            else: 
                # loading 15m dataframe
                st.session_state.posdb.connect()
                loader = DataLoader(st.session_state.posdb)
                transformer = DataFrameTransformer()
                df_15m = loader.make_df('15m', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
                df_15m = transformer.make_atr(df_15m)
                st.dataframe(df_15m)
                st.session_state.posdb.disconnect()
                # rendering graph 
                graph = GraphLoader()
                df_15m['date'] = df_15m['open_time'].dt.date
                df_15m.groupby('date').apply(lambda g: graph.candle_sequence_15m(g, '15m', threshold, atr_line=atr_line))
        else: 
            st.warning('You should input date')

else: 
    st.warning('postgresql is not ready to use...')
    
    
    
    
    
    
