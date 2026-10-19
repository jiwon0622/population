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
    layout="wide",
)

# --------------------------------------------------
# 2. 따뜻한 크림색 디자인
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
    .notice {
        color: #A33A2B;
        font-weight: 700;
        font-size: 0.95rem;
        margin-top: -0.35rem;
        margin-bottom: 0.6rem;
    }
    .insight {
        background-color: #FFF0D9;
        border-left: 5px solid #D99A58;
        padding: 14px 18px;
        border-radius: 8px;
        color: #5C4432;
        font-size: 1.05rem;
        margin-top: 0.8rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    "우리 동네의 연령별 인구 구성을 살펴보세요. "
    "남성은 왼쪽, 여성은 오른쪽에 표시됩니다."
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
    # URL의 ZIP 압축 파일을 pandas가 직접 읽는다.
    df = pd.read_csv(DATA_URL, encoding="utf-8-sig")
    df.columns = df.columns.astype(str).str.strip()

    # 연도 열을 숫자로 바꾸고, 연도가 없는 행은 제외한다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 지역명 앞뒤의 공백을 정리한다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].astype("string").str.strip()

    return df


try:
    df = load_data()
except Exception:
    st.error(
        "인구 데이터를 불러오지 못했어요. "
        "인터넷 연결과 GitHub 데이터 주소를 확인해 주세요."
    )
    st.stop()

# --------------------------------------------------
# 4. 가장 최신 연도만 사용
# --------------------------------------------------
latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()
st.caption(f"📅 분석 기준 연도: {latest_year}년")

# --------------------------------------------------
# 5. 나이별 남녀 인구 열 확인
# --------------------------------------------------
# 0~99세와 100세 이상을 순서대로 만든다.
age_labels = [f"{age}세" for age in range(100)] + ["100세 이상"]
male_cols = [f"남_{age}" for age in age_labels]
female_cols = [f"여_{age}" for age in age_labels]

required_cols = ["시도", "시군구", "동"] + male_cols + female_cols
missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    st.error(
        "데이터에서 필요한 열을 찾지 못했어요. "
        "CSV의 열 이름을 확인해 주세요."
    )
    st.write("찾을 수 없는 열:", ", ".join(missing_cols[:12]))
    st.stop()

# 인구 열을 숫자로 변환한다. 비어 있거나 잘못된 값은 0으로 처리한다.
population_cols = male_cols + female_cols
for col in population_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# --------------------------------------------------
# 6. 시도 → 시군구 → 동 선택
# --------------------------------------------------
st.subheader("📍 지역 선택")

sido_list = sorted(df["시도"].dropna().unique().tolist())
if not sido_list:
    st.warning("선택할 수 있는 시도 데이터가 없습니다.")
    st.stop()

selected_sido = st.selectbox("① 시도", sido_list, key="selected_sido")
sido_df = df[df["시도"] == selected_sido]

sigungu_list = sorted(sido_df["시군구"].dropna().unique().tolist())
if not sigungu_list:
    st.warning("해당 시도에 시군구 데이터가 없습니다.")
    st.stop()

selected_sigungu = st.selectbox(
    "② 시군구", sigungu_list, key="selected_sigungu"
)
sigungu_df = sido_df[sido_df["시군구"] == selected_sigungu]

dong_list = sorted(sigungu_df["동"].dropna().unique().tolist())
if not dong_list:
    st.warning("해당 시군구에 동 데이터가 없습니다.")
    st.stop()

selected_dong = st.selectbox("③ 동", dong_list, key="selected_dong")
selected_df = sigungu_df[sigungu_df["동"] == selected_dong]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없습니다.")
    st.stop()

# 지역이 여러 행으로 나뉘어 있으면 연령별 인구를 합산한다.
population = selected_df[population_cols].sum()

# --------------------------------------------------
# 7. 연령별 남녀 인구 계산
# --------------------------------------------------
male_population = np.array(
    [population[col] for col in male_cols], dtype=float
)
female_population = np.array(
    [population[col] for col in female_cols], dtype=float
)

male_population = np.rint(male_population).astype(int)
female_population = np.rint(female_population).astype(int)

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female

# --------------------------------------------------
# 8. 지표 계산
# --------------------------------------------------
# 연령별 인구의 합계를 이용한 가중평균 연령을 계산한다.
# '100세 이상'은 정확한 나이를 알 수 없어 100세로 간주한다.
age_numbers = np.arange(101, dtype=float)
combined_by_age = male_population + female_population

if total_population > 0:
    average_age = float(
        np.dot(age_numbers, combined_by_age) / total_population
    )
else:
    average_age = 0.0

# 65세 이상 인구와 고령화율을 계산한다.
# age_labels의 인덱스 65부터 100세 이상까지가 65세 이상이다.
elderly_population = int(combined_by_age[65:].sum())
elderly_rate = (
    elderly_population / total_population * 100
    if total_population > 0
    else 0.0
)

# 아동 인구는 0~14세로 정의해 고령 인구와 비교한다.
child_population = int(combined_by_age[:15].sum())

# --------------------------------------------------
# 9. 지표 카드 3개
# --------------------------------------------------
st.divider()
st.subheader(f"📊 {selected_sido} {selected_sigungu} {selected_dong} 주요 지표")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric("👥 총인구", f"{total_population:,}명")

with card2:
    st.metric("🎂 평균연령", f"{average_age:.1f}세")

with card3:
    # 고령화율이 20%를 초과할 때 카드 제목에 주의 표시를 붙인다.
    elderly_label = (
        "⚠️ 고령화율" if elderly_rate > 20 else "👵 고령화율"
    )
    st.metric(elderly_label, f"{elderly_rate:.1f}%")
    if elderly_rate > 20:
        st.markdown(
            '<div class="notice">⚠️ 고령화율이 20%를 넘습니다.</div>',
            unsafe_allow_html=True,
        )

# --------------------------------------------------
# 10. 인구 피라미드 그래프
# --------------------------------------------------
fig = go.Figure()

# 남성은 음수로 바꾸어 중앙 왼쪽에 표시한다.
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=-male_population,
        name="남성",
        orientation="h",
        marker_color="#7C9CC4",
        customdata=male_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
    )
)

# 여성은 양수로 두어 중앙 오른쪽에 표시한다.
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
        ),
    )
)

# 좌우 축의 범위를 같게 만들어 비교하기 쉽게 한다.
max_population = max(
    int(male_population.max()),
    int(female_population.max()),
    1,
)
tick_step = max(1, int(np.ceil(max_population / 5 / 100)) * 100)
axis_limit = int(np.ceil(max_population / tick_step) * tick_step)
tick_values = list(range(-axis_limit, axis_limit + 1, tick_step))
tick_text = [f"{abs(value):,}" for value in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 인구 피라미드 ({latest_year}년)",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1050,
    paper_bgcolor="#FFF9EF",
    plot_bgcolor="#FFF9EF",
    font={"family": "Arial, sans-serif", "color": "#49382B", "size": 12},
    legend={
        "title": "성별",
        "orientation": "h",
        "y": 1.03,
        "x": 0.5,
        "xanchor": "center",
    },
    margin={"l": 100, "r": 45, "t": 100, "b": 80},
    xaxis={
        "title": "인구 수 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinewidth": 2,
        "zerolinecolor": "#9A806B",
        "gridcolor": "#EADFD1",
    },
    yaxis={
        "title": "나이",
        # 나이 라벨 순서를 직접 지정한다.
        # 축을 뒤집지 않고 0세가 아래, 100세 이상이 위에 오도록 한다.
        "categoryorder": "array",
        "categoryarray": age_labels,
        "tickmode": "array",
        "tickvals": age_labels,
        "ticktext": age_labels,
        "automargin": True,
    },
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "※ 세로축은 아래에서 위로 0세 → 100세 이상 순서입니다. "
    "남성은 왼쪽, 여성은 오른쪽이며 왼쪽 눈금은 인구 수의 절댓값입니다."
)

# --------------------------------------------------
# 11. 동네 연령 구조 한 줄 설명
# --------------------------------------------------
st.subheader("💡 우리 동네 연령 특징")

if total_population == 0:
    insight = "인구 자료가 없어 연령 구조를 비교하기 어렵습니다."
elif child_population > elderly_population:
    insight = (
        f"이 동네는 0~14세 인구({child_population:,}명)가 "
        f"65세 이상 인구({elderly_population:,}명)보다 많아 "
        "상대적으로 아이가 많은 편이에요."
    )
elif elderly_population > child_population:
    insight = (
        f"이 동네는 65세 이상 인구({elderly_population:,}명)가 "
        f"0~14세 인구({child_population:,}명)보다 많아 "
        "상대적으로 어르신이 많은 편이에요."
    )
else:
    insight = (
        f"이 동네는 0~14세 인구와 65세 이상 인구가 "
        f"각각 {child_population:,}명으로 같아요."
    )

st.markdown(
    f'<div class="insight">{insight}</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# 12. 연령별 인구 표
# --------------------------------------------------
with st.expander("📋 연령별 남녀 인구 표 보기"):
    age_table = pd.DataFrame(
        {
            "나이": age_labels,
            "남성 인구": male_population,
            "여성 인구": female_population,
        }
    )
    age_table["합계"] = (
        age_table["남성 인구"] + age_table["여성 인구"]
    )
    st.dataframe(age_table, hide_index=True, use_container_width=True)

# --------------------------------------------------
# 13. 데이터 출처 및 지표 안내
# --------------------------------------------------
st.divider()
st.caption(
    "데이터 출처: first2022-cyber/contents GitHub 저장소의 "
    "population_ts_yearly_gender.zip"
)
st.caption(
    "지표 안내: 고령화율은 65세 이상 인구 비율이며, "
    "아이 인구는 0~14세로 계산했습니다. "
    "평균연령은 연령별 인구를 이용한 추정치이며 "
    "'100세 이상'은 계산 편의상 100세로 간주합니다."
)
