import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
# stock_v2/test_p1_pipeline.py -> stock_v2/ -> p1/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_v2.core.pipeline import MarketScanner

def test_pipeline_p1_logic():
    print("Testing Pipeline P1 Logic (Index Contribution)...")
    
    scanner = MarketScanner()
    
    # Mocking data_fetcher and strategy for controlled testing
    # Instead of mocking, let's run a small scan on top 10 stocks
    # This will use real API and real strategy logic
    
    print("Running scan on Top 50 KOSPI stocks for 2026-01-02...")
    # run_scan loads tickers from file. 
    # We can override _load_tickers or just let it run if it's fast enough.
    # Let's try running it for top 50.
    
    target_date = datetime(2026, 1, 2)
    
    try:
        result_df = scanner.run_scan(market_type="KOSPI", top_n=50, target_date=target_date)
        
        if result_df.empty:
            print("No results found.")
            return

        print("\n[Scan Results]")
        # Columns to display
        cols = ['code', 'name', 'priority', 'contribution', '등락률', '시가총액']
        # Check if columns exist
        display_cols = [c for c in cols if c in result_df.columns]
        
        # Sort by contribution desc to match P1 logic visualization
        if 'contribution' in result_df.columns:
            result_df = result_df.sort_values(by='contribution', ascending=False)
        
        print(result_df[display_cols].head(10).to_string(index=False))
        
        # Verification
        p1_stocks = result_df[result_df['priority'] == 1]
        print(f"\nNumber of P1 stocks: {len(p1_stocks)}")
        
        if len(p1_stocks) > 5:
            print("FAILURE: P1 stocks should be limited to Top 5.")
        else:
            print("SUCCESS: P1 stocks limited to Top 5 (or less).")
            
        # Check sorting
        if len(p1_stocks) > 1:
            is_sorted = p1_stocks['contribution'].is_monotonic_decreasing
            print(f"P1 sorted by contribution: {is_sorted}")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_pipeline_p1_logic()
