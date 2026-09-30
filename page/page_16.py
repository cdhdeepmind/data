import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql
import analyzer 

from analyzer import ExcursionAnalyzer

from datetime import datetime, date
from data_collector_psql import (
    DataLoader, DataAnalyzer, PreProcessor, 
    PullbackAnalyzer, Report, GraphLoader, DataFrameTransformer, 
    IndicatorBuilder
    )

importlib.reload(data_collector_psql)
importlib.reload(analyzer)

st.title('Mae and Mfe analysis')


start = datetime(2025, 1, 1)
end = datetime(2025, 12, 31)

if st.session_state.posdb: 
    st.write('posdb connected')

st.session_state.posdb.connect()
loader = DataLoader(st.session_state.posdb)
df_1d = loader.make_df('1d', start, end, open_time_dt=True, volume=False, ohlc_type='float')
df_1d = loader.transfer_df(df_1d, threshold=0.012)
df_1d_one_way = df_1d[df_1d['way'] == 'one_way']
df_1d_one_way_date = df_1d_one_way['open_time'].dt.date
df_15m = loader.make_df('15m', start, end, open_time_dt=True, volume=False, ohlc_type='float')
st.session_state.posdb.disconnect()

analyzer = ExcursionAnalyzer()

result_df = analyzer.analyze_mae_mfe(df_15m, threshold=0.007)

# result_df 중 one_way만 추출해서 분석 
filtered_df = result_df[result_df['date'].isin(df_1d_one_way_date)]
mae_df = filtered_df[['mae']]
# st.dataframe(df_1d_one_way_date)
# st.dataframe(filtered_df)
# st.dataframe(mae_df)

bins = [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5]
labels = ["0~0.25", "0.25~0.5", "0.5~0.75", "0.75~1.0", "1.0~1.25", "1.25~1.5", "1.5~1.75", "1.75~2.0", "2.0~2.25", "2.25~2.5"]

mae_df['range'] = pd.cut(mae_df['mae'], bins=bins, labels=labels)
range_analysis = mae_df['range'].value_counts(normalize=True).sort_index().cumsum() * 100
result = pd.DataFrame(range_analysis)
result['proportion'] = result['proportion'].round(2)

analyzer.plot_mae_mfe_bokeh(filtered_df)
st.dataframe(result)