#!/usr/bin/env python3
import requests
import json

stock_code = "600000"
market_prefix = "sh"
full_symbol = f"{market_prefix}{stock_code}"

urls = [
    ("格式1: web子域名 + 天数参数", f"http://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,,60"),
    ("格式2: ifzq域名 + 天数参数", f"http://ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,,60"),
    ("格式3: data.gtimg.cn", f"https://data.gtimg.cn/flashdata/hushen/daily/23/{full_symbol}.js")
]

for name, url in urls:
    print(f"\n测试 {name}:")
    print(f"API地址: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        if 'js' in url:
            response.encoding = 'utf-8'
        else:
            response.encoding = 'utf-8'
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            if 'js' in url:
                print(f"响应内容（前500字符）: {response.text[:500]}")
            else:
                try:
                    data = response.json()
                    print(f"响应数据结构: {list(data.keys())}")
                    print(f"完整响应（前1000字符）: {json.dumps(data, indent=2, ensure_ascii=False)[:1000]}")
                except:
                    print(f"响应内容（前500字符）: {response.text[:500]}")
        else:
            print(f"响应内容: {response.text}")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")

print("\n测试完成")
