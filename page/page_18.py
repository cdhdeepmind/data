from datetime import datetime, date, timedelta, timezone
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, IndicatorBuilder, Report

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)



st.title('Sequence_1h_pct')
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

col1, col2, col3 = st.columns(3)
candle = col1.toggle('candle', value=True)
ma = col2.toggle('ma')
bollinger = col3.toggle('bollinger', value=True)

col1, col2, col3 = st.columns(3)
rarry_line = col1.toggle('rarry_line')
velocity_line = col2.toggle('velocity_line', value=True)
max_profit_line = col3.toggle('mfe_line')

col1, _, _ = st.columns(3)
trigger_line = col1.toggle('trigger_line')
way = st.segmented_control('way', ['all', 'one_way', 'two_way', 'no_way'], default='all')

if way == 'one_way': 
    max_profit = st.segmented_control('max_profit', ['all', '~1%', '1%~2%', '2%~3%', '3%~'], default='all')
st.write('2%: 0.01 <= X < 0.03')
candle_type = st.segmented_control('candle_type', ['all', 'plus', 'minus'], default='all')

st.write(way)
btn_click = st.button('analysis')

# date to make base
start_dt = datetime(start.year, start.month, start.day)
end_dt = datetime(end.year, end.month, end.day)
# date to make indicator 
start_ib_dt = start_dt - timedelta(hours=24)
end_ib_dt = end_dt
# date to make rarry
start_k_dt = start_dt - timedelta(days=1)
end_k_dt = end_dt 

st.write(start_ib_dt, start_k_dt)


st.divider()

if btn_click: 
    if start_dt is not None and end_dt is not None: 
        # make dataframe
        if start_dt > end_dt: 
            st.warning('start date must be less than end date')
        else: 
            st.session_state.posdb.connect()

            loader = DataLoader(st.session_state.posdb)
            ibuilder = IndicatorBuilder()
            graph = GraphLoader()
            df_1h = loader.make_df('1h', start_ib_dt, end_ib_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1h = ibuilder.add_ma7(df_1h)
            df_1h = ibuilder.add_ma20(df_1h)
            df_1h = ibuilder.add_bollinger_bands(df_1h)

            df_1h = df_1h[df_1h['open_time'] >= start_dt]
            #st.dataframe(df_1h)

            df_1h = loader.transfer_pct_df(df_1h, threshold)
            #st.dataframe(df_1h)

            df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1d = loader.transfer_df(df_1d, threshold)
            df_1d['date'] = df_1d['open_time'].dt.date
            df_1d = df_1d[['date', 'type', 'way', 'way_direction', 'mfe', 'mfe_label', 'close_profit']]
            #st.dataframe(df_1d)

            ### segment df_1d by max_profit_pct 
            if way == 'one_way': 
                st.write(f'mfe: {max_profit}')   
              
                if max_profit == '~1%': 
                    df_1d = df_1d[(df_1d['mfe'] > 0) & (df_1d['mfe'] < 0.01)]
                elif max_profit == '1%~2%': 
                    df_1d = df_1d[(df_1d['mfe'] >= 0.01) & (df_1d['mfe'] < 0.02)]
                elif max_profit == '2%~3%': 
                    df_1d = df_1d[(df_1d['mfe'] >= 0.02) & (df_1d['mfe'] < 0.03)]
                elif max_profit == '3%~': 
                    df_1d = df_1d[(df_1d['mfe'] >= 0.03)]
            else: 
                max_profit = False
            
            ### segment type
            if candle_type == 'plus': 
                df_1d = df_1d[df_1d['type'] == 'plus']
            elif candle_type == 'minus': 
                df_1d = df_1d[df_1d['type'] == 'minus']

            ### segment way
            if way == 'one_way': 
                df_1d = df_1d[df_1d['way'] == 'one_way']
            elif way == 'two_way': 
                df_1d = df_1d[df_1d['way'] == 'two_way']
            elif way == 'no_way': 
                df_1d = df_1d[df_1d['way'] == 'no_way'] 

            #st.dataframe(df_1d)

            df_1h = pd.merge(df_1h, df_1d, on='date', how='right')
            st.dataframe(df_1h)
            df_1h.groupby('date').apply(lambda g: graph.candle_sequence_month_pct(g, '1h', threshold, candle, ma, bollinger, velocity_line, max_profit_line, trigger_line))


            st.session_state.posdb.disconnect()

    else: 
        st.warning('You should input date')


