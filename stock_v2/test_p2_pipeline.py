import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_v2.core.pipeline import MarketScanner

def test_p2_logic():
    print("Testing P2 Logic (Supply & Demand Intersection)...")
    
    scanner = MarketScanner()
    # Use a recent trading day for testing
    target_date = datetime(2026, 1, 2) 
    
    # 1. Scan KOSPI
    print(f"\n[1] Scanning KOSPI (Top 60 Market Cap)...")
    try:
        df_kospi = scanner.run_scan(market_type="KOSPI", top_n=60, target_date=target_date)
        p2_kospi = scanner.filter_p2_stocks(df_kospi)
        print(f"-> KOSPI P2 Candidates: {len(p2_kospi)}")
    except Exception as e:
        print(f"Error scanning KOSPI: {e}")
        p2_kospi = pd.DataFrame()

    # 2. Scan KOSDAQ
    print(f"\n[2] Scanning KOSDAQ (Top 60 Market Cap)...")
    try:
        df_kosdaq = scanner.run_scan(market_type="KOSDAQ", top_n=60, target_date=target_date)
        p2_kosdaq = scanner.filter_p2_stocks(df_kosdaq)
        print(f"-> KOSDAQ P2 Candidates: {len(p2_kosdaq)}")
    except Exception as e:
        print(f"Error scanning KOSDAQ: {e}")
        p2_kosdaq = pd.DataFrame()

    # 3. Combine Results
    print(f"\n[3] Combining Results...")
    if p2_kospi.empty and p2_kosdaq.empty:
        print("No P2 candidates found in either market.")
        return

    final_df = pd.concat([p2_kospi, p2_kosdaq], ignore_index=True)
    
    # 4. Sort by Consecutive Buy Days (Foreigner)
    if 'consecutive_days' in final_df.columns:
        final_df = final_df.sort_values(by='consecutive_days', ascending=False)
    
    # Display
    print(f"\n[Final P2 Result] Total: {len(final_df)} stocks")
    
    cols = ['code', 'name', 'consecutive_days', '외국인순매수', '기관순매수', '등락률']
    display_cols = [c for c in cols if c in final_df.columns]
    
    display_df = final_df[display_cols].copy()
    
    # Format for readability
    if '외국인순매수' in display_df.columns:
        display_df['외국인순매수'] = display_df['외국인순매수'].apply(lambda x: f"{x/100000000:.1f}억")
    if '기관순매수' in display_df.columns:
        display_df['기관순매수'] = display_df['기관순매수'].apply(lambda x: f"{x/100000000:.1f}억")
        
    print(display_df.to_string(index=False))

if __name__ == "__main__":
    test_p2_logic()
