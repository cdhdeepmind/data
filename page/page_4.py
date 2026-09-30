from datetime import datetime, date

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)
from data_collector_psql import (
    DataLoader, DataAnalyzer, PreProcessor, 
    PullbackAnalyzer, Report, GraphLoader
    )


st.title('Pull Back analysis')
st.divider()


########## session initializing ##########
if st.session_state.posdb:
    st.write('postgresql is ready to use')


# -> transform to st.element
col1, col2 = st.columns(2)
start = col1.date_input('start_date', date(2025, 1, 1))
end = col2.date_input('end_date', date(2025, 1, 31))

start_dt = datetime(start.year, start.month, start.day)
end_dt = datetime(end.year, end.month, end.day)
threshold = 0.012
losscut = threshold * 2
times = 10

btn_click = st.button('analysis')
st.divider()

if btn_click and st.session_state.posdb: 
    if start_dt is not None and end_dt is not None: 
        # make dataframe and store to session 
        if start_dt > end_dt: 
            st.warning('start date must be less than end date')
        else:   
            st.session_state.posdb.connect()

            loader = DataLoader(st.session_state.posdb)
            processor = PreProcessor()
            analyzer = PullbackAnalyzer()
            report = Report()
            graph = GraphLoader()

            df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
            df_1h = loader.make_df('1h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
            
            pre_df_1d, pre_df_1h = processor.run_pullback(df_1d, df_1h, threshold)
            result_df_1d = analyzer.run(pre_df_1d, pre_df_1h, threshold, losscut)
            
            report.pullback_report(result_df_1d, losscut)
            report_dict = report.pullback_dist_report(result_df_1d, threshold, max_mean=1, min_margin=1)
            df_1d_ap = report.pullback_high_report(result_df_1d, threshold)

            graph = GraphLoader()
            graph.pull_back_distribution(report_dict)
            # graph.pull_back_high(df_1d_ap)
            report.pullback_step_max_profit(df_1d_ap)

            # this part needs refactoring later










            # df_1d = loader.transfer_df(df_1d, threshold)
            # st.write(df_1d.head())

            # analyzer = DataAnalyzer()
            # df_1d_pullback, df_1h_pullback, original_1d = analyzer.pull_back_data(df_1d, df_1h)

            # st.write(df_1h_pullback.head())
            # result_df, total_df = analyzer.pull_back(df_1d_pullback, df_1h_pullback, original_1d, threshold)

            # graph = GraphLoader()
            # # graph.pull_back_vertical(result_df, threshold)
            # graph.pull_back_all_vertical(total_df, threshold, loss_cut)
            # st.divider()

            # profit_arr, total_loss, report_dict = analyzer.pre_calc_profit(df_1d, result_df, threshold, loss_cut, times)
            # total_profit_arr = analyzer.calc_profit(profit_arr, total_loss, times)
            # st.dataframe(report_dict)
            # st.divider()

            # graph.make_histogram(total_profit_arr)

            # ###########
            # st.write(f'threshold: {threshold}')
            # st.write(f'loss_cut: {loss_cut}')
            # st.write(f'times: {times}')

            # st.write(report_dict)
            # report_df = analyzer.report(report_dict, loader)
            # st.write("")
            # st.write("")

            st.session_state.posdb.disconnect()

    else: 
        st.warning('You should input date')









# import streamlit as st
# import pandas as pd
# import numpy as np
# from scipy.stats import gaussian_kde
# from bokeh.plotting import figure
# from bokeh.palettes import Category10

# ### --------------------------
# ###  예시 데이터프레임 준비
# ### --------------------------
# df = result_df_1d.copy()

# groups = df['pullback_type'].unique()
# colors = Category10[len(groups)]

# ### --------------------------
# ###  보케 figure 생성
# ### --------------------------
# p = figure(
#     title="Group-wise Smooth Line Histogram (KDE)",
#     width=850, height=450,
#     tools="pan,wheel_zoom,box_zoom,reset"
# )

# legend_items = []

# ### --------------------------
# ###  각 그룹별 KDE 커브 플롯
# ### --------------------------
# for (g, color) in zip(groups, colors):
#     data = df.loc[df['pullback_type'] == g, 'max_profit_pct'].values

#     # KDE 밀도 추정
#     kde = gaussian_kde(data)

#     # X축 범위 생성 (데이터 전체 범위에서 촘촘히)
#     xs = np.linspace(data.min(), data.max(), 400)
#     ys = kde(xs)

#     r = p.line(xs, ys, line_width=2, color=color)
#     legend_items.append((str(g), [r]))

# ### --------------------------
# ###  범례 추가
# ### --------------------------
# from bokeh.models import Legend
# legend = Legend(items=legend_items)
# p.add_layout(legend, "right")

# ### --------------------------
# ###  Streamlit 출력
# ### --------------------------
# st.bokeh_chart(p)
