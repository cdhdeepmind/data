import streamlit as st 
import psycopg2 

st.title('postgresql connect test')

try: 
    conn = psycopg2.connect(
        host = '127.0.0.1', 
        port = 5432, 
        dbname = 'btcusdt', 
        user = 'chododa', 
        password = '3705'
    )

except Exception as e: 
    print('conn error ##########')
    st.write('conn error')
else: 
    print('DB conn succeed')
    st.write('conn success')

finally: 
    if conn is not None and not conn.closed:
        conn.close()
        st.write('conn disclosed')