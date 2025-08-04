# app.py

import requests
from bs4 import BeautifulSoup
import time
import json

from utils.utils import save_to_excel, save_to_json

# --- 기능 함수 1: 모든 부서 목록 가져오기 ---
def get_smc_departments(headers):
    """삼성서울병원에서 모든 부서의 이름과 코드를 수집합니다."""
    group_codes = [{'type': 'O', 'name': '진료과'}, {'type': 'C', 'name': '센터'}, {'type': 'N', 'name': '클리닉'}]
    base_url = "https://www.samsunghospital.com/home/reservation/DoctorScheduleGubun.do"
    all_departments = []
    
    print("1단계: 전체 부서 목록 수집을 시작합니다...")
    for group in group_codes:
        print(f"  - 그룹 '{group['name']}({group['type']})' 목록 수집 중...")
        params = {'dp_type': group['type'], '_': int(time.time() * 1000)}
        try:
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for option in soup.select('option'):
                if dept_code := option.get('value'):
                    all_departments.append({
                        'group_name': group['name'], 'group_code': group['type'],
                        'dept_name': option.get_text(strip=True), 'dept_code': dept_code
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"  - 요청 실패 (그룹: {group['type']}): {e}")
    return all_departments

# --- 기능 함수 2: 특정 부서의 의료진 정보 가져오기 (최종 수정) ---
def get_smc_doctors_by_dept(headers, department):
    """주어진 부서의 의료진 목록 HTML을 파싱하여 상세 정보를 추출합니다."""
    base_url = "https://www.samsunghospital.com/home/reservation/doctorInfoLists.do"
    params = {'cPage': 1, 'DP_CODE': department['dept_code'], 'DP_TYPE': department['group_code'], '_': int(time.time() * 1000)}
    try:
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        doctors_in_dept = []
        for item in soup.select('ul.masonry li.card-item.doctor-profile'):
            name_tag = item.select_one('span[name="fullName"]')
            name = name_tag.get_text(strip=True) if name_tag else ''
            
            # h3 태그에서 직위와 소속과 추출
            title_tag = item.select_one('h3.card-content-title')
            full_title_text = title_tag.get_text(strip=True) if title_tag else ''
            position = full_title_text.replace(name, '').split('[')[0].strip()
            
            # --- 👇 네가 알려준 '진료분야' 선택자 정확하게 반영 ---
            fields_tag = item.select_one('p.card-content-text')
            fields = fields_tag.get_text(strip=True) if fields_tag else ''
            
            img_tag = item.select_one('div.card-content-img img')
            img_url = f"https://www.samsunghospital.com{img_tag['src']}" if img_tag and img_tag.has_attr('src') else ''

            link_tag = item.select_one('section.card-item-inner > a')
            detail_url = f"https://www.samsunghospital.com{link_tag['href']}" if link_tag and link_tag.has_attr('href') else ''

            doctors_in_dept.append({
                "소속": department['dept_name'],
                "이름": name,
                "직위": position,
                "진료분야": fields,
                "이미지URL": img_url,
                "상세정보URL": detail_url
            })
        return doctors_in_dept
    except Exception as e:
        print(f"    - {department['dept_name']} 처리 중 에러: {e}")
        return []

# --- 기능 함수 3: 의료진 상세 정보 가져오기 (학력/경력) ---
def get_doctor_profile(detail_url, headers):
    """상세 페이지 URL을 받아 학력/경력 정보를 스크래핑합니다."""
    if not detail_url:
        return {}
    try:
        response = requests.get(detail_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        profile_data = {}
        for title_tag in soup.select('h2.doctor-paper-career-title'):
            title = title_tag.get_text(strip=True)
            if title in ['학력', '경력']:
                table_div = title_tag.find_next_sibling('div', class_='table-wrapper')
                if table_div:
                    records = []
                    for row in table_div.select('tbody tr'):
                        date = row.select_one('th').get_text(strip=True)
                        content = row.select_one('td').get_text(strip=True)
                        records.append(f"{date} {content}")
                    profile_data[title] = records
        return profile_data
    except Exception as e:
        print(f"      - 상세 정보 처리 중 에러: {e}")
        return {}

# --- 메인 실행 로직 ---
if __name__ == "__main__":
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Referer': 'https://www.samsunghospital.com/home/reservation/deptAndDr.do',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    departments = get_smc_departments(headers)
    if not departments:
        print("\n❌ 1단계 실패. 종료합니다.")
    else:
        print(f"\n✅ 1단계 완료: 총 {len(departments)}개 부서 수집.")
        all_doctors = []
        print("\n2단계: 각 부서별 의료진 목록 수집 시작...")
        for i, dept in enumerate(departments):
            print(f"  - ({i+1}/{len(departments)}) {dept['dept_name']} 수집 중...")
            doctors = get_smc_doctors_by_dept(headers, dept)
            if doctors:
                all_doctors.extend(doctors)
            time.sleep(0.2)
        
        print(f"\n✅ 2단계 완료: 총 {len(all_doctors)}명 의료진 목록 수집.")

        print("\n3단계: 각 의료진의 상세 프로필(학력/경력) 수집 시작...")
        for i, doctor in enumerate(all_doctors):
            print(f"  - ({i+1}/{len(all_doctors)}) {doctor['이름']} 상세 정보 수집 중...")
            profile = get_doctor_profile(doctor.get('상세정보URL'), headers)
            doctor['profile'] = profile
            time.sleep(0.2)
            
        print(f"\n✅ 3단계 완료: 모든 정보 통합. 최종 데이터를 저장합니다.")

        file_name = '삼성서울병원_smc'
        save_to_json(all_doctors, file_name)

        # 2. utils.py의 함수를 이용해 Excel 파일로 저장
        save_to_excel(all_doctors, file_name)