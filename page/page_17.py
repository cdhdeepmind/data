from data_collector_psql import PostgresHandler, DataCollector, Utility, DataLoader, GraphLoader, PreProcessor, DataFrameTransformer, Report
from datetime import datetime, date, timedelta

import streamlit as st 
import pandas as pd 
import importlib
import time
import data_collector_psql 

importlib.reload(data_collector_psql)

st.title('mfe distribution')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready to use')

    st.session_state.posdb.connect()



    st.sesssion_state.posdb.disconnect()