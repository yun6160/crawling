import re
import pandas as pd
import os
import json
from datetime import datetime # 날짜 생성을 위해 추가

def _generate_filenames(base_name):
    """(내부 헬퍼 함수) 주어진 기본 이름으로 최종 파일명들을 생성합니다."""
    today_str = datetime.now().strftime('%y%m%d')
    json_filename = f"{base_name}_crawling_{today_str}.json"
    excel_filename = f"{base_name}_crawling_{today_str}.xlsx"
    return json_filename, excel_filename

def _clean_text(text):
    """⭐️ (핵심 기능) 문자열에서 Excel에서 허용하지 않는 XML 제어 문자를 제거합니다."""
    if not isinstance(text, str):
        return text
    # \b 와 같은 문자를 여기서 걸러냅니다.
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

def save_to_excel(data, base_name):
    """
    주어진 데이터를 받아 Excel 파일로 저장합니다.
    - 중첩된 'profile' 데이터를 '학력', '경력' 컬럼으로 자동 분리
    - 리스트 데이터를 줄바꿈 문자열로 변환
    - ⭐️ 모든 문자열 데이터에서 불법 제어 문자 제거 (소독)
    """
    _, filename = _generate_filenames(base_name)

    if not data:
        print("⚠️ 변환할 데이터가 없습니다. Excel 파일을 생성하지 않습니다.")
        return

    print(f"\n🔄 데이터를 Excel 파일({filename})로 변환합니다...")
    
    try:
        # 1. 원본 데이터로 DataFrame 생성
        df = pd.DataFrame(data)

        # 2. 'profile' 컬럼이 있다면 펼쳐서 '학력', '경력' 컬럼으로 만듦
        if 'profile' in df.columns:
            profiles_df = df['profile'].fillna({}).apply(pd.Series)
            df = pd.concat([df.drop('profile', axis=1), profiles_df], axis=1)

        # 3. 모든 컬럼을 순회하며 데이터 형식 정리 및 정제
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, list)).any():
                df[col] = df[col].apply(lambda x: '\n'.join(x) if isinstance(x, list) else '')
            
            # ⭐️ 최종적으로 모든 문자열 데이터에서 제어 문자를 제거
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).apply(_clean_text)

        # 4. 완전히 정리된 DataFrame을 Excel 파일로 저장
        df.to_excel(filename, index=False, engine='openpyxl')
        
        print(f"✅ 성공! 데이터가 '{filename}' 파일로 저장되었습니다.")
        print(f"   -> 저장 위치: {os.path.abspath(filename)}")

    except Exception as e:
        print(f"❌ Excel 변환 중 에러 발생: {e}")

def save_to_json(data, base_name):
    """주어진 데이터와 기본 이름을 받아 오늘 날짜가 포함된 JSON 파일로 저장합니다."""
    filename, _ = _generate_filenames(base_name)

    print(f"\n💾 데이터를 JSON 파일({filename})로 저장합니다...")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ 성공! 데이터가 '{filename}' 파일로 저장되었습니다.")
    except (IOError, TypeError) as e:
        print(f"❌ 파일 저장 중 에러 발생: {e}")
