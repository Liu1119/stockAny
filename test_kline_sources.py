#!/usr/bin/env python3
import requests
import json

stock_code = "600000"

# 测试新浪财经K线API
print("测试新浪财经K线API:")
url_sina = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={stock_code}&scale=240&ma=no&datalen=60"
print(f"URL: {url_sina}")

try:
    response = requests.get(url_sina, timeout=10)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"响应内容（前500字符）: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "="*60 + "\n")

# 测试东方财富K线API
print("测试东方财富K线API:")
url_east = f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.{stock_code}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&end=20500101&lmt=60"
print(f"URL: {url_east}")

try:
    response = requests.get(url_east, timeout=10)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"响应数据结构: {list(data.keys())}")
        if 'data' in data and data['data']:
            klines = data['data'].get('klines', [])
            print(f"K线数据条数: {len(klines)}")
            if klines:
                print(f"第一条数据: {klines[0]}")
                print(f"最后一条数据: {klines[-1]}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "="*60 + "\n")

# 测试网易财经K线API
print("测试网易财经K线API:")
url_163 = f"http://api.money.126.net/data/feed/{stock_code}.money"
print(f"URL: {url_163}")

try:
    response = requests.get(url_163, timeout=10)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"响应内容（前500字符）: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")

print("\n测试完成")
