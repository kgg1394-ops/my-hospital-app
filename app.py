import streamlit as st
import requests
import xml.etree.ElementTree as ET
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime
import pandas as pd

# 1. 페이지 설정 및 상태 초기화
st.set_page_config(page_title="실시간 병원 찾기", layout="wide")

if 'hospital_data' not in st.session_state:
    st.session_state.hospital_data = []
if 'my_location' not in st.session_state:
    st.session_state.my_location = None

st.title("🏥 내 위치 기반 실시간 병원 & 응급실 검색")

# 2. 인증키 확인
try:
    service_key = st.secrets["SERVICE_KEY"]
except:
    st.error("Secrets 설정에서 SERVICE_KEY를 확인해주세요.")
    st.stop()

# 3. 데이터 로드 함수 (캐싱)
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

# 4. 사이드바 - 위치 정보 (버튼 유실 방지 로직)
st.sidebar.header("📍 위치 정보")

# GPS 정보를 가져오는 컴포넌트 (레이아웃을 위해 항상 하단에 배치되거나 별도 변수로 관리)
loc = streamlit_js_eval(data_key='getLocation', label='📡 [클릭] 현재 위치 수신하기', key='get_loc')

if loc:
    st.session_state.my_location = {
        'lat': loc['coords']['latitude'],
        'lon': loc['coords']['longitude']
    }
    st.sidebar.success(f"위치 수신 완료: {st.session_state.my_location['lat']:.4f}, {st.session_state.my_location['lon']:.4f}")
else:
    st.sidebar.info("위의 '현재 위치 수신하기'를 누르면 GPS 좌표를 가져옵니다.")

st.sidebar.markdown("---")
# 검색 입력창
city_input = st.sidebar.text_input("시/도", "서울특별시")
town_input = st.sidebar.text_input("시/군구", "강남구")
num_rows = st.sidebar.slider("검색 결과 수", 10, 200, 50)

is_open_now = st.sidebar.checkbox("✅ 현재 진료 중인 곳")
is_emergency = st.sidebar.checkbox("🚨 응급실 운영 기관")

# 검색 버튼
if st.sidebar.button("🔍 병원 검색 시작", key="search_btn"):
    with st.spinner('최신 데이터를 가져오는 중...'):
        st.session_state.hospital_data = get_hospital_data(city_input, town_input, num_rows, service_key)

# 5. 화면 출력 부분 (데이터가 있을 때)
if st.session_state.hospital_data:
    raw_data = st.session_state.hospital_data
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
        col1, col2 = st.columns([2, 1])
        with col1:
            # 지도 중심 설정
            center = [filtered[0]['lat'], filtered[0]['lon']]
            if st.session_state.my_location:
                center = [st.session_state.my_location['lat'], st.session_state.my_location['lon']]
            
            m = folium.Map(location=center, zoom_start=14)
            
            # 내 위치 아이콘 표시
            if st.session_state.my_location:
                folium.Marker(
                    [st.session_state.my_location['lat'], st.session_state.my_location['lon']], 
                    popup="내 위치", 
                    icon=folium.Icon(color='green', icon='user', prefix='fa')
                ).add_to(m)

            for f in filtered:
                m_color = 'red' if f['응급실'] == '🚨 운영' else 'blue'
                folium.Marker(
                    [f['lat'], f['lon']],
                    popup=f"<b>{f['병원명']}</b><br>{f['전화']}",
                    icon=folium.Icon(color=m_color, icon='info-sign')
                ).add_to(m)
            st.components.v1.html(m._repr_html_(), height=600)
        with col2:
            st.dataframe(pd.DataFrame(filtered).drop(['lat', 'lon'], axis=1), height=600)
