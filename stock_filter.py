import pandas as pd
import logging
from data_fetcher import DataFetcher

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockFilter:
    def __init__(self, default_source='tencent'):
        # 禁用模拟数据模式，使用指定的数据源
        self.fetcher = DataFetcher(use_mock_data=False, default_source=default_source)
    
    def calculate_indicators(self, kline_data):
        """
        计算技术指标
        :param kline_data: K线数据DataFrame
        :return: 包含技术指标的DataFrame
        """
        try:
            # 确保数据包含必要的列
            if not all(col in kline_data.columns for col in ['open', 'high', 'low', 'close', 'volume']):
                logger.error("K线数据缺少必要的列")
                return pd.DataFrame()
            
            # 确保数据类型正确，处理None值
            for col in ['open', 'high', 'low', 'close', 'volume']:
                kline_data[col] = pd.to_numeric(kline_data[col], errors='coerce')
            
            # 移除包含NaN值的行
            kline_data = kline_data.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
            
            if kline_data.empty:
                logger.error("K线数据为空或包含无效值")
                return pd.DataFrame()
            
            # 计算移动平均线
            try:
                kline_data['MA5'] = kline_data['close'].rolling(window=5).mean()
                kline_data['MA10'] = kline_data['close'].rolling(window=10).mean()
                kline_data['MA20'] = kline_data['close'].rolling(window=20).mean()
                kline_data['MA60'] = kline_data['close'].rolling(window=60).mean()
            except Exception as e:
                logger.warning(f"计算移动平均线失败: {str(e)}")
            
            # 计算成交量移动平均线
            try:
                kline_data['MA_VOL5'] = kline_data['volume'].rolling(window=5).mean()
                kline_data['MA_VOL10'] = kline_data['volume'].rolling(window=10).mean()
            except Exception as e:
                logger.warning(f"计算成交量移动平均线失败: {str(e)}")
            
            # 计算MACD指标
            try:
                ema12 = kline_data['close'].ewm(span=12, adjust=False).mean()
                ema26 = kline_data['close'].ewm(span=26, adjust=False).mean()
                kline_data['MACD'] = ema12 - ema26
                kline_data['MACD_SIGNAL'] = kline_data['MACD'].ewm(span=9, adjust=False).mean()
                kline_data['MACD_HIST'] = kline_data['MACD'] - kline_data['MACD_SIGNAL']
            except Exception as e:
                logger.warning(f"计算MACD指标失败: {str(e)}")
            
            # 计算RSI指标
            try:
                delta = kline_data['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                kline_data['RSI'] = 100 - (100 / (1 + rs))
            except Exception as e:
                logger.warning(f"计算RSI指标失败: {str(e)}")
            
            # 计算布林带
            try:
                kline_data['BB_MIDDLE'] = kline_data['close'].rolling(window=20).mean()
                std = kline_data['close'].rolling(window=20).std()
                kline_data['BB_UPPER'] = kline_data['BB_MIDDLE'] + (std * 2)
                kline_data['BB_LOWER'] = kline_data['BB_MIDDLE'] - (std * 2)
            except Exception as e:
                logger.warning(f"计算布林带失败: {str(e)}")
            
            # 计算KDJ指标
            try:
                low_min = kline_data['low'].rolling(window=9).min()
                high_max = kline_data['high'].rolling(window=9).max()
                rsv = (kline_data['close'] - low_min) / (high_max - low_min) * 100
                kline_data['K'] = rsv.ewm(com=2, adjust=False).mean()
                kline_data['D'] = kline_data['K'].ewm(com=2, adjust=False).mean()
                kline_data['J'] = 3 * kline_data['K'] - 2 * kline_data['D']
            except Exception as e:
                logger.warning(f"计算KDJ指标失败: {str(e)}")
            
            # 计算WR指标（威廉指标）
            try:
                high_max_14 = kline_data['high'].rolling(window=14).max()
                low_min_14 = kline_data['low'].rolling(window=14).min()
                kline_data['WR14'] = (high_max_14 - kline_data['close']) / (high_max_14 - low_min_14) * 100
                
                high_max_21 = kline_data['high'].rolling(window=21).max()
                low_min_21 = kline_data['low'].rolling(window=21).min()
                kline_data['WR21'] = (high_max_21 - kline_data['close']) / (high_max_21 - low_min_21) * 100
            except Exception as e:
                logger.warning(f"计算WR指标失败: {str(e)}")
            
            return kline_data
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {str(e)}")
            return pd.DataFrame()
    
    def filter_stocks(self, market_data):
        """
        筛选股票（基于基础行情的"平替"策略）
        :param market_data: 市场股票数据DataFrame
        :return: 筛选后的股票列表
        """
        try:
            filtered_stocks = []
            
            # 限制处理的股票数量，避免处理时间过长
            max_stocks = 100
            processed_count = 0
            
            for idx, row in market_data.iterrows():
                if processed_count >= max_stocks:
                    break
                
                try:
                    stock_code = row['代码']
                    stock_name = row['名称']
                    
                    # 1. 筛选所有市场的股票（上证、深证、创业板）
                    # 移除创业板的限制，让所有市场的股票都能进入筛选流程
                    
                    # 2. 基本面筛选
                    # 基于股票价格和涨跌幅来判断是否退市风险较低
                    price = row.get('最新价', 0)
                    change = row.get('涨跌幅', 0)
                    volume = row.get('成交量', 0)
                    
                    # 基本面条件：价格大于10元，且近期没有大幅下跌
                    if price < 10 or change < -8:
                        continue
                    
                    # 3. 获取基础行情指标
                    volume_ratio = row.get('量比', 1.0)
                    order_ratio = row.get('委比', 0.0)
                    turnover_rate = row.get('换手率', 0.0)
                    sector_change = row.get('板块涨幅', 0.0)
                    
                    # 4. "平替"筛选策略
                    # 1) 异动平替：量比 > 1.8
                    volume_ratio_qualified = volume_ratio > 1.8
                    
                    # 2) 强度平替：委比为正数（最好 > 30%）
                    order_ratio_qualified = order_ratio > 30
                    
                    # 3) 活跃平替：换手率在 3% - 10% 之间
                    turnover_rate_qualified = 3 <= turnover_rate <= 10
                    
                    # 4) 空间平替：个股涨幅 > 板块平均涨幅
                    sector_qualified = change > sector_change
                    
                    # 综合筛选条件
                    short_term_qualified = volume_ratio_qualified and order_ratio_qualified and turnover_rate_qualified and sector_qualified
                    
                    if not short_term_qualified:
                        continue
                    
                    # 5. 确保数据不为None
                    if price is None:
                        price = 0
                    
                    if change is None:
                        change = 0
                    
                    stock_info = {
                        'code': stock_code,
                        'name': stock_name,
                        'price': price,
                        'change': change,
                        'volume': volume,
                        'volume_ratio': round(volume_ratio, 2),
                        'order_ratio': round(order_ratio, 2),
                        'turnover_rate': round(turnover_rate, 2),
                        'sector_change': round(sector_change, 2),
                        'indicators': {
                            'volume_ratio_qualified': volume_ratio_qualified,
                            'order_ratio_qualified': order_ratio_qualified,
                            'turnover_rate_qualified': turnover_rate_qualified,
                            'sector_qualified': sector_qualified,
                            'short_term_qualified': short_term_qualified
                        }
                    }
                    filtered_stocks.append(stock_info)
                    
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"处理股票 {row.get('代码', '未知')} 失败: {str(e)}")
                    continue
            
            logger.info(f"筛选出 {len(filtered_stocks)} 只符合'平替'策略条件的股票")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"筛选股票失败: {str(e)}")
            return []
    
    def filter_all_markets(self):
        """
        筛选所有市场的股票
        :return: 筛选后的股票列表
        """
        try:
            # 获取所有市场数据
            all_markets_data = self.fetcher.get_all_markets_data()
            
            all_filtered_stocks = []
            
            for market, data in all_markets_data.items():
                if not data.empty:
                    logger.info(f"开始筛选{market}市场的股票")
                    filtered_stocks = self.filter_stocks(data)
                    all_filtered_stocks.extend(filtered_stocks)
            
            logger.info(f"所有市场共筛选出 {len(all_filtered_stocks)} 只符合条件的股票")
            return all_filtered_stocks
            
        except Exception as e:
            logger.error(f"筛选所有市场股票失败: {str(e)}")
            return []