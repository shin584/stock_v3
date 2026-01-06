import pandas as pd
from typing import Dict, Any, Tuple

class StockStrategy:
    """
    P1, P2, P3 전략 정의 클래스
    """

    def check_p1_leader(self, df: pd.DataFrame, cap: float = 0) -> Tuple[bool, str, float]:
        """
        [P1] 주도주 (Trend Leading) - 지수 기여도 방식
        - 시장을 주도하는 강력한 상승 추세 종목
        - 로직: 시가총액 * 등락률 = 지수 기여도 점수
        - 반환: (True, "지수기여도산출", 기여도점수)
        """
        if df.empty:
            return False, "", 0.0
            
        current = df.iloc[-1]
        rate = current.get('등락률', 0)
        
        # 기여도 점수 계산 (시가총액 * 등락률)
        # cap 단위: 원
        contribution_score = cap * rate
        
        # P1은 항상 True로 반환하되, 점수로 순위를 매김
        # 단, 하락한 종목(기여도가 음수)은 제외할 수도 있으나, 
        # "하락 주도주"도 정보가 될 수 있으므로 일단 계산함.
        # 여기서는 "상승 기여"를 찾으므로 양수일 때만 의미를 부여할 수 있음.
        
        if contribution_score > 0:
            return True, f"지수기여:{contribution_score:.0f}", contribution_score
            
        return False, "", 0.0

    def check_p2_momentum(self, df: pd.DataFrame) -> Tuple[bool, str, int]:
        """
        [P2] 수급 주도주 (Supply & Demand)
        - 외국인/기관 양매수 종목 중 외국인 연속 매수일수 체크
        - 반환: (True, "수급체크", 연속매수일수)
        """
        if df.empty:
            return False, "", 0
            
        # 외국인 연속 매수 일수 계산
        consecutive_days = 0
        # 최근 데이터부터 역순으로 확인
        # '외국인_순매수금액' 또는 '외국인_순매수' 사용 (여기서는 금액 기준 권장)
        col = '외국인_순매수금액'
        if col not in df.columns:
            return False, "데이터없음", 0
            
        # 역순 순회
        for i in range(len(df) - 1, -1, -1):
            val = df.iloc[i][col]
            if val > 0:
                consecutive_days += 1
            else:
                break
                
        # P2 후보군 조건: 일단 양매수 여부는 Pipeline에서 Top 50 교집합으로 거르므로
        # 여기서는 연속 매수 일수만 계산해서 반환하고, 
        # 단, 연속 일수가 0일 경우(오늘 순매도)에는 후보 자격 없음.
        
        if consecutive_days > 0:
            return True, f"외인연속:{consecutive_days}일", consecutive_days
            
        return False, "외인순매도", 0

    def check_p3_rebound(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        [P3] 바닥 반등주 (Rebound)
        1. 수급: 외국인 3일 연속 순매수
        2. 상태: 이격도(20일선 기준) 98% 이하
        3. 트리거: 오늘 양봉
        """
        if df.empty or len(df) < 20:
            return False, ""
            
        current = df.iloc[-1]
        close = current['종가']
        open_price = current['시가']
             
        # 3. 트리거: 오늘 양봉 (종가 > 시가)
        if close <= open_price:
            return False, ""
            
        # 2. 상태: 이격도 98% 이하 (20일선 대비)
        ma20 = current.get('MA20', 0)
        disparity = (close / ma20 * 100) if ma20 > 0 else 0
        if disparity > 98:
            return False, ""
            
        # 2. 수급: 외국인 2일 연속 순매수
        consecutive_days = 0
        if '외국인_순매수금액' in df.columns:
            for i in range(len(df) - 1, -1, -1):
                val = df.iloc[i]['외국인_순매수금액']
                if val > 0:
                    consecutive_days += 1
                else:
                    break
        
        # (루프 밖에서 체크)
        if consecutive_days >= 2:
            return True, f"바닥반등(이격{disparity:.0f}%)"
            
        return False, ""

    def analyze(self, df: pd.DataFrame, cap: float = 0) -> Dict[str, Any]:
        """
        종목 하나에 대해 모든 전략을 체크하고 결과를 반환
        """
        score = 0
        reasons = []
        priority = 99
        contribution = 0.0
        
        # 데이터가 너무 적으면 분석 불가
        if df is None or len(df) < 60:
            return {"score": 0, "priority": None, "reasons": "데이터 부족", "contribution": 0}

        # P1 체크 (지수 기여도)
        is_p1, reason_p1, contrib_score = self.check_p1_leader(df, cap)
        if is_p1:
            # P1은 별도 랭킹 시스템이므로 여기서는 우선순위만 표시하고
            # 실제 선정은 Pipeline에서 점수 순으로 자름
            score = 100
            priority = 1
            reasons.append(f"[P1] {reason_p1}")
            contribution = contrib_score
            
        # P2 체크 (수급 연속성)
        is_p2, reason_p2, consec_days = self.check_p2_momentum(df)
        if is_p2:
            # P2도 별도 랭킹(교집합) 시스템
            # P1이 아닐 때만 P2 우선순위 부여 (P1 > P2)
            if priority > 1:
                score = 80 # P1(100)보다 낮게
                priority = 2
            reasons.append(f"[P2] {reason_p2}")
            
        # [추가] 개인 연속 순매도 일수 계산
        consec_personal_sell = 0
        if '개인_순매수금액' in df.columns:
            for i in range(len(df) - 1, -1, -1):
                val = df.iloc[i]['개인_순매수금액']
                if val < 0: # 순매도 (음수)
                    consec_personal_sell += 1
                else:
                    break
            
        # P3 체크
        is_p3, reason_p3 = self.check_p3_rebound(df)
        if is_p3:
            if score < 40:
                score = 40
                priority = 3
            reasons.append(f"[P3] {reason_p3}")
            
        return {
            "score": score,
            "priority": priority if score > 0 else None,
            "reasons": ", ".join(reasons) if reasons else "-",
            "contribution": contribution,
            "consecutive_days": consec_days if is_p2 else 0,
            "consecutive_personal_sell_days": consec_personal_sell,
            "is_p1": is_p1,
            "is_p2": is_p2,
            "is_p3": is_p3
        }
