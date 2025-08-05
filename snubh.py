import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlencode, urlparse, parse_qs
import time
import re

# utils.py의 파일 저장 함수들을 가져옴
# 이 코드를 실행하려면 프로젝트 폴더에 utils/utils.py 파일이 있어야 합니다.
from utils.utils import save_to_json, save_to_excel

def scrape_department_links(base_url, headers):
    """
    1단계: 전체 의료진 페이지에서 각 부서/센터 페이지로 연결되는 링크와 이름을 수집합니다.
    """
    print("1단계: 전체 부서 링크 수집을 시작합니다...")
    departments = []
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        department_list_items = soup.select('li[id^="pos_"]')
        print(f"-> 총 {len(department_list_items)}개의 부서/센터를 찾았습니다.")

        for item in department_list_items:
            a_tag = item.select_one('a.dept_tit')
            if a_tag and a_tag.has_attr('href'):
                dept_name = a_tag.get_text(strip=True)
                relative_url = a_tag['href']
                full_url = urljoin(base_url, relative_url)
                departments.append({'name': dept_name, 'url': full_url})
        return departments
    except requests.exceptions.RequestException as e:
        print(f"❌ 페이지 요청 중 에러 발생: {e}")
        return []

def scrape_doctors_from_dept(department_url, headers):
    """
    2단계: 각 부서 페이지에서 소속된 의사들의 기본 정보를 수집합니다.
    """
    doctors = []
    try:
        response = requests.get(department_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        parsed_dept_url = urlparse(department_url)
        base_params = {k: v[0] for k, v in parse_qs(parsed_dept_url.query).items()}

        for item in soup.select('li.bh_bookmark_list3'):
            name_strong_tag = item.select_one('div.bh_doctor_name_n > strong')
            
            name = '이름 정보 없음'
            position_from_list = ''

            if name_strong_tag:
                position_em_tag = name_strong_tag.find('em')
                if position_em_tag:
                    position_from_list = position_em_tag.get_text(strip=True)
                    position_em_tag.extract()
                name = name_strong_tag.get_text(strip=True)

            fields_dd_tag = item.select_one('dl.bh_doctor_dept_n > dd')
            fields = fields_dd_tag.get_text(strip=True) if fields_dd_tag else '전문분야 정보 없음'
            
            intro_button = item.select_one('input.bh_doctor_btn_intro')
            detail_url = ''
            if intro_button and intro_button.has_attr('onclick'):
                onclick_attr = intro_button['onclick']
                
                onclick_params = {}
                sDrSid_match = re.search(r"'sDrSid'\s*:\s*'([^']*)'", onclick_attr)
                sDrStfNo_match = re.search(r"'sDrStfNo'\s*:\s*'([^']*)'", onclick_attr)
                sDpTp_match = re.search(r"'sDpTp'\s*:\s*'([^']*)'", onclick_attr)
                sDpCdDtl_match = re.search(r"'sDpCdDtl'\s*:\s*'([^']*)'", onclick_attr)

                if sDrSid_match: onclick_params['sDrSid'] = sDrSid_match.group(1)
                if sDrStfNo_match: onclick_params['sDrStfNo'] = sDrStfNo_match.group(1)
                if sDpTp_match: onclick_params['sDpTp'] = sDpTp_match.group(1)
                if sDpCdDtl_match: onclick_params['sDpCdDtl'] = sDpCdDtl_match.group(1)
                
                final_params = {**base_params, **onclick_params}
                
                if final_params:
                    base_detail_url = "https://www.snubh.org/medical/drIntroduce.do"
                    detail_url = f"{base_detail_url}?{urlencode(final_params)}"

            doctor_info = {
                'name': name,
                'position_from_list': position_from_list,
                'fields': fields,
                'detail_url': detail_url
            }
            doctors.append(doctor_info)
        return doctors
    except Exception as e:
        print(f"   - 의료진 목록 처리 중 에러: {e}")
        return []

def scrape_doctor_details(detail_url, headers):
    """
    3단계: 의사 상세 정보 페이지에서 이름, 직함, 학력, 경력 정보를 수집합니다.
    (⭐️ 핵심 수정: 제목 텍스트를 정확하게 추출하도록 변경)
    """
    details = {}
    try:
        response = requests.get(detail_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 공통 정보: 이름과 직함(소속) 정보 추출
        name_tag = soup.select_one('p.bh_doctor_name')
        if name_tag:
            details['name'] = name_tag.get_text(strip=True)
        
        position_tag = soup.select_one('p.bh_doctor_dept')
        if position_tag:
            details['position'] = position_tag.get_text(strip=True)

        # 학력 및 경력 정보 추출
        for title_tag in soup.select('h6.tit_h4'):
            # ⭐️ .contents[0]를 사용해 <span> 태그를 제외한 순수 텍스트만 가져옴
            title = title_tag.contents[0].strip()
            
            if title == '학력' or title == '경력':
                ul_tag = title_tag.find_next_sibling('ul')
                if ul_tag:
                    records = [' '.join(li.get_text().split()) for li in ul_tag.find_all('li')]
                    details[title] = records
                        
        return details
    except Exception as e:
        print(f"     - 상세 정보 처리 중 에러: {e}")
        return {}

if __name__ == "__main__":
    target_url = "https://www.snubh.org/medical/drMedicalTeam2.do"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }

    # 1단계: 부서 목록 수집
    departments = scrape_department_links(target_url, headers)
    
    if departments:
        print(f"\n✅ 1단계 완료: 총 {len(departments)}개 부서 수집.")
        
        # 2단계: 모든 부서의 의료진 목록 수집
        all_doctors_list = []
        print("\n2단계: 각 부서별 의료진 목록 수집을 시작합니다...")
        for i, dept in enumerate(departments):
            print(f"  - ({i+1}/{len(departments)}) {dept['name']} 의료진 목록 수집 중...")
            doctors = scrape_doctors_from_dept(dept['url'], headers)
            all_doctors_list.extend(doctors)
            time.sleep(0.2)
        
        print(f"\n✅ 2단계 완료! 총 {len(all_doctors_list)}개의 의료진 항목을 수집했습니다.")

        # 3단계: 중복을 제외한 고유 의료진의 상세 정보 수집
        unique_doctors_map = {doc['detail_url']: doc for doc in all_doctors_list if doc.get('detail_url')}
        unique_doctors_list = list(unique_doctors_map.values())

        print(f"\n3단계: 중복을 제외한 {len(unique_doctors_list)}명의 고유 의료진 상세 정보 수집 시작...")
        final_data = []
        for i, doctor in enumerate(unique_doctors_list):
            print(f"  - ({i+1}/{len(unique_doctors_list)}) {doctor.get('name', '이름없음')} 교수님 상세 정보 수집 중...")
            
            # 상세 정보 스크래핑
            details = scrape_doctor_details(doctor['detail_url'], headers)
            
            # 2단계 정보와 3단계 정보를 합침
            final_doctor_info = {
                '이름': details.get('name', doctor.get('name')),
                '직위/소속': details.get('position', doctor.get('position_from_list')),
                '전문분야': doctor.get('fields'),
                '학력': details.get('학력', []),
                '경력': details.get('경력', []),
                '상세정보URL': doctor.get('detail_url')
            }
            final_data.append(final_doctor_info)
            time.sleep(0.2)

        print(f"\n✅ 3단계 완료! 최종 데이터를 파일로 저장합니다.")

        # 4단계: 최종 데이터 저장
        file_base_name = '분당서울대학교병원_의료진'
        save_to_json(final_data, file_base_name)
        save_to_excel(final_data, file_base_name)
    else:
        print("\n❌ 1단계 부서 목록 수집에 실패하여 프로그램을 종료합니다.")
