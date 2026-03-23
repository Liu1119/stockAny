#!/usr/bin/env python3
# 测试K线API是否能正确返回数据

import requests
import json

# 测试股票代码
stock_code = "600000"
market_prefix = "sh"
full_symbol = f"{market_prefix}{stock_code}"

# 测试API地址 - 尝试不同的格式
import datetime

# 测试所有可能的API格式
end_date = datetime.datetime.now().strftime('%Y%m%d')
start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')

urls = [
    ("格式1: ifzq域名 + 天数参数", f"http://ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,,30"),
    ("格式2: ifzq域名 + 具体日期", f"http://ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,{start_date},{end_date}"),
    ("格式3: web子域名 + 天数参数", f"http://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,,30"),
    ("格式4: web子域名 + 具体日期", f"http://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,{start_date},{end_date}")
]

# 测试所有格式
for name, url in urls:
    print(f"\n测试 {name}:")
    print(f"API地址: {url}")
    
    # 发送请求
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'utf-8'
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据结构: {list(data.keys())}")
            
            # 检查数据是否存在
            if full_symbol in data:
                print(f"找到股票数据: {full_symbol}")
                kline_data = data[full_symbol].get('day', [])
                print(f"K线数据条数: {len(kline_data)}")
                if kline_data:
                    print(f"第一条数据: {kline_data[0]}")
                    print(f"最后一条数据: {kline_data[-1]}")
            elif 'data' in data:
                print(f"找到data字段")
                print(f"data字段类型: {type(data['data'])}")
                if isinstance(data['data'], dict):
                    print(f"data字段键: {list(data['data'].keys())}")
                    if full_symbol in data['data']:
                        print(f"在data中找到股票数据: {full_symbol}")
                        kline_data = data['data'][full_symbol].get('day', [])
                        print(f"K线数据条数: {len(kline_data)}")
                    else:
                        print(f"data中未找到 {full_symbol}")
                elif isinstance(data['data'], list):
                    print(f"data字段长度: {len(data['data'])}")
                    if data['data']:
                        print(f"第一条数据类型: {type(data['data'][0])}")
                        if isinstance(data['data'][0], dict):
                            print(f"第一条数据键: {list(data['data'][0].keys())}")
                print(f"完整data内容: {json.dumps(data['data'], indent=2)}")
            else:
                print("未找到股票数据")
                print(f"完整响应: {json.dumps(data, indent=2)}")
        else:
            print(f"响应内容: {response.text}")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")

print("\n测试完成")
