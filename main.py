# main.py
# 동네별 인구 피라미드
# Streamlit Cloud에서 실행하는 앱

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)


# --------------------------------------------------
# 2. 따뜻한 크림색 디자인 설정
# --------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9EF;
        color: #49382B;
    }

    h1, h2, h3 {
        color: #6E4935 !important;
    }

    div[data-testid="stSelectbox"] label {
        color: #76543E;
        font-weight: bold;
        font-size: 16px;
    }

    div[data-testid="stMetric"] {
        background-color: #FFF0D9;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #F0D7B5;
    }

    div[data-testid="stAlert"] {
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# --------------------------------------------------
# 3. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents/main/"
    "population_ts_yearly_gender.zip"
)


@st.cache_data
def load_data():
    # ZIP 파일 안의 CSV를 판다스로 읽는다.
    # URL이 .zip으로 끝나므로 압축 형식은 자동으로 인식된다.
    df = pd.read_csv(DATA_URL, encoding="utf-8-sig")

    # 열 이름 앞뒤에 불필요한 공백이 있다면 제거한다.
    df.columns = df.columns.astype(str).str.strip()

    # 연도는 숫자로 변환한다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")

    # 연도 정보가 없는 행은 제외한다.
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 지역 이름의 공백을 정리한다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].astype("string").str.strip()

    return df


# --------------------------------------------------
# 4. 데이터 불러오기 오류 처리
# --------------------------------------------------
st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    "우리 동네의 연령별 인구 구성을 살펴보세요. "
    "남성은 왼쪽, 여성은 오른쪽에 표시됩니다."
)

try:
    df = load_data()
except Exception as e:
    st.error(
        "인구 데이터를 불러오지 못했어요. "
        "인터넷 연결이나 GitHub 데이터 주소를 확인해 주세요."
    )
    st.exception(e)
    st.stop()


# --------------------------------------------------
# 5. 가장 최신 연도만 선택
# --------------------------------------------------
latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()

st.caption(f"📅 분석 기준 연도: {latest_year}년")


# --------------------------------------------------
# 6. 나이별 남녀 인구 열 찾기
# --------------------------------------------------
# 0세부터 99세까지, 마지막은 100세 이상으로 구성한다.
age_labels = [f"{age}세" for age in range(100)]
age_labels.append("100세 이상")

# 실제 데이터의 열 이름 형식에 맞춰 남녀 인구 열을 만든다.
male_cols = [f"남_{age}" for age in age_labels]
female_cols = [f"여_{age}" for age in age_labels]

# 지역 열과 연령별 인구 열이 실제로 존재하는지 확인한다.
required_cols = ["시도", "시군구", "동"] + male_cols + female_cols
missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    st.error(
        "데이터에서 필요한 열을 찾지 못했어요. "
        "CSV의 열 이름을 확인해 주세요."
    )
    st.write("찾을 수 없는 열 예시:", missing_cols[:10])
    st.stop()

# 인구 데이터가 문자로 읽혀도 숫자로 계산할 수 있도록 변환한다.
population_cols = male_cols + female_cols

for col in population_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


# --------------------------------------------------
# 7. 시도 → 시군구 → 동 드롭다운
# --------------------------------------------------
st.subheader("📍 지역 선택")

# 첫 번째 드롭다운: 시도
sido_list = sorted(df["시도"].dropna().unique().tolist())

if not sido_list:
    st.warning("선택할 수 있는 시도 데이터가 없습니다.")
    st.stop()

selected_sido = st.selectbox(
    "① 시도",
    sido_list,
    key="selected_sido"
)

# 선택한 시도에 해당하는 데이터만 남긴다.
sido_df = df[df["시도"] == selected_sido]

# 두 번째 드롭다운: 시군구
sigungu_list = sorted(
    sido_df["시군구"].dropna().unique().tolist()
)

if not sigungu_list:
    st.warning("해당 시도에 시군구 데이터가 없습니다.")
    st.stop()

selected_sigungu = st.selectbox(
    "② 시군구",
    sigungu_list,
    key="selected_sigungu"
)

# 선택한 시도와 시군구에 해당하는 데이터만 남긴다.
sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
]

# 세 번째 드롭다운: 동
dong_list = sorted(
    sigungu_df["동"].dropna().unique().tolist()
)

if not dong_list:
    st.warning("해당 시군구에 동 데이터가 없습니다.")
    st.stop()

selected_dong = st.selectbox(
    "③ 동",
    dong_list,
    key="selected_dong"
)

# 선택한 동네의 행만 추출한다.
selected_df = sigungu_df[
    sigungu_df["동"] == selected_dong
]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

# 동일한 지역이 여러 행에 나뉘어 있다면 연령별로 합산한다.
# 이렇게 하면 선택한 동네의 인구가 한 행으로 정리된다.
population = selected_df[population_cols].sum()


# --------------------------------------------------
# 8. 나이별 남녀 인구 계산
# --------------------------------------------------
# 남성은 왼쪽으로 보이도록 음수로 바꾼다.
male_population = np.array(
    [population[col] for col in male_cols],
    dtype=float
)

# 여성은 오른쪽으로 보이도록 양수로 유지한다.
female_population = np.array(
    [population[col] for col in female_cols],
    dtype=float
)

# 인구 수가 소수로 표시되지 않도록 정수로 변환한다.
male_population = np.rint(male_population).astype(int)
female_population = np.rint(female_population).astype(int)

# 남녀 전체 인구를 계산한다.
total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# --------------------------------------------------
# 9. 요약 숫자 표시
# --------------------------------------------------
st.divider()
st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    label="전체 인구",
    value=f"{total_population:,}명"
)

metric2.metric(
    label="남성 인구",
    value=f"{total_male:,}명"
)

metric3.metric(
    label="여성 인구",
    value=f"{total_female:,}명"
)


# --------------------------------------------------
# 10. 인구 피라미드 그래프 만들기
# --------------------------------------------------
fig = go.Figure()

# 남성: 음수 값을 사용해 중앙 왼쪽에 표시한다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=-male_population,
        name="남성",
        orientation="h",
        marker_color="#7C9CC4",
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
        customdata=male_population
    )
)

# 여성: 양수 값을 사용해 중앙 오른쪽에 표시한다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_population,
        name="여성",
        orientation="h",
        marker_color="#E8A28F",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,}명"
            "<extra></extra>"
        )
    )
)

# 좌우가 균형 있게 보이도록 양쪽 축 범위를 동일하게 설정한다.
max_population = max(
    int(male_population.max()),
    int(female_population.max()),
    1
)

# 눈금 간격을 적당한 크기로 정한다.
tick_step = max(1, int(np.ceil(max_population / 5 / 100)) * 100)
axis_limit = int(np.ceil(max_population / tick_step) * tick_step)

tick_values = list(range(-axis_limit, axis_limit + 1, tick_step))

# 왼쪽의 음수 눈금도 양수 인구 수로 읽히도록 라벨을 바꾼다.
tick_text = [f"{abs(value):,}" for value in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 인구 피라미드 ({latest_year}년)",
        "x": 0.5,
        "xanchor": "center"
    },
    barmode="overlay",
    bargap=0.12,
    height=1050,
    paper_bgcolor="#FFF9EF",
    plot_bgcolor="#FFF9EF",
    font={
        "family": "Arial, sans-serif",
        "color": "#49382B",
        "size": 12
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "y": 1.03,
        "x": 0.5,
        "xanchor": "center"
    },
    margin={
        "l": 100,
        "r": 45,
        "t": 100,
        "b": 80
    },
    xaxis
