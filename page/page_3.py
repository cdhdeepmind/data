from data_collector_psql import DataLoader, GraphLoader
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Span


import streamlit as st
import importlib



st.title('Test page')


########## session initializing ##########
if st.session_state.posdb:
    st.write('postgresql is ready to use') 

    loader = DataLoader(st.session_state.posdb)
    graph = GraphLoader()

    if not st.session_state.source_df.empty: 
        df = loader.transfer_df(st.session_state.source_df, threshold=1.9)
        st.dataframe(df)
        profit_arr = loader.calculate_profit_dist(df, threshold=1, times=20)
        st.write(len(profit_arr))
        print(profit_arr)
        graph.make_histogram(profit_arr)
        
        

     




