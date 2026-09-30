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

st.title('Sequence_6h')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready!')

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
    max_profit = st.segmented_control('max_profit', ['all', '1%', '2%', '3%'], default='all')
    candle_type = st.segmented_control('candle_type', ['all','plus', 'minus'], default='all')
    btn_click = st.button('analysis')

    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day)

    st.divider()

    if btn_click:  
        if start_dt is not None and end_dt is not None: 
            if start_dt > end_dt: 
                st.warning('start date must be less than end date')
            else: 
                st.session_state.posdb.connect()
                loader = DataLoader(st.session_state.posdb)
                df_6h = loader.make_df('6h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
                df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
                df_1d = loader.transfer_df(df_1d, threshold)
                
                st.session_state.posdb.disconnect() 

                transformer = DataFrameTransformer()
                df_6h = transformer.make_date(df_6h)
                df_6h = transformer.make_ohlc_pct(df_6h, '6h')
                #st.dataframe(df_6h)
                #st.dataframe(df_6h.head())

                # Filter the dataframe by MFE
                if max_profit == '1%': 
                    df_1d = df_1d[(df_1d['max_profit_pct'] > 0) & (df_1d['max_profit_pct'] < 0.01)]
                elif max_profit == '2%': 
                    df_1d = df_1d[(df_1d['max_profit_pct'] >= 0.01) & (df_1d['max_profit_pct'] < 0.02)]
                elif max_profit == '3%': 
                    df_1d = df_1d[(df_1d['max_profit_pct'] >= 0.02)]


                if candle_type == 'plus': 
                    df_1d = df_1d[(df_1d['type'] == 'plus')]
                elif candle_type == 'minus': 
                    df_1d = df_1d[(df_1d['type'] == 'minus')]
                
                
                
                df_1d['date'] = df_1d['open_time'].dt.date
                st.dataframe(df_1d)
                df_1d = df_1d[['date', 'max_profit_pct']]
                st.dataframe(df_1d)
                df_6h['date'] = df_6h['open_time'].dt.date

                df_6h = pd.merge(df_6h, df_1d, on='date', how='right')
                st.dataframe(df_6h)
                

                chunk_size = 32
                groups = [df_6h.iloc[i:i+chunk_size] for i in range(0, len(df_6h), chunk_size)]

                graph = GraphLoader()

                for i in range(0, len(groups), 2): 
                    start = groups[i].iloc[0]['open_time']
                    if len(groups) % 2 == 0: 
                        end = groups[i+1].iloc[-1]['open_time']
                    else: 
                        end = groups[i].iloc[-1]['open_time']
                    df_6h_sub = df_6h[(df_6h['open_time'] >= start) & (df_6h['open_time'] <= end)]
                    st.write(start,end)
                    
                    graph.candle_sequence_6h(df_6h_sub)

                    
                    for df in groups[i:i+2]:
                        if max_profit == 'all': 
                            graph.candle_sequence_pct(df, threshold)
                        else: 
                            st.write('else +++++')
                            df['time_str'] = df['open_time'].dt.strftime("%Y-%m-%d %H:%M")
                            graph.candle_sequence_str_pct(df, threshold)

        else: 
            st.warning('You should input date')

else: 
    st.warning('postgresql is not ready')

