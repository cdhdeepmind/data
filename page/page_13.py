from datetime import datetime, date

import streamlit as st 
import pandas as pd 
import numpy as np
import importlib
import data_collector_psql

importlib.reload(data_collector_psql)
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, DataFrameTransformer

st.title('test')
st.divider()

if st.session_state.posdb: 
    st.write('postgresql is ready to use')

col1, col2 = st.columns(2)



start_dt = datetime(2025, 1, 1)
end_dt = datetime(2025, 6, 30)

st.divider()

st.session_state.posdb.connect()

loader = DataLoader(st.session_state.posdb)
transformer = DataFrameTransformer()
df_1h = loader.make_df('1h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1h = transformer.make_date(df_1h)

st.session_state.posdb.disconnect()

def inner(g): 
    base = g.iat[0, 1]
    date = g.iat[0, 5]
    close = g.iat[23, 4]
    profit = round((close - base) / base * 100, 2)
    g['base_direction'] = np.where(g['close'] > base, 'u', 'd')
    result = g.loc[g['base_direction'] != g['base_direction'].shift(), 'base_direction']
    result = result.values
    change_num = len(result) - 1

    return pd.DataFrame({
        'date': [date],
        'change': [result], 
        'change_num': [change_num],
        'profit': [profit]
    })

result = df_1h.groupby('date').apply(inner)
result.reset_index(drop=True, inplace=True)
result['profit_abs'] = result['profit'].abs()
count = result['change_num'].value_counts()

statistics = result.groupby('change_num')['profit_abs'].agg(['count', 'mean', 'std', 'min', 'max'])
statistics['count_ratio'] = (statistics['count'] / statistics['count'].sum()) * 100
statistics['count_ratio'] = statistics['count_ratio'].round(2)
st.dataframe(result)
st.dataframe(count)
st.dataframe(statistics)