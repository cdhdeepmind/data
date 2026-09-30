from datetime import datetime, date, timedelta, timezone
from data_collector_psql import DataLoader, DataAnalyzer, GraphLoader, IndicatorBuilder, Report
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, Range1d, Span
from bokeh.palettes import Spectral4

import time

import streamlit as st 
import pandas as pd 
import importlib
import data_collector_psql
import matplotlib.pyplot as plt
import numpy as np 



importlib.reload(data_collector_psql)


from streamlit_lightweight_charts import renderLightweightCharts

chart_options = {
    "layout": {
        "textColor": "white",
        "background": {
            "type": "solid",
            "color": "#131722"
        }
    },
    "width": 1000,
    "height": 600,
}

series = [{
    "type": "Candlestick",
    "data": [
        {
            "time": "2026-06-01",
            "open": 100,
            "high": 110,
            "low": 95,
            "close": 105
        },
        {
            "time": "2026-06-02",
            "open": 105,
            "high": 115,
            "low": 100,
            "close": 112
        }
    ]
}]

renderLightweightCharts(
    [{"chart": chart_options,
      "series": series}]
)

