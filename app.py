import streamlit as st
import requests
import xml.etree.ElementTree as ET
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime
import pandas as pd
import math # 거리 계산을 위해 추가

# 1. 페이지 설정 및 상태 초기화
st.set_page_config(page_title="내 주변 병원 찾기", layout="wide")

if 'hospital_data' not in st.session_state:
    st.session_state.hospital_data = []
if 'my_location' not in st.session_state:
    st.session_state.my_location = None

# 두 지점 사이의 거리를 계산하는 함수 (단위: km)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # 지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

st.title("🏥 반경 내 실시간 병원 찾기")

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

# 4. 사이드바 - 설정
st.sidebar.header("📍 내 위치 정보")
loc = streamlit_js_eval(data_key='getLocation', label='📡 내 위치 수신 (클릭)', key='get_loc')

if loc:
    st.session_state.my_location = {'lat': loc['coords']['latitude'], 'lon': loc['coords']['longitude']}
    st.sidebar.success(f"위치 확인: {st.session_state.my_location['lat']:.4f}, {st.session_state.my_location['lon']:.4f}")

st.sidebar.markdown("---")
city_input = st.sidebar.text_input("시/도", "서울특별시")
town_input = st.sidebar.text_input("시/군구", "강남구")

# 반경 필터 슬라이더 추가
radius_km = st.sidebar.slider("📍 내 위치 기준 반경 (km)", 0.5, 10.0, 3.0, step=0.5)

st.sidebar.markdown("---")
is_open_now = st.sidebar.checkbox("✅ 현재 진료 중인 곳")
is_emergency = st.sidebar.checkbox("🚨 응급실 운영 기관")

if st.sidebar.button("🔍 병원 검색 시작"):
    with st.spinner('데이터를 불러오는 중...'):
        st.session_state.hospital_data = get_hospital_data(city_input, town_input, 200, service_key)

# 5. 화면 출력 및 필터링
if st.session_state.hospital_data:
    raw_data = st.session_state.hospital_data
    now = datetime.now()
    weekday = now.isoweekday()
    curr_time = now.strftime("%H%M")

    filtered = []
    for h in raw_data:
        if not h['lat'] or not h['lon']: continue
        
        # 거리 계산
        dist = 0
        if st.session_state.my_location:
            dist = calculate_distance(
                st.session_state.my_location['lat'], st.session_state.my_location['lon'],
                float(h['lat']), float(h['lon'])
            )
            # 반경 필터 적용: 설정한 거리보다 멀면 제외
            if dist > radius_km: continue
        
        # 진료 시간 필터
        st_t, en_t = h[f't{weekday}s'], h[f't{weekday}e']
        is_open = (st_t and en_t and st_t <= curr_time <= en_t)
        
        if is_open_now and not is_open: continue
        if is_emergency and h['eryn'] != '1': continue
        
        filtered.append({
            '병원명': h['name'], 
            '거리(km)': round(dist, 2) if st.session_state.my_location else "알수없음",
            '상태': '✅ 진료중' if is_open else '⏳ 종료/휴진',
            '응급실': '🚨 운영' if h['eryn'] == '1' else 'X',
            '전화': h['tel'], '주소': h['addr'],
            'lat': float(h['lat']), 'lon': float(h['lon'])
        })

    # 거리순으로 정렬 (내 위치가 있을 때만)
    if st.session_state.my_location:
        filtered = sorted(filtered, key=lambda x: x['거리(km)'])

    if filtered:
        st.info(f"📍 내 위치에서 **{radius_km}km** 이내에 있는 병원 {len(filtered)}곳을 찾았습니다.")
        col1, col2 = st.columns([2, 1])
        with col1:
            center = [filtered[0]['lat'], filtered[0]['lon']]
            if st.session_state.my_location:
                center = [st.session_state.my_location['lat'], st.session_state.my_location['lon']]
            
            m = folium.Map(location=center, zoom_start=14)
            
            # 내 위치 아이콘
            if st.session_state.my_location:
                folium.Marker(
                    [st.session_state.my_location['lat'], st.session_state.my_location['lon']], 
                    popup="내 위치", icon=folium.Icon(color='green', icon='user', prefix='fa')
                ).add_to(m)
                # 내 위치 기준 반경 원 그리기
                folium.Circle(
                    location=[st.session_state.my_location['lat'], st.session_state.my_location['lon']],
                    radius=radius_km * 1000, color='green', fill=True, fill_opacity=0.1
                ).add_to(m)

            for f in filtered:
                m_color = 'red' if f['응급실'] == '🚨 운영' else 'blue'
                folium.Marker(
                    [f['lat'], f['lon']],
                    popup=f"<b>{f['병원명']}</b> ({f['거리(km)']}km)<br>{f['전화']}",
                    icon=folium.Icon(color=m_color, icon='plus' if f['응급실'] == '🚨 운영' else 'info-sign')
                ).add_to(m)
            st.components.v1.html(m._repr_html_(), height=600)
        with col2:
            st.dataframe(pd.DataFrame(filtered).drop(['lat', 'lon'], axis=1), height=600)
    else:
        st.warning(f"{radius_km}km 이내에는 조건에 맞는 병원이 없습니다. 반경을 넓혀보세요.")
