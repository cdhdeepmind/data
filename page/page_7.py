from datetime import datetime

import streamlit as st 
import pandas as pd 
import numpy as np
import importlib
import data_collector_psql


importlib.reload(data_collector_psql)
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader

st.title('loss_cut')
st.divider()

theta = st.number_input(
    'threshold',
    min_value = 0.005, 
    max_value = 0.021, 
    step = 0.001, 
    format = '%.3f', 
    value = 0.012
    )

alpha = np.arange(29, 0, -1)
beta = np.arange(1, 30, 1) 
times = 1

st.write('must implement way report')

st.write("")
st.write("")

st.markdown(r"$ 1 \leq \beta \leq 29 $")
st.markdown(r"$ 29 \geq \alpha \geq 1 $")
st.markdown(r"$ 0.1 \leq z \leq 2 $")
# st.latex(r"(1 - 2t)^{10} \times (1 + r)^{20} = 1")
st.markdown(r"$ (1 - z\theta)^\beta \times (1 + r)^\alpha = 1 $")
st.markdown(r"$ (1 - z\theta)^\beta \times (1 + r)^{30 - \beta} = 1 $")
st.markdown(r"$ 1 + r = \left[\frac{1}{1-z\theta}\right]^\frac{\beta}{\beta - 30} $")
st.markdown(r"$ r = \left[\frac{1}{1-z\theta}\right]^\frac{\beta}{\beta - 30} -1 $")

b_a = np.divide(beta, alpha)
z_value_old = np.arange(0.1, 2.1, 0.1)

row = len(z_value_old) 
column = len(b_a) 

z_value = z_value_old.reshape(row, 1)

t_space = np.full((row, column), theta)
inner = 1 / (1 - z_value * t_space * times)
inner = np.round(inner, 3)

last_table = (np.power(inner, b_a) - 1) / times
last_table = np.round(last_table, 3)

columns = pd.MultiIndex.from_tuples(
    [(b, round(b / (30-b), 2)) for b in beta]
)

df_one = pd.DataFrame(inner)
df_two = pd.DataFrame(last_table, columns=columns)
df_two.index = z_value_old

st.write("")
st.write("")
st.dataframe(df_two)