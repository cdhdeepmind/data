import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

from datetime import datetime, date, timedelta, timezone
from data_collector_psql import (
    DataLoader, DataAnalyzer, PreProcessor, PullbackAnalyzer, Report, 
    GraphLoader, DataFrameTransformer, IndicatorBuilder
    )

importlib.reload(data_collector_psql)

st.title('pattern_test')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready!')

    col1, col2 = st.columns(2)
    start = col1.date_input('start_date', date(2025, 1, 1))
    end = col2.date_input('end_date', date(2025, 6, 30))
    threshold = st.number_input(
        'threshold', 
        min_value = 0.004, 
        max_value = 0.021, 
        step = 0.001, 
        format = '%.3f', 
        value = 0.012
    )

    btn_click = st.button('analysis')

    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day)

    st.divider()

    if btn_click: 
        if start_dt is not None and end_dt is not None: 
            if start_dt > end_dt: 
                st.warning('start date must be less than end date')
            else: 
                pass 
        else: 
            st.warning('You should input date')
    
else: 
    st.warning('postgresql is not ready')