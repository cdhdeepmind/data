
from data_collector_psql import PostgresHandler, DataCollector, Utility
from datetime import datetime

import streamlit as st 
import pandas as pd 
import time
import sys 

print('trading.py')
print(sys.path)

# Initialize the DB handler in the main page
if 'posdb' not in st.session_state: 
    st.session_state.posdb = PostgresHandler('btcusdt')


############ Navigation ############# 

data_collect_page = st.Page('page_1.py', title='Data Collect')
threshold_page = st.Page('page_2.py', title='Threshold')
test_page = st.Page('./page/page_3.py', title='test')
pullback_page = st.Page('./page/page_4.py', title='pullback')
sequence_1h_page = st.Page('./page/page_5.py', title='sequence_1h')
sequence_15m_page = st.Page('./page/page_6.py', title='sequence_15m')
loss_cut = st.Page('./page/page_7.py', title='loss_cut')
test_page_two = st.Page('./page/page_8.py', title='volatility')
sequence_30m_page = st.Page('./page/page_9.py', title='sequence_30m')
pattern_6h_page = st.Page('./page/page_10.py', title='pattern_6h')
sequence_6h_page = st.Page('./page/page_11.py', title='sequence_6h')
sequence_12h_page = st.Page('./page/page_12.py', title='sequence_12h')
test_two_page = st.Page('./page/page_13.py', title='test_two')
pattern_test_page = st.Page('./page/page_14.py', title='pattern_test')
test_three_page = st.Page('./page/page_15.py', title='test_three')
mae_mfe_page = st.Page('./page/page_16.py', title='mae_mfe')
mfe_distribution_page = st.Page('./page/page_17.py', title='mfe_distribution')
sequence_1h_pct_page = st.Page('./page/page_18.py', title='sequence_1h_pct')
improving_return_page = st.Page('./page/page_19.py', title='improving_return')
test_four_page = st.Page('./page/page_20.py', title='test_four')
test_five_page = st.Page('./page/page_21.py', title='test_five')
test_six_page = st.Page('./page/page_22.py', title='test_six')

pages = [
    data_collect_page, 
    threshold_page, 
    test_page, 
    pullback_page, 
    sequence_1h_page, 
    sequence_15m_page, 
    loss_cut, 
    test_page_two, 
    sequence_30m_page, 
    pattern_6h_page, 
    sequence_6h_page, 
    sequence_12h_page, 
    test_two_page, 
    pattern_test_page, 
    test_three_page, 
    mae_mfe_page, 
    mfe_distribution_page, 
    sequence_1h_pct_page, 
    improving_return_page, 
    test_four_page, 
    test_five_page, 
    test_six_page
]

pg = st.navigation(pages)
pg.run()

# if "df" not in st.session_state: 
#     st.session_state.df = pd.DataFrame({'A': [1, 2, 3], 'B': [2, 4, 5]})

# if "change" not in st.session_state: 
#     st.session_state.change = False

# df_container = st.empty()

# if not st.session_state.change: 
#     df_container.dataframe(st.session_state.df)
#     st.write('first')

# # if st.button('button change'):  
# #     st.session_state.df['A'][0] = 7
# #     st.session_state.change = True

# #     df_container.dataframe(st.session_state.df)
# #     st.write('second')

# for i in range(7): 
#     st.session_state.df['A'][0] = i
#     df_container.dataframe(st.session_state.df)
#     time.sleep(2)

def test(): 
    st.write('trading.py')