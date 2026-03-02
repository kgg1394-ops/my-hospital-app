import streamlit as st
import requests
import xml.etree.ElementTree as ET
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime
import pandas as pd
import math

# 1. 페이지 설정 및 상태 초기화
st.set_page_config(page_title="내 주변 병원 찾기", layout="wide")

if 'hospital_data' not in st.session_state:
    st.session_state.hospital_data = []
if 'my_location' not in st.session_state:
    st.session_state.my_location = None

# 진료과목 이름과 코드 매핑
DEPT_CODES = {
    "전체": "", "내과": "D001", "소아청소년과": "D002", "신경과": "D003", 
    "정신건강의학과": "D004", "외과": "D005", "정형외과": "D006", "신경외과": "D007", 
    "성형외과": "D009", "산부인과": "D011", "안과": "D012", "이비인후과": "D013", 
    "피부과": "D014", "비뇨의학과": "D016", "재활의학과": "D021", "가정의학과": "D024", 
    "응급의학과": "D026", "치과": "D034"
}

# 거리 계산 함수 (km 단위)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

st.title("🏥 실시간 병원 검색 & 네이버 길찾기")

# 2. 인증키 확인
try:
    service_key = st.secrets["SERVICE_KEY"]
except:
    st.error("Secrets 설정에서 SERVICE_KEY를 확인해주세요.")
    st.stop()

# 3. 데이터 로드 함수 (캐싱)
@st.cache_data(ttl=600)
def get_hospital_data(city, town, rows, s_key, dept_code):
    url = 'http://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire'
    params = {'serviceKey': s_key, 'Q0': city, 'Q1': town, 'QD': dept_code, 'numOfRows': rows, 'pageNo': '1'}
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

# 4. 사이드바 설정
st.sidebar.header("📍 내 위치 수신")
loc = streamlit_js_eval(data_key='getLocation', label='📡 내 위치 확인 (클릭)', key='get_loc')

if loc:
    st.session_state.my_location = {'lat': loc['coords']['latitude'], 'lon': loc['coords']['longitude']}
    st.sidebar.success("위치 확인 완료!")

st.sidebar.markdown("---")
city_input = st.sidebar.text_input("시/도", "서울특별시")
town_input = st.sidebar.text_input("시/군구", "강남구")
selected_dept = st.sidebar.selectbox("👨‍⚕️ 진료과목", list(DEPT_CODES.keys()))
radius_km = st.sidebar.slider("📍 반경 (km)", 0.5, 10.0, 3.0, step=0.5)

is_open_now = st.sidebar.checkbox("✅ 현재 진료 중")
is_emergency = st.sidebar.checkbox("🚨 응급실 운영")

if st.sidebar.button("🔍 검색 시작"):
    with st.spinner('데이터를 불러오는 중...'):
        st.session_state.hospital_data = get_hospital_data(city_input, town_input, 300, service_key, DEPT_CODES[selected_dept])

# 5. 화면 출력
if st.session_state.hospital_data:
    raw_data = st.session_state.hospital_data
    now = datetime.now()
    weekday = now.isoweekday()
    curr_time = now.strftime("%H%M")

    filtered = []
    for h in raw_data:
        if not h['lat'] or not h['lon']: continue
        
        # 거리 필터
        dist = 0
        if st.session_state.my_location:
            dist = calculate_distance(st.session_state.my_location['lat'], st.session_state.my_location['lon'], float(h['lat']), float(h['lon']))
            if dist > radius_km: continue
        
        # 시간 필터
        st_t, en_t = h[f't{weekday}s'], h[f't{weekday}e']
        is_open = (st_t and en_t and st_t <= curr_time <= en_t)
        if is_open_now and not is_open: continue
        if is_emergency and h['eryn'] != '1': continue
        
        # [수정] 맵핑 데이터 추가 (이 부분이 KeyError 해결 핵심!)
        filtered.append({
            '병원명': h['name'], 
            '거리(km)': round(dist, 2) if st.session_state.my_location else "N/A",
            '상태': '✅ 진료중' if is_open else '⏳ 종료',
            '응급실': '🚨 운영' if h['eryn'] == '1' else 'X',
            '길찾기': f"https://map.naver.com/v5/search/{h['name']}?c={h['lon']},{h['lat']},15,0,0,0,dh",
            '분류': h['div'], '전화': h['tel'], '주소': h['addr'],
            'lat': float(h['lat']), 'lon': float(h['lon'])
        })

    if st.session_state.my_location:
        filtered = sorted(filtered, key=lambda x: x['거리(km)'])

    if filtered:
        st.info(f"📍 {selected_dept} 결과: {len(filtered)}곳 발견")
        col1, col2 = st.columns([1.5, 1])
        with col1:
            center = [st.session_state.my_location['lat'], st.session_state.my_location['lon']] if st.session_state.my_location else [filtered[0]['lat'], filtered[0]['lon']]
            m = folium.Map(location=center, zoom_start=14)
            if st.session_state.my_location:
                folium.Marker(center, popup="내 위치", icon=folium.Icon(color='green', icon='user', prefix='fa')).add_to(m)
                folium.Circle(center, radius=radius_km * 1000, color='green', fill=True, fill_opacity=0.05).add_to(m)
            for f in filtered:
                color = 'red' if f['응급실'] == '🚨 운영' else 'blue'
                folium.Marker([f['lat'], f['lon']], 
                              popup=folium.Popup(f"<b>{f['병원명']}</b><br><a href='{f['길찾기']}' target='_blank'>네이버 지도</a>", max_width=200),
                              icon=folium.Icon(color=color, icon='info-sign')).add_to(m)
            st.components.v1.html(m._repr_html_(), height=550)
        with col2:
            st.dataframe(pd.DataFrame(filtered).drop(['lat', 'lon'], axis=1), 
                         column_config={"길찾기": st.column_config.LinkColumn("네이버 지도", display_text="길찾기")},
                         height=550, hide_index=True)
    else:
        st.warning("조건에 맞는 병원이 없습니다.")
