import json
import os
from typing import Dict, Any

def load_secrets(file_path: str = None) -> Dict[str, Any]:
    """
    secrets.json 파일을 로드합니다.
    기본적으로 상위 디렉토리의 secrets.json을 찾습니다.
    """
    if file_path is None:
        # stock_v2/config.py -> stock_v2/ -> p1/secrets.json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, 'secrets.json')
        
        if not os.path.exists(file_path):
            # fallback: try looking in the same directory or specific locations
            # p1/market_logic_kis/secrets.json (legacy support)
            legacy_path = os.path.join(base_dir, 'market_logic_kis', 'secrets.json')
            if os.path.exists(legacy_path):
                file_path = legacy_path
            else:
                # secrets.json이 없으면 빈 딕셔너리 반환 (Streamlit Secrets 사용 시도)
                return {}

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_kis_config() -> Dict[str, Any]:
    # 1. Try Streamlit Secrets (Cloud Deployment)
    try:
        import streamlit as st
        # st.secrets 접근 시 toml 파일이 없으면 FileNotFoundError 등이 발생할 수 있음
        # 혹은 실행 환경이 streamlit이 아닐 경우를 대비
        if hasattr(st, "secrets") and "APP_KEY" in st.secrets:
            return {
                "app_key": st.secrets["APP_KEY"],
                "app_secret": st.secrets["APP_SECRET"],
                "acc_no": st.secrets["ACCOUNT_NO"],
                "mock": st.secrets.get("MOCK", True)
            }
    except Exception:
        pass

    # 2. Fallback to local secrets.json
    secrets = load_secrets()
    if not secrets:
        raise FileNotFoundError("API 설정을 찾을 수 없습니다. (secrets.json 또는 Streamlit Secrets)")
        
    return {
        "app_key": secrets.get("APP_KEY"),
        "app_secret": secrets.get("APP_SECRET"),
        "acc_no": secrets.get("ACCOUNT_NO"),
        "mock": secrets.get("MOCK", True)
    }
