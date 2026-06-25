# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# 페이지 기본 설정
st.set_page_config(
    page_title="CIAM Attack Analysis Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# 0. 커스텀 CSS 스타일링 (Rich Aesthetics & Premium UX)
# ----------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

/* 전역 폰트 설정 */
html, body, [class*="css"] {
    font-family: 'Outfit', 'Noto Sans KR', sans-serif;
}

/* 사이드바 스타일링 */
[data-testid="stSidebar"] {
    background-color: #0E1117;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}

/* 카드 컴포넌트 스타일링 (Glassmorphism) */
.metric-card-box {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: all 0.3s ease-in-out;
}
.metric-card-box:hover {
    transform: translateY(-4px);
    border: 1px solid rgba(0, 242, 254, 0.4);
    box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.15);
}
.metric-card-title {
    font-size: 13px;
    color: #A0AEC0;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
}
.metric-card-value {
    font-size: 32px;
    font-weight: 800;
    background: linear-gradient(135deg, #00F2FE 0%, #4FACFE 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 4px;
}
.metric-card-desc {
    font-size: 11px;
    color: #718096;
}

/* 헤더 그라디언트 배너 */
.header-banner {
    background: linear-gradient(90deg, #1F1C2C 0%, #928DAB 100%);
    padding: 30px;
    border-radius: 20px;
    margin-bottom: 25px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 1. 데이터 로드 및 전처리 기법 (Caching 적용)
# ----------------------------------------------------
@st.cache_data
def load_data():
    # 로컬/서버 배포 경로 대응을 위해 데이터베이스 파일 탐색
    db_name = "attack_ciam.db"
    if not os.path.exists(db_name):
        # 차선책으로 ciam_attack.db 사용
        db_name = "ciam_attack.db"
        if not os.path.exists(db_name):
            return pd.DataFrame() # 빈 데이터프레임 반환
            
    conn = sqlite3.connect(db_name)
    df = pd.read_sql_query("SELECT * FROM attack_account", conn)
    conn.close()
    
    # [데이터 전처리]
    # 'approved_date' 가 '[NULL]' 이라는 문자열인 경우 실제 결측치(None)로 변환
    df['approved_date_clean'] = df['approved_date'].replace('[NULL]', None)
    
    # 날짜 데이터타입 파싱
    df['req_dt'] = pd.to_datetime(df['requested_date'], format='mixed', errors='coerce')
    df['app_dt'] = pd.to_datetime(df['approved_date_clean'], format='mixed', errors='coerce')
    
    # 신청~승인 지연 시간 계산 (초 단위)
    df['delay_sec'] = (df['app_dt'] - df['req_dt']).dt.total_seconds()
    
    # 시간대 컬럼 생성
    df['hour'] = df['req_dt'].dt.hour
    
    # 이메일 도메인 추출
    df['email_domain'] = df['requestor_email'].apply(lambda x: str(x).split('@')[-1] if '@' in str(x) else 'Unknown')
    
    # 이메일 ID 내 온점(dot) 개수 계산
    df['email_id_dots'] = df['requestor_email'].apply(lambda x: str(x).split('@')[0].count('.') if '@' in str(x) else 0)
    
    # 회사명 결측치 보완
    df['requestor_company_name'] = df['requestor_company_name'].fillna('Unknown')
    
    return df

df_raw = load_data()

if df_raw.empty:
    st.error("❌ 데이터베이스 파일을 로드할 수 없습니다. attack_ciam.db 또는 ciam_attack.db 파일이 존재하는지 확인해 주세요.")
    st.stop()

# ----------------------------------------------------
# 2. 사이드바 제어 패널 (Sidebar Controls)
# ----------------------------------------------------
st.sidebar.markdown("<h2 style='color:#00F2FE;'>🛡️ 필터 컨트롤러</h2>", unsafe_allow_html=True)
st.sidebar.write("대시보드 분석용 데이터를 실시간으로 제어합니다.")

# DB 정보 및 환경 표시
st.sidebar.info(f"📂 **DB 파일**: `attack_ciam.db` ({len(df_raw):,} 건)")

# 필터 1: 가입 채널 멀티 셀렉터
all_channels = sorted(df_raw['channel'].dropna().unique().tolist())
selected_channels = st.sidebar.multiselect(
    "💬 가입 채널 필터",
    options=all_channels,
    default=all_channels
)

# 필터 2: 통합 키워드 검색기
st.sidebar.markdown("---")
st.sidebar.markdown("🔍 **실시간 키워드 분석 필터**")
search_keyword = st.sidebar.text_input(
    "검색어 입력",
    value="",
    placeholder="이메일, 회사명, 회사코드 등..."
)

search_column = st.sidebar.selectbox(
    "검색 적용 열 선택",
    options=["전체(All)", "requestor_email", "requestor_company_name", "requestor_company_code"]
)

# ----------------------------------------------------
# 3. 데이터 필터링 수행
# ----------------------------------------------------
df = df_raw.copy()

# 채널 필터 적용
if selected_channels:
    df = df[df['channel'].isin(selected_channels)]

# 키워드 검색 필터 적용
if search_keyword.strip():
    keyword_lower = search_keyword.strip().lower()
    if search_column == "전체(All)":
        df = df[
            df['requestor_email'].str.lower().str.contains(keyword_lower, na=False) |
            df['requestor_company_name'].str.lower().str.contains(keyword_lower, na=False) |
            df['requestor_company_code'].str.lower().str.contains(keyword_lower, na=False)
        ]
    else:
        df = df[df[search_column].str.lower().str.contains(keyword_lower, na=False)]

# ----------------------------------------------------
# 4. 메인 화면 - 상단 타이틀 배너 및 요약 지표
# ----------------------------------------------------
st.markdown("""
<div class="header-banner">
    <h1 style="margin:0; color:#FFFFFF; font-size:32px; font-weight:800;">🛡️ CIAM 계정 등록 공격 탐지 대시보드</h1>
    <p style="margin:5px 0 0 0; color:#E2E8F0; font-size:14px;">회원 가입 트래픽 내 봇 대량 가입 패턴 및 어뷰징 계정 행동 분석 통계 화면</p>
</div>
""", unsafe_allow_html=True)

# 4대 KPI 요약 지표 연산
total_attempts = len(df)

if total_attempts > 0:
    # Gmail 계정 비중 (%)
    gmail_cnt = len(df[df['requestor_email'].str.endswith('@gmail.com', na=False)])
    gmail_ratio = (gmail_cnt / total_attempts) * 100
    
    # 초고속 자동 승인율 (%) -> 신청 후 1초 이하이고 approver_id가 system 인 건수 비율
    immediate_approve = df[(df['delay_sec'] <= 1.0) & (df['approver_id'] == 'system')]
    immediate_ratio = (len(immediate_approve) / total_attempts) * 100
    
    # 결측 계정 수 (approved_date가 '[NULL]'인 경우)
    missing_approvals = (df['approved_date'] == '[NULL]').sum()
else:
    gmail_ratio = 0
    immediate_ratio = 0
    missing_approvals = 0

# 요약 지표 레이아웃 (Glassmorphism 카드 매핑)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f"""
    <div class="metric-card-box">
        <div class="metric-card-title">총 가입 시도 건수</div>
        <div class="metric-card-value">{total_attempts:,}건</div>
        <div class="metric-card-desc">필터링 기준 현재 가입 요청 수</div>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""
    <div class="metric-card-box">
        <div class="metric-card-title">Gmail 계정 비중</div>
        <div class="metric-card-value">{gmail_ratio:.2f}%</div>
        <div class="metric-card-desc">전체 중 Gmail 도메인 사용 비율 ({gmail_cnt:,}건)</div>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    st.markdown(f"""
    <div class="metric-card-box">
        <div class="metric-card-title">초고속 자동 승인율</div>
        <div class="metric-card-value">{immediate_ratio:.2f}%</div>
        <div class="metric-card-desc">1초 이내 시스템 자동 승인 완료 건</div>
    </div>
    """, unsafe_allow_html=True)

with kpi4:
    st.markdown(f"""
    <div class="metric-card-box">
        <div class="metric-card-title">결측 계정 수 (미승인)</div>
        <div class="metric-card-value" style="background: linear-gradient(135deg, #FF0844 0%, #FFB199 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{missing_approvals:,}건</div>
        <div class="metric-card-desc">승인 일시가 존재하지 않는 대기 계정</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------
# 5. 메인 레이아웃 탭(Tab) 설계
# ----------------------------------------------------
tab1, tab2 = st.tabs(["📊 기초 EDA (탐색적 데이터 분석)", "🔍 키워드 기반 공격 패턴 비교"])

# ==========================================
# Tab 1: 기초 EDA 분석 화면
# ==========================================
with tab1:
    if total_attempts == 0:
        st.warning("⚠️ 필터 조건에 부합하는 데이터가 존재하지 않습니다. 필터를 조절해 주세요.")
    else:
        # --- 그래프 1: 시간대별 가입 신청 분포 ---
        st.markdown("### 1️⃣ 시간대별 가입 신청 분포")
        hour_counts = df['hour'].value_counts().reindex(range(24), fill_value=0).reset_index()
        hour_counts.columns = ['Hour', 'Count']
        
        fig1 = px.line(
            hour_counts, 
            x='Hour', 
            y='Count', 
            title='시간대별 가입 트래픽 추이 (0시 ~ 23시)',
            labels={'Hour': '시간대 (시)', 'Count': '가입 시도 (건)'},
            markers=True
        )
        # 차트 스타일 고도화
        fig1.update_traces(
            line=dict(color='#00F2FE', width=3, shape='spline'),
            marker=dict(size=8, color='#4FACFE', symbol='circle')
        )
        fig1.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#FFFFFF'),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickmode='linear', tick0=0, dtick=2),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            height=350
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # 그래프 1 하단 테이블: 시간대 x 채널 가입 신청 교차 피봇 테이블 (Crosstab)
        st.markdown("**🔍 시간대 x 채널 가입 신청 교차 분포 (Top 4 채널 및 기타)**")
        top_4_channels = df['channel'].value_counts().nlargest(4).index.tolist()
        df['channel_group'] = df['channel'].apply(lambda x: x if x in top_4_channels else 'Others')
        
        pivot_table = pd.crosstab(
            df['hour'], 
            df['channel_group'], 
            margins=True, 
            margins_name='Total'
        ).reindex(range(24), fill_value=0)
        
        # 합계 행 추가 정비
        all_crosstab = pd.crosstab(df['hour'], df['channel_group'])
        margin_sum = all_crosstab.sum().to_frame().T
        margin_sum.index = ['Total']
        pivot_table = pd.concat([all_crosstab, margin_sum])
        
        st.dataframe(pivot_table, use_container_width=True)
        st.markdown("---")
        
        
        # --- 그래프 2: 가입 유입 경로(Channel)별 점유 비율 ---
        col_g2, col_g3 = st.columns(2)
        
        with col_g2:
            st.markdown("### 2️⃣ 가입 유입 경로(Channel) 점유 비율")
            channel_counts = df['channel'].value_counts().reset_index()
            channel_counts.columns = ['Channel', 'Count']
            
            fig2 = px.pie(
                channel_counts, 
                names='Channel', 
                values='Count', 
                hole=0.45,
                title='유입 채널 비중',
                color_discrete_sequence=px.colors.sequential.Tealgrn
            )
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FFFFFF'),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                height=380
            )
            fig2.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig2, use_container_width=True)
            
            # 그래프 2 하단 테이블: 채널별 빈도 및 누적 비율
            st.markdown("**🔍 채널별 누적 가입 비중 통계**")
            ch_total = channel_counts['Count'].sum()
            channel_counts['비율(%)'] = (channel_counts['Count'] / ch_total) * 100
            channel_counts['누적 비율(%)'] = channel_counts['비율(%)'].cumsum()
            st.dataframe(
                channel_counts.rename(columns={'Channel': '채널명', 'Count': '가입 시도 건수'}),
                use_container_width=True,
                hide_index=True
            )
            
        # --- 그래프 3: 이메일 도메인 Top 10 분포 ---
        with col_g3:
            st.markdown("### 3️⃣ 이메일 도메인 Top 10 분포")
            domain_counts = df['email_domain'].value_counts().reset_index().head(10)
            domain_counts.columns = ['Domain', 'Count']
            
            # 가로 막대 그래프 구현 (Y축이 도메인명이므로 역순 정렬해서 출력)
            fig3 = px.bar(
                domain_counts.iloc[::-1], 
                x='Count', 
                y='Domain', 
                orientation='h',
                title='최다 가입 이메일 도메인 Top 10',
                color='Count',
                color_continuous_scale='Blues'
            )
            fig3.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FFFFFF'),
                coloraxis_showscale=False,
                height=380
            )
            fig3.update_traces(marker_line_color='rgba(0,0,0,0)', marker_line_width=0)
            st.plotly_chart(fig3, use_container_width=True)
            
            # 그래프 3 하단 테이블: 이메일 도메인 Top 10 빈도표
            st.markdown("**🔍 이메일 도메인 신뢰수준 분석**")
            domain_table = df['email_domain'].value_counts().reset_index().head(10)
            domain_table.columns = ['도메인 주소', '계정 수']
            domain_table['순위'] = domain_table.index + 1
            domain_table['비율(%)'] = (domain_table['계정 수'] / total_attempts) * 100
            
            # 도메인 신뢰 수준 라벨 부여 (임의 신뢰도 계산)
            normal_domains = ['gmail.com', 'naver.com', 'daum.net', 'hanmail.net', 'kakao.com', 'nate.com', 'outlook.com', 'hotmail.com']
            domain_table['도메인 신뢰 수준'] = domain_table['도메인 주소'].apply(
                lambda x: "🟢 정상 도메인 (포털)" if x in normal_domains else "🔴 의심 도메인 (임시/스팸)"
            )
            
            # 순위 컬럼을 가장 앞으로 배치
            domain_table = domain_table[['순위', '도메인 주소', '계정 수', '비율(%)', '도메인 신뢰 수준']]
            st.dataframe(domain_table, use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        
        # --- 그래프 4: 이메일 ID 내 온점(dot) 개수 분포 ---
        col_g4, col_g5 = st.columns(2)
        
        with col_g4:
            st.markdown("### 4️⃣ 이메일 ID 내 온점(dot) 개수 분포")
            # Gmail Dot Trick은 보통 Gmail 계정에서 유효하므로 가시성을 위해 Gmail에 표시
            gmail_only = df[df['email_domain'] == 'gmail.com']
            if gmail_only.empty:
                gmail_only = df # Gmail이 없을 경우 전체 대상
                st.caption("ℹ️ 분석 대상 Gmail 데이터가 없어 전체 데이터를 기준으로 분석합니다.")
            else:
                st.caption("ℹ️ Gmail Dot Trick 공격 모니터링을 위해 Gmail 계정(@gmail.com)만 필터링한 분포입니다.")
                
            dot_counts = gmail_only['email_id_dots'].value_counts().sort_index().reset_index()
            dot_counts.columns = ['Dots', 'Count']
            
            fig4 = px.bar(
                dot_counts, 
                x='Dots', 
                y='Count',
                title='Gmail 이메일 ID의 마침표(.) 개수별 계정 분포',
                labels={'Dots': '온점 개수 (개)', 'Count': '계정 수 (건)'},
                color='Count',
                color_continuous_scale='Purples'
            )
            fig4.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FFFFFF'),
                coloraxis_showscale=False,
                xaxis=dict(tickmode='linear', tick0=0, dtick=1),
                height=380
            )
            st.plotly_chart(fig4, use_container_width=True)
            
            # 그래프 4 하단 테이블: 기술 통계 요약 및 빈도 분포표
            st.markdown("**🔍 온점 수 요약 통계량 및 빈도표**")
            dot_desc = gmail_only['email_id_dots'].describe().to_frame().T
            dot_desc = dot_desc.rename(columns={
                'count': '전체 표본 수', 'mean': '평균', 'std': '표준편차',
                'min': '최솟값', '25%': '25%', '50%': '중앙값(50%)', '75%': '75%', 'max': '최댓값'
            })
            st.dataframe(dot_desc, use_container_width=True, hide_index=True)
            
            # 빈도표
            dot_dist = gmail_only['email_id_dots'].value_counts().sort_index().reset_index()
            dot_dist.columns = ['온점 개수', '계정 건수']
            dot_dist['백분율(%)'] = (dot_dist['계정 건수'] / len(gmail_only)) * 100
            st.dataframe(dot_dist, use_container_width=True, hide_index=True)
            
            
        # --- 그래프 5: 가입 신청 건수 Top 15 회사명 ---
        with col_g5:
            st.markdown("### 5️⃣ 최다 가입 신청 회사명 Top 15")
            # 회사명을 기준으로 직접 집계
            company_counts = df['requestor_company_name'].value_counts().reset_index().head(15)
            company_counts.columns = ['Company', 'Count']
            
            fig5 = px.bar(
                company_counts.iloc[::-1], 
                x='Count', 
                y='Company', 
                orientation='h',
                title='가입 신청 집중 타겟 회사명 Top 15',
                color='Count',
                color_continuous_scale='Reds'
            )
            fig5.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FFFFFF'),
                coloraxis_showscale=False,
                height=380
            )
            st.plotly_chart(fig5, use_container_width=True)
            
            # 그래프 5 하단 테이블: Top 15 회사명 통계 표 (피크 시간 포함)
            st.markdown("**🔍 Top 15 공격 의심 회사명 분석**")
            top_15_comp_names = df['requestor_company_name'].value_counts().head(15).index.tolist()
            
            company_details = []
            for name in top_15_comp_names:
                comp_df = df[df['requestor_company_name'] == name]
                
                # 대표 회사 코드 (가장 많이 매칭된 코드 구하기)
                if not comp_df['requestor_company_code'].empty:
                    code = comp_df['requestor_company_code'].mode().iloc[0]
                else:
                    code = "N/A"
                    
                cnt = len(comp_df)
                ratio = (cnt / total_attempts) * 100
                
                # 최빈 가입 시간대 구하기
                if not comp_df['hour'].empty:
                    peak_hour = int(comp_df['hour'].mode().iloc[0])
                    peak_str = f"{peak_hour:02d}시 ~ {(peak_hour+1):02d}시"
                else:
                    peak_str = "N/A"
                    
                company_details.append({
                    '회사명': name,
                    '대표 회사 코드': code,
                    '가입 건수': cnt,
                    '비율(%)': ratio,
                    '최빈 가입 시간대': peak_str
                })
                
            st.dataframe(pd.DataFrame(company_details), use_container_width=True, hide_index=True)


# ==========================================
# Tab 2: 키워드 기반 공격 패턴 비교 분석
# ==========================================
with tab2:
    st.markdown("### 🔍 특정 키워드 그룹 vs 비매칭 그룹 비교 분석")
    st.write("사이드바에 검색 키워드를 입력하시면, 해당 키워드를 포함한 그룹과 나머지 그룹의 보안 위협 지표를 대조하여 즉시 위협 수준을 시각화합니다.")
    
    # 키워드 검색 여부에 따라 분기
    if not search_keyword.strip():
        st.info("💡 사이드바의 **[실시간 키워드 분석 필터]**에 분석하고자 하는 특정 문자열(예: 회사명, 메일 키워드 등)을 입력해 주세요.")
    else:
        # 데이터 그룹화
        keyword_lower = search_keyword.strip().lower()
        if search_column == "전체(All)":
            matched_mask = (
                df_raw['requestor_email'].str.lower().str.contains(keyword_lower, na=False) |
                df_raw['requestor_company_name'].str.lower().str.contains(keyword_lower, na=False) |
                df_raw['requestor_company_code'].str.lower().str.contains(keyword_lower, na=False)
            )
        else:
            matched_mask = df_raw[search_column].str.lower().str.contains(keyword_lower, na=False)
            
        matched_df = df_raw[matched_mask]
        non_matched_df = df_raw[~matched_mask]
        
        # 키워드 필터가 채널 선택에도 종속되도록 반영
        if selected_channels:
            matched_df = matched_df[matched_df['channel'].isin(selected_channels)]
            non_matched_df = non_matched_df[non_matched_df['channel'].isin(selected_channels)]
            
        m_cnt = len(matched_df)
        nm_cnt = len(non_matched_df)
        
        if m_cnt == 0:
            st.warning(f"❌ 검색 키워드 '{search_keyword}'에 매칭되는 계정 데이터가 없습니다. 다른 키워드를 입력해 주세요.")
        else:
            # 1. 수치 연산
            # 평균 온점 개수
            m_dots = matched_df['email_id_dots'].mean()
            nm_dots = non_matched_df['email_id_dots'].mean() if nm_cnt > 0 else 0
            
            # 초고속 자동 승인율 (%)
            m_imm_cnt = len(matched_df[(matched_df['delay_sec'] <= 1.0) & (matched_df['approver_id'] == 'system')])
            m_imm_ratio = (m_imm_cnt / m_cnt) * 100 if m_cnt > 0 else 0
            
            nm_imm_cnt = len(non_matched_df[(non_matched_df['delay_sec'] <= 1.0) & (non_matched_df['approver_id'] == 'system')])
            nm_imm_ratio = (nm_imm_cnt / nm_cnt) * 100 if nm_cnt > 0 else 0
            
            # 특정 채널(가장 큰 위협 유입인 edo_attack) 점유 비중
            m_edo_cnt = len(matched_df[matched_df['channel'] == 'edo_attack'])
            m_edo_ratio = (m_edo_cnt / m_cnt) * 100 if m_cnt > 0 else 0
            
            nm_edo_cnt = len(non_matched_df[non_matched_df['channel'] == 'edo_attack'])
            nm_edo_ratio = (nm_edo_cnt / nm_cnt) * 100 if nm_cnt > 0 else 0
            
            # 2. 메트릭 카드 대조 화면
            st.markdown(f"#### 🎯 '{search_keyword}' 키워드 검색 그룹 ({m_cnt:,}건) vs 비매칭 그룹 ({nm_cnt:,}건) 교차 비교")
            
            col_k1, col_k2, col_k3 = st.columns(3)
            
            with col_k1:
                st.markdown(f"""
                <div class="metric-card-box" style="border: 1px solid rgba(155, 81, 224, 0.4);">
                    <div class="metric-card-title">평균 이메일 온점(dot) 수</div>
                    <div class="metric-card-value" style="background: linear-gradient(135deg, #E2B0FF 0%, #9B51E0 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                        {m_dots:.2f}개 <span style="font-size:16px; color:#A0AEC0;">vs {nm_dots:.2f}개</span>
                    </div>
                    <div class="metric-card-desc">아이디 내 점(.)의 평균 갯수 대조</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_k2:
                st.markdown(f"""
                <div class="metric-card-box" style="border: 1px solid rgba(0, 242, 254, 0.4);">
                    <div class="metric-card-title">초고속 자동 승인율</div>
                    <div class="metric-card-value">
                        {m_imm_ratio:.2f}% <span style="font-size:16px; color:#A0AEC0;">vs {nm_imm_ratio:.2f}%</span>
                    </div>
                    <div class="metric-card-desc">1초 이내 자동 승인 완료 비율</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_k3:
                st.markdown(f"""
                <div class="metric-card-box" style="border: 1px solid rgba(255, 8, 68, 0.4);">
                    <div class="metric-card-title">edo_attack 채널 유입 편중도</div>
                    <div class="metric-card-value" style="background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                        {m_edo_ratio:.2f}% <span style="font-size:16px; color:#A0AEC0;">vs {nm_edo_ratio:.2f}%</span>
                    </div>
                    <div class="metric-card-desc">가장 위험한 채널 집중성</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. 비교 시각화: 시간대별 가입 신청 분포 대조 (Grouped Bar Chart)
            st.markdown("#### 📈 두 그룹 간 시간대별 가입 트래픽 추이 비교")
            
            m_hours = matched_df['hour'].value_counts().reindex(range(24), fill_value=0).reset_index()
            m_hours.columns = ['Hour', 'Count']
            m_hours['Group'] = f"키워드 그룹 ('{search_keyword}')"
            # 가중치 비교를 위해 백분율로 환산
            m_hours['Ratio(%)'] = (m_hours['Count'] / m_cnt) * 100
            
            nm_hours = non_matched_df['hour'].value_counts().reindex(range(24), fill_value=0).reset_index()
            nm_hours.columns = ['Hour', 'Count']
            nm_hours['Group'] = '기타 비매칭 그룹'
            nm_hours['Ratio(%)'] = (nm_hours['Count'] / nm_cnt) * 100 if nm_cnt > 0 else 0
            
            compare_df = pd.concat([m_hours, nm_hours])
            
            fig_compare = px.bar(
                compare_df,
                x='Hour',
                y='Ratio(%)',
                color='Group',
                barmode='group',
                title='시간대별 유입량 비율 비교 (%)',
                labels={'Hour': '시간대 (시)', 'Ratio(%)': '해당 그룹 내 가입 비율 (%)'},
                color_discrete_sequence=['#9B51E0', '#4FACFE']
            )
            fig_compare.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FFFFFF'),
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickmode='linear', tick0=0, dtick=1),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                height=400
            )
            st.plotly_chart(fig_compare, use_container_width=True)
            
            # 요약 보고서 텍스트 생성
            st.markdown("#### 📄 분석 리포트 요약")
            
            report_text = f"""
            * 키워드 **`{search_keyword}`** 그룹은 총 **{m_cnt:,}건** 가입을 시도하였으며, 전체 트래픽 중 약 **{(m_cnt/len(df_raw))*100:.2f}%**를 차지합니다.
            * 이 그룹의 평균 온점(dot) 개수는 **{m_dots:.2f}개**로 비매칭 그룹 평균(**{nm_dots:.2f}개**)과 대조했을 때 """
            
            if m_dots > nm_dots + 1.0:
                report_text += "Gmail Dot Trick을 활용한 **어뷰징 우회 가입 징후가 매우 강력하게** 관찰됩니다. ⚠️"
            else:
                report_text += "온점 수 기준 특이 징후는 비교적 미비한 수준입니다. 🟢"
                
            report_text += f"""
            * 또한, 가입 신청 즉시 시스템에 의해 자동 승인 처리된 비율이 **{m_imm_ratio:.2f}%**에 달합니다. 
            * 가입에 집중된 유입 경로는 `{matched_df['channel'].value_counts().index[0]}`(이)며, 이 채널의 점유 비중은 **{(matched_df['channel'].value_counts().values[0] / m_cnt)*100:.2f}%** 입니다.
            """
            
            st.info(report_text)
