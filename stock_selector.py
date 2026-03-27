import pandas as pd
import numpy as np
import logging
import requests
import json
import concurrent.futures
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import time
import os
import pickle

# 设置时区为北京时间（东八区）
BEIJING_TZ = timezone(timedelta(hours=8))

class BeijingFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=BEIJING_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

# 配置日志处理器
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = BeijingFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
# 允许日志传播到根日志记录器，以便被HTTPHandler捕获
# logger.propagate = False

class KLineDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive'
        })
        # 增加连接池大小以支持20个并发线程
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=30,
            pool_maxsize=30,
            max_retries=3
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.request_interval = 0.1  # 减少请求间隔，提高速度
        self.max_retries = 3  # 最大重试次数
        self.max_workers = 20  # 增加并行度，提高速度
        
        # K线数据缓存配置
        self.cache_dir = 'kline_cache'
        self.cache_expiry_hours = 24  # 缓存有效期24小时
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_file_path(self, stock_code: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{stock_code}.pkl")
    
    def _is_cache_valid(self, cache_file: str) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(cache_file):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        expiry_time = datetime.now() - timedelta(hours=self.cache_expiry_hours)
        
        return file_time > expiry_time
    
    def _load_from_cache(self, stock_code: str) -> Optional[pd.DataFrame]:
        """从缓存加载K线数据"""
        cache_file = self._get_cache_file_path(stock_code)
        
        if self._is_cache_valid(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    kline_data = pickle.load(f)
                    logger.info(f"从缓存加载 {stock_code} K线数据")
                    return kline_data
            except Exception as e:
                logger.error(f"加载缓存失败 {stock_code}: {str(e)}")
        
        return None
    
    def _save_to_cache(self, stock_code: str, kline_data: pd.DataFrame):
        """保存K线数据到缓存"""
        cache_file = self._get_cache_file_path(stock_code)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(kline_data, f)
                logger.info(f"保存 {stock_code} K线数据到缓存")
        except Exception as e:
            logger.error(f"保存缓存失败 {stock_code}: {str(e)}")

    def get_kline_data(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        # 优先从缓存加载K线数据
        cached_data = self._load_from_cache(stock_code)
        if cached_data is not None:
            return cached_data
        
        # 缓存不存在或已过期，从腾讯API获取
        try:
            kline_data = self._get_kline_from_qq(stock_code, days)
            if kline_data is not None:
                # 保存到缓存
                self._save_to_cache(stock_code, kline_data)
                return kline_data
        except Exception as e:
            logger.error(f"使用腾讯API获取K线数据失败: {str(e)}")
            
        # 腾讯API失败
        logger.error(f"无法获取 {stock_code} 的K线数据")
        return None

    def _get_kline_from_qq(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """从腾讯财经获取K线数据"""
        for retry in range(self.max_retries):
            try:
                market = 'sh' if stock_code.startswith('60') or stock_code.startswith('688') else 'sz'
                symbol = f"{market}{stock_code}"
                # 使用正确的腾讯财经API参数格式
                url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq"
                
                time.sleep(self.request_interval)
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data and isinstance(data, dict):
                        # 腾讯财经API返回的数据结构: data -> symbol -> qfqday
                        stock_data = data.get('data', {}).get(symbol)
                        if stock_data:
                            klines = stock_data.get('qfqday', [])
                            if klines and isinstance(klines, list):
                                kline_list = []
                                for item in klines:
                                    if isinstance(item, list) and len(item) >= 5:
                                        kline_list.append({
                                            'date': item[0],
                                            'open': float(item[1]),
                                            'close': float(item[2]),
                                            'high': float(item[3]),
                                            'low': float(item[4]),
                                            'volume': float(item[5]) if len(item) > 5 else 0,
                                            'amount': 0  # 腾讯财经API不返回成交额
                                        })
                                df = pd.DataFrame(kline_list)
                                df['date'] = pd.to_datetime(df['date'])
                                return df
                else:
                    logger.error(f"腾讯财经API失败: HTTP {response.status_code}")
                    if response.status_code in [456, 502]:
                        time.sleep(3.0)
            except Exception as e:
                logger.error(f"腾讯财经API错误: {str(e)}")
        return None
    
    def get_kline_data_batch(self, stock_codes: List[str], days: int = 60) -> Dict[str, Optional[pd.DataFrame]]:
        """批量获取K线数据，使用并行处理"""
        logger.info(f"开始批量获取 {len(stock_codes)} 只股票的K线数据")
        
        results = {}
        
        # 使用线程池并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_stock = {executor.submit(self.get_kline_data, stock_code, days): stock_code for stock_code in stock_codes}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_stock):
                stock_code = future_to_stock[future]
                try:
                    kline_data = future.result()
                    results[stock_code] = kline_data
                    if kline_data is not None:
                        logger.info(f"成功获取 {stock_code} K线数据，共 {len(kline_data)} 条")
                    else:
                        logger.warning(f"无法获取 {stock_code} K线数据")
                except Exception as e:
                    logger.error(f"获取 {stock_code} K线数据时发生错误: {str(e)}")
                    results[stock_code] = None
        
        logger.info(f"批量获取K线数据完成，成功 {sum(1 for v in results.values() if v is not None)} 只，失败 {sum(1 for v in results.values() if v is None)} 只")
        return results
    
    def has_big_yang_line_or_limit_up(self, kline_data: pd.DataFrame, lookback_days: int = 30) -> bool:
        if kline_data is None or len(kline_data) < lookback_days:
            return False
        
        recent_data = kline_data.iloc[-lookback_days:]
        
        for idx, row in recent_data.iterrows():
            if row['open'] > 0:
                change = (row['close'] - row['open']) / row['open']
                
                if change >= 0.07:
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
    
    def is_ma10_near_ma20(self, kline_data: pd.DataFrame, threshold: float = 0.03) -> bool:
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
    
    def is_price_near_ma10(self, kline_data: pd.DataFrame, threshold: float = 0.03) -> bool:
        if kline_data is None or len(kline_data) < 15:
            return False
        
        kline_data['MA10'] = kline_data['close'].rolling(window=10).mean()
        
        latest = kline_data.iloc[-1]
        close = latest['close']
        ma10 = latest['MA10']
        
        if pd.isna(ma10) or ma10 == 0:
            return False
        
        distance = abs(close - ma10) / ma10
        
        return distance <= threshold
    
    def is_volume_shrink(self, kline_data: pd.DataFrame, threshold: float = 0.8) -> bool:
        if kline_data is None or len(kline_data) < 20:
            return False
        
        recent_data = kline_data.iloc[-20:]
        avg_volume = recent_data['volume'].mean()
        latest_volume = kline_data.iloc[-1]['volume']
        
        if avg_volume == 0:
            return False
        
        volume_ratio = latest_volume / avg_volume
        
        return volume_ratio <= threshold

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
                                volume_ratio = float(fields[49]) if len(fields) > 49 and fields[49] else 1.0
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
        logger.info("=" * 60)
        logger.info("开始筛选股票")
        logger.info("=" * 60)
        logger.info(f"待筛选股票数: {len(stock_codes)}")
        
        logger.info("\n【步骤1】获取实时数据...")
        realtime_data = self.get_realtime_data(stock_codes)
        
        if not realtime_data:
            logger.warning("✗ 未获取到实时数据")
            return []
        
        logger.info(f"✓ 成功获取 {len(realtime_data)} 只股票的实时数据")
        
        # 统计变量
        filtered_by_yin = 0
        filtered_by_kline = 0
        
        selected_stocks = []
        
        logger.info("\n【步骤2】开始筛选...")
        logger.info("筛选条件：")
        logger.info("  - 买阴不买阳：收盘价 < 开盘价，收纯阴线")
        logger.info("  - 缩量回调10日线：量能萎缩80%以内 + 股价紧贴10日线")
        logger.info("  - 10日线向上、贴近20日线：10日均线多头 + 两线距离＜3%")
        logger.info("  - 前期有涨停/大阳线：30天内出现过7%以上大阳/涨停")
        logger.info("")
        
        # 先进行基础筛选，收集需要进行K线分析的股票
        stocks_to_analyze = []
        for stock in realtime_data:
            try:
                code = stock['code']
                name = stock['name']
                
                # 1. 买阴不买阳：收盘价 < 开盘价，收纯阴线
                if not stock['is_yin_line']:
                    filtered_by_yin += 1
                    continue
                
                # 通过基础筛选，加入待分析列表
                stocks_to_analyze.append(stock)
            except Exception as e:
                logger.error(f"处理股票 {stock.get('code', '未知')} 时出错: {str(e)}")
                continue
        
        logger.info(f"基础筛选完成，共 {len(stocks_to_analyze)} 只股票需要进行K线分析")
        
        # 批量获取K线数据
        kline_data_dict = {}
        if stocks_to_analyze:
            stock_codes = [stock['code'] for stock in stocks_to_analyze]
            kline_data_dict = self.kline_fetcher.get_kline_data_batch(stock_codes, days=60)
        
        # 对每个股票进行K线分析
        for stock in stocks_to_analyze:
            try:
                code = stock['code']
                name = stock['name']
                
                # 获取K线数据
                kline_data = kline_data_dict.get(code)
                
                if kline_data is not None and len(kline_data) >= 30:
                    # 2. 缩量回调10日线：量能萎缩80%以内 + 股价紧贴10日线
                    is_volume_shrink = self.kline_fetcher.is_volume_shrink(kline_data, threshold=0.8)
                    is_price_near_ma10 = self.kline_fetcher.is_price_near_ma10(kline_data, threshold=0.03)
                    
                    if not (is_volume_shrink and is_price_near_ma10):
                        filtered_by_kline += 1
                        continue
                    
                    # 3. 10日线向上、贴近20日线：10日均线多头 + 两线距离＜3%
                    ma10_upward = self.kline_fetcher.is_ma10_upward(kline_data, days=3)
                    ma_near = self.kline_fetcher.is_ma10_near_ma20(kline_data, threshold=0.03)
                    
                    if not (ma10_upward and ma_near):
                        filtered_by_kline += 1
                        continue
                    
                    # 4. 前期有涨停/大阳线：30天内出现过7%以上大阳/涨停
                    has_big_yang = self.kline_fetcher.has_big_yang_line_or_limit_up(kline_data, lookback_days=30)
                    
                    if not has_big_yang:
                        filtered_by_kline += 1
                        continue
                else:
                    # K线数据获取失败，跳过该股票
                    filtered_by_kline += 1
                    continue
                
                # 计算优先级
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
                    'code': code,
                    'name': name,
                    'price': stock['price'],
                    'change_percent': stock['change_percent'],
                    'volume_ratio': stock['volume_ratio'],
                    'turnover_rate': stock['turnover_rate'],
                    'order_ratio': stock['order_ratio'],
                    'volume': stock['volume'],
                    'priority': priority
                }
                
                selected_stocks.append(stock_info)
                logger.info(f"✓ 筛选通过: {code} {name} - 价格:{stock['price']:.2f} 跌幅:{stock['change_percent']:.2f}% 量比:{stock['volume_ratio']:.2f} 优先级:{priority}")
                
            except Exception as e:
                logger.error(f"✗ 处理股票 {stock.get('code', '未知')} 失败: {str(e)}")
                continue
        
        selected_stocks.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info("\n【步骤3】筛选统计")
        logger.info(f"  - 总股票数: {len(realtime_data)}")
        logger.info(f"  - 非阴线: {filtered_by_yin} 只 (通过率: {(len(realtime_data) - filtered_by_yin) / len(realtime_data) * 100:.1f}%)")
        logger.info(f"  - K线形态不符: {filtered_by_kline} 只 (通过率: {(len(realtime_data) - filtered_by_yin - filtered_by_kline) / len(realtime_data) * 100:.1f}%)")
        logger.info(f"  - 最终通过: {len(selected_stocks)} 只 (总通过率: {len(selected_stocks) / len(realtime_data) * 100:.2f}%)")
        

        
        logger.info("\n【步骤4】选股完成")
        logger.info(f"✓ 筛选完成，共选中 {len(selected_stocks)} 只股票")
        logger.info("=" * 60)
        
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
                    f"• 缩量回调（量比 < 2.0）",
                    f"• 跌幅适中（跌幅 <= 0%）",
                    f"• 价格区间（5元 ~ 60元）",
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
        
        # 禁用自动发送飞书消息，改为手动发送
        # self.notifier.send_message(selected_stocks)
        
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
