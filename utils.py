import pandas as pd
import os

def save_to_excel(data, filename):
    """
    주어진 데이터(딕셔너리 리스트)를 Excel 파일로 저장합니다.
    중첩된 'profile' 데이터를 '학력', '경력' 컬럼으로 분리하여 저장합니다.
    """
    if not data:
        print("⚠️ 변환할 데이터가 없습니다. Excel 파일을 생성하지 않습니다.")
        return

    print(f"\n🔄 데이터를 Excel 파일로 변환합니다...")
    try:
        # 1. pandas DataFrame으로 변환
        df = pd.DataFrame(data)

        # 2. 중첩된 'profile' 컬럼 처리
        # 'profile' 컬럼이 있는지, 그리고 딕셔너리를 포함하고 있는지 확인
        if 'profile' in df.columns and isinstance(df['profile'].iloc[0], dict):
            # .apply(pd.Series)를 사용해 딕셔너리를 여러 컬럼으로 확장
            profile_df = df['profile'].apply(pd.Series)
            
            # '학력', '경력' 컬럼이 리스트 형태일 경우, 줄바꿈 문자로 연결된 문자열로 변환
            # 이렇게 해야 Excel 셀 하나에 여러 줄로 표시됨
            for col_name in ['학력', '경력']:
                if col_name in profile_df.columns:
                    profile_df[col_name] = profile_df[col_name].apply(
                        lambda items: '\n'.join(items) if isinstance(items, list) else items
                    )
            
            # 기존 DataFrame에서 원본 'profile' 컬럼을 삭제하고, 확장된 컬럼들을 병합
            df = df.drop('profile', axis=1)
            df = pd.concat([df, profile_df], axis=1)

        # 3. DataFrame을 Excel 파일로 저장
        # index=False 옵션으로 불필요한 인덱스 열 제거
        df.to_excel(filename, index=False, engine='openpyxl')
        
        print(f"✅ 성공! 데이터가 '{filename}' 파일로 저장되었습니다.")
        # 사용자가 파일을 쉽게 찾도록 절대 경로 출력
        print(f"   -> 저장 위치: {os.path.abspath(filename)}")

    except Exception as e:
        print(f"❌ Excel 변환 중 에러 발생: {e}")
