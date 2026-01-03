import requests
import json
import datetime
import time
import logging
import os
from typing import Optional, Dict, Any, List, Union

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KisClient:
    """
    한국투자증권(KIS) API 클라이언트
    """
    def __init__(self, app_key: str, app_secret: str, acc_no: str, mock: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        
        # 계좌번호 처리 (12345678-01 형태 가정)
        if '-' in acc_no:
            self.acc_no_prefix = acc_no.split('-')[0]
            self.acc_no_suffix = acc_no.split('-')[1]
        else:
            self.acc_no_prefix = acc_no
            self.acc_no_suffix = "01"
            
        self.mock = mock
        
        # 모의투자 vs 실전투자 URL 설정
        if mock:
            self.base_url = "https://openapivts.koreainvestment.com:29443"
            logger.info("[KIS] 모의투자 모드로 초기화되었습니다.")
        else:
            self.base_url = "https://openapi.koreainvestment.com:9443"
            logger.info("[KIS] 실전투자 모드로 초기화되었습니다.")
            
        self.access_token = None
        self.token_expiry = None
        self.token_file = "kis_token.json" # Current directory

        # Try to load token
        self._load_token()

    def _load_token(self):
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    expiry = datetime.datetime.strptime(data['expiry'], "%Y-%m-%d %H:%M:%S")
                    if expiry > datetime.datetime.now():
                        self.access_token = data['access_token']
                        self.token_expiry = expiry
                        logger.info(f"[KIS] Loaded valid token (Expires: {expiry})")
            except Exception as e:
                logger.warning(f"[KIS] Failed to load token: {e}")

    def _save_token(self, token, expiry):
        try:
            with open(self.token_file, 'w') as f:
                json.dump({
                    'access_token': token,
                    'expiry': expiry.strftime("%Y-%m-%d %H:%M:%S")
                }, f)
        except Exception as e:
            logger.warning(f"[KIS] Failed to save token: {e}")

    def _get_headers(self, tr_id: Optional[str] = None) -> Dict[str, str]:
        """API 요청 헤더 생성"""
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        if tr_id:
            headers["tr_id"] = tr_id
        return headers

    def _send_request(self, method: str, url: str, headers: Optional[Dict] = None, 
                     params: Optional[Dict] = None, data: Optional[Dict] = None, 
                     max_retries: int = 10) -> Optional[Dict[str, Any]]:
        """API 요청 전송 (재시도 로직 포함)"""
        for i in range(max_retries):
            try:
                if method == 'GET':
                    res = requests.get(url, headers=headers, params=params)
                else:
                    res = requests.post(url, headers=headers, data=json.dumps(data) if data else None)
                
                if res.status_code == 200:
                    data_json = res.json()
                    # 초당 전송건수 초과 체크 (msg1에 포함됨)
                    msg = data_json.get('msg1', '')
                    if '초당 전송건수' in msg or '초과' in msg:
                        # 잠시 대기 후 재시도 (지수 백오프)
                        wait_time = 0.5 * (2 ** i) 
                        logger.warning(f"[KIS] API 제한 도달. {wait_time}초 대기 후 재시도 ({i+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    return data_json
                else:
                    # 500번대 에러 등은 잠시 대기 후 재시도
                    if res.status_code >= 500:
                        logger.warning(f"[KIS] Server Error {res.status_code}. Retrying...")
                        time.sleep(1.0)
                        continue
                    logger.error(f"[KIS] Request Failed: {res.status_code} {res.text}")
                    return None
            except Exception as e:
                logger.error(f"[KIS] Request Error: {e}")
                time.sleep(1.0)
        return None

    def auth(self) -> bool:
        """접근 토큰 발급"""
        # Check if current token is valid
        if self.access_token and self.token_expiry and self.token_expiry > datetime.datetime.now():
            return True

        path = "/oauth2/tokenP"
        url = f"{self.base_url}{path}"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            res = requests.post(url, data=json.dumps(body), headers={"content-type": "application/json"})
            if res.status_code == 200:
                data = res.json()
                self.access_token = data['access_token']
                self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(data['expires_in']))
                logger.info(f"[KIS] Access Token 발급 완료 (만료: {self.token_expiry})")
                self._save_token(self.access_token, self.token_expiry)
                return True
            else:
                logger.error(f"[KIS] Auth Failed: {res.text}")
                return False
        except Exception as e:
            logger.error(f"[KIS] Auth Error: {e}")
            return False

    def get_current_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """주식 현재가 시세 및 종목 정보 조회"""
        if not self.access_token:
            if not self.auth():
                return None
            
        path = "/uapi/domestic-stock/v1/quotations/inquire-price"
        url = f"{self.base_url}{path}"
        
        # TR_ID: 주식현재가 시세 (FHKST01010100)
        headers = self._get_headers(tr_id="FHKST01010100")
        params = {
            "fid_cond_mrkt_div_code": "J", # J: 주식, ETF, ETN
            "fid_input_iscd": ticker
        }
        
        data = self._send_request('GET', url, headers=headers, params=params)
        if data and data.get('rt_cd') == '0':
            return data['output']
        elif data:
            logger.error(f"[KIS] API Error (Price): {data.get('msg1')}")
            return None
        else:
            return None

    def get_balance(self) -> Optional[tuple]:
        """주식 잔고 조회"""
        if not self.access_token:
            if not self.auth():
                return None

        path = "/uapi/domestic-stock/v1/trading/inquire-balance"
        url = f"{self.base_url}{path}"
        
        # TR_ID: 주식잔고조회 (모의투자: VTTC8434R, 실전투자: TTTC8434R)
        tr_id = "VTTC8434R" if self.mock else "TTTC8434R"
        
        headers = self._get_headers(tr_id=tr_id)
        
        params = {
            "CANO": self.acc_no_prefix,
            "ACNT_PRDT_CD": self.acc_no_suffix,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "N",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        data = self._send_request('GET', url, headers=headers, params=params)
        if data and data.get('rt_cd') == '0':
            # output2는 리스트로 반환되므로 첫 번째 요소를 추출
            account_info = data.get('output2')
            if isinstance(account_info, list) and len(account_info) > 0:
                account_info = account_info[0]
            return data.get('output1'), account_info
        elif data:
            logger.error(f"[KIS] API Error (Balance): {data.get('msg1')}")
            return None
        else:
            return None

    def get_chart_price(self, ticker: str, start_date: str, end_date: str, period: str = "D") -> Optional[List[Dict[str, Any]]]:
        """
        기간별 시세 조회 (차트 데이터)
        period: D(일), W(주), M(월), Y(년)
        """
        if not self.access_token:
            if not self.auth():
                return None

        path = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        url = f"{self.base_url}{path}"
        
        # TR_ID: 국내주식기간별시세 (FHKST03010100)
        headers = self._get_headers(tr_id="FHKST03010100")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start_date, # 시작일자 (YYYYMMDD)
            "FID_INPUT_DATE_2": end_date,   # 종료일자 (YYYYMMDD)
            "FID_PERIOD_DIV_CODE": period,  # 기간분류코드
            "FID_ORG_ADJ_PRC": "0"          # 수정주가반영여부 (0:반영)
        }
        
        data = self._send_request('GET', url, headers=headers, params=params)
        if data and data.get('rt_cd') == '0':
            return data.get('output2') # 일별 데이터 리스트
        elif data:
            logger.error(f"[KIS] API Error (Chart): {data.get('msg1')}")
            return None
        else:
            return None

    def get_investor_trend(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        종목별 투자자 매매동향 (당일 실시간 추정치 아님, 일별 집계)
        """
        if not self.access_token:
            if not self.auth():
                return None

        path = "/uapi/domestic-stock/v1/quotations/inquire-investor"
        url = f"{self.base_url}{path}"
        
        # TR_ID: 국내주식 투자자별 매매동향 (FHKST01010900)
        headers = self._get_headers(tr_id="FHKST01010900")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker
        }
        
        data = self._send_request('GET', url, headers=headers, params=params)
        if data and data.get('rt_cd') == '0':
            return data.get('output') # 일별 투자자 동향 리스트
        elif data:
            logger.error(f"[KIS] API Error (Investor): {data.get('msg1')}")
            return None
        else:
            return None
