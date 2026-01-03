import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import stock_v2.core.pipeline
import importlib
importlib.reload(stock_v2.core.pipeline)
from stock_v2.core.pipeline import MarketScanner

st.set_page_config(page_title="Stock V2 Analyzer", layout="wide")

st.title("📈 Stock V2 Market Analyzer")
st.caption("KIS API 기반 실시간 수급/주도주 분석 (P1 & P2)")

# 사이드바: 설정
st.sidebar.header("설정")
analysis_date = st.sidebar.date_input("분석 기준일", datetime.now())
# datetime 객체로 변환
target_datetime = datetime.combine(analysis_date, datetime.min.time())

# 탭 구성 (현재는 탭 1만 구현)
tab1, tab2 = st.tabs(["📊 시장 스캔 (P1/P2)", "🔍 종목 검색 (준비중)"])

with tab1:
    st.header("시장 전체 스캔")
    
    with st.expander("📋 분석 로직 설명"):
        st.markdown("""
        * **P1 (지수 주도주)**: 시장 상승을 이끄는 대장주
          - **조건**: 시가총액 * 등락률 (지수 기여도) 상위 종목
          - **Target**: KOSPI/KOSDAQ 통합 Top 5
        
        * **P2 (수급 주도주)**: 외국인/기관 양매수 집중 종목
          - **조건**: (외국인 순매수 Top 50 ∩ 기관 순매수 Top 50) AND (양매수 필수)
          - **분류**:
            - **🌱 초기포착**: 외인 연속 2-4일 & 이격도 105% 이하
            - **🚀 추세확정**: 외인 연속 5-9일 & 이격도 105-115%
            - **🔥 과열/주의**: 외인 연속 10일↑ OR 이격도 120%↑
        """)

    col1, col2 = st.columns(2)
    with col1:
        # 통합 스캔이 기본이므로 선택 옵션 제거하고 안내 문구로 대체
        st.info("✅ KOSPI와 KOSDAQ을 통합하여 분석합니다.")
        # scan_mode 변수는 내부적으로 "통합 스캔"으로 고정
        scan_mode = "통합 스캔 (KOSPI + KOSDAQ)"
    
    with col2:
        top_n = st.number_input("시장별 스캔 종목 수 (시총 상위)", min_value=50, max_value=300, value=100, step=50)

    if st.button("🚀 스캔 시작", key="btn_scan_v2"):
        scanner = MarketScanner()
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        results_kospi = pd.DataFrame()
        results_kosdaq = pd.DataFrame()
        
        try:
            # 1. KOSPI Scan
            if scan_mode != "KOSDAQ만":
                status_text.text(f"KOSPI 시가총액 상위 {top_n}개 스캔 중...")
                
                def update_kospi(p, msg):
                    # KOSPI는 전체의 0~50% 구간 사용
                    current_p = int(p * 50)
                    progress_bar.progress(current_p)
                    status_text.text(msg)
                    
                results_kospi = scanner.run_scan(market_type="KOSPI", top_n=top_n, target_date=target_datetime, progress_callback=update_kospi)
            
            # 2. KOSDAQ Scan
            if scan_mode != "KOSPI만":
                status_text.text(f"KOSDAQ 시가총액 상위 {top_n}개 스캔 중...")
                
                def update_kosdaq(p, msg):
                    # KOSDAQ은 전체의 50~100% 구간 사용
                    # KOSPI를 안 했으면 0~100% 사용해야 하지만, 여기서는 통합 스캔 기준
                    base = 50 if scan_mode != "KOSDAQ만" else 0
                    scale = 50 if scan_mode != "KOSDAQ만" else 100
                    
                    current_p = base + int(p * scale)
                    if current_p > 100: current_p = 100
                    progress_bar.progress(current_p)
                    status_text.text(msg)
                    
                results_kosdaq = scanner.run_scan(market_type="KOSDAQ", top_n=top_n, target_date=target_datetime, progress_callback=update_kosdaq)
                
            # 3. 결과 통합 및 P1/P2 필터링
            status_text.text("결과 분석 및 필터링 중...")
            
            all_results = pd.concat([results_kospi, results_kosdaq], ignore_index=True)
            
            if all_results.empty:
                st.warning("스캔 결과가 없습니다. 장이 열리지 않았거나 데이터가 부족할 수 있습니다.")
            else:
                # --- P1 결과 처리 ---
                st.subheader("🏆 P1: 지수 주도주 (Index Leaders)")
                # 기여도(contribution) 양수인 것 중 상위 5개
                p1_candidates = all_results[all_results['contribution'] > 0].copy()
                if not p1_candidates.empty:
                    p1_final = p1_candidates.sort_values(by='contribution', ascending=False).head(5)
                    
                    # 포맷팅
                    p1_display = p1_final[['code', 'name', '현재가', '등락률', 'contribution', '외국인순매수', '기관순매수']].copy()
                    p1_display['contribution'] = p1_display['contribution'].apply(lambda x: f"{x/100000000:.1f}억")
                    p1_display['외국인순매수'] = p1_display['외국인순매수'].apply(lambda x: f"{x/100000000:.1f}억")
                    p1_display['기관순매수'] = p1_display['기관순매수'].apply(lambda x: f"{x/100000000:.1f}억")
                    p1_display['등락률'] = p1_display['등락률'].apply(lambda x: f"{x:.2f}%")
                    p1_display['현재가'] = p1_display['현재가'].apply(lambda x: f"{x:,}원")
                    
                    st.dataframe(p1_display, use_container_width=True)
                else:
                    st.info("P1 조건(지수 기여도 양수)을 만족하는 종목이 없습니다.")

                # --- P2 결과 처리 ---
                st.subheader("🌊 P2: 수급 주도주 (Supply Leaders)")
                
                # 각 시장별로 P2 필터링 수행 후 병합 (Top 50 교집합 로직은 시장별로 적용해야 함)
                p2_list = []
                if not results_kospi.empty:
                    p2_list.append(scanner.filter_p2_stocks(results_kospi))
                if not results_kosdaq.empty:
                    p2_list.append(scanner.filter_p2_stocks(results_kosdaq))
                
                if p2_list:
                    p2_final = pd.concat(p2_list, ignore_index=True)
                else:
                    p2_final = pd.DataFrame()

                if not p2_final.empty:
                    # 정렬: 연속 매수 일수 내림차순
                    if 'consecutive_days' in p2_final.columns:
                        p2_final = p2_final.sort_values(by='consecutive_days', ascending=False)
                    
                    # 포맷팅
                    cols = ['code', 'name', 'stage', '이격도', 'consecutive_days', '외국인순매수', '기관순매수', '등락률', '현재가']
                    display_cols = [c for c in cols if c in p2_final.columns]
                    
                    p2_display = p2_final[display_cols].copy()
                    
                    # 컬럼명 한글화/직관화
                    col_map = {
                        'code': '종목코드', 'name': '종목명', 'stage': '진입단계', 
                        'consecutive_days': '외인연속(일)', '외국인순매수': '외인순매수', 
                        '기관순매수': '기관순매수'
                    }
                    p2_display = p2_display.rename(columns=col_map)
                    
                    # 숫자 포맷팅
                    if '외인순매수' in p2_display.columns:
                        p2_display['외인순매수'] = p2_display['외인순매수'].apply(lambda x: f"{x/100000000:.1f}억")
                    if '기관순매수' in p2_display.columns:
                        p2_display['기관순매수'] = p2_display['기관순매수'].apply(lambda x: f"{x/100000000:.1f}억")
                    if '이격도' in p2_display.columns:
                        p2_display['이격도'] = p2_display['이격도'].apply(lambda x: f"{x:.1f}%")
                    if '등락률' in p2_display.columns:
                        p2_display['등락률'] = p2_display['등락률'].apply(lambda x: f"{x:.2f}%")
                    if '현재가' in p2_display.columns:
                        p2_display['현재가'] = p2_display['현재가'].apply(lambda x: f"{x:,}원")

                    # 스타일링 (색상 강조)
                    def highlight_stage(val):
                        color = ''
                        if '초기포착' in str(val):
                            color = 'background-color: #e6fffa; color: #006644' # 민트/초록
                        elif '추세확정' in str(val):
                            color = 'background-color: #fff0f0; color: #cc0000' # 연한 빨강
                        elif '과열' in str(val):
                            color = 'background-color: #fff5e6; color: #993300' # 주황
                        return color

                    st.dataframe(p2_display.style.applymap(highlight_stage, subset=['진입단계']), use_container_width=True)
                else:
                    st.info("P2 조건(양매수 & Top 50 교집합)을 만족하는 종목이 없습니다.")
            
            progress_bar.progress(100)
            status_text.text("분석 완료!")
            
        except Exception as e:
            st.error(f"오류 발생: {e}")
            import traceback
            st.text(traceback.format_exc())

with tab2:
    st.info("종목 상세 분석 기능은 준비 중입니다.")
