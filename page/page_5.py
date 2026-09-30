from datetime import datetime, date, timedelta, timezone
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, IndicatorBuilder, Report

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)



st.title('Sequence_1h')
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

bollinger = st.toggle('bollinger', value=True)
rarry_line = st.toggle('rarry_line')
max_profit_line = st.toggle('mfe_line')
way = st.segmented_control('way', ['all', 'one_way', 'two_way', 'no_way'], default='all')

if way == 'one_way': 
    max_profit = st.segmented_control('max_profit', ['all', '~1%', '1%~3%', '3%~'], default='all')
st.write('2%: 0.01 <= X < 0.03')
candle_type = st.segmented_control('candle_type', ['all', 'plus', 'minus'], default='all')
st.write(way)
btn_click = st.button('analysis')

start_dt = datetime(start.year, start.month, start.day)
end_dt = datetime(end.year, end.month, end.day)
start_ib_dt = start_dt - timedelta(hours=24)
end_ib_dt = end_dt
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
            df_1h = loader.make_df('1h', start_ib_dt, end_ib_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1h = ibuilder.add_ma7(df_1h)
            df_1h = ibuilder.add_ma20(df_1h)

            if bollinger: 
                df_1h = ibuilder.add_bollinger_bands(df_1h)
          
            df_1h = df_1h[df_1h['open_time'] >= start_dt]
            df_1h['date'] = df_1h['open_time'].dt.date
            st.dataframe(df_1h)

            if rarry_line: 
                df_k_1d = loader.make_df(
                    '1d', start_k_dt, end_k_dt, 
                    open_time_dt = True, volume=False, ohlc_type='float'
                )
                df_k_1d = loader.volatility_transfer_df(df_k_1d, k=0.35)
                df_k_1d.dropna(inplace=True)
                df_k_1d['date'] = df_k_1d['open_time'].dt.date
                df_k_1d = df_k_1d[['date', 'k_threshold']]
                df_1h = pd.merge(df_1h, df_k_1d, on='date', how='left')
                st.write('rarry_line')
                st.dataframe(df_1h)

                pass 

            # df_1h 에 컬럼 추가 (prev_open, prev_high, prev_low, prev_type)
            df_1d = loader.make_df('1d', start_ib_dt, end_ib_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1d = loader.transfer_df(df_1d, threshold)

            df_1d['prev_open'] = df_1d['open'].shift(1)
            df_1d['prev_high'] = df_1d['high'].shift(1)
            df_1d['prev_low'] = df_1d['low'].shift(1)
            df_1d['prev_type'] = df_1d['type'].shift(1)
            df_1d = df_1d[df_1d['open_time'] >= start_dt]
            df_1d['date'] = df_1d['open_time'].dt.date
            df_1d_prev = df_1d[['date','prev_open', 'prev_high', 'prev_low', 'prev_type']]


            # 원웨이 투웨이 비율 분석 
            df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1d = loader.transfer_df(df_1d, threshold)
            # df_15m = loader.make_df('15m', start, end, open_time_dt=True, volume=False, ohlc_type='float')

            # analysis report
            analyzer = DataAnalyzer()
            
            st.write('way report')
            analyzer.report_way(df_1d)

            # to add 
            st.write('1. 분석하는 달 + 이전 한달의 1d sequence')
            st.write('2. 볼린저 밴드')
            st.write('3. rsi')

            ### rendering graph ###
            graph = GraphLoader()
            df_1h['date'] = df_1h['open_time'].dt.date

            df_1d['date'] = df_1d['open_time'].dt.date
            df_1d = df_1d[['date', 'type', 'way', 'mfe', 'mfe_label', 'close_profit']]
            

            ### segment df_1d by max_profit_pct 
            if way == 'one_way': 
                st.write(f'mfe: {max_profit}')   
              
                if max_profit == '~1%': 
                    df_1d = df_1d[(df_1d['mfe'] > 0) & (df_1d['mfe'] < 0.01)]
                elif max_profit == '1%~3%': 
                    df_1d = df_1d[(df_1d['mfe'] >= 0.01) & (df_1d['mfe'] <= 0.03)]
                elif max_profit == '3%~': 
                    df_1d = df_1d[(df_1d['mfe'] > 0.03)]

            else: 
                max_profit = False
            
            st.write('segmented')
            # st.dataframe(df_1d)
            report = Report()
            report.close_profit_report(df_1d)


            df_1h = pd.merge(df_1h, df_1d, on='date', how='right')
            st.write('last df_1h')
            # st.dataframe(df_1h)

            if candle_type == 'plus': 
                df_1h = df_1h[df_1h['type'] == 'plus']
            elif candle_type == 'minus': 
                df_1h = df_1h[df_1h['type'] == 'minus']

            if way == 'one_way': 
                df_1h = df_1h[df_1h['way'] == 'one_way']
            elif way == 'two_way': 
                df_1h = df_1h[df_1h['way'] == 'two_way']
            elif way == 'no_way': 
                df_1h = df_1h[df_1h['way'] == 'no_way'] 
            # df_1h, df_1d_prev merge
            # result_df = df_1h.merge(df_1d_prev, on='date', how='left')
          
            # st.dataframe(result_df)

            df_1h.groupby('date').apply(lambda g: graph.candle_sequence_month(g, '1h', threshold, max_profit, max_profit_line, rarry_line, bollinger, indicator='ma'))

            st.session_state.posdb.disconnect()

    else: 
        st.warning('You should input date')





    

    