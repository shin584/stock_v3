import sys
import os
import pandas as pd
from tqdm import tqdm
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Add project root to path
# stock_v2/run_p1_scan.py -> stock_v2/ -> p1/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_v2.core.data_fetcher import DataFetcher

def load_top_50_kospi():
    # Load tickers from stock_v2/tickers.json
    # __file__ = .../stock_v2/run_p1_scan.py
    # dirname(__file__) = .../stock_v2
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "tickers.json")
    
    try:
        df = pd.read_json(json_path)
        # Filter KOSPI
        df = df[df['market'] == 'KOSPI']
        # Sort by Cap desc
        df = df.sort_values(by='cap', ascending=False)
        # Top 50
        return df.head(50)
    except Exception as e:
        print(f"Error loading tickers: {e}")
        return pd.DataFrame()

def fetch_price_data(client, ticker, name, cap, target_date):
    try:
        # Fetch chart data (small range)
        # target_date format: YYYY-MM-DD
        # API needs YYYYMMDD
        target_str = target_date.replace("-", "")
        
        end_dt = datetime.strptime(target_str, "%Y%m%d")
        start_dt = end_dt - timedelta(days=10)
        
        start_str = start_dt.strftime("%Y%m%d")
        end_str = target_str
        
        data = client.get_chart_price(ticker, start_str, end_str, period="D")
        
        if not data:
            return None
            
        # Find target date
        for day_data in data:
            if day_data['stck_bsop_date'] == target_str:
                close = float(day_data['stck_clpr'])
                
                # Try to find previous day close
                prev_close = 0
                # data is usually sorted by date DESC (recent first)
                idx = data.index(day_data)
                if idx + 1 < len(data):
                    prev_day = data[idx+1]
                    prev_close = float(prev_day['stck_clpr'])
                    rate = ((close - prev_close) / prev_close) * 100
                else:
                    rate = 0
                
                contribution = cap * rate
                
                return {
                    'code': ticker,
                    'name': name,
                    'cap': cap,
                    'rate': rate,
                    'contribution': contribution,
                    'close': close
                }
                
    except Exception as e:
        pass
    return None

def main():
    target_date = "2026-01-02"
    print(f"Starting P1 (Index Contribution) Scan for date: {target_date} (Parallel)")
    print("Target: Top 50 KOSPI Stocks by Market Cap")
    
    fetcher = DataFetcher()
    # Ensure auth
    if not fetcher.client.access_token:
        if not fetcher.client.auth():
            print("Authentication failed.")
            return
        
    tickers_df = load_top_50_kospi()
    
    if tickers_df.empty:
        print("No tickers found.")
        return

    print(f"Scanning {len(tickers_df)} stocks...")
    
    results = []
    client = fetcher.client
    
    max_workers = 2
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, row in tickers_df.iterrows():
            ticker = str(row['code']).zfill(6)
            name = row['name']
            cap = row['cap']
            futures.append(executor.submit(fetch_price_data, client, ticker, name, cap, target_date))
            
        for future in tqdm(as_completed(futures), total=len(futures)):
            res = future.result()
            if res:
                results.append(res)
        
    if not results:
        print("No data found for the target date.")
        return

    df_res = pd.DataFrame(results)
    
    # Sort by Contribution descending
    df_res = df_res.sort_values(by='contribution', ascending=False)
    
    print(f"\n[P1 Result] Top 5 Index Contributors ({target_date})")
    print(f"{'Rank':<5} {'Code':<10} {'Name':<15} {'Rate(%)':<10} {'Cap(Trillion)':<15} {'Contribution Score':<20}")
    print("-" * 80)
    
    for i in range(min(5, len(df_res))):
        row = df_res.iloc[i]
        cap_trillion = row['cap'] / 1000000000000
        print(f"{i+1:<5} {row['code']:<10} {row['name']:<15} {row['rate']:<10.2f} {cap_trillion:<15.2f} {row['contribution']:<20.0f}")

if __name__ == "__main__":
    main()
