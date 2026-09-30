from data_collector_psql import PostgresHandler, DataCollector, Utility
from datetime import datetime

import streamlit as st 
import pandas as pd 
import time


### utils function ###

utils = Utility()

def make_df_from_update_info(data): 
    data = [
        (
            item[0], 
            utils.make_dt_from_millis(item[1]), 
            utils.make_dt_from_millis(item[2])
        ) 
        for item in data
    ]
  
    df = pd.DataFrame(data, columns=['interval', 'last_millis', 'start_millis'])
    return df




### header code ###

st.title('Data Collector')







### main code ####

if 'df' not in st.session_state:
    # load update_info data
    st.session_state.posdb.connect()

    data = st.session_state.posdb.get_update_info()
    st.session_state.df = make_df_from_update_info(data)

    st.session_state.posdb.disconnect()

df_container = st.empty()
df_container.dataframe(st.session_state.df)

date = st.date_input('end_time')
end_dt = datetime(date.year, date.month, date.day)
end_utc_dt = utils.make_utc_dt(end_dt)

if st.button('start'): 
    st.session_state.posdb.connect()
        
    collector = DataCollector(st.session_state.posdb)
    
    progress_end = st.empty()
    
    for interval in collector.run_all_iter(end_utc_dt): 
        data = st.session_state.posdb.get_update_info()
        st.session_state.df = make_df_from_update_info(data) 
        df_container.dataframe(st.session_state.df)
        progress_end.write(f'{interval} complete ✅ !')
    
    progress_end.empty()
    
    st.session_state.posdb.disconnect()
