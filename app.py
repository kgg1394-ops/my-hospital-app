import streamlit as st
import requests
import xml.etree.ElementTree as ET
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime
import pandas as pd
import math

# 1. 페이지 설정 및 상태 유지
st.set_page_config(page_title="전국 병원 찾기 (지역 선택형)", layout="wide")

if 'hospital_data' not in st.session_state:
    st.session_state.hospital_data = []
if 'my_location' not in st.session_state:
    st.session_state.my_location = None

# --- [데이터] 대한민국 행정구역 맵핑 (시/도별 시/군/구) ---
KOREA_REGION_MAP = {
    "서울특별시": ["강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"],
    "경기도": ["가평군", "고양시 덕양구", "고양시 일산동구", "고양시 일산서구", "과천시", "광명시", "광주시", "구리시", "군포시", "김포시", "남양주시", "동두천시", "부천시", "성남시 수정구", "성남시 중원구", "성남시 분당구", "수원시 장안구", "수원시 권선구", "수원시 팔달구", "수원시 영통구", "시흥시", "안산시 상록구", "안산시 단원구", "안성시", "안양시 만안구", "안양시 동안구", "양주시", "양평군", "여주시", "연천군", "오산시", "용인시 처인구", "용인시 기흥구", "용인시 수지구", "의왕시", "의정부시", "이천시", "파주시", "평택시", "포천시", "하남시", "화성시"],
    "부산광역시": ["강서구", "금정구", "기장군", "남구", "동구", "동래구", "부산진구", "북구", "사상구", "사하구", "서구", "수영구", "연제구", "영도구", "중구", "해운대구"],
    "인천광역시": ["강화군", "계양구", "미추홀구", "남동구", "동구", "부평구", "서구", "연수구", "옹진군", "중구"],
    "대구광역시": ["남구", "달서구", "달성군", "동구", "북구", "서구", "수성구", "중구", "군위군"],
    "광주광역시": ["광산구", "남구", "동구", "북구", "서구"],
    "대전광역시": ["대덕구", "동구", "서구", "유성구", "중구"],
    "울산광역시": ["남구", "동구", "북구", "울주군", "중구"],
    "세종특별자치시": ["세종시"],
    "강원특별자치도": ["강릉시", "고성군", "동해시", "삼척시", "속초시", "양구군", "양양군", "영월군", "원주시", "인제군", "정선군", "철원군", "춘천시", "태백시", "평창군", "홍천군", "화천군", "횡성군"],
    "충청북도": ["괴산군", "단양군", "보은군", "영동군", "옥천군", "음성군", "제천시", "증평군", "진천군", "청주시 상당구", "청주시 서원구", "청주시 흥덕구", "청주시 청원구", "충주시"],
    "충청남도": ["계룡시", "공주시", "금산군", "논산시", "당진시", "보령시", "부여군", "서산시", "서천군", "아산시", "연기군", "예산군", "천안시 동남구", "천안시 서북구", "청양군", "태안군", "홍성군"],
    "전북특별자치도": ["고창군", "군산시", "김제시", "남원시", "무주군", "부안군", "순창군", "완주군", "익산시", "임실군", "장수군", "전주시 완산구", "전주시 덕진구", "정읍시", "진안군"],
    "전라남도": ["강진군", "고흥군", "곡성군", "광양시", "구례군", "나주시", "담양군", "목포시", "무안군", "보성군", "순천시", "신안군", "여수시", "영광군", "영암군", "완도군", "장성군", "장흥군", "진도군", "함평군", "해남군", "화순군"],
    "경상북도": ["경산시", "경주시", "고령군", "구미시", "김천시", "문경시", "봉화군", "상주시", "성주군", "안동시", "영덕군", "영양군", "영주시", "영천시", "예천군", "울릉군", "울진군", "의성군", "청도군", "청송군", "칠곡군", "포항시 남구", "포항시 북구"],
    "경상남도": ["거제시", "거창군", "고성군", "김해시", "남해군", "밀양시", "사천시", "산청군", "양산시", "의령군", "진주시", "창녕군", "창원시 마산합포구", "창원시 마산회원구", "창원시 성산구", "창원시 의창구", "창원시 진해구", "통영시", "하동군", "함안군", "함양군", "합천군"],
    "제주특별자치도": ["제주시", "서귀포시"]
}

# 진료과목 코드
DEPT_CODES = {"전체": "", "내과": "D001", "소아과": "D002", "정형외과": "D006", "이비인후과": "D013", "피부과": "D014", "치과": "D034"}

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

@st.cache_data(ttl=600)
def fetch_api_data(city, town, dept_code, s_key):
    url = 'http://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire'
    params = {'serviceKey': s_key, 'Q0': city, 'Q1': town, 'QD': dept_code, 'numOfRows': 500, 'pageNo': '1'}
    try:
        res = requests.get(url, params=params, timeout=10)
        root = ET.fromstring(res.text)
        items = root.findall('.//item')
        return [{
            'name': i.findtext('dutyName'), 'div': i.findtext('dutyDivName'),
            'eryn': i.findtext('dutyEryn'), 'tel': i.findtext('dutyTel1'),
            'addr': i.findtext('dutyAddr'), 'lat': i.findtext('wgs84Lat'),
            'lon': i.findtext('wgs84Lon'),
            'times': {d: [i.findtext(f'dutyTime{d}s'), i.findtext(f'dutyTime{d}e')] for d in range(1, 9)}
        } for i in items]
    except: return []

# --- 사이드바 ---
st.sidebar.header("📍 1. 내 위치 정보")
loc = streamlit_js_eval(data_key='getLocation', label='📡 내 위치 수신 (클릭)', key='get_loc')
if loc:
    st.session_state.my_location = {'lat': loc['coords']['latitude'], 'lon': loc['coords']['longitude']}

st.sidebar.markdown("---")
st.sidebar.header("🔍 2. 지역 및 과목 선택")

# [핵심] 시/도 선택
selected_city = st.sidebar.selectbox("시/도 선택", list(KOREA_REGION_MAP.keys()))

# [핵심] 시/도 선택에 따른 시/군/구 목록 필터링
town_list = KOREA_REGION_MAP[selected_city]
selected_town = st.sidebar.selectbox("시/군/구 선택", town_list)

selected_dept = st.sidebar.selectbox("진료과목 선택", list(DEPT_CODES.keys()))

if st.sidebar.button("🚀 데이터 업데이트"):
    with st.spinner('정보를 가져오고 있습니다...'):
        st.session_state.hospital_data = fetch_api_data(selected_city, selected_town, DEPT_CODES[selected_dept], st.secrets["SERVICE_KEY"])

st.sidebar.markdown("---")
st.sidebar.header("🎯 3. 필터 설정")
radius_km = st.sidebar.slider("반경 (km)", 0.5, 10.0, 3.0)
only_open = st.sidebar.checkbox("✅ 현재 진료 중")

# 5. 메인 로직 (필터링 부분)
if st.session_state.hospital_data:
    raw_data = st.session_state.hospital_data
    now = datetime.now()
    weekday = now.isoweekday()
    curr_time = now.strftime("%H%M")

    filtered = []
    for h in raw_data:
        if not h['lat'] or not h['lon']: continue
        
        # [핵심 추가] 지역명 엄격 체크 (양주 vs 남양주 구분)
        # 선택한 '양주시'가 주소에 포함되어 있지 않으면 과감히 버립니다.
        if selected_town not in h['addr']:
            continue

        # 거리 필터
        dist = 0
        if st.session_state.my_location:
            dist = calculate_distance(st.session_state.my_location['lat'], st.session_state.my_location['lon'], float(h['lat']), float(h['lon']))
            if dist > radius_km: continue
        
        # (이하 기존 필터 로직 동일...)
        st_t, en_t = h['times'][weekday]
        is_open = (st_t and en_t and st_t <= curr_time <= en_t)
        if only_open and not is_open: continue
        
        # 데이터 담기
        filtered.append({
            '병원명': h['name'], 
            '거리(km)': round(dist, 2) if st.session_state.my_location else "N/A",
            '상태': '✅ 진료중' if is_open else '⏳ 종료',
            '응급실': '🚨 운영' if h['eryn'] == '1' else 'X',
            '길찾기': f"https://map.naver.com/v5/search/{h['name']}?c={h['lon']},{h['lat']},15,0,0,0,dh",
            '전화': h['tel'], '주소': h['addr'], 'lat': float(h['lat']), 'lon': float(h['lon'])
        })

    if st.session_state.my_location:
        filtered = sorted(filtered, key=lambda x: x['거리(km)'])

    if filtered:
        col1, col2 = st.columns([1.5, 1])
        with col1:
            center = [st.session_state.my_location['lat'], st.session_state.my_location['lon']] if st.session_state.my_location else [filtered[0]['lat'], filtered[0]['lon']]
            m = folium.Map(location=center, zoom_start=14)
            if st.session_state.my_location:
                folium.Marker(center, popup="내 위치", icon=folium.Icon(color='green', icon='user', prefix='fa')).add_to(m)
            for f in filtered:
                color = 'red' if f['응급실'] == '🚨 운영' else 'blue'
                folium.Marker([f['lat'], f['lon']], 
                              popup=folium.Popup(f"<b>{f['병원명']}</b><br><a href='{f['길찾기']}' target='_blank'>지도보기</a>", max_width=200),
                              icon=folium.Icon(color=color, icon='info-sign')).add_to(m)
            st.components.v1.html(m._repr_html_(), height=550)
        with col2:
            st.dataframe(pd.DataFrame(filtered).drop(['lat', 'lon'], axis=1), 
                         column_config={"길찾기": st.column_config.LinkColumn("네이버", display_text="열기")},
                         height=550, hide_index=True)
