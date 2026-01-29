#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试300620股票通过各个数据源返回的价格数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
import requests


def test_tencent_api(stock_code):
    """
    测试腾讯财经API获取股票价格
    """
    print(f"\n=== 测试腾讯财经API获取 {stock_code} 价格 ===")
    
    # 构建腾讯财经API URL
    # 300620是创业板股票，使用sz前缀
    url = f"http://qt.gtimg.cn/q=sz{stock_code}"
    print(f"API URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'gbk'  # 腾讯财经返回GBK编码
        
        if response.status_code == 200:
            print(f"响应状态: {response.status_code}")
            print(f"响应内容: {response.text}")
            
            # 解析响应数据
            lines = response.text.strip().split(';')
            for line in lines:
                if not line:
                    continue
                
                try:
                    parts = line.split('=')
                    if len(parts) != 2:
                        continue
                    
                    symbol_part = parts[0].strip()
                    data_part = parts[1].strip().strip('"')
                    
                    if symbol_part.startswith('v_'):
                        fields = data_part.split('~')
                        if len(fields) >= 34:
                            name = fields[1]      # 股票名称
                            price = float(fields[3])  # 最新价
                            change = float(fields[32])  # 涨跌幅
                            print(f"股票名称: {name}")
                            print(f"最新价格: {price}")
                            print(f"涨跌幅: {change}%")
                except Exception as e:
                    print(f"解析失败: {e}")
        else:
            print(f"请求失败: {response.status_code}")
    except Exception as e:
        print(f"测试失败: {e}")


def test_baostock_api(stock_code):
    """
    测试baostock获取股票价格
    """
    print(f"\n=== 测试baostock获取 {stock_code} 价格 ===")
    
    fetcher = DataFetcher(use_mock_data=False)
    
    if fetcher.bs_init:
        print("baostock初始化成功")
        # 测试获取股票数据
        data = fetcher.get_stock_data('cyb')  # 创业板
        print(f"获取到创业板股票数量: {len(data)}")
        
        # 查找300620
        if not data.empty:
            stock_data = data[data['代码'] == stock_code]
            if not stock_data.empty:
                print(f"找到股票: {stock_data.iloc[0]['名称']}")
                print(f"最新价格: {stock_data.iloc[0]['最新价']}")
            else:
                print(f"未找到股票 {stock_code}")
    else:
        print("baostock初始化失败")


def test_data_fetcher(stock_code):
    """
    测试DataFetcher的综合功能
    """
    print(f"\n=== 测试DataFetcher获取 {stock_code} 价格 ===")
    
    fetcher = DataFetcher(use_mock_data=False)
    
    # 测试获取所有市场数据
    all_data = fetcher.get_all_markets_data()
    
    for market, data in all_data.items():
        print(f"\n{market}市场股票数量: {len(data)}")
        if not data.empty:
            # 查找300620
            stock_data = data[data['代码'] == stock_code]
            if not stock_data.empty:
                print(f"找到股票: {stock_data.iloc[0]['名称']}")
                print(f"最新价格: {stock_data.iloc[0]['最新价']}")
                print(f"涨跌幅: {stock_data.iloc[0]['涨跌幅']}")


if __name__ == "__main__":
    stock_code = "300620"
    print(f"测试股票代码: {stock_code}")
    print("=" * 60)
    
    # 测试腾讯财经API
    test_tencent_api(stock_code)
    
    # 测试baostock
    test_baostock_api(stock_code)
    
    # 测试DataFetcher
    test_data_fetcher(stock_code)
    
    print("\n" + "=" * 60)
    print("测试完成")
