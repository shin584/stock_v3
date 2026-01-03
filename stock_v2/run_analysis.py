import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_v2.core.pipeline import MarketScanner

def main():
    print("=== Stock Analysis V2 (P1 & P2) ===")
    
    scanner = MarketScanner()
    target_date = datetime.now() # Or specific date
    # For testing, we might want to use the date from the context or let it default to today/yesterday
    # But since today is Saturday (2026-01-03), the last market day was 2026-01-02.
    # The scanner usually handles "latest available" or we can specify.
    # Let's use a fixed date for now or logic to find last business day if needed.
    # But run_scan takes target_date. If None, it might default to something or fail.
    # Let's set it to 2026-01-02 as per user context.
    target_date = datetime(2026, 1, 2)
    
    print(f"Target Date: {target_date.strftime('%Y-%m-%d')}")
    
    # 1. Scan KOSPI
    print("\n[1] Scanning KOSPI...")
    df_kospi = scanner.run_scan(market_type="KOSPI", top_n=100, target_date=target_date)
    
    # 2. Scan KOSDAQ
    print("\n[2] Scanning KOSDAQ...")
    df_kosdaq = scanner.run_scan(market_type="KOSDAQ", top_n=100, target_date=target_date)
    
    # 3. Process P1 (Index Leaders) - Global Top 5
    print("\n[Processing P1: Index Leaders]")
    # Combine for P1? Or P1 is usually KOSPI heavy?
    # P1 logic in pipeline.py sorts by contribution.
    # We can combine and sort globally.
    
    all_results = pd.concat([df_kospi, df_kosdaq], ignore_index=True)
    
    if not all_results.empty:
        # P1: Contribution Score > 0, Top 5
        p1_candidates = all_results[all_results['contribution'] > 0].copy()
        p1_final = p1_candidates.sort_values(by='contribution', ascending=False).head(5)
        
        print(f"-> P1 Top 5 Selected")
        print(p1_final[['code', 'name', '현재가', '등락률', 'contribution']].to_string(index=False))
    else:
        print("No data found.")
        p1_final = pd.DataFrame()

    # 4. Process P2 (Supply Leaders)
    print("\n[Processing P2: Supply Leaders]")
    # Filter P2 for KOSPI
    p2_kospi = scanner.filter_p2_stocks(df_kospi)
    # Filter P2 for KOSDAQ
    p2_kosdaq = scanner.filter_p2_stocks(df_kosdaq)
    
    # Combine
    p2_final = pd.concat([p2_kospi, p2_kosdaq], ignore_index=True)
    
    # Sort by consecutive days
    if not p2_final.empty and 'consecutive_days' in p2_final.columns:
        p2_final = p2_final.sort_values(by='consecutive_days', ascending=False)
        
    print(f"-> P2 Total: {len(p2_final)}")
    if not p2_final.empty:
        cols = ['code', 'name', 'stage', '이격도', 'consecutive_days', '외국인순매수', '기관순매수', '등락률']
        display_cols = [c for c in cols if c in p2_final.columns]
        
        # Format for display
        disp = p2_final[display_cols].copy()
        if '외국인순매수' in disp.columns:
            disp['외국인순매수'] = disp['외국인순매수'].apply(lambda x: f"{x/100000000:.1f}억")
        if '기관순매수' in disp.columns:
            disp['기관순매수'] = disp['기관순매수'].apply(lambda x: f"{x/100000000:.1f}억")
        if '이격도' in disp.columns:
            disp['이격도'] = disp['이격도'].apply(lambda x: f"{x:.1f}%")
            
        print(disp.to_string(index=False))

if __name__ == "__main__":
    main()
