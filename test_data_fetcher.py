#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试data_fetcher.py文件的功能
"""

import sys
import os
from data_fetcher import DataFetcher

def test_data_fetcher():
    """
    测试DataFetcher类的功能
    """
    print("=" * 80)
    print("测试DataFetcher类的功能")
    print("=" * 80)
    
    # 测试1: 使用默认数据源（akshare）
    print("\n测试1: 使用默认数据源（akshare）")
    print("-" * 60)
    
    try:
        fetcher = DataFetcher(use_mock_data=False)
        print("✓ DataFetcher初始化成功")
        
        # 测试获取单个市场数据
        markets = ['sh', 'sz', 'cyb', 'kcb']
        for market in markets:
            data = fetcher.get_stock_data(market)
            if not data.empty:
                print(f"✓ 成功获取{market}市场数据，共{len(data)}条")
                print(f"  数据示例: {data.head(1).to_dict('records')[0]}")
            else:
                print(f"⚠ {market}市场数据为空，可能使用了模拟数据")
        
        # 测试获取K线数据
        test_symbol = '600000'  # 浦发银行
        kline_data = fetcher.get_stock_kline(test_symbol, period='1d')
        if not kline_data.empty:
            print(f"\n✓ 成功获取{test_symbol}的K线数据，共{len(kline_data)}条")
            print(f"  最近5条数据:")
            print(kline_data.tail())
        else:
            print(f"⚠ {test_symbol}的K线数据为空，可能使用了模拟数据")
            
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
    
    # 测试2: 测试多数据源自动切换
    print("\n测试2: 测试多数据源自动切换")
    print("-" * 60)
    
    try:
        # 尝试使用tushare作为默认数据源（即使没有token也会自动切换）
        fetcher_ts = DataFetcher(use_mock_data=False, default_source='tushare')
        print("✓ DataFetcher(tushare)初始化成功")
        
        # 测试获取单个市场数据
        data = fetcher_ts.get_stock_data('sh')
        if not data.empty:
            print(f"✓ 成功获取sh市场数据，共{len(data)}条")
        else:
            print(f"⚠ sh市场数据为空")
            
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
    
    # 测试3: 测试模拟数据
    print("\n测试3: 测试模拟数据")
    print("-" * 60)
    
    try:
        fetcher_mock = DataFetcher(use_mock_data=True)
        print("✓ DataFetcher(模拟数据)初始化成功")
        
        # 测试获取单个市场数据
        for market in markets:
            data = fetcher_mock.get_stock_data(market)
            if not data.empty:
                print(f"✓ 成功获取{market}市场模拟数据，共{len(data)}条")
                print(f"  数据示例: {data.head(1).to_dict('records')[0]}")
            else:
                print(f"⚠ {market}市场模拟数据为空")
        
        # 测试获取K线数据
        kline_data = fetcher_mock.get_stock_kline(test_symbol, period='1d')
        if not kline_data.empty:
            print(f"\n✓ 成功获取{test_symbol}的模拟K线数据，共{len(kline_data)}条")
            print(f"  最近5条数据:")
            print(kline_data.tail())
        else:
            print(f"⚠ {test_symbol}的模拟K线数据为空")
            
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_data_fetcher()
