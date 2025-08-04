# app.py

import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, parse_qs, urlparse
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import os

def save_to_json(data, filename):
    """주어진 데이터를 JSON 파일로 저장하는 함수"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ 성공! 데이터가 '{filename}' 파일로 저장되었습니다.")
    except (IOError, TypeError) as e:
        print(f"❌ 파일 저장 중 에러 발생: {e}")

def convert_json_to_excel(json_filename, excel_filename):
    """JSON 파일을 읽어 Excel 파일로 변환하는 함수"""
    print("\n🔄 4단계: 수집된 데이터를 Excel 파일로 변환합니다...")
    try:
        # 1. JSON 파일 읽기
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data:
            print("⚠️ 변환할 데이터가 없습니다. Excel 파일을 생성하지 않습니다.")
            return

        # 2. pandas DataFrame으로 변환
        df = pd.DataFrame(data)
        
        # 3. DataFrame을 Excel 파일로 저장
        # index=False 옵션은 엑셀에 불필요한 인덱스 열이 추가되는 것을 방지해 줌
        df.to_excel(excel_filename, index=False, engine='openpyxl')
        
        print(f"✅ 성공! 데이터가 '{excel_filename}' 파일로 저장되었습니다.")
        # 절대 경로를 표시하여 사용자가 파일을 쉽게 찾을 수 있도록 함
        print(f"   -> 저장 위치: {os.path.abspath(excel_filename)}")

    except FileNotFoundError:
        print(f"❌ 에러: JSON 파일 '{json_filename}'을 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ Excel 변환 중 에러 발생: {e}")


def get_all_departments_selenium(base_urls):
    """Selenium을 사용하여 동적으로 로드되는 모든 부서 목록을 수집합니다."""
    all_departments = []
    print("🎯 1단계: Selenium으로 전체 부서 목록 수집을 시작합니다...")
    
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"❌ Selenium 드라이버 설정 중 오류 발생: {e}")
        return []

    try:
        for category, url in base_urls.items():
            print(f"  - [{category}] 페이지 접속 및 분석 중...")
            driver.get(url)
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            dept_links = soup.select("a.x_tag")
            
            count = 0
            for link in dept_links:
                href = link.get('href')
                if not href or 'javascript:' in href: continue
                full_url = urljoin(url, href)
                dept_name = link.get('title', '').strip() or link.get_text(strip=True).replace('# ', '')
                if dept_name and dept_name != '전체':
                    all_departments.append({'category': category, 'name': dept_name, 'url': full_url})
                    count += 1
            print(f"    -> {count}개 부서 수집 완료.")
    except Exception as e:
        print(f"  - 페이지 처리 중 오류 발생: {e}")
    finally:
        driver.quit()
        print("\n✅ Selenium 드라이버 종료.")
            
    print(f"\n✅ 1단계 완료: 총 {len(all_departments)}개의 부서 링크(중복 포함)를 찾았습니다.")
    return all_departments

def fetch_doctors_from_department(department, headers):
    """주어진 부서 페이지에서 모든 의료진 정보를 추출합니다."""
    dept_name = department['name']
    category = department['category']
    url = department['url']
    
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    dept_no = query_params.get('deptNo', [None])[0]

    doctors = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        doctor_items = soup.select("ul.c_doc_list > li.doc_blk")
        for item in doctor_items:
            name_tag = item.select_one("p.tit span.t")
            name = name_tag.get_text(strip=True) if name_tag else "이름 정보 없음"
            
            specialty_tag = item.select_one("dl.txt dd.link")
            specialty = specialty_tag.get_text(strip=True) if specialty_tag else "전문분야 정보 없음"
            
            prof_no = "ID 없음"
            link_tag = item.select_one("div.btn_w a[href*='openDoctorView']")
            if link_tag:
                href_attr = link_tag.get('href', '')
                match = re.search(r"openDoctorView\(\s*'.*?',\s*'([^']*)'\s*\)", href_attr)
                if match:
                    prof_no = match.group(1)

            doctors.append({
                '소속분류': category, '소속부서': dept_name, '이름': name,
                '전문분야': specialty, 'deptNo': dept_no, 'profNo': prof_no
            })
        return doctors
    except requests.exceptions.RequestException as e:
        print(f"      - {dept_name} 의료진 정보 처리 중 에러: {e}")
        return []

def fetch_doctor_details(doctor, headers):
    """requests로 팝업 HTML에 숨겨진 학력/경력 정보를 수집합니다."""
    dept_no = doctor.get('deptNo')
    prof_no = doctor.get('profNo')
    
    if not dept_no or not prof_no or prof_no == "ID 없음":
        return {"학력": "상세 정보 조회 불가", "경력": "상세 정보 조회 불가"}
        
    detail_url = f"https://hosp.ajoumc.or.kr/doctor/profViewPop.do?deptNo={dept_no}&profNo={prof_no}"
    details = {"학력": "정보 없음", "경력": "정보 없음"}
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 숨겨진 mobile용 div에서 정보 추출
        career_area = soup.select_one("div#careerMobArea")
        if career_area:
            sections = career_area.select("ul.detailsBox_txt_list > li")
            for section in sections:
                title_tag = section.select_one("p.tit span.t")
                if not title_tag: continue
                
                title = title_tag.get_text(strip=True)
                items = []
                for li in section.select("ul.list_basic.list_dot > li"):
                    # <span> 안의 텍스트를 공백으로 합쳐서 정리
                    item_text = ' '.join(li.find('span').find_all(string=True, recursive=False)).strip()
                    item_text = re.sub(r'\s+', ' ', item_text) # 여러 공백을 하나로
                    items.append(item_text)
                
                if items:
                    if '학력' in title:
                        details['학력'] = "\n".join(items)
                    elif '경력' in title:
                        details['경력'] = "\n".join(items)

    except requests.exceptions.RequestException as e:
        print(f"      [Error] 상세 정보 수집 중 에러: {e}")
    
    return details

if __name__ == "__main__":
    base_urls = {
        "진료과": "https://hosp.ajoumc.or.kr/doctor/profDeptList.do",
        "전문센터": "https://hosp.ajoumc.or.kr/doctor/profCenterList.do",
        "암센터": "https://hosp.ajoumc.or.kr/doctor/profCancerList.do",
        "치과병원": "https://hosp.ajoumc.or.kr/doctor/profDentalList.do",
        "전문클리닉": "https://hosp.ajoumc.or.kr/doctor/profClinicList.do"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }

    json_output_file = 'ajou_doctors_with_details.json'
    excel_output_file = 'ajou_doctors_with_details.xlsx'
    
    departments = get_all_departments_selenium(base_urls)
    
    if departments:
        unique_checker_dept = {}
        for dept in departments:
            unique_key = (dept['name'], dept['url'])
            if unique_key not in unique_checker_dept:
                unique_checker_dept[unique_key] = dept
        unique_departments = list(unique_checker_dept.values())
        print(f"\n✅ 중복 제거 후, 최종 {len(unique_departments)}개의 부서를 대상으로 2단계를 시작합니다.")

        all_doctors = []
        print("\n🎯 2단계: 각 부서별 의료진 목록 수집을 시작합니다...")
        for i, dept in enumerate(unique_departments):
            print(f"  - ({i+1}/{len(unique_departments)}) {dept['name']} ({dept['category']}) 의료진 수집 중...")
            doctors_in_dept = fetch_doctors_from_department(dept, headers)
            if doctors_in_dept:
                print(f"    -> {len(doctors_in_dept)}명 수집 완료.")
                all_doctors.extend(doctors_in_dept)
            else:
                print("    -> 의료진 정보 없음.")
            time.sleep(0.3)
            
        print(f"\n✅ 2단계 완료: 수집된 의료진 정보는 총 {len(all_doctors)}건 입니다.")
        
        unique_doctors = {doc['profNo']: doc for doc in all_doctors if doc['profNo'] != "ID 없음"}.values()
        print(f"✅ 중복 제거 후, 최종 {len(unique_doctors)}명의 의료진 정보를 대상으로 3단계를 시작합니다.")

        print("\n🎯 3단계: 각 의료진의 상세 정보(학력/경력) 수집을 시작합니다...")
        final_data = []
        for i, doc in enumerate(list(unique_doctors)):
            print(f"  - ({i+1}/{len(unique_doctors)}) {doc['이름']} 의료진 상세 정보 수집 중...")
            details = fetch_doctor_details(doc, headers) # Selenium 드라이버가 더 이상 필요 없음
            doc['학력'] = details['학력']
            doc['경력'] = details['경력']
            final_data.append(doc)
            time.sleep(0.3)

        print(f"\n✅ 3단계 완료: 최종적으로 {len(final_data)}명의 상세 정보를 수집했습니다.")
        save_to_json(final_data, json_output_file)

        # 2. 저장된 JSON 파일을 Excel 파일로 변환 (새로 추가된 부분)
        convert_json_to_excel(json_output_file, excel_output_file)
    else:
        print("\n❌ 1단계 부서 수집에 실패하여 프로그램을 종료합니다.")