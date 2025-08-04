import requests
from requests.adapters import HTTPAdapter
import ssl
import time

# utils.py의 함수들은 그대로 사용
from utils.utils import save_to_excel, save_to_json

# --- SSL 에러 우회용 커스텀 어댑터 ---
class LegacyCipherAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.set_ciphers('DEFAULT:@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

# --- 기능 함수 1: 전체 부서 목록 가져오기 ---
def get_all_departments(session, headers):
    group_codes = ['A', 'B', 'C']
    all_depts = []
    print("1단계: 전체 부서 목록 수집을 시작합니다...")
    for code in group_codes:
        print(f"   - 그룹 '{code}' 목록 수집 중...")
        api_url = f"https://www.cmcseoul.or.kr/api/department?deptClsf={code}"
        try:
            response = session.get(api_url, headers=headers)
            response.raise_for_status()
            api_data = response.json()
            for item in api_data:
                if item.get('exposeYn') == 'Y':
                    all_depts.append({
                        'group_code': code, 'name': item.get('deptNm'), 'code': item.get('deptCd')
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"   - API 요청 실패 (그룹: {code}): {e}")
    return all_depts

# --- 기능 함수 2: 특정 부서의 의료진 가져오기 (⭐️ 핵심 수정 부분) ---
def get_doctors_by_dept(session, headers, department):
    """API 응답에서 필요한 정보만 추출하여 간소화된 딕셔너리 리스트를 반환합니다."""
    api_url = "https://www.cmcseoul.or.kr/api/doctor"
    params = {'deptClsf': department['group_code'], 'deptCd': department['code']}
    
    cleaned_doctors = []
    try:
        response = session.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        doctors_data = response.json()
        
        for doc in doctors_data:
            # 필요한 정보만 선택하여 새로운 딕셔너리 생성
            cleaned_info = {
                "이름": doc.get('drName'),
                "직위": doc.get('nuHptlJobTitle'),
                "소속": department['name'],
                "진료분야": doc.get('doctorDept', {}).get('special'),
                # 상세 정보 조회를 위해 drNo와 deptCd는 유지
                "drNo": doc.get('drNo'),
                "deptCd": doc.get('deptCd')
            }
            cleaned_doctors.append(cleaned_info)
        return cleaned_doctors
        
    except Exception as e:
        print(f"   - 의료진 API 요청 실패 (부서: {department['name']}): {e}")
        return []

# --- 기능 함수 3: 의료진 상세 정보 가져오기 (학력/경력) ---
def get_doctor_details(session, headers, doctor_info):
    """의사 정보(딕셔너리)를 받아 상세 프로필을 API로 가져옵니다."""
    doctor_id = doctor_info.get('drNo')
    dept_cd = doctor_info.get('deptCd')

    if not doctor_id or not dept_cd:
        return None
    
    api_url = f"https://www.cmcseoul.or.kr/api/doctor/{dept_cd}/{doctor_id}"
    
    try:
        response = session.get(api_url, headers=headers)
        response.raise_for_status()
        detail_data = response.json()

        profile = {"학력": [], "경력": []}
        record_list = detail_data.get('doctorDetail', {}).get('doctorRecordList', [])
        for record in record_list:
            record_type = record.get('recordType')
            record_content = record.get('recordContent')
            if record_type == 'A' and record_content:
                profile['학력'].append(record_content)
            elif record_type == 'B' and record_content:
                profile['경력'].append(record_content)
        return profile

    except Exception as e:
        print(f"     - 상세 정보 요청 실패 (ID: {doctor_id}): {e}")
        return None

# --- 메인 실행 로직 ---
if __name__ == "__main__":
    session = requests.Session()
    adapter = LegacyCipherAdapter()
    session.mount('https://', adapter)

    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://www.cmcseoul.or.kr/common.examination.doc_list.sp',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    department_list = get_all_departments(session, headers)
    if not department_list:
        print("\n❌ 1단계 부서 목록 수집에 실패하여 프로그램을 종료합니다.")
    else:
        print(f"\n✅ 1단계 완료: 총 {len(department_list)}개의 부서 목록을 수집했습니다.")
        
        all_doctors_list = []
        print("\n2단계: 각 부서별 의료진 정보 수집을 시작합니다...")
        for i, dept in enumerate(department_list):
            print(f"   - ({i+1}/{len(department_list)}) {dept['name']} 의료진 정보 수집 중...")
            doctors = get_doctors_by_dept(session, headers, dept)
            if doctors:
                all_doctors_list.extend(doctors)
            time.sleep(0.3)
        
        print(f"\n✅ 2단계 완료: 총 {len(all_doctors_list)}명의 의료진 목록을 수집했습니다.")

        print("\n3단계: 각 의료진의 상세 프로필 정보 수집을 시작합니다...")
        final_data = []
        for i, doctor in enumerate(all_doctors_list):
            # ⭐️ 키가 'drName'에서 '이름'으로 변경됨
            print(f"   - ({i+1}/{len(all_doctors_list)}) {doctor.get('이름')} 교수님 상세 정보 추가 중...")
            
            details = get_doctor_details(session, headers, doctor)
            
            # 상세 정보 조회를 위해 사용했던 ID값들은 최종 결과에서 제외
            doctor.pop('drNo', None)
            doctor.pop('deptCd', None)
            
            if details:
                doctor['profile'] = details
            
            final_data.append(doctor)
            time.sleep(0.3)
            
        print(f"\n✅ 3단계 완료: 모든 정보가 통합되었습니다. 최종 데이터를 저장합니다.")

        file_name = '가톨릭대학교_서울성모병원_cmc'
        save_to_json(final_data, file_name)
        save_to_excel(final_data, file_name)
