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

start_dt = datetime(2026, 1, 1)
end_dt = datetime(2026, 5, 31)
threshold = 0.012

st.session_state.posdb.connect()

loader = DataLoader(st.session_state.posdb)
df_1h = loader.make_df('1h', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1h = loader.transfer_pct_df(df_1h, threshold, indicator=False)
df_1d = loader.make_df('1d', start_dt, end_dt, open_time_dt=True, volume=False, ohlc_type='float')
df_1d = loader.transfer_df(df_1d, threshold)
df_1d = df_1d[['date', 'type', 'way', 'way_direction', 'mfe', 'mfe_label']]

df_1h = pd.merge(df_1h, df_1d, on='date', how='left')

st.session_state.posdb.disconnect()

st.dataframe(df_1h)
def prepare_data(df_1h, threshold): 
    ghost_data_list = []
    lda_data_list = []

    for i, date in enumerate(df_1h['date'].unique()): 
        df_day = df_1h[df_1h['date'] == date]
        way = df_day.iat[0, 11]
        way_direction = df_day.iat[0, 12]
        df_day['time_step'] = range(len(df_day))
       
        

        if way == 'one_way': 
            if way_direction == 'low': 
                condition = (df_day['high_pct'] >= -threshold*100) & (df_day['low_pct'] <= -threshold*100)
                df_cross = df_day[condition]
                first_cross_idx = df_cross.index[0]
                df_day['return_pct'] = df_day['close_pct'] * -1
                df_day['first_touch'] = 0
                df_day.loc[first_cross_idx, 'first_touch'] = 1
                last_close_pct = df_day.iat[23, 9] * -1
            elif way_direction == 'high':
                condition = (df_day['high_pct'] >= threshold*100) & (df_day['low_pct'] <= threshold*100)
                df_cross = df_day[condition]
                first_cross_idx = df_cross.index[0]
           
                df_day['return_pct'] = df_day['close_pct']
                df_day['first_touch'] = 0
                df_day.loc[first_cross_idx, 'first_touch'] = 1
                last_close_pct = df_day.iat[23, 9]

            # calculate volatility
            high_pct = df_day.loc[first_cross_idx, 'high_pct']
            low_pct = df_day.loc[first_cross_idx, 'low_pct']
            volatility = high_pct - low_pct 
            first_touch_idx = condition.values.argmax()

        else: 
            continue
        
        
        mfe_label = df_day.iat[0, 14]

        lda_data_list.append({
            'first_touch_hour': first_touch_idx, 
            'volatility_at_touch': volatility, 
            'mfe_category': mfe_label
        })

        for _, row in df_day.iterrows(): 
            ghost_data_list.append({
                'trade_id': f'Trade_{i}',
                'time_stamp': row['open_time'],
                'time_step': row['time_step'],
                'return_pct': row['return_pct'], 
                'label': mfe_label, 
                'is_touch': row['first_touch'], 
                'volatility': volatility,
                'date': row['date'], 
                'last_close_pct': last_close_pct
            })
        
    
    return pd.DataFrame(ghost_data_list), pd.DataFrame(lda_data_list)








# 4. Bokeh 차트 생성
def create_ghost_chart(data, labels):
    # 차트 기본 설정
    p = figure(
        title="Price Trajectory After Breakout",
        x_axis_label="Time Steps (After Entry)",
        y_axis_label="Return (%)",
        plot_height=500,
        tools="pan,wheel_zoom,box_zoom,reset,save"
    )

    # 기준선 (0% 라인 및 손절/익절 마일스톤)
    # p.add_layout(Range1d(-2, 5))
    p.line([0, 24], [0, 0], line_dash="dashed", line_color="gray", alpha=0.5) # 본절선
    p.line([0, 24], [1.2, 1.2], line_dash="dotted", line_color="purple", legend_label="MFE 1% Line")
    p.line([0, 24], [2, 2], line_dash="dotted", line_color="green", legend_label="MFE 1% Line")
    p.line([0, 24], [3, 3], line_dash="dotted", line_color="green", legend_label="MFE 1% Line")
    p.line([0, 24], [4, 4], line_dash="dotted", line_color="green", legend_label="MFE 1% Line")

    p.line([0, 23], [0, 2], line_color="green", legend_label="MFE 1% Line")
    p.line([0, 23], [0, 3], line_color="green", legend_label="MFE 1% Line")
    p.line([0, 23], [0, 4], line_color="green", legend_label="MFE 1% Line")

    # 그룹별 색상 매핑
    colors = {0: "red", 1: "dodgerblue", 2: 'green', 3: 'purple'}

    for label in labels:
        group_df = data[data['label'] == label]
        trade_ids = group_df['trade_id'].unique()
        
        # 개별 트레이드 경로 그리기 (고스트 선)
        # for tid in trade_ids:
        #     single_trade = group_df[group_df['trade_id'] == tid]
        #     source = ColumnDataSource(single_trade)
        #     p.line(
        #         x='time_step', y='return_pct', source=source,
        #         line_width=1, line_alpha=0.2, color=colors[label]
        #     )

        # 2. 첫 터치 지점(is_touch == 1) 표시하기
        # 해당 그룹에서 터치가 발생한 데이터만 필터링
        touch_df = group_df[group_df['is_touch'] == 1]
        
        if not touch_df.empty:
            touch_source = ColumnDataSource(touch_df)
            p.circle(
                x='time_step', y='return_pct', 
                source=touch_source,
                size=5, 
                color=colors.get(label, "black"), # 라인과 같은 색상
                line_color="white", # 테두리를 줘서 강조
                fill_alpha=0.8,
                legend_label=f"{label} Touch Point"
            )

        
        # 그룹 평균선 (분리력을 확인하는 핵심 선)
        mean_path = group_df.groupby('time_step')['return_pct'].mean().reset_index()
        st.write(label)
        st.dataframe(group_df)
        p.line(
            mean_path['time_step'], mean_path['return_pct'],
            line_width=2, color=colors[label], legend_label=f"Mean {label}"
        )

    # 툴팁 설정
    hover = HoverTool(tooltips=[
        ("Trade ID", "@trade_id"),
        ("Open time", "@time_stamp{%Y-%m-%d %H:%M}"),
        ("Touch close_pct", "@return_pct{0.00}%"), 
        ("Last close_pct", "@last_close_pct{0.00}%")
        ], 
        formatters={
            '@time_stamp': 'datetime'
        }    
    )

    p.y_range = Range1d(start=-5, end=15)

    p.add_tools(hover)
    
    p.legend.location = "top_left"
    p.legend.click_policy = "hide" # 레전드 클릭 시 해당 그룹 숨기기
    
    return p



def create_ghost_one_chart(data, labels):
    # 차트 기본 설정
    p = figure(
        title="Price Trajectory After Breakout",
        x_axis_label="Close_pct(First Touch, %)",
        y_axis_label="Last_close_pct(%)",
        plot_height=600,
        tools="pan,wheel_zoom,box_zoom,reset,save"
    )

    # 기준선 (0% 라인 및 손절/익절 마일스톤)
    # p.add_layout(Range1d(-2, 5))
    p.line([0, 24], [0, 0], line_dash="dashed", line_color="gray", alpha=0.5) # 본절선
    p.line([0, 24], [1.2, 1.2], line_dash="dotted", line_color="purple", legend_label="MFE 1% Line")
    p.line([0, 24], [2, 2], line_dash="dotted", line_color="green", legend_label="MFE 1% Line")
    p.line([0, 24], [3, 3], line_dash="dotted", line_color="green", legend_label="MFE 1% Line")
    p.line([0, 24], [4, 4], line_dash="dotted", line_color="green", legend_label="MFE 1% Line")

    

    vline = Span(location=1.2, dimension='height', line_color='green', line_width=1, line_dash='dashed')

    # 그룹별 색상 매핑
    colors = {0: "red", 1: "dodgerblue", 2: 'green', 3: 'purple'}

    for label in labels:
        group_df = data[data['label'] == label]
        trade_ids = group_df['trade_id'].unique()
        
        # 개별 트레이드 경로 그리기 (고스트 선)
        # for tid in trade_ids:
        #     single_trade = group_df[group_df['trade_id'] == tid]
        #     source = ColumnDataSource(single_trade)
        #     p.line(
        #         x='time_step', y='return_pct', source=source,
        #         line_width=1, line_alpha=0.2, color=colors[label]
        #     )

        # 2. 첫 터치 지점(is_touch == 1) 표시하기
        # 해당 그룹에서 터치가 발생한 데이터만 필터링
        touch_df = group_df[group_df['is_touch'] == 1]
        
        if not touch_df.empty:
            touch_source = ColumnDataSource(touch_df)
            p.circle(
                x='return_pct', y='last_close_pct', 
                source=touch_source,
                size=5, 
                color=colors.get(label, "black"), # 라인과 같은 색상
                line_color="white", # 테두리를 줘서 강조
                fill_alpha=0.8,
                legend_label=f"{label} Touch Point"
            )

        
        

    # 툴팁 설정
    hover = HoverTool(tooltips=[
        ("Trade ID", "@trade_id"),
        ("Open time", "@time_stamp{%Y-%m-%d %H:%M}"),
        ("Return", "@return_pct{0.00}%"), 
        ], 
        formatters={
            '@time_stamp': 'datetime'
        }    
    )

    p.y_range = Range1d(start=-2, end=10)

    p.add_tools(hover)
    p.add_layout(vline)
    
    p.legend.location = "top_left"
    p.legend.click_policy = "hide" # 레전드 클릭 시 해당 그룹 숨기기
    
    return p



# entry_arr = find_breakout_signals(df_1h, threshold)
start = time.time()
ghost_df, lda_df = prepare_data(df_1h, threshold)

st.write('ghost')
st.dataframe(ghost_df)
st.dataframe(lda_df)

end = time.time()
total_time = end - start
st.write(f'total_second: {total_time}')

st.sidebar.header("Filter Settings")
selected_labels = st.sidebar.multiselect(
    "MFE Group 선택", [0, 1, 2, 3], default=[0]
)

filtered_df = ghost_df[ghost_df['label'].isin(selected_labels)]
bokeh_p = create_ghost_chart(filtered_df, selected_labels)
bokeh_p_one = create_ghost_one_chart(filtered_df, selected_labels)
st.bokeh_chart(bokeh_p, use_container_width=True)
st.bokeh_chart(bokeh_p_one, use_container_width=True)




st.subheader('분리력 실험 1')

df = ghost_df.copy()
df = df[df['is_touch'] == 1]
st.write('new_df')
df = df[['time_step', 'return_pct', 'label', 'last_close_pct']]
st.dataframe(df)
df['target'] = np.where((df['label'] >= 1), 1, 0)
df = df.rename(columns={'time_step': 'hour', 'return_pct': 'pct_from_open'})
df = df[['hour', 'pct_from_open', 'target', 'last_close_pct']]
st.dataframe(df)

# ==========================================
# 2. 트레이더의 고정 속도 기준선 정의 및 위치 판정
# 직선 방정식: y = (2.2 / 23) * x
# ==========================================
m_user = 2.2 / 23  # 기울기 (약 0.0956)

# 각 점이 기준선보다 위에 있는지(True) 아래에 있는지(False) 판정
df['is_above_line'] = df['pct_from_open'] > (m_user * df['hour'])

# ==========================================
# 3. 영역별 분리 비율 및 통계 계산
# ==========================================
# 전체 데이터 개수
total_cnt = len(df)

# A. 선 위에 위치한 그룹 분석
above_df = df[df['is_above_line'] == True]
above_total = len(above_df)
above_success = above_df['target'].sum()  # MFE 1% 이상 성공 개수
above_fail = above_total - above_success
success_rate_above = (above_success / above_total * 100) if above_total > 0 else 0

above_plus_df = df[(df['is_above_line']==True) & (df['last_close_pct'] >= 1.2)]
st.write(len(above_plus_df))
st.write(len(above_plus_df) / above_total)


profit_df = above_df.copy()
profit_df['last_profit'] = (profit_df['last_close_pct'] / 100) - 0.012
profit_df['last_profit_10'] = profit_df['last_profit'] * 10
last_profit = (1 + profit_df['last_profit_10']).prod()
st.write(last_profit)

st.dataframe(profit_df)
# B. 선 아래에 위치한 그룹 분석
below_df = df[df['is_above_line'] == False]
below_total = len(below_df)
below_success = below_df['target'].sum()  # MFE 1% 이상 성공 개수
below_fail = below_total - below_success
success_rate_below = (below_success / below_total * 100) if below_total > 0 else 0

# C. 전체적인 매칭 정확도 (선 위=성공, 선 아래=실패라고 가정했을 때의 적중률)
correct_predictions = above_success + below_fail
total_accuracy = (correct_predictions / total_cnt) * 100

# ==========================================
# 4. 결과 레포트 출력
# ==========================================
st.write("---")
st.write("### 📈 트레이더 고정 속도 기준선 (23, 2.2) 분리력 성적표")
st.write("---")
st.write(f"**총 분석 데이터 개수:** {total_cnt}개")

# 1. 🟩 [선 위에 찍힌 점들]
st.write(f"#### 🟩 [선 위에 찍힌 점들] (총 {above_total}개, 전체의 {above_total/total_cnt*100:.1f}%)")
st.write(f"- MFE 1% 이상 분출 (성공): {above_success}개")
st.write(f"- MFE 1% 미만 분출 (실패): {above_fail}개")
st.write(f"👉 **선 위 영역에서의 롱 돌파 승률:** `{success_rate_above:.2f}%`")

# 2. 🟥 [선 아래에 찍힌 점들]
st.write(f"#### 🟥 [선 아래에 찍힌 점들] (총 {below_total}개, 전체의 {below_total/total_cnt*100:.1f}%)")
st.write(f"- MFE 1% 이상 분출 (성공): {below_success}개")
st.write(f"- MFE 1% 미만 분출 (실패): {below_fail}개")
st.write(f"👉 **선 아래 영역에서의 롱 돌파 승률:** `{success_rate_below:.2f}%`")

st.write("---")
st.write(f"#### 🏆 핵심 분리도 점수 (Separation Gap): `{success_rate_above - success_rate_below:.2f}%p`")
st.caption("(이 격차가 15%~20%이상 벌어져 있다면 매우 훌륭한 필터선입니다.)")
st.write(f"#### 🎯 선 기준 조건부 단순 적중률: `{total_accuracy:.2f}%`")
st.write("---")








st.title("Matplotlib 렌더링 예시")


import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
import matplotlib.pyplot as plt

# 1. 가상의 샘플 데이터 생성 (사용자 데이터셋 구조 모사)
np.random.seed(42)
n_samples = 500

# 가상 데이터: 첫 터치 시간(0~23시), 터치 시점 변동성, MFE 카테고리(0, 1, 2, 3)
mock_data = {
    'first_touch_hour': np.random.randint(0, 24, n_samples),
    'volatility_at_touch': np.random.uniform(0.1, 2.0, n_samples),
    'mfe_category': np.random.choice([0, 1, 2, 3], n_samples)
}
df = pd.DataFrame(mock_data)

# 의도적으로 MFE 3(대추세)은 특정 시간대(예: 미 증시 개장 정규시간 14~16시 표준화 가정)에 더 많이 터치되도록 노이즈 주입
df.loc[df['mfe_category'] == 3, 'first_touch_hour'] = np.clip(
    df.loc[df['mfe_category'] == 3, 'first_touch_hour'] + np.random.normal(15, 3, len(df[df['mfe_category'] == 3])), 0, 23
).astype(int)

st.dataframe(df)
# --- 방법 [1] 통계적 검정 (Kruskal-Wallis) ---
st.write("=== [1] 통계적 검정 결과 ===")
groups = [lda_df[lda_df['mfe_category'] == i]['first_touch_hour'].values for i in range(4)]
stat, p_val = stats.kruskal(*groups)
st.write(f"Kruskal-Wallis 통계량: {stat:.4f}")
st.write(f"p-value: {p_val:.4f}")
if p_val < 0.05:
    st.write("▶ 결론: MFE 카테고리별로 퍼스트 터치 시간의 분포가 통계적으로 유의미하게 다릅니다! (분리력 있음)")
else:
    st.write("▶ 결론: 통계적으로 유의미한 차이가 없습니다. (눈 착시일 확률 높음)")
st.write("-" * 50)


# --- 방법 [2] 머신러닝 분류 모델을 통한 예측력 측정 ---
st.write("=== [2] ML 모델 기반 예측력 검증 ===")
X = lda_df[['first_touch_hour', 'volatility_at_touch']]
# X = lda_df[['first_touch_hour']]
y = lda_df['mfe_category']

model = RandomForestClassifier(n_estimators=100, random_state=42)
# 5-Fold 교차 검증
scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')

st.write(f"5-Fold 교차 검증 정확도: {scores.mean()*100:.2f}% (표준편차: {scores.std()*100:.2f}%)")
st.write(f"무작위 예측 기준 점수(Baseline): 25.00%")
if scores.mean() > 0.35: # 기준점보다 유의미하게 높을 때
    st.write("▶ 결론: 모델이 첫 터치 정보를 가지고 MFE를 유의미하게 예측합니다. 분리력 존재.")
else:
    st.write("▶ 결론: 무작위 수준과 비슷합니다. 분리력이 매우 약하거나 없습니다.")
st.write("-" * 50)


# --- 방법 [3] LDA를 통한 2차원 시각화 ---
st.write("=== [3] LDA 시각화 플롯 생성 ===")
lda = LinearDiscriminantAnalysis(n_components=2)
X_lda = lda.fit_transform(X, y)





# Bokeh용 데이터프레임 생성
df_lda = pd.DataFrame(X_lda, columns=['LD1', 'LD2'])
# df_lda = pd.DataFrame(X_lda, columns=['LD1'])
df_lda['Category'] = y
colors = ["red", "blue", "green", "purple"]

# 2. Bokeh Figure 생성
p = figure(title="LDA - Maximize MFE Category Separation", 
           x_axis_label='LD 1', y_axis_label='LD 2',
           width=700, height=500)

# p = figure(title="LDA - 1D MFE Category Separation", 
#            x_axis_label='LD 1', y_axis_label='Category (dummy)',
#            width=700, height=300)

# 3. 카테고리별로 스캐터 플롯 추가
for i, color in enumerate(colors):
    subset = df_lda[df_lda['Category'] == i]
    p.scatter(subset['LD1'], subset['LD2'], 
              color=color, alpha=0.6, legend_label=f"MFE Cat {i}")

# for i, color in enumerate(colors):
#     subset = df_lda[df_lda['Category'] == i]
#     # Y축이 없으므로 0을 대입하거나, 카테고리별로 약간의 Offset을 주어 겹치지 않게 할 수 있음
#     p.scatter(subset['LD1'], [0]*len(subset), 
#               color=color, alpha=0.6, legend_label=f"MFE Cat {i}")

# 4. Streamlit에서 렌더링
st.bokeh_chart(p, use_container_width=True)







import numpy as np
import pandas as pd
import streamlit as st
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource
from scipy.stats import gaussian_kde  # 밀도 계산용 (scipy 설치 필요)

st.title("MFE 분석 및 필터링 시뮬레이션")

# --- [데이터 준비] 예시용 데이터 생성 ---
np.random.seed(42)
n = 1000
df = pd.DataFrame({
    'touch_hour': np.concatenate([np.random.normal(5, 3, int(n*0.3)), np.random.normal(14, 4, int(n*0.7))]),
    'mfe_category': np.random.choice([0, 1, 2, 3], n, p=[0.3, 0.4, 0.2, 0.1])
})
df.loc[df['mfe_category'] == 0, 'touch_hour'] = np.random.normal(4, 2, len(df[df['mfe_category'] == 0]))
df['touch_hour'] = np.clip(df['touch_hour'], 0, 23)

# 이진화
df['is_trash'] = np.where(df['mfe_category'] == 0, 'Fail', 'Success')


# --- [방법 1] Bokeh 2.0 기반 KDE 플롯 구현 ---
st.write("### === [1] KDE Density Plot (Bokeh 2.0) ===")

# Bokeh 도화지 생성
p = figure(title="KDE Density Plot: Fail vs Success by Touch Hour",
           x_axis_label="First Touch Hour (0H-23H)", y_axis_label="Density",
           width=750, height=400)

# 두 그룹(Fail, Success)의 선 두께와 색상 정의
categories = ['Fail', 'Success']
colors = {'Fail': '#d62728', 'Success': '#1f77b4'} # Red, Blue

# 0부터 23시까지 밀도를 계산할 x축 포인트 생성
x_eval = np.linspace(0, 23, 200)

for cat in categories:
    subset = df[df['is_trash'] == cat]['touch_hour']
    
    # Scipy를 이용한 가우시안 커널 밀도 추정(KDE) 계산
    kde = gaussian_kde(subset)
    y_eval = kde(x_eval)
    
    # 면적 채우기(fill=True) 효과를 위해 다각형(patch) 좌표 구성 (바닥 선 닫기)
    x_patch = np.append(np.insert(x_eval, 0, x_eval[0]), x_eval[-1])
    y_patch = np.append(np.insert(y_eval, 0, 0), 0)
    
    # 데이터 소스 생성
    source = ColumnDataSource(data=dict(x=x_eval, y=y_eval, x_p=x_patch, y_p=y_patch))
    
    # 1) 면적 채우기 (Alpha 0.3)
    p.patch('x_p', 'y_p', source=source, color=colors[cat], alpha=0.3, legend_label=cat)
    # 2) 외곽선 그리기
    p.line('x', 'y', source=source, color=colors[cat], line_width=2.5, legend_label=cat)

p.legend.location = "top_right"
p.legend.click_policy = "hide"  # 범례 클릭 시 해당 그래프 숨김 기능 (Bokeh 장점)

# Streamlit에 차트 출력
st.bokeh_chart(p, use_container_width=True)
st.info("💡 안내: 위 인터랙티브 그래프에서 두 선의 높낮이 차이가 크게 벌어지는 구간이 바로 필터링 컷오프 지점입니다.")


# --- [방법 2] 실전 필터링 시뮬레이션 ---
st.write("### === [2] 실전 필터링 시뮬레이션 ===")

# Streamlit 슬라이더를 이용해 대시보드에서 컷오프 시간 조절 가능하게 변경
cutoff_hour = st.slider("컷오프 시간 설정 (H)", min_value=0.0, max_value=23.0, value=6.0, step=0.5)

raw_trash_ratio = (df['mfe_category'] == 0).mean() * 100
filtered_df = df[df['touch_hour'] > cutoff_hour]

# 결과를 텍스트 상자(code block 또는 markdown)로 대시보드에 표기
if len(filtered_df) > 0:
    new_trash_ratio = (filtered_df['mfe_category'] == 0).mean() * 100
    total_eliminated_trash = (df['mfe_category'] == 0).sum() - (filtered_df['mfe_category'] == 0).sum()
    pct_eliminated_trash = (total_eliminated_trash / (df['mfe_category'] == 0).sum()) * 100
    
    results = f"""
    필터 적용 전 순수 상태의 MFE 0~1% 비율: {raw_trash_ratio:.2f}%
    필터 적용 후 남은 진입 중 MFE 0~1% 비율: {new_trash_ratio:.2f}%
    
    ▶ 전체 쓰레기 진입(MFE 0~1%) 중 {pct_eliminated_trash:.2f}% 를 사전에 차단(Filtering) 성공했습니다.
    ▶ 살아남은 총 트레이드 기회: {len(filtered_df)} / {len(df)} 건
    """
    st.code(results, language="text")
else:
    st.warning("조건을 만족하는 데이터가 없습니다.")











import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

# 1. 스트림릿 페이지 레이아웃 설정

st.title("📊 MFE 분석 및 실전 필터링 시뮬레이션")

# --- [데이터 준비] 예시용 데이터 생성 (실제 데이터 로드 시 이 함수 내부를 수정) ---
@st.cache_data
def get_data():
    np.random.seed(42)
    n = 1000
    sample_df = pd.DataFrame({
        'touch_hour': np.concatenate([np.random.normal(5, 3, int(n*0.3)), np.random.normal(14, 4, int(n*0.7))]),
        'mfe_category': np.random.choice([0, 1, 2, 3], n, p=[0.3, 0.4, 0.2, 0.1])
    })
    # 에러 데이터(MFE 0)는 특정 시간대에 더 많이 몰려있다고 가정
    sample_df.loc[sample_df['mfe_category'] == 0, 'touch_hour'] = np.random.normal(4, 2, len(sample_df[sample_df['mfe_category'] == 0]))
    sample_df['touch_hour'] = np.clip(sample_df['touch_hour'], 0, 23)
    
    # MFE 0~1% 이면 'Fail'(Trash), 아니면 'Success'
    sample_df['is_trash'] = np.where(sample_df['mfe_category'] == 0, 'MFE 0~1% (Fail)', 'MFE 1%+ (Success)')
    return sample_df

df = get_data()

st.dataframe(df)

lda_df['is_trash'] = np.where(lda_df['mfe_category'] == 0, 'MFE 0~1% (Fail)', 'MFE 1%+ (Success)')
df = lda_df[['first_touch_hour', 'mfe_category', 'is_trash']]
df = df.rename(columns={'first_touch_hour': 'touch_hour'})

st.dataframe(df)

# --- 2. 화면 레이아웃 분할 (좌측: 차트, 우측: 시뮬레이터) ---

st.write("### [방법 1] 이진화(Binary) 및 커널 밀도(KDE) 플롯")

# 스레드 안전을 위해 figure 객체를 명시적으로 생성합니다.
fig, ax = plt.subplots(figsize=(10, 5.5))

sns.kdeplot(
    data=df, 
    x='touch_hour', 
    hue='is_trash', 
    fill=True, 
    common_norm=False, 
    palette='Set1', 
    alpha=0.4,
    ax=ax  # 생성한 축(ax)에 그리도록 지정
)

ax.set_title('KDE Density Plot: Fail vs Success by Touch Hour')
ax.set_xlabel('First Touch Hour (0H-23H)')
ax.set_ylabel('Density')
ax.grid(True, linestyle='--')

# matplotlib figure를 streamlit에 전달하여 렌더링
st.pyplot(fig)
st.info("💡 **안내:** 위 그래프에서 두 선의 높낮이 차이가 크게 벌어지는 구간(예: 특정 시간대)이 바로 필터링 컷오프 지점입니다.")


st.write("### [방법 2] 실전 필터링 시뮬레이션")

# 기존 고정값(6.0) 대신 사용자가 직접 조절 가능한 슬라이더 UI 적용
cutoff_hour = st.slider(
    "가설 적용: 첫 터치 시간 컷오프 설정 (H)", 
    min_value=0.0, 
    max_value=23.0, 
    value=6.0, 
    step=0.5,
    help="설정한 시간 이전에 첫 터치가 발생한 진입을 필터링하여 쳐냅니다."
)

st.write(f"**기준:** 첫 터치 시간 > {cutoff_hour}H 일 때만 진입")
st.markdown("---")

# 전체 진입 건수 중 MFE 0~1%의 원래 비율
raw_trash_ratio = (df['mfe_category'] == 0).mean() * 100

# 필터 조건을 만족하는 진입만 남김
filtered_df = df[df['touch_hour'] > cutoff_hour]

if len(filtered_df) > 0:
    new_trash_ratio = (filtered_df['mfe_category'] == 0).mean() * 100
    total_eliminated_trash = (df['mfe_category'] == 0).sum() - (filtered_df['mfe_category'] == 0).sum()
    pct_eliminated_trash = (total_eliminated_trash / (df['mfe_category'] == 0).sum()) * 100
    
    # 가시성을 극대화하기 위해 st.metric 컴포넌트 활용
    m_col1, m_col2 = st.columns(2)
    m_col1.metric(label="필터 전 Fail 비율", value=f"{raw_trash_ratio:.2f}%")
    m_col2.metric(label="필터 후 Fail 비율", value=f"{new_trash_ratio:.2f}%", delta=f"-{raw_trash_ratio - new_trash_ratio:.2f}%", delta_color="inverse")
    
    # 요약 결과 출력
    results_text = (
        f"▶ 전체 쓰레기 진입(MFE 0~1%) 중 {pct_eliminated_trash:.2f}%를 사전에 차단(Filtering) 성공했습니다.\n"
        f"▶ 살아남은 총 트레이드 기회: {len(filtered_df)} / {len(df)} 건"
    )
    st.code(results_text, language="text")
    
else:
    st.warning("⚠️ 조건을 만족하는 데이터가 없습니다. 컷오프 시간을 낮춰주세요.")








import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from scipy.interpolate import make_interp_spline  # 부드러운 곡선 보간용

st.subheader("MFE 그룹별 첫 터치 시간 누적 추이 비교")

# --- [1] 가상 데이터 생성 (0~23시 분포) ---
# np.random.seed(42)
# n = 1000
# df = pd.DataFrame({
#     'touch_hour': np.clip(np.concatenate([
#         np.random.normal(5, 2, int(n*0.4)),  # Fail은 초반 시간대에 몰림
#         np.random.normal(14, 4, int(n*0.6))  # Success는 후반 시간대에 몰림
#     ]), 0, 23).astype(int),
#     'mfe_category': np.random.choice([0, 1, 2, 3], n, p=[0.3, 0.4, 0.2, 0.1])
# })
# # 이진화 라벨링


# df['is_trash'] = np.where(df['mfe_category'] == 0, 'MFE 0~1% (Fail)', 'MFE 1%+ (Success)')


# --- [2] 0시~23시 구간별 '순수 빈도수' 추출 (누적 제거) ---
hours = np.arange(0, 24)

def get_hourly_counts(data, label):
    # cumsum()을 제거하고, 해당 시간대의 순수 발생 건수만 반환합니다.
    return data[data['is_trash'] == label]['touch_hour'].value_counts().reindex(hours, fill_value=0).values

fail_counts = get_hourly_counts(df, 'MFE 0~1% (Fail)')
success_counts = get_hourly_counts(df, 'MFE 1%+ (Success)')


# --- [3] Spline 보간으로 선 부드럽게 만들기 ---
x_smooth = np.linspace(0, 23, 300)

# Fail 그룹 빈도수 곡선화 (k=3: 3차 스플라인, 음수 값 방지 가공)
spl_fail = make_interp_spline(hours, fail_counts, k=3)
fail_smooth = np.clip(spl_fail(x_smooth), 0, None)

# Success 그룹 빈도수 곡선화
spl_success = make_interp_spline(hours, success_counts, k=3)
success_smooth = np.clip(spl_success(x_smooth), 0, None)


# --- [4] Matplotlib로 면적 플롯 그리기 ---
fig, ax = plt.subplots(figsize=(10, 5.5))

# Fail 그룹 (Red 면적 및 외곽선)
ax.fill_between(x_smooth, fail_smooth, color='#d62728', alpha=0.3, label='MFE 0~1% (Fail)')
ax.plot(x_smooth, fail_smooth, color='#d62728', linewidth=2)

# Success 그룹 (Blue 면적 및 외곽선)
ax.fill_between(x_smooth, success_smooth, color='#1f77b4', alpha=0.3, label='MFE 1%+ (Success)')
ax.plot(x_smooth, success_smooth, color='#1f77b4', linewidth=2)

# 차트 디테일 설정
ax.set_title('Hourly Trade Count: Fail vs Success', fontsize=14, fontweight='bold')
ax.set_xlabel('First Touch Hour (0H - 23H)', fontsize=11)
ax.set_ylabel('Trade Count (Frequency)', fontsize=11)  # Y축을 빈도수로 명시
ax.set_xticks(hours)  # 0시부터 23시까지 모든 시간 눈금 표시
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend(loc='upper right')

# Streamlit 앱 화면에 렌더링
st.pyplot(fig)





import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from scipy.interpolate import make_interp_spline  # 부드러운 곡선 보간용

st.subheader("MFE 그룹별 시간대별 발생 비율(%) 비교")



# --- [2] 0시~23시 구간별 '발생 비율(%)' 추출 ---
hours = np.arange(0, 24)

def get_hourly_percentage(data, label):
    # 1. 해당 그룹의 시간별 순수 빈도수 추출
    counts = data[data['is_trash'] == label]['touch_hour'].value_counts().reindex(hours, fill_value=0).values
    # 2. 해당 그룹의 총 건수로 나누고 100을 곱해 퍼센트(%)로 변환
    total_count = counts.sum()
    if total_count == 0:
        return np.zeros_like(hours)
    return (counts / total_count) * 100

fail_pct = get_hourly_percentage(df, 'MFE 0~1% (Fail)')
success_pct = get_hourly_percentage(df, 'MFE 1%+ (Success)')


# --- [3] Spline 보간으로 선 부드럽게 만들기 ---
x_smooth = np.linspace(0, 23, 300)

# Fail 그룹 백분율 곡선화 (음수 값 방지 가공)
spl_fail = make_interp_spline(hours, fail_pct, k=3)
fail_smooth = np.clip(spl_fail(x_smooth), 0, None)

# Success 그룹 백분율 곡선화
spl_success = make_interp_spline(hours, success_pct, k=3)
success_smooth = np.clip(spl_success(x_smooth), 0, None)


# --- [4] Matplotlib로 면적 플롯 그리기 ---
fig, ax = plt.subplots(figsize=(10, 5.5))

# Fail 그룹 (Red 면적 및 외곽선)
ax.fill_between(x_smooth, fail_smooth, color='#d62728', alpha=0.3, label='MFE 0~1% (Fail)')
ax.plot(x_smooth, fail_smooth, color='#d62728', linewidth=1)

# Success 그룹 (Blue 면적 및 외곽선)
ax.fill_between(x_smooth, success_smooth, color='#1f77b4', alpha=0.3, label='MFE 1%+ (Success)')
ax.plot(x_smooth, success_smooth, color='#1f77b4', linewidth=1)

# 차트 디테일 설정
ax.set_title('Hourly Trade Distribution (Percentage)', fontsize=14, fontweight='bold')
ax.set_xlabel('First Touch Hour (0H - 23H)', fontsize=11)
ax.set_ylabel('Percentage of Group (%)', fontsize=11)  # Y축을 퍼센트로 명시
ax.set_xticks(hours)  # 0시부터 23시까지 모든 시간 눈금 표시
ax.grid(True, linestyle='--', alpha=0.5)

# 지원하는 올바른 loc 값인 'upper right'로 적용
ax.legend(loc='upper right')

# Streamlit 앱 화면에 렌더링
st.pyplot(fig)