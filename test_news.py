import akshare as ak
print("--- News ---")
try:
    df_news = ak.stock_news_em(symbol="600076")
    print(df_news.head(3))
except Exception as e:
    print("News Error:", e)

print("\n--- Notices/Announcements (Trying stock_zh_a_gdhs via similar path or generic) ---")
# Searching for notices API...
# Actually let's try 'stock_notice_report' if exists, otherwise ...
try:
    # Just checking list
    print("Skipping notice specific test, relying on News first")
except:
    pass
