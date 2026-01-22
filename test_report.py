import akshare as ak
try:
    print("Fetching reports for 600076...")
    df = ak.stock_research_report_em(symbol="600076")
    print(df.head())
    print("\nColumns:", df.columns)
except Exception as e:
    print("Error:", e)
