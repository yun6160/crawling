# app.py

import requests
from bs4 import BeautifulSoup
import re
import json
import time

from utils import save_to_excel

def save_to_json(data, filename):
    """주어진 데이터를 JSON 파일로 저장하는 함수"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ 성공! 데이터가 '{filename}' 파일로 저장되었습니다.")
    except (IOError, TypeError) as e:
        print(f"❌ 파일 저장 중 에러 발생: {e}")

def get_snuh_department_codes():
    """서울대학교병원 메인 페이지에서 진료과 이름과 코드를 추출합니다."""
    main_url = "https://www.snuh.org/reservation/meddept/main.do"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}
    try:
        print("1단계: 전체 부서 코드 수집 중...")
        response = requests.get(main_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        department_list = []
        treat_items = soup.select("div.treatItemWrap")
        for item in treat_items:
            dept_name_tag = item.select_one("span")
            if not dept_name_tag: continue
            dept_name = dept_name_tag.get_text(strip=True)
            doctor_link_tag = item.find('a', string='의료진')
            if doctor_link_tag:
                href_attr = doctor_link_tag.get('href', '')
                match = re.search(r"goDetail\('([^']*)'", href_attr)
                if match:
                    dept_code = match.group(1)
                    department_list.append({'진료과명': dept_name, '진료과코드': dept_code})
        print(f"✅ 1단계 완료: '의료진' 정보가 있는 {len(department_list)}개의 부서 코드를 수집했습니다.")
        return department_list
    except requests.exceptions.RequestException as e:
        print(f"페이지를 가져오는 중 에러 발생: {e}")
        return []

def fetch_doctors_from_department(department, headers):
    """Form 제출을 시뮬레이션하여 모든 의료진 정보를 수집합니다."""
    dept_code = department['진료과코드']
    dept_name = department['진료과명']
    doctor_list_url = f"https://www.snuh.org/reservation/meddept/{dept_code}/mainDoctor.do"
    all_doctors_in_dept = []
    page_index = 1
    with requests.Session() as s:
        s.headers.update(headers)
        while True:
            try:
                payload = {'pageIndex': str(page_index)}
                response = s.post(doctor_list_url, data=payload, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                doctor_items = soup.select("ul.doctorSchedule > li")
                if not doctor_items: break
                current_first_doctor_name_tag = doctor_items[0].select_one("a.doctorNameWrap > strong")
                if current_first_doctor_name_tag:
                    current_first_doctor = current_first_doctor_name_tag.get_text(strip=True)
                    if page_index > 1 and all_doctors_in_dept and current_first_doctor == all_doctors_in_dept[0]['이름']:
                        break
                for item in doctor_items:
                    name_tag = item.select_one("a.doctorNameWrap > strong")
                    name = name_tag.get_text(strip=True) if name_tag else "이름 정보 없음"
                    specialty = "세부전공 정보 없음"
                    specialty_wrap = item.select_one(".doctor-concentration-wrap")
                    if specialty_wrap and specialty_wrap.select_one("p:nth-of-type(2)"):
                        specialty = specialty_wrap.select_one("p:nth-of-type(2)").get_text(strip=True).replace(', &nbsp', ',')
                    link_tag = item.select_one("a.doctor-view-button")
                    detail_link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "링크 없음"
                    all_doctors_in_dept.append({'소속진료과': dept_name, '이름': name, '세부전공': specialty, '상세정보링크': detail_link})
                page_index += 1
                time.sleep(0.3)
            except requests.exceptions.RequestException as e:
                print(f"      - {dept_name} {page_index}페이지 처리 중 에러: {e}")
                break
    unique_doctors = [dict(t) for t in {tuple(d.items()) for d in all_doctors_in_dept}]
    return unique_doctors

def fetch_doctor_details(detail_url, headers):
    """의료진 상세 페이지에서 학력/경력 정보를 추출하는 함수"""
    details = {"학력": "정보 없음", "경력": "정보 없음"}
    if not detail_url or "javascript" in detail_url or detail_url == "링크 없음":
        return details

    try:
        # Step 1: 메인 페이지에서 기본 정보 수집
        response = requests.get(detail_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Step 2: 먼저 정적 HTML에서 기본 학력/경력 정보 수집
        education_list = []
        experience_list = []
        
        # 학력/경력 섹션 찾기 (id="career")
        career_section = soup.find('div', {'id': 'career'})
        if career_section:
            print(f"        [DEBUG] career 섹션 발견")
            
            # 학력/경력이 하나의 ul 안에 h3로 구분되어 있음
            current_section = None
            
            # career 섹션 내의 모든 요소를 순서대로 처리
            for element in career_section.find_all(['h3', 'li']):
                if element.name == 'h3':
                    # 섹션 제목 확인
                    section_title = element.get_text(strip=True)
                    if '학력' in section_title:
                        current_section = '학력'
                        print(f"        [DEBUG] 학력 섹션 시작")
                    elif '경력' in section_title:
                        current_section = '경력'
                        print(f"        [DEBUG] 경력 섹션 시작")
                    else:
                        current_section = None
                
                elif element.name == 'li' and element.has_attr('class') and 'blogCont-history-item' in element['class']:
                    # 학력/경력 항목 처리
                    if current_section:
                        # 날짜 추출 (p 태그)
                        date_p = element.find('p', class_='blogCont-history-date')
                        date_text = date_p.get_text(strip=True) if date_p else ''
                        
                        # 내용 추출 (div > p 구조)
                        content_p = element.find('p', class_='blogCont-history-content')
                        content_text = content_p.get_text(strip=True) if content_p else ''
                        
                        if content_text:
                            history_item = f"{date_text} {content_text}".strip()
                            
                            if current_section == '학력':
                                education_list.append(history_item)
                            elif current_section == '경력':
                                experience_list.append(history_item)
        
        else:
            # career 섹션이 없는 경우 기존 방식으로 시도
            print(f"        [DEBUG] career 섹션 없음, 기존 방식으로 시도")
            
            # 학력 섹션 찾기
            edu_h3 = soup.find('h3', string=lambda text: text and '학력' in text)
            if edu_h3:
                # 다음 ul 또는 형제 요소들에서 li 찾기
                next_sibling = edu_h3.find_next_sibling()
                while next_sibling:
                    if next_sibling.name == 'h3' and '경력' in next_sibling.get_text():
                        break
                    if next_sibling.name == 'li' and 'blogCont-history-item' in (next_sibling.get('class') or []):
                        date_p = next_sibling.find('p', class_='blogCont-history-date')
                        content_p = next_sibling.find('p', class_='blogCont-history-content')
                        
                        date_text = date_p.get_text(strip=True) if date_p else ''
                        content_text = content_p.get_text(strip=True) if content_p else ''
                        
                        if content_text:
                            history_item = f"{date_text} {content_text}".strip()
                            education_list.append(history_item)
                    
                    next_sibling = next_sibling.find_next_sibling()
            
            # 경력 섹션 찾기
            exp_h3 = soup.find('h3', string=lambda text: text and '경력' in text)
            if exp_h3:
                next_sibling = exp_h3.find_next_sibling()
                while next_sibling:
                    if next_sibling.name == 'h3':
                        break
                    if next_sibling.name == 'li' and 'blogCont-history-item' in (next_sibling.get('class') or []):
                        date_p = next_sibling.find('p', class_='blogCont-history-date')
                        content_p = next_sibling.find('p', class_='blogCont-history-content')
                        
                        date_text = date_p.get_text(strip=True) if date_p else ''
                        content_text = content_p.get_text(strip=True) if content_p else ''
                        
                        if content_text:
                            history_item = f"{date_text} {content_text}".strip()
                            experience_list.append(history_item)
                    
                    next_sibling = next_sibling.find_next_sibling()
        
        print(f"        정적 HTML: 학력 {len(education_list)}개, 경력 {len(experience_list)}개 항목 수집")
        
        # Step 3: 더보기 버튼 확인 및 AJAX 데이터 추가 수집
        more_button = soup.find('button', {'id': 'addCarBtn'}) or soup.find('a', {'id': 'addCarBtn'})
        if more_button:
            print(f"        더보기 버튼 발견, AJAX 추가 데이터 수집 시작...")
            
            # doctor_id를 URL에서 추출 (예: /blog/01102/philosophy.do)
            doctor_id = None
            url_match = re.search(r'/blog/(\d+)/', detail_url)
            if url_match:
                doctor_id = url_match.group(1)
            else:
                # JavaScript 변수에서 추출 시도
                dr_cd_match = re.search(r'var\s+dr_cd\s*=\s*["\'](\d+)["\']', response.text)
                if dr_cd_match:
                    doctor_id = dr_cd_match.group(1)
            
            if doctor_id:
                print(f"        Doctor ID: {doctor_id}")
                
                # totalCareerCount 추출해서 전체 데이터 가져오기
                total_count_match = re.search(r'var\s+totalCareerCount\s*=\s*(\d+)', response.text)
                total_count = int(total_count_match.group(1)) if total_count_match else 100
                
                # AJAX로 전체 경력 정보 가져오기
                ajax_url = f"https://www.snuh.org/m/blog/{doctor_id}/ajaxMobileCareer.do"
                params = {'firstIndex': '0', 'lastIndex': str(total_count)}
                
                ajax_response = requests.get(ajax_url, headers=headers, params=params, timeout=15)
                ajax_response.raise_for_status()
                
                if ajax_response.text.strip():
                    try:
                        ajax_data = ajax_response.json()
                        
                        # AJAX 데이터에서 추가 학력/경력 정보 추출
                        ajax_education_list = []
                        ajax_experience_list = []
                        current_section = None
                        
                        print(f"        AJAX: 총 {len(ajax_data)}개의 항목 처리 중...")
                        
                        for item in ajax_data:
                            gubun = item.get('gubun', '')
                            content = item.get('content') or ''  # None일 경우 빈 문자열로 처리
                            sdate = item.get('sdate') or ''      # None일 경우 빈 문자열로 처리
                            
                            content = content.strip() if content else ''
                            sdate = sdate.strip() if sdate else ''
                            
                            if gubun == 'TITLE':
                                if '학력' in content:
                                    current_section = '학력'
                                elif '경력' in content:
                                    current_section = '경력'
                                else:
                                    current_section = '기타'  # 학회 등 기타 정보
                            elif gubun == 'CAR' and current_section in ['학력', '경력']:
                                # CAR은 주로 경력 정보
                                if content and current_section:
                                    history_item = f"{sdate} {content}" if sdate else content
                                    if current_section == '학력':
                                        ajax_education_list.append(history_item)
                                    elif current_section == '경력':
                                        ajax_experience_list.append(history_item)
                            elif gubun == 'EDU' and current_section == '학력':
                                # EDU는 학력 정보
                                if content:
                                    history_item = f"{sdate} {content}" if sdate else content
                                    ajax_education_list.append(history_item)
                        
                        # 기존 리스트와 AJAX 리스트 합치기 (중복 제거)
                        all_education = education_list + [item for item in ajax_education_list if item not in education_list]
                        all_experience = experience_list + [item for item in ajax_experience_list if item not in experience_list]
                        
                        education_list = all_education
                        experience_list = all_experience
                        
                        print(f"        AJAX 추가: 학력 {len(ajax_education_list)}개, 경력 {len(ajax_experience_list)}개 항목")
                        
                    except json.JSONDecodeError:
                        print(f"        AJAX JSON 파싱 실패")
                else:
                    print(f"        AJAX 응답 데이터 없음")
            else:
                print(f"        Doctor ID를 찾을 수 없음")
        else:
            print(f"        더보기 버튼 없음, 정적 데이터만 사용")
        
        # 최종 결과 설정
        details['학력'] = "\n".join(education_list) if education_list else "정보 없음"
        details['경력'] = "\n".join(experience_list) if experience_list else "정보 없음"
        
        print(f"        최종: 학력 {len(education_list)}개, 경력 {len(experience_list)}개 항목")
        
    except requests.exceptions.RequestException as e:
        print(f"        [Error] 네트워크 에러: {e}")
    except Exception as e:
        print(f"        [Error] 예상치 못한 에러: {e}")
    
    return details



if __name__ == "__main__":
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Referer': 'https://www.snuh.org/'
    }
    
    departments = get_snuh_department_codes()
    
    if departments:
        all_doctors_list = []
        print("\n2단계: 각 부서별 의료진 목록 수집을 시작합니다...")
        for i, dept in enumerate(departments):
            print(f"  - ({i+1}/{len(departments)}) {dept['진료과명']} 의료진 목록 수집 중...")
            doctors_in_dept = fetch_doctors_from_department(dept, headers)
            if doctors_in_dept:
                all_doctors_list.extend(doctors_in_dept)
        
        print(f"\n✅ 2단계 완료: 총 {len(all_doctors_list)}명의 의료진 목록을 수집했습니다.")
        

        print("\n3단계: 각 의료진의 상세 정보(학력/경력) 수집을 시작합니다...")
        
        final_data = []
        for i, doc in enumerate(all_doctors_list):
            print(f"  - ({i+1}/{len(all_doctors_list)}) {doc['이름']} 의료진 상세 정보 수집 중...")
            details = fetch_doctor_details(doc['상세정보링크'], headers)
            
            doc['학력'] = details['학력']
            doc['경력'] = details['경력']
            final_data.append(doc)
            time.sleep(0.5)  # 요청 간격을 조금 늘림
            
        print(f"\n✅ 3단계 완료: 최종적으로 {len(final_data)}명의 상세 정보를 수집했습니다.")
        save_to_json(final_data, 'snuh_doctors_test_result.json')

        save_to_excel(final_data, 'snuh_doctors_final.xlsx')
    else:
        print("수집할 부서 정보가 없습니다.")