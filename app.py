"""
서울 지하철 실시간 열차 위치 (출발 시각 추천 서비스 베타)

서울시 '지하철 실시간 열차 위치정보' API로 노선별 운행 열차를 보여준다.
인증키는 Streamlit secrets 의 SEOUL_SUBWAY_KEY 에 넣는다 (코드에 적지 않는다).
"""

import os
from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import requests
import streamlit as st

KST = timezone(timedelta(hours=9))
URL = "http://swopenapi.seoul.go.kr/api/subway/{key}/json/realtimePosition/0/1000/{line}"
LINES = ["1호선", "2호선", "3호선", "4호선", "5호선", "6호선", "7호선", "8호선", "9호선"]
STATUS = {"0": "진입", "1": "도착", "2": "출발", "3": "전역출발"}

st.set_page_config(page_title="지하철 실시간 열차 위치", page_icon="🚇", layout="wide")


def get_key():
    try:
        return st.secrets["SEOUL_SUBWAY_KEY"]
    except Exception:
        return os.environ.get("SEOUL_SUBWAY_KEY", "")


@st.cache_data(ttl=30, show_spinner=False)
def fetch(line):
    """30초 동안은 같은 결과를 재사용해 하루 호출 한도를 아낀다."""
    r = requests.get(URL.format(key=get_key(), line=line), timeout=10)
    body = r.json()
    items = body.get("realtimePositionList") or []
    msg = (body.get("errorMessage") or {}).get("message", "")
    return items, msg, datetime.now(KST)


def direction(line, updn):
    if line == "2호선":
        return "내선" if str(updn) == "0" else "외선"
    return "상행" if str(updn) == "0" else "하행"


st.title("🚇 서울 지하철 실시간 열차 위치")
st.caption("출근길 출발 시각 추천 서비스의 베타 화면입니다. 지금 노선 위에 있는 열차와 상태를 보여줍니다.")

line = st.selectbox("노선", LINES, index=1)

if not get_key():
    st.error("인증키가 설정되지 않았습니다. secrets 에 SEOUL_SUBWAY_KEY 를 넣어 주세요.")
    st.stop()

try:
    items, msg, fetched = fetch(line)
except Exception as e:
    st.error(f"데이터를 불러오지 못했습니다: {type(e).__name__}")
    st.stop()

if not items:
    st.warning(f"지금 운행 정보가 없습니다. {msg}")
    st.stop()

df = pd.DataFrame(items)
df["방향"] = [direction(line, u) for u in df.get("updnLine", "")]
df["상태"] = df.get("trainSts", "").astype(str).map(STATUS).fillna("-")
df["급행"] = df.get("directAt", "").astype(str).map({"1": "급행", "7": "특급"}).fillna("")
df["역순서"] = pd.to_numeric(df.get("statnId", 0), errors="coerce")

c1, c2, c3 = st.columns(3)
c1.metric("운행 중인 열차", f"{len(df)}대")
c2.metric("조회 시각", fetched.strftime("%H:%M:%S"))
c3.metric("데이터 생성 시각", str(df["recptnDt"].max())[-8:] if "recptnDt" in df else "-")

order = df.sort_values("역순서")["statnNm"].drop_duplicates().tolist()
chart = (
    alt.Chart(df)
    .mark_circle(size=160)
    .encode(
        x=alt.X("statnNm:N", sort=order, title="역 (역 ID 순)", axis=alt.Axis(labelAngle=-60)),
        y=alt.Y("방향:N", title=None),
        color=alt.Color("상태:N", title="상태"),
        tooltip=["trainNo", "statnNm", "방향", "상태", "statnTnm", "급행", "recptnDt"],
    )
    .properties(height=220)
)
st.altair_chart(chart, use_container_width=True)

table = df.rename(columns={"trainNo": "열차번호", "statnNm": "현재역", "statnTnm": "종착역",
                           "recptnDt": "수신시각"})
st.dataframe(table[["열차번호", "현재역", "방향", "상태", "종착역", "급행", "수신시각"]]
             .sort_values(["방향", "현재역"]), use_container_width=True, hide_index=True)

st.caption("출처: 서울특별시 열린데이터광장 '서울시 지하철 실시간 열차 위치정보' (공공누리 제1유형). "
           "30초마다 갱신되며 실제 열차 위치와 차이가 있을 수 있습니다.")
