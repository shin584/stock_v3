import time
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from stock_v2.core.data_fetcher import DataFetcher
from stock_v2.core.strategy import StockStrategy
from stock_v2.core.indicators import calculate_indicators
import json
import os

class MarketScanner:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.strategy = StockStrategy()

    def _load_tickers(self, market_type="KOSPI", top_n=100):
        """
        로컬 파일(tickers.json)에서 시가총액 상위 종목 로드
        """
        # stock_v2/tickers.json 경로 찾기 (pipeline.py는 stock_v2/core/에 위치)
        # __file__ = .../stock_v2/core/pipeline.py
        # dirname(__file__) = .../stock_v2/core
        # dirname(...) = .../stock_v2
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, 'tickers.json')
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                df_all = pd.DataFrame(data)
                # 시장 필터링
                df_market = df_all[df_all['market'] == market_type]
                # 시가총액 상위 N개
                return df_market.head(top_n).copy()
        else:
            print(f"로컬 파일도 찾을 수 없습니다: {file_path}")
            return pd.DataFrame()

    def filter_p2_stocks(self, df_results):
        """
        P2 (수급 주도주) 필터링 로직
        - Group A: 코스피 외인 순매수 Top 50 ∩ 기관 순매수 Top 50
        - Group B: 코스닥 외인 순매수 Top 50 ∩ 기관 순매수 Top 50
        - Final: Group A + Group B -> 외국인 연속 매수 일수 정렬
        """
        if df_results.empty:
            return pd.DataFrame()
            
        # 0. 양수 필터링 (순매수가 양수인 종목만 대상)
        # "양매수"가 전제 조건이므로 둘 다 0보다 커야 함
        df_positive = df_results[
            (df_results['외국인순매수'] > 0) & 
            (df_results['기관순매수'] > 0)
        ].copy()
        
        if df_positive.empty:
            return pd.DataFrame()
        
        # 1. 외인 순매수 Top 50 (양수 중에서)
        top50_foreign = df_positive.sort_values(by='외국인순매수', ascending=False).head(50)
        codes_foreign = set(top50_foreign['code'])
        
        # 2. 기관 순매수 Top 50 (양수 중에서)
        top50_inst = df_positive.sort_values(by='기관순매수', ascending=False).head(50)
        codes_inst = set(top50_inst['code'])
        
        # 3. 교집합
        intersection = codes_foreign.intersection(codes_inst)
        
        # 교집합 종목만 추출
        p2_final = df_positive[df_positive['code'].isin(intersection)].copy()
        
        # P2 단계 분류 (Stage Classification)
        def classify_stage(row):
            days = row.get('consecutive_days', 0)
            disp = row.get('이격도', 0)
            
            # 3. 과열/주의 (Overheated)
            # 외국인 연속 순매수 10일 이상 OR 이격도 120% 이상
            if days >= 10 or disp >= 120:
                return "🔥과열/주의"
                
            # 2. 추세 확정 (Trend Confirmation)
            # 외국인 연속 순매수 5~9일 AND 이격도 105~115%
            if 5 <= days <= 9 and 105 <= disp <= 115:
                return "🚀추세확정"
                
            # 1. 초기 포착 (Early Detection)
            # 외국인 연속 순매수 2~4일 AND 이격도 105% 이하
            if 2 <= days <= 4 and disp <= 105:
                return "🌱초기포착"
                
            return "👀관망/기타"

        if not p2_final.empty:
            p2_final['stage'] = p2_final.apply(classify_stage, axis=1)

        # 연속 매수 일수 내림차순 정렬
        if 'consecutive_days' in p2_final.columns:
            p2_final = p2_final.sort_values(by='consecutive_days', ascending=False)
            
        return p2_final

    def run_scan(self, market_type="KOSPI", top_n=100, target_date=None, progress_callback=None):
        """
        KIS API 기반 순수 스캔 실행
        1. 로컬 파일에서 시가총액 상위 종목 로드
        2. KIS API로 각 종목의 상세 데이터 조회 및 분석
        """
        print(f"[{market_type}] 스캔 시작 (Pure KIS Mode)...")
        
        tickers_df = self._load_tickers(market_type, top_n)
        
        if tickers_df.empty:
            print("종목 리스트를 가져오지 못했습니다.")
            return pd.DataFrame()
            
        print(f"분석 대상: {len(tickers_df)}개 종목 (시가총액 상위)")
        
        results = []
        
        # Analyze using KIS API
        # tqdm으로 진행상황 표시
        
        def process_stock(row):
            ticker = row['code']
            name = row['name']
            
            # KIS API로 데이터 조회 (120일치 일봉)
            df, error = self.data_fetcher.get_stock_data(ticker, days=120, end_date=target_date)
            
            if error:
                return None
                
            # 지표 계산
            df = calculate_indicators(df)
            
            # 이격도 계산 (20일선 기준)
            current_close = df.iloc[-1]['종가']
            ma20 = df.iloc[-1].get('MA20', 0)
            disparity = (current_close / ma20 * 100) if ma20 > 0 else 0
            
            # 전략 분석 (시가총액 전달)
            cap = row.get('cap', 0)
            analysis_result = self.strategy.analyze(df, cap=cap)
            
            # 외국인 순매수 정보 업데이트 (KIS 데이터 사용)
            current_foreign_buy = df.iloc[-1].get('외국인_순매수금액', 0)
            current_inst_buy = df.iloc[-1].get('기관_순매수금액', 0)
            
            if analysis_result['score'] > 0:
                return {
                    'code': ticker,
                    'name': name,
                    '현재가': int(current_close),
                    '등락률': float(df.iloc[-1]['등락률']),
                    '외국인순매수': current_foreign_buy,
                    '기관순매수': current_inst_buy,
                    '시가총액': cap,
                    '이격도': disparity,
                    **analysis_result
                }
            return None

        max_workers = 5
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_stock, row) for _, row in tickers_df.iterrows()]
            
            total_futures = len(futures)
            for i, future in enumerate(tqdm(as_completed(futures), total=total_futures)):
                res = future.result()
                if res:
                    results.append(res)
                
                # UI 진행률 업데이트 콜백
                if progress_callback:
                    # 0.0 ~ 1.0 사이 값 전달
                    progress = (i + 1) / total_futures
                    progress_callback(progress, f"[{market_type}] {i + 1}/{total_futures} 분석 중...")
            
        # 결과 정리
        if results:
            result_df = pd.DataFrame(results)
            
            # P1(1순위) 필터링 및 재정렬 로직
            # 1. P1 후보군(priority=1) 추출
            p1_candidates = result_df[result_df['priority'] == 1].copy()
            
            # 2. 기여도 점수(contribution) 기준 내림차순 정렬 후 상위 5개 선정
            if not p1_candidates.empty:
                p1_top5 = p1_candidates.sort_values(by='contribution', ascending=False).head(5)
                # 선정된 5개만 남기고 나머지는 P1 자격 박탈 (또는 제외)
                # 여기서는 P1은 오직 Top 5만 인정
                p1_codes = p1_top5['code'].tolist()
                
                # 전체 결과에서 P1이면서 Top 5에 들지 못한 종목은 제외하거나 우선순위 조정
                # 여기서는 간단하게 P1은 Top 5만 남기고 나머지는 제거하는 방식으로 구현
                # (P2, P3는 그대로 유지)
                
                # P1이 아니거나(P2, P3), P1이면서 Top 5에 든 종목만 유지
                result_df = result_df[
                    (result_df['priority'] != 1) | 
                    (result_df['code'].isin(p1_codes))
                ]
            
            # 최종 정렬: 우선순위(1->2->3), 기여도(높은순), 점수(높은순)
            # P1은 기여도순, P2/P3는 점수순이므로 복합 정렬 필요하지만
            # 일단 priority -> contribution(desc) -> score(desc) 로 정렬하면 얼추 맞음
            result_df = result_df.sort_values(by=['priority', 'contribution', 'score'], ascending=[True, False, False])
            
            return result_df
        else:
            return pd.DataFrame()
