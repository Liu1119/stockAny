import pandas as pd
import numpy as np
import logging
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KLineDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_kline_data(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        try:
            secid = f"1.{stock_code}" if stock_code.startswith('60') or stock_code.startswith('688') else f"0.{stock_code}"
            
            url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&end=20500101&lmt={days}"
            
            logger.info(f"获取K线数据: {stock_code}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"获取K线数据失败: HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            if 'data' not in data or not data['data']:
                logger.warning(f"未找到股票 {stock_code} 的K线数据")
                return None
            
            klines = data['data'].get('klines', [])
            
            if not klines:
                logger.warning(f"股票 {stock_code} K线数据为空")
                return None
            
            kline_list = []
            for kline in klines:
                parts = kline.split(',')
                if len(parts) >= 7:
                    kline_list.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                        'volume': float(parts[5]),
                        'amount': float(parts[6])
                    })
            
            df = pd.DataFrame(kline_list)
            df['date'] = pd.to_datetime(df['date'])
            
            logger.info(f"成功获取 {stock_code} K线数据，共 {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取K线数据失败 {stock_code}: {str(e)}")
            return None
    
    def has_big_yang_line_or_limit_up(self, kline_data: pd.DataFrame, lookback_days: int = 30) -> bool:
        if kline_data is None or len(kline_data) < lookback_days:
            return False
        
        recent_data = kline_data.iloc[-lookback_days:]
        
        for idx, row in recent_data.iterrows():
            if row['open'] > 0:
                change = (row['close'] - row['open']) / row['open']
                
                if change >= 0.095:
                    return True
                
                if change >= 0.05:
                    avg_volume = recent_data['volume'].mean()
                    if row['volume'] > avg_volume * 1.5:
                        return True
        
        return False
    
    def is_ma10_upward(self, kline_data: pd.DataFrame, days: int = 3) -> bool:
        if kline_data is None or len(kline_data) < 15:
            return False
        
        kline_data['MA10'] = kline_data['close'].rolling(window=10).mean()
        
        ma10_series = kline_data['MA10'].dropna()
        
        if len(ma10_series) < days + 1:
            return False
        
        recent_ma = ma10_series.iloc[-days-1:]
        
        return all(recent_ma.iloc[i] < recent_ma.iloc[i+1] for i in range(len(recent_ma)-1))
    
    def is_ma10_near_ma20(self, kline_data: pd.DataFrame, threshold: float = 0.05) -> bool:
        if kline_data is None or len(kline_data) < 25:
            return False
        
        kline_data['MA10'] = kline_data['close'].rolling(window=10).mean()
        kline_data['MA20'] = kline_data['close'].rolling(window=20).mean()
        
        latest = kline_data.iloc[-1]
        ma10 = latest['MA10']
        ma20 = latest['MA20']
        
        if pd.isna(ma10) or pd.isna(ma20) or ma20 == 0:
            return False
        
        distance = abs(ma10 - ma20) / ma20
        
        return distance <= threshold

class StockSelector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.kline_fetcher = KLineDataFetcher()
    
    def get_realtime_data(self, stock_codes: List[str]) -> List[Dict]:
        try:
            logger.info(f"开始获取 {len(stock_codes)} 只股票的实时数据")
            
            market_prefix_map = {}
            for code in stock_codes:
                if code.startswith('60') or code.startswith('688'):
                    market_prefix_map[code] = 'sh'
                elif code.startswith('00') or code.startswith('300'):
                    market_prefix_map[code] = 'sz'
                else:
                    market_prefix_map[code] = 'sh'
            
            symbols = [f"{market_prefix_map[code]}{code}" for code in stock_codes]
            
            batch_size = 100
            all_data = []
            
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i+batch_size]
                symbols_str = ",".join(batch_symbols)
                url = f"http://qt.gtimg.cn/q={symbols_str}"
                
                logger.info(f"获取批次 {i//batch_size + 1}/{(len(symbols) + batch_size - 1) // batch_size}")
                
                try:
                    response = self.session.get(url, timeout=10)
                    response.encoding = 'gbk'
                    
                    if response.status_code != 200:
                        logger.error(f"API请求失败: {response.status_code}")
                        continue
                    
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
                                symbol = symbol_part[2:]
                                stock_code = symbol[2:]
                                
                                fields = data_part.split('~')
                                if len(fields) < 40:
                                    continue
                                
                                name = fields[1]
                                price = float(fields[3]) if fields[3] else 0
                                yesterday_close = float(fields[4]) if fields[4] else 0
                                open_price = float(fields[5]) if fields[5] else 0
                                volume = int(float(fields[6])) if fields[6] else 0
                                amount = float(fields[37]) if len(fields) > 37 and fields[37] else 0
                                high = float(fields[33]) if len(fields) > 33 and fields[33] else 0
                                low = float(fields[34]) if len(fields) > 34 and fields[34] else 0
                                
                                change_percent = float(fields[32]) if len(fields) > 32 and fields[32] else 0
                                volume_ratio = float(fields[43]) if len(fields) > 43 and fields[43] else 1.0
                                turnover_rate = float(fields[38]) if len(fields) > 38 and fields[38] else 0.0
                                
                                try:
                                    order_data = fields[35].split('/') if len(fields) > 35 and fields[35] else []
                                    order_ratio = float(order_data[0]) if len(order_data) > 0 else 0.0
                                except:
                                    order_ratio = 0.0
                                
                                if price > 0 and open_price > 0:
                                    stock_data = {
                                        'code': stock_code,
                                        'name': name,
                                        'price': price,
                                        'open': open_price,
                                        'high': high,
                                        'low': low,
                                        'yesterday_close': yesterday_close,
                                        'change_percent': change_percent,
                                        'volume': volume,
                                        'amount': amount,
                                        'volume_ratio': volume_ratio,
                                        'order_ratio': order_ratio,
                                        'turnover_rate': turnover_rate,
                                        'is_yin_line': price < open_price
                                    }
                                    all_data.append(stock_data)
                        
                        except Exception as e:
                            logger.error(f"解析股票数据失败: {str(e)}")
                            continue
                
                except Exception as e:
                    logger.error(f"请求API失败: {str(e)}")
                    continue
                
                time.sleep(0.1)
            
            logger.info(f"成功获取 {len(all_data)} 只股票的实时数据")
            return all_data
            
        except Exception as e:
            logger.error(f"获取实时数据失败: {str(e)}")
            return []
    
    def select_stocks(self, stock_codes: List[str]) -> List[Dict]:
        logger.info(f"开始筛选股票，共 {len(stock_codes)} 只")
        
        realtime_data = self.get_realtime_data(stock_codes)
        
        if not realtime_data:
            logger.warning("未获取到实时数据")
            return []
        
        selected_stocks = []
        
        for stock in realtime_data:
            try:
                if not stock['is_yin_line']:
                    continue
                
                if stock['change_percent'] > 0:
                    continue
                
                if stock['volume_ratio'] > 1.5:
                    continue
                
                if stock['price'] < 5 or stock['price'] > 60:
                    continue
                
                if stock['volume'] < 50000:
                    continue
                
                kline_data = self.kline_fetcher.get_kline_data(stock['code'], days=60)
                
                if kline_data is not None and len(kline_data) >= 30:
                    has_big_yang = self.kline_fetcher.has_big_yang_line_or_limit_up(kline_data, lookback_days=30)
                    ma10_upward = self.kline_fetcher.is_ma10_upward(kline_data, days=3)
                    ma_near = self.kline_fetcher.is_ma10_near_ma20(kline_data, threshold=0.05)
                    
                    if not has_big_yang:
                        continue
                    
                    if not ma10_upward:
                        continue
                    
                    if not ma_near:
                        continue
                
                priority = 0
                
                if stock['volume_ratio'] < 0.5:
                    priority += 3
                elif stock['volume_ratio'] < 0.8:
                    priority += 2
                
                if stock['turnover_rate'] >= 3 and stock['turnover_rate'] <= 8:
                    priority += 2
                
                if stock['change_percent'] >= -5 and stock['change_percent'] <= -2:
                    priority += 2
                
                if stock['order_ratio'] > 0:
                    priority += 1
                
                stock_info = {
                    'code': stock['code'],
                    'name': stock['name'],
                    'price': stock['price'],
                    'change_percent': stock['change_percent'],
                    'volume_ratio': stock['volume_ratio'],
                    'turnover_rate': stock['turnover_rate'],
                    'order_ratio': stock['order_ratio'],
                    'volume': stock['volume'],
                    'priority': priority
                }
                
                selected_stocks.append(stock_info)
                logger.info(f"选中股票: {stock['code']} {stock['name']}")
                
            except Exception as e:
                logger.error(f"处理股票 {stock.get('code', '未知')} 失败: {str(e)}")
                continue
        
        selected_stocks.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"筛选完成，共选中 {len(selected_stocks)} 只股票")
        return selected_stocks

class FeishuNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_message(self, selected_stocks: List[Dict]) -> bool:
        try:
            if not selected_stocks:
                message = {
                    "msg_type": "text",
                    "content": {
                        "text": f"股票筛选结果\n\n筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n今日未筛选出符合条件的股票。"
                    }
                }
            else:
                content_lines = [
                    f"股票筛选结果",
                    f"",
                    f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"筛选条件:",
                    f"• 阴线（收盘价 < 开盘价）",
                    f"• 缩量回调（量比 < 1.5）",
                    f"• 跌幅适中（-5% ~ -2%）",
                    f"• 价格适中（5元 ~ 60元）",
                    f"• 前30天有大阳线或涨停板",
                    f"• 10日线倾斜向上（多头排列）",
                    f"• 10日线与20日线距离较近",
                    f"",
                    f"共筛选出 {len(selected_stocks)} 只股票:",
                    f""
                ]
                
                for idx, stock in enumerate(selected_stocks[:20], 1):
                    content_lines.append(
                        f"{idx}. {stock['code']} {stock['name']} | "
                        f"价格: {stock['price']} | "
                        f"跌幅: {stock['change_percent']}% | "
                        f"量比: {stock['volume_ratio']} | "
                        f"换手率: {stock['turnover_rate']}% | "
                        f"优先级: {stock['priority']}"
                    )
                
                if len(selected_stocks) > 20:
                    content_lines.append(f"\n... 还有 {len(selected_stocks) - 20} 只股票未显示")
                
                message = {
                    "msg_type": "text",
                    "content": {
                        "text": "\n".join(content_lines)
                    }
                }
            
            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(message),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info("飞书消息发送成功")
                    return True
                else:
                    logger.error(f"飞书消息发送失败: {result}")
                    return False
            else:
                logger.error(f"飞书消息发送失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"发送飞书消息失败: {str(e)}")
            return False

class ScheduledStockSelector:
    def __init__(self, feishu_webhook: str):
        self.feishu_webhook = feishu_webhook
        self.selector = StockSelector()
        self.notifier = FeishuNotifier(feishu_webhook)
    
    def run_selection(self, stock_codes: List[str]):
        logger.info("开始执行定时选股任务")
        
        selected_stocks = self.selector.select_stocks(stock_codes)
        
        self.notifier.send_message(selected_stocks)
        
        logger.info("定时选股任务执行完成")
        return selected_stocks

if __name__ == "__main__":
    FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d6930274-cf9f-48d9-80d9-b1f735c43fc2"
    
    test_stocks = [
        '600000', '600036', '600519', '600887', '600030',
        '000001', '000002', '000333', '000651', '000858',
        '600276', '601318', '601398', '601288', '601988',
        '000001', '000002', '000063', '000333', '000651'
    ]
    
    scheduler = ScheduledStockSelector(FEISHU_WEBHOOK)
    result = scheduler.run_selection(test_stocks)
    
    print(f"\n筛选结果: {len(result)} 只股票")
    for stock in result:
        print(f"{stock['code']} {stock['name']} - 价格: {stock['price']}, 跌幅: {stock['change_percent']}%, 优先级: {stock['priority']}")
