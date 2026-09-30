from datetime import datetime, date, timedelta, timezone
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, IndicatorBuilder, Report

import time

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)



st.title('Improving_return')
st.divider()


if st.session_state.posdb: 
    st.write('postgresql is ready to use')

col1, col2 = st.columns(2)
start = col1.date_input('start_date', date(2026, 1, 1))
end = col2.date_input('end_date', date(2026, 1, 31))
threshold = st.number_input(
'threshold',
min_value = 0.004, 
max_value = 0.021, 
step = 0.001, 
format = '%.3f',
value = 0.012
)  

btn_click = st.button('analysis')

# date to make base
start_dt = datetime(start.year, start.month, start.day)
end_dt = datetime(end.year, end.month, end.day)

# @st.cache_data()
def get_adr_summary(_loader, _indicator, threshold): 
    start_cache_dt = datetime(2024, 12, 21)
    ene_cache_dt = datetime(2025, 12, 1)
    df_1d_cache = _loader.make_df('1d', start_cache_dt, ene_cache_dt, open_time_dt=True, volume=False, ohlc_type='float')
    df_1d_cache = _loader.transfer_df(df_1d_cache, threshold)
    df_1d_cache = _indicator.add_adr(df_1d_cache)
    df_1d_cache = _indicator.add_madr(df_1d_cache, period=1)
    df_1d_cache = _indicator.add_madr(df_1d_cache, period=2)
    df_1d_cache = _indicator.add_madr(df_1d_cache, period=3)
    df_1d_cache = _indicator.add_madr(df_1d_cache, period=4)
    df_1d_cache = _indicator.add_madr(df_1d_cache, period=5)
    df = df_1d_cache.loc[df_1d_cache['open_time'] >= datetime(2025, 1, 1)].copy()
    return df

if btn_click: 
    if start_dt is not None and end_dt is not None: 
        if start_dt > end_dt: 
            st.warning('start date must be less than end date')
        else: 
            st.session_state.posdb.connect()

            loader = DataLoader(st.session_state.posdb)
            indicator = IndicatorBuilder()

            df_1d_cache = get_adr_summary(_loader=loader, _indicator=indicator, threshold=threshold)
            st.dataframe(df_1d_cache)

            report = Report()
            _, sr = report.adr_report(df_1d_cache)
            st.dataframe(sr)
            arr = sr.to_numpy() * 100

            graph = GraphLoader()
            graph.make_histogram(arr, 8)

            df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1d = loader.transfer_df(df_1d, threshold)
            df_1h = loader.make_df('1h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1h = loader.transfer_pct_df(df_1h, threshold, indicator=False)
        
            df_trans_1d = df_1d[['date', 'way', 'way_direction']]
            df_trans_1d = df_trans_1d[(df_1d['way'] == 'one_way')]

            df_1h = pd.merge(df_1h, df_trans_1d, on='date', how='right')
            # filter one_way

            # It needs to be implemented as a method within the data_collector module later

            def inner(group, threshold): 
                threshold = threshold * 100
                date = group.iat[0, 5]
                way_direction = group.iat[0, 11]
        
                if way_direction == 'high': 
                    cross = (group['high_pct'] >= threshold) & (group['low_pct'] <= threshold)
                    first_cross_time = cross.values.argmax()
                    
                elif way_direction == 'low': 
                    cross = (group['high_pct'] >= -threshold) & (group['low_pct'] <= -threshold)
                    first_cross_time = cross.values.argmax()
            
                return pd.DataFrame({
                    'date': [date], 
                    'fct': [first_cross_time] 
                })

            result = df_1h.groupby('date', group_keys=False).apply(inner, threshold=threshold)

            df_1d_merged = pd.merge(df_1d, result, on='date', how='left').fillna(-1)

            report = Report()
            graph = GraphLoader()


            _, two_way = report.way_report(df_1d, 'fixed')

            two_way_profit = (1 - threshold * 10) ** two_way
            two_way_profit = round(two_way_profit, 2)
            st.write('two_way_profit: ', str(two_way_profit))

            df_1d = report.pandl_report(df_1d_merged, threshold, times=10)
            report.mfe_report(df_1d)
            
            graph.cumprofit_line_graph(df_1d)
            st.dataframe(df_1d)

            # @st.fragment
            def backtest_section(): 
                if st.button('backtest'): 
                    time.sleep(10)
                    st.write('section complete')
            
            backtest_section()







import streamlit as st
import pandas as pd
import numpy as np
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, Range1d
from bokeh.palettes import Spectral4

# 1. 페이지 설정

st.subheader("BTC Breakout Trajectory: Ghost Chart Analysis")
st.write("진입 시점을 $T=0$으로 정규화하여 MFE 그룹별 가격 궤적을 비교합니다.")

# 2. 가상 데이터 생성 (실제 사용 시에는 DB에서 로드)
@st.cache_data
def load_mock_data():
    num_trades = 50
    steps = 25  # 15분봉 24개 + 진입직후
    data_list = []
    
    for i in range(num_trades):
        # 23% 확률로 성공(Label 1), 77% 확률로 실패(Label 0) 시뮬레이션
        is_success = np.random.random() < 0.3
        mfe_label = "Target_3%" if is_success else "Fail_1%"
        
        # 궤적 생성
        volatility = 0.2
        drift = 0.15 if is_success else -0.05
        returns = np.cumsum(np.random.normal(drift, volatility, steps))
        returns[0] = 0  # T=0 시점은 수익률 0%
        
        for t, ret in enumerate(returns):
            data_list.append({
                'trade_id': f'Trade_{i}',
                'time_step': t,
                'return_pct': ret,
                'label': mfe_label
            })
            
    return pd.DataFrame(data_list)

df = load_mock_data()

# 3. 사이드바 필터
st.sidebar.header("Filter Settings")
selected_labels = st.sidebar.multiselect(
    "MFE Group 선택", ["Fail_1%", "Target_3%"], default=["Fail_1%", "Target_3%"]
)

# 4. Bokeh 차트 생성
def create_ghost_chart(data, labels):
    # 차트 기본 설정
    p = figure(
        title="Price Trajectory After Breakout",
        x_axis_label="Time Steps (After Entry)",
        y_axis_label="Return (%)",
        plot_height=600,
        tools="pan,wheel_zoom,box_zoom,reset,save"
    )

    # 기준선 (0% 라인 및 손절/익절 마일스톤)
    # p.add_layout(Range1d(-2, 5))
    p.line([0, 24], [0, 0], line_dash="dashed", line_color="gray", alpha=0.5) # 본절선
    p.line([0, 24], [1, 1], line_dash="dotted", line_color="orange", legend_label="MFE 1% Line")

    # 그룹별 색상 매핑
    colors = {"Fail_1%": "red", "Target_3%": "dodgerblue"}
    st.write(labels)
    for label in labels:
        group_df = data[data['label'] == label]
        trade_ids = group_df['trade_id'].unique()
        
        # 개별 트레이드 경로 그리기 (고스트 선)
        for tid in trade_ids:
            single_trade = group_df[group_df['trade_id'] == tid]
            source = ColumnDataSource(single_trade)
            p.line(
                x='time_step', y='return_pct', source=source,
                line_width=1, line_alpha=0.2, color=colors[label]
            )

        # 그룹 평균선 (분리력을 확인하는 핵심 선)
        mean_path = group_df.groupby('time_step')['return_pct'].mean().reset_index()
        p.line(
            mean_path['time_step'], mean_path['return_pct'],
            line_width=4, color=colors[label], legend_label=f"Mean {label}"
        )

    # 툴팁 설정
    hover = HoverTool(tooltips=[
        ("Trade ID", "@trade_id"),
        ("Step", "@time_step"),
        ("Return", "@return_pct{0.00}%")
    ])
    p.add_tools(hover)
    
    p.legend.location = "top_left"
    p.legend.click_policy = "hide" # 레전드 클릭 시 해당 그룹 숨기기
    
    return p

# 5. 차트 출력
st.dataframe(df)
filtered_df = df[df['label'].isin(selected_labels)]
bokeh_p = create_ghost_chart(filtered_df, selected_labels)
st.bokeh_chart(bokeh_p, use_container_width=True)

# 6. 통계 요약 (하단)
st.subheader("Statistical Separation")
col1, col2 = st.columns(2)

with col1:
    st.write("**진입 1시간(4 Step) 후 평균 수익률**")
    step_4_stats = df[df['time_step'] == 4].groupby('label')['return_pct'].mean()
    st.dataframe(step_4_stats)

with col2:
    st.write("**그룹별 변동성 (표준편차)**")
    std_stats = df.groupby('label')['return_pct'].std()
    st.dataframe(std_stats)
