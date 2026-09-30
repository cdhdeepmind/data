import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql

from datetime import datetime, date
from data_collector_psql import (
    DataLoader, DataAnalyzer, PreProcessor, 
    PullbackAnalyzer, Report, GraphLoader, DataFrameTransformer, 
    IndicatorBuilder
    )

importlib.reload(data_collector_psql)

st.title('Pattern 6H')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready to use')

st.session_state.posdb.connect()

loader = DataLoader(st.session_state.posdb)
df_6h = loader.make_df(
    '6h', datetime(2025, 1, 1), datetime(2025, 10, 31), 
    open_time_dt=True, volume=False, ohlc_type='float'
    )

st.session_state.posdb.disconnect()


transformer = DataFrameTransformer()

df_6h = transformer.make_close_type(df_6h)
df_6h['date'] = df_6h['open_time'].dt.date

st.dataframe(df_6h)


patterns = (
    df_6h.groupby('date')['close_type']
        .apply(lambda g: tuple(g.values))
        .to_frame(name='pattern')
)

st.dataframe(patterns)


pattern_stats = (
    patterns['pattern']
    .value_counts()
    .to_frame(name='count')
)

pattern_stats['ratio'] = (
    pattern_stats['count'] / pattern_stats['count'].sum()
)

pattern_stats['ratio_100'] = (
    pattern_stats['ratio'] * 100
)

pattern_stats['ratio_100'] = pattern_stats['ratio_100'].round(2)

st.dataframe(pattern_stats)
st.write(f'total pattern is: {len(pattern_stats)}')



st.divider()

st.session_state.posdb.connect()
indicator = IndicatorBuilder(st.session_state.posdb)
df = indicator.make_bbw(datetime(2024, 8, 1), datetime(2025, 10, 31), '6h')
st.session_state.posdb.disconnect()

transformer = DataFrameTransformer()
df = transformer.make_close_type(df)

df['bbw_state'] = pd.qcut(
    df['prev_bbw'], 
    q = [0.0, 0.33, 0.66, 1.0], 
    labels = ['low', 'mid', 'high']
)

df['date'] = df['open_time'].dt.date

daily_state = df.groupby('date').first()[['bbw_state']]
patterns = (
    df.groupby('date')['close_type']
        .apply(lambda x: tuple(x.to_numpy()))
        .to_frame('pattern')
)

combined = patterns.join(daily_state, how='left')
count_table = combined.groupby(['bbw_state', 'pattern']).size()

st.dataframe(count_table)

