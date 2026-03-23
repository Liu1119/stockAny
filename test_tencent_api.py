#!/usr/bin/env python3
import requests

stock_code = "600000"
market_prefix = "sh"
full_symbol = f"{market_prefix}{stock_code}"

url = f"http://qt.gtimg.cn/q={full_symbol}"

print(f"测试API: {url}")

response = requests.get(url, timeout=10)
response.encoding = 'gbk'

print(f"响应状态码: {response.status_code}")
print(f"\n完整响应内容:")
print(response.text)

print(f"\n\n解析数据:")
lines = response.text.strip().split(';')

for line in lines:
    if not line:
        continue
    
    parts = line.split('=')
    if len(parts) != 2:
        continue
    
    symbol_part = parts[0].strip()
    data_part = parts[1].strip().strip('"')
    
    print(f"\n符号部分: {symbol_part}")
    print(f"数据部分: {data_part[:200]}...")
    
    fields = data_part.split('~')
    print(f"\n字段数量: {len(fields)}")
    print(f"\n所有字段:")
    for i, field in enumerate(fields):
        print(f"  字段{i}: {field}")
