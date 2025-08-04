# main.py

from bs4 import BeautifulSoup
import requests
import math
import time
from utils.utils import save_to_json, save_to_excel

def get_profile_details(empNo, deptSeq):
    """empNo와 deptSeq를 받아 상세 페이지에서 학력/경력을 스크래핑하는 함수"""
    detail_url = f"https://gs.severance.healthcare/gs/doctor/doctor-view.do?empNo={empNo}&deptSeq={deptSeq}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=10) # 타임아웃 추가
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        profile_data = {}
        for dt in soup.select('dt.text-title'):
            title = dt.get_text(strip=True)
            if title in ['학력', '경력']:
                dd = dt.find_next_sibling('dd')
                if dd:
                    details = [li.get_text(strip=True) for li in dd.select('li')]
                    profile_data[title] = details
        return profile_data
    except requests.exceptions.RequestException:
        return {"error": "페이지를 가져올 수 없습니다."}
    except Exception:
        return {"error": "프로필 처리 중 알 수 없는 에러 발생"}

def scrape_gangnam_severance():
    """강남세브란스병원 의료진 정보를 스크래핑하는 메인 함수"""
    
    # 1. 모든 의사 기본 목록 가져오기
    base_url = "https://gs.severance.healthcare/api/doctor/list.do"
    page_per_num = 50
    params = {'insttCode': '4', 'tyCode': 'DP010100', 'page': 1, 'pagePerNum': page_per_num}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': 'https://gs.severance.healthcare/gs/doctor/doctor.do',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        print("1단계: 전체 의사 목록 수집을 시작합니다...")
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()
        first_page_data = response.json()
        
        if 'data' not in first_page_data or 'pagenation' not in first_page_data['data']:
            raise KeyError("'data' 또는 'pagenation' 키를 찾을 수 없습니다.")

        total_count = first_page_data['data']['pagenation']['totalCount']
        total_pages = math.ceil(total_count / page_per_num)
        print(f"총 의료진: {total_count}명, 총 페이지: {total_pages}페이지")

        all_doctors_list = []
        for page in range(1, total_pages + 1):
            params['page'] = page
            print(f"  - 목록 {page}/{total_pages} 페이지 요청 중...")
            response = requests.get(base_url, params=params, headers=headers)
            page_data = response.json()
            doctors_on_page = page_data.get('data', {}).get('list', [])
            if doctors_on_page:
                all_doctors_list.extend(doctors_on_page)
            time.sleep(0.3)
        
        print(f"기본 목록 수집 완료. 총 {len(all_doctors_list)}명")
        
        # 2. 각 의사의 상세 정보 스크래핑하여 추가
        print("\n2단계: 각 의사의 상세 정보 스크래핑을 시작합니다...")
        for i, doctor in enumerate(all_doctors_list):
            empNo = doctor.get('empNo')
            deptSeq = doctor.get('deptSeq')
            doctor_name = doctor.get('nm')

            if not empNo or not deptSeq:
                continue

            print(f"  - {i+1}/{len(all_doctors_list)}: {doctor_name} 의사 정보 가져오는 중...")
            profile_details = get_profile_details(empNo, deptSeq)
            doctor['profile'] = profile_details
            time.sleep(0.3)
            
        # 3. 최종 데이터 파일로 저장
        print("\n3단계: 모든 정보를 파일에 저장합니다...")

        file_name = '강남세브란스병원_gs'
        save_to_json(all_doctors_list, file_name)
        save_to_excel(all_doctors_list, file_name)

    except Exception as e:
        print(f"\n❌ 전체 프로세스 중단. 에러: {e}")

# 이 스크립트가 직접 실행될 때만 scrape_gangnam_severance() 함수를 호출
if __name__ == "__main__":
    scrape_gangnam_severance()