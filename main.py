import json
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Streamlit 페이지 설정
st.set_page_config(page_title="전국 인구구조 단계구분도", layout="wide")
st.title("📊 전국 시군구별 인구구조 단계구분도")


@st.cache_data
def load_base_data():
    # 1. 인구 데이터 로드 (Raw URL 사용)
    csv_url = "https://raw.githubusercontent.com/jiwon0622/population/main/population_ts_yearly_gender.zip"
    df = pd.read_csv(csv_url, encoding="utf-8-sig")

    # 2. GeoJSON 로드 (Raw URL 사용)
    geojson_url = "https://raw.githubusercontent.com/jiwon0622/population/main/sigungu_kr.geojson.txt"
    response = requests.get(geojson_url)
    geojson_data = response.json()

    # GeoJSON 내부 속성의 '코드'를 문자열 5자리로 확정 보정
    geojson_codes = set()
    sigungu_info = {}

    for feature in geojson_data["features"]:
        props = feature["properties"]
        # 숫자로 들어왔거나 소수점이 붙었을 경우 보정
        code = str(props["코드"]).split(".")[0].zfill(5)
        props["코드"] = code  # properties.코드 값을 5자리 문자열로 통일
        feature["id"] = code  # feature id도 동일하게 통일

        sido_name = props.get("시도", "")
        sigungu_name = props.get("시군구", "")
        fullname = f"{sido_name} {sigungu_name}".strip()

        geojson_codes.add(code)
        sigungu_info[code] = {
            "sido": sido_name,
            "sigungu": sigungu_name,
            "fullname": fullname if fullname else sigungu_name,
        }

    return df, geojson_data, geojson_codes, sigungu_info


# 기본 데이터 로드
with st.spinner("기초 데이터 및 지도 경계를 불러오는 중입니다..."):
    df_raw, geojson_data, geojson_codes, sigungu_info = load_base_data()

# -----------------------------------------------------------------------------
# 사이드바 설정
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ 검색 및 필터 설정")

# 1. 연도 선택 슬라이더 (2015 ~ 2026)
available_years = sorted(
    [int(y) for y in df_raw["연도"].astype(str).unique() if y.isdigit()]
)
selected_year = st.sidebar.slider(
    "연도 선택",
    min_value=min(available_years),
    max_value=max(available_years),
    value=max(available_years),
    step=1,
)

# 2. 지표 선택
metric_option = st.sidebar.selectbox(
    "지표 선택", ["고령화율 (65세 이상 %)", "유소년 비율 (0~14세 %)"]
)

# 3. 시도 선택 드롭다운
sido_list = ["전국"] + sorted(
    list(
        set(
            info["sido"] for info in sigungu_info.values() if info["sido"] != ""
        )
    )
)
selected_sido = st.sidebar.selectbox("시도 선택", sido_list)


# -----------------------------------------------------------------------------
# 연도별 데이터 전처리 함수
# -----------------------------------------------------------------------------
def process_data(df, year):
    df_yr = df[df["연도"].astype(str) == str(year)].copy()

    # 1. 동 코드를 문자열로 변환 후 앞 5자리(시군구 코드) 추출
    df_yr["sigungu_code"] = (
        df_yr["코드"].astype(str).str.split(".").str[0].str.zfill(10).str[:5]
    )

    # 2. 행정구역 개편 보정 (강원: 42->51, 전북: 45->52, 군위군: 47720->27720)
    code_remap = {"47720": "27720"}

    def remap_code(code):
        if code in code_remap:
            return code_remap[code]
        if code.startswith("42"):
            return "51" + code[2:]
        if code.startswith("45"):
            return "52" + code[2:]
        return code

    df_yr["sigungu_code"] = df_yr["sigungu_code"].apply(remap_code)

    # 3. 인구 집계 컬럼 정의
    total_cols = [c for c in df_yr.columns if c.startswith("계_")]

    # 65세 이상 (고령)
    elderly_cols = [f"계_{i}세" for i in range(65, 100)]
    elderly_cols += [c for c in ["계_100세 이상", "계_100세이상"] if c in df_yr.columns]

    # 0~14세 (유소년)
    youth_cols = [f"계_{i}세" for i in range(0, 15)]

    total_cols = [c for c in total_cols if c in df_yr.columns]
    elderly_cols = [c for c in elderly_cols if c in df_yr.columns]
    youth_cols = [c for c in youth_cols if c in df_yr.columns]

    df_yr["전체인구"] = df_yr[total_cols].sum(axis=1)
    df_yr["고령인구"] = df_yr[elderly_cols].sum(axis=1)
    df_yr["유소년인구"] = df_yr[youth_cols].sum(axis=1)

    grouped = (
        df_yr.groupby("sigungu_code")[["전체인구", "고령인구", "유소년인구"]]
        .sum()
        .reset_index()
    )

    grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"]) * 100
    grouped["유소년비율"] = (grouped["유소년인구"] / grouped["전체인구"]) * 100

    # 시군구 명칭 매핑
    grouped["시도"] = grouped["sigungu_code"].apply(
        lambda x: sigungu_info.get(x, {}).get("sido", "기타")
    )
    grouped["시군구명"] = grouped["sigungu_code"].apply(
        lambda x: sigungu_info.get(x, {}).get("fullname", "미매핑 지역")
    )

    return grouped


df_processed = process_data(df_raw, selected_year)

# 선택된 시도 필터링
if selected_sido != "전국":
    df_view = df_processed[df_processed["시도"] == selected_sido].copy()
else:
    df_view = df_processed.copy()

# 지표 및 구간 설정
if "고령화율" in metric_option:
    target_metric = "고령화율"
    metric_label = "고령화율 (%)"

    # 고령화율 색 구간 (19, 23, 28, 38%)
    bins = [-np.inf, 19, 23, 28, 38, np.inf]
    labels = ["19% 미만", "19% ~ 23%", "23% ~ 28%", "28% ~ 38%", "38% 이상"]
    color_discrete_map = {
        "19% 미만": "#fee5d9",
        "19% ~ 23%": "#fcae91",
        "23% ~ 28%": "#fb6a4a",
        "28% ~ 38%": "#de2d26",
        "38% 이상": "#a50f15",
    }
else:
    target_metric = "유소년비율"
    metric_label = "유소년 비율 (%)"

    # 유소년 비율 맞춤 색 구간 (7, 10, 13, 16%)
    bins = [-np.inf, 7, 10, 13, 16, np.inf]
    labels = ["7% 미만", "7% ~ 10%", "10% ~ 13%", "13% ~ 16%", "16% 이상"]
    color_discrete_map = {
        "7% 미만": "#eff3ff",
        "7% ~ 10%": "#bdd7e7",
        "10% ~ 13%": "#6baed6",
        "13% ~ 16%": "#3182bd",
        "16% 이상": "#08519c",
    }

# 데이터프레임에 구간 범주(Category) 추가
df_processed["구간"] = pd.cut(
    df_processed[target_metric], bins=bins, labels=labels
)


# -----------------------------------------------------------------------------
# 상단 지표 카드 3개
# -----------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)

total_pop = df_view["전체인구"].sum()
sub_pop = (
    df_view["고령인구"].sum()
    if "고령화율" in metric_option
    else df_view["유소년인구"].sum()
)
avg_rate = (sub_pop / total_pop * 100) if total_pop > 0 else 0

valid_df = df_view[df_view["시군구명"] != "미매핑 지역"]
if not valid_df.empty:
    max_row = valid_df.loc[valid_df[target_metric].idxmax()]
    min_row = valid_df.loc[valid_df[target_metric].idxmin()]

    max_str = f"{max_row['시군구명']} ({max_row[target_metric]:.2f}%)"
    min_str = f"{min_row['시군구명']} ({min_row[target_metric]:.2f}%)"
else:
    max_str = "-"
    min_str = "-"

region_title = "전국" if selected_sido == "전국" else selected_sido

col1.metric(f"📍 {region_title} 평균 {target_metric}", f"{avg_rate:.2f}%")
col2.metric(f"🔴 가장 높은 시군구", max_str)
col3.metric(f"🔵 가장 낮은 시군구", min_str)

st.markdown("---")

# -----------------------------------------------------------------------------
# 시도별 중심 위치 및 확대 레벨 (Zoom) 설정
# -----------------------------------------------------------------------------
sido_centers = {
    "전국": {"lat": 35.8, "lon": 127.8, "zoom": 6.0},
    "서울특별시": {"lat": 37.5665, "lon": 126.9780, "zoom": 9.5},
    "부산광역시": {"lat": 35.1796, "lon": 129.0756, "zoom": 9.5},
    "대구광역시": {"lat": 35.8714, "lon": 128.6014, "zoom": 9.0},
    "인천광역시": {"lat": 37.4563, "lon": 126.7052, "zoom": 9.0},
    "광주광역시": {"lat": 35.1595, "lon": 126.8526, "zoom": 10.0},
    "대전광역시": {"lat": 36.3504, "lon": 127.3845, "zoom": 10.0},
    "울산광역시": {"lat": 35.5384, "lon": 129.3114, "zoom": 9.5},
    "세종특별자치시": {"lat": 36.4800, "lon": 127.2890, "zoom": 10.5},
    "경기도": {"lat": 37.4138, "lon": 127.5183, "zoom": 8.0},
    "강원특별자치도": {"lat": 37.8228, "lon": 128.1555, "zoom": 7.8},
    "충청북도": {"lat": 36.6357, "lon": 127.4912, "zoom": 8.2},
    "충청남도": {"lat": 36.5184, "lon": 126.8000, "zoom": 8.2},
    "전북특별자치도": {"lat": 35.7175, "lon": 127.1530, "zoom": 8.2},
    "전라남도": {"lat": 34.8161, "lon": 126.4629, "zoom": 7.8},
    "경상북도": {"lat": 36.5760, "lon": 128.5056, "zoom": 7.8},
    "경상남도": {"lat": 35.4606, "lon": 128.2132, "zoom": 8.0},
    "제주특별자치도": {"lat": 33.4996, "lon": 126.5312, "zoom": 9.0},
}

map_config = sido_centers.get(
    selected_sido, {"lat": 35.8, "lon": 127.8, "zoom": 6.0}
)

# -----------------------------------------------------------------------------
# Plotly Choropleth Map 생성 (px.choropleth_map)
# -----------------------------------------------------------------------------
fig = px.choropleth_map(
    df_processed,
    geojson=geojson_data,
    locations="sigungu_code",  # DataFrame 매핑 열
    featureidkey="properties.코드",  # GeoJSON 매핑 키
    color="구간",
    color_discrete_map=color_discrete_map,
    category_orders={"구간": labels},
    map_style="white-bg",  # 배경 타일 없이 경계선만 표기
    center={"lat": map_config["lat"], "lon": map_config["lon"]},
    zoom=map_config["zoom"],
    hover_name="시군구명",
    hover_data={
        "sigungu_code": False,
        "구간": False,
        target_metric: ":.2f%",
    },
    labels={target_metric: metric_label, "구간": "비율 구간"},
)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=720,
)

fig.update_traces(marker_line_width=0.5, marker_line_color="gray")

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 미매핑(회색 영역) 지역 안내
# -----------------------------------------------------------------------------
unmapped_codes = geojson_codes - set(df_processed["sigungu_code"])

if unmapped_codes:
    unmapped_names = [
        f"{sigungu_info[code]['fullname']}({code})"
        for code in unmapped_codes
        if code in sigungu_info
    ]
    st.info(
        f"💡 **안내**: 인구 데이터와 행정구역 경계 코드가 일치하지 않거나 해당 연도 데이터가 존재하지 않는 일부 지역은 지도에 **회색**으로 표시됩니다.\n"
        f"- 미매핑/데이터 미비 지역: {', '.join(unmapped_names) if unmapped_names else '없음'}"
    )

# 하단 상세 데이터표
with st.expander(f"📌 {selected_year}년 {selected_sido} 시군구별 상세 데이터 보기"):
    st.dataframe(
        df_view[
            [
                "sigungu_code",
                "시군구명",
                "전체인구",
                "고령인구",
                "유소년인구",
                "고령화율",
                "유소년비율",
            ]
        ]
        .sort_values(by=target_metric, ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
    )
