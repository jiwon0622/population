import json
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Streamlit 페이지 설정
st.set_page_config(page_title="전국 고령화 단계구분도", layout="wide")
st.title("📊 전국 시군구별 고령화율 단계구분도 (2026년 6월 기준)")


@st.cache_data
def load_data():
    # 1. 인구 데이터 로드 (Raw URL 사용)
    csv_url = "https://raw.githubusercontent.com/jiwon0622/population/main/population_ts_yearly_gender.zip"
    df = pd.read_csv(csv_url, encoding="utf-8-sig")

    # 2026년 데이터만 필터링
    df_2026 = df[df["연도"].astype(str) == "2026"].copy()

    # 동 코드를 문자열로 변환 후 앞 5자리(시군구 코드) 추출
    df_2026["sigungu_code"] = df_2026["코드"].astype(str).str.zfill(10).str[:5]

    # 2. 인구 컬럼 구분
    # 전체 인구: '계_'로 시작하는 모든 열의 합
    total_cols = [c for c in df_2026.columns if c.startswith("계_")]

    # 65세 이상 인구: '계_65세' ~ '계_99세', '계_100세 이상'
    elderly_cols = [f"계_{i}세" for i in range(65, 100)]
    for col_100 in ["계_100세 이상", "계_100세이상"]:
        if col_100 in df_2026.columns:
            elderly_cols.append(col_100)

    # 존재하는 컬럼만 선택
    total_cols = [c for c in total_cols if c in df_2026.columns]
    elderly_cols = [c for c in elderly_cols if c in df_2026.columns]

    # 3. 시군구별 인구 집계
    df_2026["전체인구"] = df_2026[total_cols].sum(axis=1)
    df_2026["고령인구"] = df_2026[elderly_cols].sum(axis=1)

    grouped = (
        df_2026.groupby("sigungu_code")[["전체인구", "고령인구"]]
        .sum()
        .reset_index()
    )

    # 고령화율(%) 계산
    grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"]) * 100
    grouped["고령화율"] = grouped["고령화율"].round(2)

    # 4. 시군구 GeoJSON 로드 (Raw URL 사용)
    geojson_url = "https://raw.githubusercontent.com/jiwon0622/population/main/sigungu_kr.geojson.txt"
    response = requests.get(geojson_url)
    geojson_data = response.json()

    # GeoJSON 속성에서 시군구 이름 및 시도 이름 매핑 (마우스 오버 툴팁용)
    code_to_name = {}
    for feature in geojson_data["features"]:
        props = feature["properties"]
        code_str = str(props["코드"])
        sido_name = props.get("시도", "")
        sigungu_name = props.get("시군구", "")
        fullname = f"{sido_name} {sigungu_name}".strip()
        code_to_name[code_str] = fullname if fullname else sigungu_name

    grouped["시군구명"] = grouped["sigungu_code"].map(code_to_name)

    return grouped, geojson_data


# 데이터 로딩
with st.spinner("데이터를 로딩하고 지도를 생성 중입니다..."):
    df_sigungu, geojson_data = load_data()

# Plotly 단계구분도 (Choropleth Map) 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations="sigungu_code",  # 데이터프레임의 시군구 코드 (문자열)
    featureidkey="properties.코드",  # GeoJSON의 코드 속성
    color="고령화율",
    color_continuous_scale="Reds",  # 고령화율이 높을수록 진하게
    mapbox_style="white-bg",  # 배경 타일 없이 경계만 그리기
    hover_name="시군구명",
    hover_data={"sigungu_code": False, "고령화율": ":.2f%"},
    labels={"고령화율": "고령화율 (%)"},
)

# 대한민국 중심 좌표 및 카메라 시점 설정
fig.update_layout(
    mapbox=dict(
        center={"lat": 35.8, "lon": 127.8},
        zoom=6.0,
    ),
    margin={"r": 0, "t": 30, "l": 0, "b": 0},
    height=750,
)

# 시군구 경계선 스타일 적용 (회색 실선)
fig.update_traces(marker_line_width=0.5, marker_line_color="gray")

# Streamlit에 지도 출력
st.plotly_chart(fig, use_container_width=True)

# 하단 데이터 요약 테이블
with st.expander("📌 시군구별 상세 데이터 보기"):
    st.dataframe(
        df_sigungu[["sigungu_code", "시군구명", "전체인구", "고령인구", "고령화율"]]
        .sort_values(by="고령화율", ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
    )
