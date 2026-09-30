from datetime import datetime, date, timedelta, timezone
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, IndicatorBuilder, Report
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, Range1d
from bokeh.palettes import Spectral4

import time

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)

st.title('test page')
st.divider()


if st.session_state.posdb: 
    st.write('postgresql is ready to use')

start_dt = datetime(2025, 1, 1)
end_dt = datetime(2025, 12, 31)
threshold = 0.012

st.session_state.posdb.connect()

loader = DataLoader(st.session_state.posdb)
df_1h = loader.make_df('1h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1h = loader.transfer_pct_df(df_1h, threshold, indicator=False)
df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1d = loader.transfer_df(df_1d, threshold)
df_1d = df_1d[['date', 'type', 'way', 'way_direction', 'mfe', 'mfe_label']]

df_1h = pd.merge(df_1h, df_1d, on='date', how='left')

st.session_state.posdb.disconnect()



@st.cache_data
def prepare_ghost_data(df_1h, entry_signals, steps=24): 
    ghost_data_list = []

    for i, entry in enumerate(entry_signals): 
        entry_idx = entry[0]
        up_entry_prc = entry[2]
        down_entry_prc = entry[3]
        end_idx = entry_idx + steps + 1
        entry_ridx = entry[4]

        if end_idx > len(df_1h): 
            continue
        
        traj_df = df_1h.iloc[entry_idx:end_idx].copy()
        
        way_direction = traj_df.iat[0, 12]

        traj_df['time_step'] = range(len(traj_df))
        if way_direction == 'low': 
            traj_df['return_pct'] = (1 - traj_df['close'] / down_entry_prc) * 100
        elif way_direction == 'high':
            traj_df['return_pct'] = (traj_df['close'] / up_entry_prc -1) * 100
    
        traj_df['return_pct'].iloc[0] = 0
        
        
        mfe_label = traj_df.iat[0, 14]


        for _, row in traj_df.iterrows(): 
            ghost_data_list.append({
                'trade_id': f'Trade_{i}', 
                'time_stamp': row['open_time'],
                'time_step': row['time_step'], 
                'return_pct': row['return_pct'], 
                'label': mfe_label, 
                'entry_idx': entry_ridx
            })

    return pd.DataFrame(ghost_data_list) 


@st.cache_data
def find_breakout_signals(df_1h, threshold=0.012):
    entry_dices = []

    for date in df_1h['date'].unique(): 
        df_day = df_1h[df_1h['date'] == date]
        open_prc = round(df_day.iat[0, 1], 1)
        up_threshold_prc = round(open_prc * (1 + threshold), 1)
        down_threshold_prc = round(open_prc * (1 - threshold), 1)
        way = df_day.iat[0, 11]
        way_direction = df_day.iat[0, 12]
        # st.write(date)
        # st.dataframe(df_day)
        if way == "one_way": 
            if way_direction == 'high': 
                condition = (df_day['high_pct'] >= threshold*100) & (df_day['low_pct'] <= threshold*100)
                df_cross = df_day[condition]
                # st.dataframe(df_cross)
                first_cross_idx = df_cross.index[0]
                first_cross_ridx = condition.to_numpy().argmax()
                cross_time = df_cross.iat[0, 0]
            elif way_direction == 'low': 
                condition = (df_day['high_pct'] >= -threshold*100) & (df_day['low_pct'] <= -threshold*100)
                df_cross = df_day[condition]
                first_cross_idx = df_cross.index[0] 
                first_cross_ridx = condition.to_numpy().argmax()
                cross_time = df_cross.index[0]
                # st.dataframe(df_cross)
        else: 
            continue

        entry_dices.append((first_cross_idx, cross_time, up_threshold_prc, down_threshold_prc, first_cross_ridx))
    # st.dataframe(entry_dices)

    return entry_dices




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
    colors = {0: "red", 1: "dodgerblue", 2: 'green', 3: 'purple'}
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
                line_width=1, line_alpha=0.1, color=colors[label]
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
        ("Return", "@return_pct{0.00}%"), 
        ("Entry_ridx", "@entry_idx")
    ])

    p.y_range = Range1d(start=-5, end=15)

    p.add_tools(hover)
    
    p.legend.location = "top_left"
    p.legend.click_policy = "hide" # 레전드 클릭 시 해당 그룹 숨기기
    
    return p



entry_arr = find_breakout_signals(df_1h, threshold)
df = prepare_ghost_data(df_1h, entry_arr, steps=24)

st.dataframe(df)

st.sidebar.header("Filter Settings")
selected_labels = st.sidebar.multiselect(
    "MFE Group 선택", [0, 1, 2, 3], default=[0, 1]
)

filtered_df = df[df['label'].isin(selected_labels)]
bokeh_p = create_ghost_chart(filtered_df, selected_labels)
st.bokeh_chart(bokeh_p, use_container_width=True)