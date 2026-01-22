import akshare as ak
df = ak.stock_news_em(symbol="600076")
print(df.columns)
print(df.iloc[0])
