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

    # GeoJSON 내 속성의 '코드'를 문자열 5자리로 보정 및 feature id 부여
    geojson_codes = set()
    sigungu_info = {}

    for feature in geojson_data["features"]:
        props = feature["properties"]
        code = str(props["코드"]).split(".")[0].zfill(5)
        props["코드"] = code
        feature["id"] = code  # Plotly choropleth 매핑용 ID 추가

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
    metric_label = "유소년
