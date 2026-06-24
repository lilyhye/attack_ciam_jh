# -*- coding: utf-8 -*-
"""
공격 패턴 Top 5 분석을 터미널에 출력하는 고도화된 스크립트입니다.
"""

import sys
import io
import os
import sqlite3
import pandas as pd

# Windows 터미널에서 한글이 정상 출력되도록 설정
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

# 파일 경로 정의
db_path = r"C:\Users\JMC003\Desktop\attack_ciam\ciam_attack.db"
sheet_name = "_attack 계정"
table_name = "attack_account"

    try:
        # 두 번째 행(인덱스 1)을 컬럼 이름(Header)으로 지정하여 로드
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=1, engine='openpyxl')
        print(f"   - 로드 완료. 초기 데이터 크기: {df.shape[0]} 행 x {df.shape[1]} 열")
        
        # 2. 데이터 전처리 (이름 없는 빈 컬럼 제거)
        # 컬럼 이름에 'Unnamed'가 들어간 컬럼들을 필터링하여 제거합니다.
        cleaned_columns = [col for col in df.columns if not str(col).startswith('Unnamed')]
        df = df[cleaned_columns]
        print(f"2. 불필요한 빈 컬럼 제거 완료. 정제 후 크기: {df.shape[0]} 행 x {df.shape[1]} 열")

        # 3. SQLite 데이터베이스에 연결 및 데이터 쓰기
        print(f"3. SQLite DB 연결 중... ({db_path})")
        conn = sqlite3.connect(db_path)
        
        # 데이터프레임을 SQLite 테이블로 저장 (기존 테이블이 있으면 덮어씁니다: replace)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.commit()
        
        # 저장 확인
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        print(f"4. 데이터베이스 저장 성공!")
        print(f"   - 생성된 테이블명: {table_name}")
        print(f"   - 데이터베이스에 저장된 행(Row) 수: {row_count}개")
        
        conn.close()
        
        # ----------------------------------------------------
        # [신규 기능] 데이터 기반 공격 패턴 분석 Top 5 출력
        # ----------------------------------------------------
        print("\n" + "="*60)
        print("                 [ 공격 패턴 분석 Top 5 ]")
        print("="*60)
        
        total_cnt = len(df)
        
        # 1. 가입 채널 편중 공격 (edo_attack 채널 비율)
        edo_cnt = len(df[df['channel'] == 'edo_attack'])
        print(f"1. 가입 채널 편중 공격 (edo_attack 채널 집중):")
        print(f"   - 건수: {edo_cnt}건 / 비율: {edo_cnt/total_cnt*100:.2f}%")
        
        # 2. Gmail Dot Trick 기법 남용 (온점 1개 이상 포함 Gmail)
        gmail_df = df[df['requestor_email'].str.endswith('@gmail.com', na=False)]
        dot_trick_df = gmail_df[gmail_df['requestor_email'].apply(lambda x: str(x).split('@')[0].count('.') >= 1)]
        print(f"2. Gmail Dot Trick 기법 남용 (온점 포함 Gmail 계정):")
        print(f"   - 건수: {len(dot_trick_df)}건 / 비율: {len(dot_trick_df)/total_cnt*100:.2f}%")
        
        # 3. 초고속 기계적 가입 승인 (신청 1초 이내 자동 승인)
        df['req_dt'] = pd.to_datetime(df['requested_date'], format='mixed', errors='coerce')
        df['app_dt'] = pd.to_datetime(df['approved_date'], format='mixed', errors='coerce')
        df['delay_sec'] = (df['app_dt'] - df['req_dt']).dt.total_seconds()
        immediate_approve = df[df['delay_sec'] <= 1.0]
        print(f"3. 초고속 기계적 가입 승인 (신청 후 1초 이내 승인 완료):")
        print(f"   - 건수: {len(immediate_approve)}건 / 비율: {len(immediate_approve)/total_cnt*100:.2f}%")
        
        # 4. 기계적 동시 가입 시도 (동일 초당 대량 신청)
        # requested_date 컬럼을 초 단위 문자열로 포맷팅하여 카운트
        time_counts = df['req_dt'].value_counts()
        concurrent_cnt = time_counts[time_counts > 1].sum()
        print(f"4. 기계적 동시 가입 시도 (동일 초에 2건 이상 중복 신청):")
        print(f"   - 건수: {concurrent_cnt}건 / 비율: {concurrent_cnt/total_cnt*100:.2f}%")
        
        # 5. 특정 회사 코드 대량 가입 (Top 1 가입 의심 회사)
        company_counts = df['requestor_company_code'].value_counts()
        if not company_counts.empty:
            top_comp_code = company_counts.index[0]
            top_comp_name = df[df['requestor_company_code'] == top_comp_code]['requestor_company_name'].iloc[0]
            top_comp_cnt = company_counts.values[0]
            print(f"5. 특정 회사 코드 대량 가입 (가장 많이 기재된 가짜 회사 코드):")
            print(f"   - 코드: {top_comp_code} ({top_comp_name})")
            print(f"   - 건수: {top_comp_cnt}건 / 비율: {top_comp_cnt/total_cnt*100:.2f}%")
        else:
            print(f"5. 특정 회사 코드 대량 가입: 데이터 없음")
            
        print("="*60)

    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
