import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from stock_v2.api.kis_client import KisClient
from stock_v2.config import get_kis_config

class DataFetcher:
    def __init__(self):
        config = get_kis_config()
        self.client = KisClient(**config)

    def get_stock_data(self, ticker: str, days: int = 100, end_date: Optional[datetime] = None, period: str = "D") -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        특정 종목의 차트 데이터와 투자자 동향을 가져와서 DataFrame으로 반환
        """
        # 날짜 계산
        if end_date:
            end_dt = end_date
        else:
            end_dt = datetime.now()
            
        start_dt = end_dt - timedelta(days=days)
        
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")

        # 1. 차트 데이터 조회
        chart_data = self.client.get_chart_price(ticker, start_str, end_str, period=period)
        if not chart_data:
            return None, "차트 데이터 조회 실패"

        # 2. 투자자 동향 조회 (일봉일 때만)
        investor_data = None
        if period == "D":
            investor_data = self.client.get_investor_trend(ticker)
        
        # 데이터프레임 변환 및 병합
        df = pd.DataFrame(chart_data)
        
        # 컬럼명 매핑 (한투 API -> 내부 표준)
        df = df.rename(columns={
            'stck_bsop_date': '날짜',
            'stck_clpr': '종가',
            'stck_oprc': '시가',
            'stck_hgpr': '고가',
            'stck_lwpr': '저가',
            'acml_vol': '거래량',
            'acml_tr_pbmn': '거래대금'
        })
        
        # 숫자형 변환
        cols = ['종가', '시가', '고가', '저가', '거래량', '거래대금']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col])
            
        # 날짜 인덱스 설정
        df['날짜'] = pd.to_datetime(df['날짜'])
        df = df.set_index('날짜').sort_index()

        # 등락률 계산 (API에서 제공하지 않을 경우)
        if '등락률' not in df.columns:
            df['등락률'] = df['종가'].pct_change() * 100
            df['등락률'] = df['등락률'].fillna(0)

        # 투자자 데이터 병합 (날짜 기준, 일봉일 때만)
        if investor_data and period == "D":
            df_inv = pd.DataFrame(investor_data)
            
            # 컬럼 매핑
            df_inv = df_inv.rename(columns={
                'stck_bsop_date': '날짜',
                'prsn_ntby_qty': '개인_순매수', 
                'frgn_ntby_qty': '외국인_순매수',
                'orgn_ntby_qty': '기관_순매수',
                'prsn_ntby_tr_pbmn': '개인_순매수금액',
                'frgn_ntby_tr_pbmn': '외국인_순매수금액',
                'orgn_ntby_tr_pbmn': '기관_순매수금액'
            })
            df_inv['날짜'] = pd.to_datetime(df_inv['날짜'])
            df_inv = df_inv.set_index('날짜')
            
            # 필요한 컬럼만 숫자형 변환
            inv_cols = ['개인_순매수', '외국인_순매수', '기관_순매수', '개인_순매수금액', '외국인_순매수금액', '기관_순매수금액']
            for col in inv_cols:
                if col in df_inv.columns:
                    df_inv[col] = pd.to_numeric(df_inv[col])
            
            # 금액 컬럼 단위 보정 (백만원 -> 원)
            amt_cols = ['개인_순매수금액', '외국인_순매수금액', '기관_순매수금액']
            for col in amt_cols:
                if col in df_inv.columns:
                    df_inv[col] = df_inv[col] * 1000000
                
            # 병합
            df = df.join(df_inv[inv_cols], how='left').fillna(0)

        return df, None

    def get_current_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self.client.get_current_price(ticker)
