import pandas as pd

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    이동평균선 및 보조지표(MACD) 계산
    """
    # 이동평균선 계산
    df['MA20'] = df['종가'].rolling(window=20).mean()
    df['MA60'] = df['종가'].rolling(window=60).mean()

    # MACD 계산 (12, 26, 9)
    ema12 = df['종가'].ewm(span=12, adjust=False).mean()
    ema26 = df['종가'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Oscillator'] = df['MACD'] - df['Signal']
    
    return df

def check_ma_status(df: pd.DataFrame) -> tuple[bool, str]:
    if len(df) < 60:
        return False, "데이터 부족 (60일 미만)"
    
    current = df.iloc[-1]
    
    # 조건: 현재가가 20일선, 60일선 위에 있는지
    cond_ma20 = current['종가'] > current['MA20']
    cond_ma60 = current['종가'] > current['MA60']
    
    if cond_ma20 and cond_ma60:
        return True, "정배열 (20일, 60일 상회)"
    elif cond_ma20:
        return True, "20일선 상회"
    else:
        return False, "역배열 또는 하회"
