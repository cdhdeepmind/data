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

st.title('test page')
st.divider()


if st.session_state.posdb: 
    st.write('postgresql is ready to use')

start_dt = datetime(2025, 1, 1)
end_dt = datetime(2025, 12, 30)
threshold = 0.012

st.session_state.posdb.connect()

loader = DataLoader(st.session_state.posdb)
df_1h = loader.make_df('1h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1h = loader.transfer_pct_df(df_1h, threshold, indicator=False)
df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1d = loader.transfer_df(df_1d, threshold)
df_1d['volatility'] = df_1d['high_pct'] - df_1d['low_pct']
df_1d = df_1d[['date', 'type', 'way', 'way_direction', 'mfe', 'mfe_label', 'volatility']]

df_1h = pd.merge(df_1h, df_1d, on='date', how='left')

st.session_state.posdb.disconnect()


df_1d['prev_volatility'] = df_1d['volatility'].shift(1)
df_1d['prev_volatility_pct'] = df_1d['prev_volatility'] * 100
df_1d['mfe_pct'] = df_1d['mfe'] * 100
df_1d.dropna(inplace=True)

df_1d = df_1d[df_1d['way'] == 'one_way']
df_1d = df_1d[['date', 'prev_volatility_pct', 'mfe_pct']]
st.dataframe(df_1d)






def render_mfe_scatter_widget(df):
    """Streamlit 대시보드 내에 Bokeh 2.0 산점도를 렌더링하는 함수"""

    # 1. 데이터 카피 및 시각화용 조건부 속성 추가
    plot_df = df.copy()
    # MFE 1% 미만은 빨간색(페이크아웃), 1% 이상은 파란색
    plot_df["color"] = np.where(plot_df["mfe_pct"] < 1.0, "#E74C3C", "#3498DB")
    plot_df["alpha"] = np.where(plot_df["mfe_pct"] < 1.0, 0.8, 0.5)

    source = ColumnDataSource(plot_df)

    # 2. Bokeh Figure 생성 (Bokeh 2.0 호환성 기준 속성 사용)
    p = figure(
        title="전날 변동성 대비 진입 후 MFE 산점도 분석",
        x_axis_label="전날 변동성률 (Prev Day Volatility, %)",
        y_axis_label="진입 후 MFE (Maximum Favorable Excursion, %)",
        plot_width=800,  # Streamlit container 안에서 기준점이 됩니다.
        plot_height=500,
        tools="pan,box_zoom,wheel_zoom,reset,save",
    )

    # 3. 산점도 추가
    p.circle(
        x="prev_volatility_pct",
        y="mfe_pct",
        size=5,
        color="color",
        alpha="alpha",
        legend_label="개별 진입 타점",
        source=source,
    )

    # 4. 필터 기준선 추가 (MFE 1.0% 점선)
    mfe_threshold_one = Span(
        location=1.0,
        dimension="width",
        line_color="#2C3E50",
        line_dash="dashed",
        line_width=2,
    )

    mfe_threshold_two = Span(
        location=2.0,
        dimension="width",
        line_color="#2C3E50",
        line_dash="dashed",
        line_width=2,
    )

    mfe_threshold_three = Span(
        location=3.0,
        dimension="width",
        line_color="#2C3E50",
        line_dash="dashed",
        line_width=2,
    )

    p.add_layout(mfe_threshold_one)
    p.add_layout(mfe_threshold_two)
    p.add_layout(mfe_threshold_three)

    # 5. 마우스 호버 툴팁 설정
    hover = HoverTool(
        tooltips=[
            ("진입 날짜", "@date"),
            ("전날 변동성", "@prev_volatility_pct{0.00}%"),
            ("최대 순행(MFE)", "@mfe_pct{0.00}%"),
        ]
    )
    p.add_tools(hover)

    # 6. 스타일 정돈
    p.title.text_font_size = "14pt"
    p.title.align = "center"
    p.legend.location = "top_right"
    p.legend.click_policy = "hide"  # 범례 클릭시 해당 점들 숨김/토글 기능

    # 7. Streamlit 전용 차트 컴포넌트로 호출 (가로폭 자동 맞춤)
    st.bokeh_chart(p, use_container_width=True)


# =====================================================================
# Streamlit 앱 실행 영역
# =====================================================================

st.title("📊 시스템 트레이딩 전략 분석 대시보드")
st.write("양방향 고정형 돌파 전략의 페이크아웃(MFE 1% 미만) 필터링 연구")

# [테스트용] 백테스팅 결과 예시를 모방한 가상 데이터 생성
np.random.seed(42)
dates = pd.date_range(start="2026-01-01", periods=120).strftime("%Y-%m-%d")
prev_vol = np.random.uniform(0.5, 6.0, 120)
mfe = np.random.exponential(scale=1.6, size=120)

# 전날 변동성이 4.0%를 넘을 때 의도적으로 MFE가 무너지는 세팅 (과변동성 페이크아웃 시뮬레이션)
for i in range(120):
    if prev_vol[i] > 4.0:
        mfe[i] = np.random.uniform(0.05, 0.95)

mock_data = pd.DataFrame(
    {"date": dates, "prev_volatility_pct": prev_vol, "mfe_pct": mfe}
)

st.dataframe(mock_data)
# 사이드바나 메인화면 통계 지표 간단히 표기
total_trades = len(mock_data)
fakeouts = len(mock_data[mock_data["mfe_pct"] < 1.0])

col1, col2 = st.columns(2)
with col1:
    st.metric("총 진입 횟수", f"{total_trades}회")
with col2:
    st.metric(
        "MFE 1% 미만 실패건 (빨간 점)",
        f"{fakeouts}회",
        delta=f"실패율 {fakeouts/total_trades*100:.1f}%",
        delta_color="inverse",
    )

st.markdown("---")

# 차트 렌더링
# render_mfe_scatter_widget(mock_data)
render_mfe_scatter_widget(df_1d)



def calculate_correlations(df):
    """전날 변동성과 MFE 간의 다양한 상관계수를 계산하는 함수"""
    
    # 1. 피어슨 상관계수 (Pearson) -> 직선 형태의 선형 관계가 있는지 측정
    pearson_corr = df['prev_volatility_pct'].corr(df['mfe_pct'], method='pearson')
    
    # 2. 스피어먼 상관계수 (Spearman) -> 한쪽이 커질 때 다른 쪽도 커지는지(비선형/단조 관계) 측정
    # ★ 올려주신 산점도 특성상 피어슨보다 스피어먼 수치가 더 의미 있게 높게 나올 확률이 큽니다.
    spearman_corr = df['prev_volatility_pct'].corr(df['mfe_pct'], method='spearman')
    
    # 3. 켄달 타우 (Kendall's Tau) -> 샘플 양이 적거나 아웃라이어가 있을 때 강한 강건한 순위 상관계수
    kendall_corr = df['prev_volatility_pct'].corr(df['mfe_pct'], method='kendall')
    
    print("====== 변동성 vs MFE 상관관계 분석 결과 ======")
    print(f"▶ 피어슨 상관계수 (Linear)    : {pearson_corr:+.4f}")
    print(f"▶ 스피어먼 상관계수 (Rank)     : {spearman_corr:+.4f}")
    print(f"▶ 켄달 타우 상관계수 (Robust)  : {kendall_corr:+.4f}")
    print("==============================================")
    
    return pearson_corr, spearman_corr


p_corr, s_corr = calculate_correlations(df_1d)

st.write(p_corr, s_corr)








def render_volatility_histogram_widget(df, bins=20):
    """Streamlit 내에 전날 변동성 히스토그램을 렌더링하는 함수 (Bokeh 2.0 호환)"""

    # 1. 넘파이를 활용해 히스토그램 데이터(빈도수, 구간 경계) 계산
    counts, edges = np.histogram(df["prev_volatility_pct"], bins=bins)

    # 2. 툴팁(Hover)에 이쁜 구간 표시를 위한 데이터프레임 가공
    hist_df = pd.DataFrame(
        {"counts": counts, "left": edges[:-1], "right": edges[1:]}
    )

    # 마우스 올렸을 때 "1.50% ~ 2.00%" 형태로 보여주기 위한 라벨 생성
    hist_df["bin_range"] = [
        f"{l:.2f}% ~ {r:.2f}%" for l, r in zip(hist_df["left"], hist_df["right"])
    ]

    source = ColumnDataSource(hist_df)

    # 3. Figure 객체 생성 (Bokeh 2.0 속성인 plot_width, plot_height 사용)
    p = figure(
        title="전날 변동성(율) 분포 히스토그램",
        x_axis_label="전날 변동성률 (%)",
        y_axis_label="발생 빈도 (일수)",
        plot_width=800,
        plot_height=400,
        tools="pan,box_zoom,wheel_zoom,reset,save",
        background_fill_color="#FDFEFE",
    )

    # 4. quad glyph를 이용해 히스토그램 막대 그리기
    p.quad(
        top="counts",
        bottom=0,
        left="left",
        right="right",
        source=source,
        fill_color="#34495E",  # 차분한 다크 네이비 톤
        line_color="white",
        alpha=0.85,
        hover_fill_color="#1ABC9C",  # 마우스 올렸을 때 민트색 변경
        hover_alpha=1.0,
    )

    # 5. 인터랙티브 툴팁 설정
    hover = HoverTool(
        tooltips=[("변동성 구간", "@bin_range"), ("발생 일수", "@counts 일")]
    )
    p.add_tools(hover)

    # 6. 세부 스타일 조정
    p.title.text_font_size = "14pt"
    p.title.align = "center"
    p.y_range.start = 0  # Y축이 항상 0부터 시작하도록 고정

    # 7. 스트림릿에 렌더링
    st.bokeh_chart(p, use_container_width=True)


# =====================================================================
# Streamlit 가동 및 테스트 데이터 영역
# =====================================================================

st.title("📊 변동성 분포 통계 분석")

# [테스트용] 비트코인 변동성 특성(전형적인 우측 꼬리가 긴 로그정규분포)을 모방한 가상 데이터 생성
np.random.seed(42)
# 평소엔 1~3% 대에 몰려있고 가끔 8~15% 터지는 비트코인 특징 반영
simulated_vol = np.random.lognormal(mean=0.8, sigma=0.5, size=250)
mock_data = pd.DataFrame({"prev_volatility_pct": simulated_vol})

# 스트림릿 사이드바로 구간(Bins) 수 조절 가능하게 연동
st.sidebar.markdown("### 차트 설정")
bin_counts = st.sidebar.slider(
    "히스토그램 구간 개수 (Bins)", min_value=10, max_value=50, value=25
)

# 대시보드 요약 지표
col1, col2 = st.columns(2)
with col1:
    st.metric("총 백테스팅 기간", f"{len(mock_data)} 일")
with col2:
    st.metric("평균 변동성", f"{mock_data['prev_volatility_pct'].mean():.2f}%")

st.markdown("---")

# 히스토그램 렌더링 호출
render_volatility_histogram_widget(df_1d, bins=bin_counts)










import pandas as pd
import numpy as np
import streamlit as st
from bokeh.plotting import figure
from bokeh.layouts import column
from bokeh.models import ColumnDataSource

# 1. 샘플 데이터 생성 (가상 코인 데이터)
np.random.seed(42)
dates = pd.date_range(start="2026-01-01", periods=100, freq="H")
close = np.random.normal(100, 2, size=100).cumsum()
open_price = close + np.random.normal(0, 1, size=100)
high = np.maximum(open_price, close) + np.abs(np.random.normal(0, 1, size=100))
low = np.minimum(open_price, close) - np.abs(np.random.normal(0, 1, size=100))

df = pd.DataFrame({
    'date': dates,
    'open': open_price,
    'high': high,
    'low': low,
    'close': close
})

# 양봉/음봉 색상 조건 정의
df['color'] = ["#00B060" if c >= o else "#FF3B30" for o, c in zip(df['open'], df['close'])]

# 지표 데이터 계산
df['indicator'] = df['close'].rolling(window=5).mean() - df['close'].rolling(window=20).mean()
df['indicator'] = df['indicator'].fillna(0)

# Bokeh용 데이터 소스 생성
source = ColumnDataSource(df)

# 2. 상단 메인 캔들스틱 차트 (p1)
p1 = figure(
    x_axis_type="datetime", 
    plot_width=900, 
    plot_height=400, 
    title="비트코인 선물 스타일 차트 (Bokeh 2.x)",
    tools="pan,wheel_zoom,box_zoom,reset,save",
    active_drag="pan"
)

# 캔들 심지(Wicks) 및 몸통(Bodies) 그리기
p1.segment('date', 'high', 'date', 'low', color="black", source=source)
p1.vbar('date', pd.Timedelta(minutes=45), 'open', 'close', fill_color='color', line_color='color', source=source)

# 3. 하단 지표 차트 (p2) - X축 범위(x_range) 동기화
p2 = figure(
    x_axis_type="datetime", 
    x_range=p1.x_range,  # 상단 차트와 x_range 공유
    plot_width=900, 
    plot_height=150, 
    tools="pan,wheel_zoom,reset",
    active_drag="pan"
)

# 지표 라인 그리기
p2.line('date', 'indicator', color="blue", line_width=2, source=source)

# 4. 여백 제거 및 경계선 정렬 (바이낸스 스타일 일체화)
p1.xaxis.visible = False  # 상단 차트의 X축 텍스트 숨김

# 두 차트 사이의 내부 마진을 최소화
p1.min_border_bottom = 0
p2.min_border_top = 10  # 약간의 간격 확보를 원치 않으시면 0으로 조절 가능합니다

# 5. column 레이아웃 결합 시 spacing을 0으로 명시하여 컴포넌트 간 물리적 여백 제거
layout = column(p1, p2, spacing=0)

st.title("스트림릿 Bokeh 연속 스크롤 차트")
st.bokeh_chart(layout, use_container_width=True)
































import streamlit as st

import pandas as pd
import numpy as np

from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource,
    Range1d,
    CrosshairTool,
    HoverTool
)

from bokeh.layouts import column
from bokeh.io import output_notebook
from bokeh.models.formatters import DatetimeTickFormatter


from bokeh.embed import components

from bokeh.models import WheelZoomTool

from bokeh.palettes import Category10

from bokeh.models import CDSView, BooleanFilter

from bokeh.models.tools import BoxZoomTool

from bokeh.models import NumeralTickFormatter

from streamlit.components.v1 import html

from bokeh.plotting import show

from bokeh.models import Span

from bokeh.models import LinearAxis

from bokeh.models import DataRange1d

from bokeh.models import CustomJS

from bokeh.models import PanTool

from bokeh.models import ResetTool

from bokeh.models import SaveTool

from bokeh.models import BoxSelectTool

from bokeh.layouts import gridplot

from bokeh.models import HoverTool

from bokeh.models import DatetimeTickFormatter

from bokeh.models import Div


# -----------------------------
# 샘플 데이터 생성
# -----------------------------

np.random.seed(0)

n = 500

dates = pd.date_range(
    "2025-01-01",
    periods=n,
    freq="1H"
)

price = np.cumsum(np.random.randn(n)) + 100

df = pd.DataFrame({
    "date": dates,
    "open": price + np.random.randn(n),
    "close": price + np.random.randn(n),
})

df["high"] = df[["open", "close"]].max(axis=1) + np.random.rand(n)
df["low"] = df[["open", "close"]].min(axis=1) - np.random.rand(n)

df["volume"] = np.random.randint(
    100,
    1000,
    size=n
)

# -----------------------------
# 이동평균
# -----------------------------

df["ma20"] = df["close"].rolling(20).mean()

# -----------------------------
# RSI 계산
# -----------------------------

delta = df["close"].diff()

gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

rs = avg_gain / avg_loss

df["rsi"] = 100 - (100 / (1 + rs))

# -----------------------------
# 상승/하락 캔들 분리
# -----------------------------

inc = df["close"] >= df["open"]
dec = df["close"] < df["open"]

source = ColumnDataSource(df)

# -----------------------------
# 메인 캔들 차트
# -----------------------------

TOOLS = "xpan,xwheel_zoom,reset,save"

p = figure(
    width=1400,
    height=500,
    x_axis_type="datetime",
    tools=TOOLS,
    active_scroll="xwheel_zoom",
)

p.xaxis.formatter = DatetimeTickFormatter(
    hours="%Y-%m-%d %H:%M"
)

p.add_tools(CrosshairTool())

# 캔들 wick
p.segment(
    "date",
    "high",
    "date",
    "low",
    color="white",
    source=source
)

# 상승 캔들
p.vbar(
    x="date",
    width=1000 * 60 * 30,
    top="close",
    bottom="open",
    fill_color="#00ff88",
    line_color="#00ff88",
    source=ColumnDataSource(df[inc])
)

# 하락 캔들
p.vbar(
    x="date",
    width=1000 * 60 * 30,
    top="open",
    bottom="close",
    fill_color="#ff3333",
    line_color="#ff3333",
    source=ColumnDataSource(df[dec])
)

# 이동평균
p.line(
    df["date"],
    df["ma20"],
    color="yellow",
    line_width=2,
    legend_label="MA20"
)

# -----------------------------
# 거래량 차트
# -----------------------------

vol = figure(
    width=1400,
    height=150,
    x_axis_type="datetime",
    x_range=p.x_range,
    tools=TOOLS,
    active_scroll="xwheel_zoom",
)

vol.vbar(
    x="date",
    top="volume",
    width=1000 * 60 * 30,
    source=source,
    color="gray"
)

# -----------------------------
# RSI 차트
# -----------------------------

rsi_fig = figure(
    width=1400,
    height=200,
    x_axis_type="datetime",
    x_range=p.x_range,
    tools=TOOLS,
    active_scroll="xwheel_zoom",
)

rsi_fig.line(
    df["date"],
    df["rsi"],
    color="cyan",
    line_width=2
)

# RSI 기준선
rsi_fig.add_layout(
    Span(
        location=70,
        dimension="width",
        line_color="red",
        line_dash="dashed"
    )
)

rsi_fig.add_layout(
    Span(
        location=30,
        dimension="width",
        line_color="green",
        line_dash="dashed"
    )
)

# -----------------------------
# 스타일
# -----------------------------

for fig in [p, vol, rsi_fig]:

    fig.background_fill_color = "#111111"
    fig.border_fill_color = "#111111"

    fig.xgrid.grid_line_color = "#333333"
    fig.ygrid.grid_line_color = "#333333"

    fig.xaxis.major_label_text_color = "white"
    fig.yaxis.major_label_text_color = "white"

    fig.xaxis.axis_line_color = "white"
    fig.yaxis.axis_line_color = "white"

# -----------------------------
# 레이아웃
# -----------------------------

layout = column(
    p,
    vol,
    rsi_fig
)

# -----------------------------
# Streamlit 출력
# -----------------------------

from bokeh.embed import file_html
from bokeh.resources import CDN

html_data = file_html(
    layout,
    CDN,
    "chart"
)

html(
    html_data,
    height=900
)