# app.py

import requests
from bs4 import BeautifulSoup
import re
import time
from utils.utils import save_to_excel, save_to_json

def get_asan_departments(headers):
    """서울아산병원 전체 진료과 팝업에서 진료과 목록을 수집합니다."""
    popup_url = "https://www.amc.seoul.kr/asan/common/dept/allDept.do?drUseYn=Y&cmeUseYn=N&thUseYn=N&allowDept=N&deptFunc=fnSelectDeptPopup"
    try:
        response = requests.get(popup_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        departments = []
        for a_tag in soup.select("a[onclick*='fnSelectDeptPopup']"):
            dept_name = a_tag.get_text(strip=True)
            onclick_attr = a_tag.get('onclick', '')
            match = re.search(r"fnSelectDeptPopup\('([^']*)'\)", onclick_attr)
            if match:
                dept_code = match.group(1)
                departments.append({'name': dept_name, 'code': dept_code})
        return departments
    except Exception as e:
        print(f"진료과 목록 수집 중 에러: {e}")
        return []

def get_asan_doctors_by_dept(department, headers):
    """주어진 부서의 의료진 목록 페이지를 파싱하여 기본 정보를 추출합니다."""
    dept_url = f"https://www.amc.seoul.kr/asan/staff/base/staffBaseInfoList.do?searchHpCd={department['code']}"
    try:
        response = requests.get(dept_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        doctors = []
        for li in soup.select('ul.serchlist_boxwrap li'):
            name_tag = li.select_one('p.doctor_name a')
            dept_th = li.find('th', scope='row', string='진료과')
            field_th = li.find('th', scope='row', string='전문분야')
            detail_button = li.select_one("a[onclick*='fnDrDetail']")
            onclick_attr = detail_button.get('onclick', '') if detail_button else ''
            match = re.search(r"fnDrDetail\('([^']*)'", onclick_attr)
            dr_emp_id = match.group(1) if match else ''
            
            if dept_th:
                raw_dept_text = dept_th.find_next_sibling('td').get_text()
                cleaned_depts = ', '.join([part.strip() for part in raw_dept_text.split(',') if part.strip()])
            else:
                cleaned_depts = department['name']

            doctor_info = {
                'name': name_tag.get_text(strip=True) if name_tag else '',
                'department': cleaned_depts,
                'fields': field_th.find_next_sibling('td').get_text(strip=True) if field_th else '',
                'drEmpId': dr_emp_id,
                'deptCode': department['code']
            }
            doctors.append(doctor_info)
        return doctors
    except Exception as e:
        print(f"  - {department['name']} 의료진 처리 중 에러: {e}")
        return []

def get_doctor_details(doctor_info, headers):
    """의료진 상세 페이지에 접속하여 학력/경력 정보를 스크래핑합니다."""
    dr_emp_id = doctor_info.get('drEmpId')
    dept_code = doctor_info.get('deptCode')
    if not dr_emp_id: return {}
        
    detail_url = f"https://www.amc.seoul.kr/asan/staff/base/staffBaseInfoDetail.do?drEmpId={dr_emp_id}&searchHpCd={dept_code}&tabIndex1=3"
    try:
        response = requests.get(detail_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        profile_data = {}
        dl_tag = soup.select_one("dl.textList2.new")
        if not dl_tag: return {}
            
        for dt_tag in dl_tag.find_all('dt', recursive=False):
            title = dt_tag.get_text(strip=True)
            if title in ['학력', '경력']:
                dd_tag = dt_tag.find_next_sibling('dd')
                if dd_tag:
                    records = [' '.join(li.get_text().split()) for li in dd_tag.select('ul.textListCon li')]
                    profile_data[title] = records
        return profile_data
    except Exception as e:
        print(f"      - 상세 정보 처리 중 에러 (ID: {dr_emp_id}): {e}")
        return {}

# --- 메인 실행 로직 ---
if __name__ == "__main__":
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Referer': 'https://www.amc.seoul.kr/asan/staff/staffList.do'
    }
    
    # 1단계
    print("1단계: 서울아산병원 진료과 목록 수집을 시작합니다...")
    department_list = get_asan_departments(headers)
    
    if department_list:
        print(f"\n✅ 1단계 완료: 총 {len(department_list)}개 부서 수집.")
        
        # 2단계
        all_doctors_list = []
        print("\n2단계: 각 부서별 의료진 목록 수집 시작...")
        for i, dept in enumerate(department_list):
            print(f"  - ({i+1}/{len(department_list)}) {dept['name']} 수집 중...")
            doctors = get_asan_doctors_by_dept(dept, headers)
            if doctors:
                all_doctors_list.extend(doctors)
            time.sleep(0.2)
        
        print(f"\n✅ 2단계 완료: 총 {len(all_doctors_list)}개의 의료진 항목 수집.")

        # 3단계 (고유 의사만 처리)
        unique_doctors_map = {doc['drEmpId']: doc for doc in all_doctors_list if doc.get('drEmpId')}
        unique_doctors_list = list(unique_doctors_map.values())
        
        print(f"\n3단계: 중복을 제외한 {len(unique_doctors_list)}명의 고유 의료진 상세 정보 수집 시작...")

        for i, doctor in enumerate(unique_doctors_list):
            print(f"  - ({i+1}/{len(unique_doctors_list)}) {doctor['name']} 상세 정보 수집 중...")
            profile = get_doctor_details(doctor, headers)
            doctor['profile'] = profile
            time.sleep(0.2)
            
        # 4단계: 최종 저장
        print(f"\n✅ 3단계 완료! 최종 데이터를 파일로 저장합니다.")

        file_name = '서울아산병원_amc'
        save_to_json(unique_doctors_list, file_name)
        save_to_excel(unique_doctors_list, file_name)
    else:
        print("\n❌ 1단계 부서 목록 수집에 실패했습니다.")