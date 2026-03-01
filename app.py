import streamlit as st
import requests
import xml.etree.ElementTree as ET
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="실시간 내 주변 병원 찾기", layout="wide")
st.title("🏥 내 위치 기반 실시간 병원 & 응급실 검색")

# 2. 인증키 불러오기 (secrets.toml 파일에서 가져옴)
try:
    service_key = st.secrets["SERVICE_KEY"]
except:
    st.error("인증키가 설정되지 않았습니다. .streamlit/secrets.toml 파일을 확인하세요.")
    st.stop()

# 3. 데이터 로드 함수 (캐싱 적용)
@st.cache_data(ttl=600)
def get_hospital_data(city, town, rows, s_key):
    url = 'http://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire'
    params = {'serviceKey': s_key, 'Q0': city, 'Q1': town, 'numOfRows': rows, 'pageNo': '1'}
    try:
        res = requests.get(url, params=params, timeout=10)
        root = ET.fromstring(res.text)
        items = root.findall('.//item')
        
        data_list = []
        for i in items:
            data_list.append({
                'name': i.findtext('dutyName'), 'div': i.findtext('dutyDivName'),
                'eryn': i.findtext('dutyEryn'), 'tel': i.findtext('dutyTel1'),
                'addr': i.findtext('dutyAddr'), 'lat': i.findtext('wgs84Lat'),
                'lon': i.findtext('wgs84Lon'),
                't1s': i.findtext('dutyTime1s'), 't1e': i.findtext('dutyTime1e'),
                't2s': i.findtext('dutyTime2s'), 't2e': i.findtext('dutyTime2e'),
                't3s': i.findtext('dutyTime3s'), 't3e': i.findtext('dutyTime3e'),
                't4s': i.findtext('dutyTime4s'), 't4e': i.findtext('dutyTime4e'),
                't5s': i.findtext('dutyTime5s'), 't5e': i.findtext('dutyTime5e'),
                't6s': i.findtext('dutyTime6s'), 't6e': i.findtext('dutyTime6e'),
                't7s': i.findtext('dutyTime7s'), 't7e': i.findtext('dutyTime7e'),
                't8s': i.findtext('dutyTime8s'), 't8e': i.findtext('dutyTime8e')
            })
        return data_list
    except: return []

# 4. GPS 기반 내 주소 가져오기 로직
st.sidebar.header("📍 위치 정보")
if st.sidebar.button("📡 현재 내 위치로 자동 설정"):
    # 브라우저에서 GPS 좌표 가져오기
    loc = streamlit_js_eval(data_key='getLocation', label='Get Location')
    if loc:
        lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
        # 카카오/구글 API 대신 간단하게 좌표만 표시하거나, 
        # 공공데이터 지역 검색을 위해 사용자가 직접 확인하도록 안내합니다.
        st.sidebar.info(f"현재 좌표: {lat:.4f}, {lon:.4f}")
        st.sidebar.warning("좌표 근처의 '시/도'와 '시/군구'를 아래에 입력해 주세요.")

# 5. 검색 및 필터 설정
city_input = st.sidebar.text_input("시/도 (예: 서울특별시)", "서울특별시")
town_input = st.sidebar.text_input("시/군구 (예: 강남구)", "강남구")
num_rows = st.sidebar.slider("검색 결과 수", 10, 200, 100)

st.sidebar.markdown("---")
is_open_now = st.sidebar.checkbox("✅ 현재 진료 중인 곳만 보기")
is_emergency = st.sidebar.checkbox("🚨 응급실 운영 기관만 보기")

search_clicked = st.sidebar.button("병원 검색 시작", key="final_search_btn")

# 6. 실행 로직
if search_clicked:
    raw_data = get_hospital_data(city_input, town_input, num_rows, service_key)
    
    if raw_data:
        now = datetime.now()
        weekday = now.isoweekday()
        curr_time = now.strftime("%H%M")

        filtered = []
        for h in raw_data:
            if not h['lat'] or not h['lon']: continue
            st_t, en_t = h[f't{weekday}s'], h[f't{weekday}e']
            is_open = (st_t and en_t and st_t <= curr_time <= en_t)
            
            if is_open_now and not is_open: continue
            if is_emergency and h['eryn'] != '1': continue
            
            filtered.append({
                '병원명': h['name'], '상태': '✅ 진료중' if is_open else '⏳ 종료/휴진',
                '응급실': '🚨 운영' if h['eryn'] == '1' else 'X', '분류': h['div'],
                '전화': h['tel'], '주소': h['addr'],
                'lat': float(h['lat']), 'lon': float(h['lon'])
            })

        if filtered:
            st.success(f"총 {len(filtered)}개의 병원을 찾았습니다.")
            col1, col2 = st.columns([2, 1])
            with col1:
                m = folium.Map(location=[filtered[0]['lat'], filtered[0]['lon']], zoom_start=14)
                for f in filtered:
                    m_color = 'red' if f['응급실'] == '🚨 운영' else 'blue'
                    folium.Marker(
                        [f['lat'], f['lon']],
                        popup=folium.Popup(f"<b>{f['병원명']}</b><br>{f['전화']}", max_width=250),
                        tooltip=f['병원명'],
                        icon=folium.Icon(color=m_color, icon='info-sign')
                    ).add_to(m)
                st.components.v1.html(m._repr_html_(), height=600)
            with col2:
                st.dataframe(pd.DataFrame(filtered).drop(['lat', 'lon'], axis=1), height=600)
    else:
        st.error("데이터를 불러오지 못했습니다. 지역명이나 인증키를 확인하세요.")