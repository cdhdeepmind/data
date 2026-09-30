import pandas as pd 
import numpy as np 
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource, HoverTool, LinearColorMapper
from bokeh.layouts import gridplot
import streamlit as st


class ExcursionAnalyzer: 

    @staticmethod
    def analyze_mae_mfe(df, threshold=0.012): 
        # df: 15m dataframe (open_time, open, high, low, close)
        df['date'] = df['open_time'].dt.date
        results = []
        dates = df['date'].unique()

        for i in range(1, len(dates)): 
            prev_close = df[df['date'] == dates[i-1]]['close'].iloc[-1]
            current_day_data = df[df['date'] == dates[i]].copy()

            upper_threshold = prev_close * (1 + threshold)
            lower_threshold = prev_close * (1 - threshold)

            entry_price, position, entry_idx = 0, None, None 

            for idx, row in current_day_data.iterrows(): 
                if (row['high'] >= upper_threshold) and (row['low'] <= lower_threshold):
                    position = 'two_way'
                elif row['high'] >= upper_threshold: 
                    entry_price, position, entry_idx = upper_threshold, 'long', idx
                    break
                elif row['low'] <= lower_threshold: 
                    entry_price, position, entry_idx = lower_threshold, 'short', idx
                    break

            if position: 
                after_entry = current_day_data.loc[entry_idx:]
                max_high = after_entry['high'].max()
                min_low = after_entry['low'].min()

                if position == 'long': 
                    mfe = (max_high - entry_price) / entry_price * 100
                    mae = (entry_price - min_low) / entry_price * 100
                elif position == 'short': 
                    mfe = (entry_price - min_low) / entry_price * 100
                    mae = (max_high - entry_price) / entry_price * 100
                elif position == 'two_way': 
                    mfe = 0 
                    mae = 0 

                exit_price = current_day_data['close'].iloc[-1]
                pnl = (exit_price - entry_price) / entry_price * 100 if position == 'long' else (entry_price - exit_price) / entry_price * 100

                results.append({
                    'date': dates[i], 
                    'mae': round(mae, 2), 
                    'mfe': round(mfe, 2), 
                    'pnl': round(pnl, 2), 
                    'position': position
                })

        return pd.DataFrame(results)


    @staticmethod    
    def plot_mae_mfe_bokeh(res_df):
        source = ColumnDataSource(res_df)
        
        # 1. MAE vs MFE 산점도
        p = figure(
                title="MAE vs MFE Correlation (Bitcoin Intraday)", 
                x_axis_label='MAE (%)', y_axis_label='MFE (%)',
                sizing_mode='stretch_width', plot_height=350,
                toolbar_location = None,
                tools="pan,box_zoom,reset,save"
            )

        # 데이터 포인트 그리기 (수익 여부에 따라 색상 구분 가능)
        p.circle('mae', 'mfe', size=6, source=source, alpha=0.6, 
                color="navy", hover_color="red")

        # 툴팁 추가
        hover = HoverTool(
            tooltips=[
                ("Date", "@date{%F}"),
                ("Position", "@position"),
                ("MAE", "@mae%"),
                ("MFE", "@mfe%"),
                ("PnL", "@pnl%")
            ], 
            formatters={
                "@date": "datetime"
            }
        )

        p.add_tools(hover)

        # 2. MAE 분포 히스토그램 (손절가 산출용)
        hist, edges = np.histogram(res_df['mae'], bins=20)
        h = figure(
                title="MAE Distribution", 
                x_axis_label='MAE (%)', y_axis_label='Frequency',
                sizing_mode='stretch_width', plot_height=350
            )
        
        h.quad(top=hist, bottom=0, left=edges[:-1], right=edges[1:], 
            fill_color="firebrick", line_color="white", alpha=0.7)

        st.bokeh_chart(gridplot([[p], [h]]))
        # Streamlit에서 출력 시: st.bokeh_chart(gridplot([[p], [h]]))
        # 일반 Jupyter 환경 시: show(gridplot([[p], [h]]))
        return gridplot([[p], [h]])