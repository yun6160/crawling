# app.py

import requests
import json
import time
from bs4 import BeautifulSoup

from utils.utils import save_to_excel, save_to_json

def fetch_departments_new(headers):
    """모든 부서의 정보를 수집합니다."""
    api_url = "https://sev.severance.healthcare/api/department/list.do"
    payloads = [
        {'payload': 'insttCode=2&tyCode=DP010200&seCode=DP020401&sort=name', 'type': '센터'},
        {'payload': 'insttCode=2&tyCode=DP010200&seCode=DP020402&sort=name', 'type': '클리닉'},
        {'payload': 'insttCode=2&tyCode=DP010100&seCode=&sort=name', 'type': '진료과'}
    ]
    all_departments = []
    print("1단계: 전체 부서 목록 수집을 시작합니다...")
    for item in payloads:
        try:
            response = requests.post(api_url, headers=headers, data=item['payload'], timeout=15)
            response.raise_for_status()
            response_data = response.json()
            department_list = response_data.get('data', {}).get('list', [])
            for dept in department_list:
                all_departments.append({
                    'type': item['type'], 'tyCode' : dept.get('tyCode'), 'seCode' : dept.get('seCode'),
                    'seq': dept.get('seq'), 'name': dept.get('deptNm')
                })
            print(f"  - {item['type']} {len(department_list)}개 수집 완료.")
            time.sleep(0.3)
        except requests.exceptions.RequestException as e:
            print(f"  - {item['type']} 목록을 가져오는 중 에러 발생: {e}")
    return all_departments

def fetch_doctors_by_department_new(department, headers):
    """'totalPage'를 미리 계산하여 효율적으로 페이지네이션을 처리하는 함수"""
    api_url = "https://sev.severance.healthcare/api/doctor/list.do"
    all_doctors_in_dept = []
    page = 1
    payload = {
        'insttCode': '2', 'tyCode': department['tyCode'], 'seCode': department['seCode'],
        'seq': department['seq'], 'page': page, 'pagePerNum': 20,
        'isChoSung': 'N', 'keyword': ''
    }
    try:
        response = requests.get(api_url, headers=headers, params=payload, timeout=15)
        response.raise_for_status()
        response_data = response.json()
        first_page_doctors = response_data.get('data', {}).get('list', [])
        if not first_page_doctors:
            return []
        all_doctors_in_dept.extend(first_page_doctors)
        total_page = response_data.get('data', {}).get('pagenation', {}).get('totalPage', 1)
        if total_page > 1:
            for page_num in range(2, total_page + 1):
                payload['page'] = page_num
                response = requests.get(api_url, headers=headers, params=payload, timeout=15)
                response.raise_for_status()
                response_data = response.json()
                doctor_list = response_data.get('data', {}).get('list', [])
                if doctor_list:
                    all_doctors_in_dept.extend(doctor_list)
                time.sleep(0.3)
    except requests.exceptions.RequestException as e:
        print(f"    - 의료진 정보 {payload.get('page')}페이지 처리 중 에러: {e}")
    return all_doctors_in_dept

def fetch_doctor_details(doctor_info, headers):
    """의료진 상세 페이지에서 학력 및 경력 정보를 가져옵니다."""
    emp_no = doctor_info.get('empNo')
    dept_seq = doctor_info.get('deptSeq')

    if not emp_no or not dept_seq:
        return {"학력": "ID 또는 부서코드가 없어 조회 불가", "경력": "ID 또는 부서코드가 없어 조회 불가"}
    
    # API가 제공하는 인코딩된 empNo 값을 그대로 사용
    detail_url = f"https://sev.severance.healthcare/sev/doctor/doctor-view.do?empNo={emp_no}&deptSeq={dept_seq}"
    
    details = {"학력": "정보 없음", "경력": "정보 없음"}
    try:
        response = requests.get(detail_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 학력 정보 추출
        education_ul = soup.find('ul', class_='acdmcrMatter')
        if education_ul:
            details['학력'] = "\n".join(li.get_text(strip=True) for li in education_ul.find_all('li'))

        # 경력 정보 추출
        experience_ul = soup.find('ul', class_='edcNdClincCareer')
        if experience_ul:
            details['경력'] = "\n".join(li.get_text(strip=True) for li in experience_ul.find_all('li'))
            
    except requests.exceptions.RequestException as e:
        print(f"      [Error] 상세 정보 수집 중 에러: {e}\n      URL: {detail_url}")
    return details

if __name__ == "__main__":
    # ⚠️ 아래 쿠키는 만료되었을 수 있으니, 실행 전 반드시 새 값으로 교체해주세요.
    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Referer': 'https://sev.severance.healthcare/sev/doctor/doctor.do',
        'X-Requested-With': 'XMLHttpRequest',
        'AJAX': 'true'
    }
    
    dept_headers = request_headers.copy()
    dept_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    
    # 1단계: 부서 목록 수집
    departments = fetch_departments_new(dept_headers)
    
    if departments:
        # 2단계: 모든 부서의 의료진 목록을 먼저 수집
        all_raw_doctors = []
        print(f"\n✅ 1단계 완료: 총 {len(departments)}개의 부서를 찾았습니다.")
        print("\n2단계: 각 부서별 의료진 목록 수집을 시작합니다...")
        
        for i, dept in enumerate(departments):
            print(f"  - ({i+1}/{len(departments)}) {dept['name']} ({dept['type']}) 의료진 목록 수집 중...")
            raw_doctors = fetch_doctors_by_department_new(dept, request_headers)
            # 각 의료진 정보에 부서 정보를 미리 추가
            for doc in raw_doctors:
                doc['dept_type'] = dept['type']
                doc['dept_name'] = dept['name']
            all_raw_doctors.extend(raw_doctors)
        
        print(f"\n✅ 2단계 완료: 총 {len(all_raw_doctors)}명의 의료진 목록을 수집했습니다.")
        print("\n3단계: 각 의료진의 상세 정보(학력/경력) 수집을 시작합니다... (시간이 많이 소요됩니다)")

        # 3단계: 각 의료진의 상세 정보 수집
        all_doctors_final_list = []
        for i, doc in enumerate(all_raw_doctors):
            print(f"  - ({i+1}/{len(all_raw_doctors)}) {doc.get('nm', '이름없음')} 의료진 상세 정보 수집 중...")
            
            details = fetch_doctor_details(doc, request_headers)
            
            # 상세 정보가 담긴 딕셔너리를 통째로 저장
            doc['학력및경력'] = details
            all_doctors_final_list.append(doc)
            time.sleep(0.3)

        print(f"\n✅ 3단계 완료: 최종적으로 {len(all_doctors_final_list)}명의 상세 정보를 수집했습니다.")
        
        # 최종적으로 저장할 때 원하는 정보만 뽑아서 저장
        final_clean_data = []
        for doc in all_doctors_final_list:
            final_clean_data.append({
                '부서타입': doc.get('dept_type'),
                '부서명': doc.get('dept_name'),
                '이름': doc.get('nm'),
                '영문이름': doc.get('nmEn'),
                '직위': doc.get('ofcps'),
                '진료분야': doc.get('clnicRealm'),
                '이메일': doc.get('emailAdres'),
                '블로그': doc.get('blog'),
                '학력': doc.get('학력및경력', {}).get('학력'),
                '경력': doc.get('학력및경력', {}).get('경력')
            })
        
        file_name = '세브란스병원(신촌)_ys'
        save_to_json(final_clean_data, file_name)
        
        save_to_excel(final_clean_data, file_name)
    else:
        print("\n❌ 부서 목록 수집에 실패하여 프로그램을 종료합니다.")