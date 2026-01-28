import pandas as pd
import pandas_ta as ta
import logging
from data_fetcher import DataFetcher

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockFilter:
    def __init__(self, default_source='akshare', tushare_token=None):
        # 禁用模拟数据模式，使用指定的数据源
        self.fetcher = DataFetcher(use_mock_data=False, default_source=default_source, tushare_token=tushare_token)
    
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
            
            # 计算MACD指标
            try:
                macd = ta.macd(kline_data['close'])
                kline_data = pd.concat([kline_data, macd], axis=1)
            except Exception as e:
                logger.warning(f"计算MACD指标失败: {str(e)}")
            
            # 计算KDJ指标
            try:
                kdj = ta.stoch(kline_data['high'], kline_data['low'], kline_data['close'])
                kline_data = pd.concat([kline_data, kdj], axis=1)
            except Exception as e:
                logger.warning(f"计算KDJ指标失败: {str(e)}")
            
            # 计算移动平均线
            try:
                kline_data['MA5'] = ta.sma(kline_data['close'], length=5)
                kline_data['MA10'] = ta.sma(kline_data['close'], length=10)
                kline_data['MA20'] = ta.sma(kline_data['close'], length=20)
                kline_data['MA60'] = ta.sma(kline_data['close'], length=60)
            except Exception as e:
                logger.warning(f"计算移动平均线失败: {str(e)}")
            
            # 计算成交量移动平均线
            try:
                kline_data['MA_VOL5'] = ta.sma(kline_data['volume'], length=5)
                kline_data['MA_VOL10'] = ta.sma(kline_data['volume'], length=10)
            except Exception as e:
                logger.warning(f"计算成交量移动平均线失败: {str(e)}")
            
            # 计算布林带
            try:
                bbands = ta.bbands(kline_data['close'])
                kline_data = pd.concat([kline_data, bbands], axis=1)
            except Exception as e:
                logger.warning(f"计算布林带失败: {str(e)}")
            
            # 计算RSI指标
            try:
                kline_data['RSI'] = ta.rsi(kline_data['close'])
            except Exception as e:
                logger.warning(f"计算RSI指标失败: {str(e)}")
            
            # 计算WR指标（威廉指标）
            try:
                kline_data['WR14'] = ta.willr(kline_data['high'], kline_data['low'], kline_data['close'], length=14)
                kline_data['WR21'] = ta.willr(kline_data['high'], kline_data['low'], kline_data['close'], length=21)
            except Exception as e:
                logger.warning(f"计算WR指标失败: {str(e)}")
            
            return kline_data
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {str(e)}")
            return pd.DataFrame()
    
    def filter_stocks(self, market_data):
        """
        筛选股票
        :param market_data: 市场股票数据DataFrame
        :return: 筛选后的股票列表
        """
        try:
            filtered_stocks = []
            
            # 限制处理的股票数量，避免处理时间过长
            max_stocks = 50
            processed_count = 0
            
            for idx, row in market_data.iterrows():
                if processed_count >= max_stocks:
                    break
                
                try:
                    stock_code = row['代码']
                    stock_name = row['名称']
                    
                    # 获取股票K线数据
                    kline_data = self.fetcher.get_stock_kline(stock_code)
                    
                    if kline_data.empty:
                        continue
                    
                    # 计算技术指标
                    kline_data = self.calculate_indicators(kline_data)
                    
                    if kline_data.empty:
                        continue
                    
                    # 获取最新数据
                    latest_data = kline_data.iloc[-1]
                    
                    # 筛选条件1: MACD金叉，柱状线翻红
                    macd_bullish = False
                    if all(col in latest_data.index for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
                        # 检查值是否为None
                        if None not in [latest_data['MACD_12_26_9'], latest_data['MACDs_12_26_9'], latest_data['MACDh_12_26_9']]:
                            # MACD线金叉信号线，且柱状线为正（翻红）
                            macd_bullish = latest_data['MACD_12_26_9'] > latest_data['MACDs_12_26_9']
                            macd_bullish = macd_bullish and latest_data['MACDh_12_26_9'] > 0
                    
                    # 筛选条件2: WR（14, 21）双线均低于 20（超卖）
                    wr_bullish = False
                    if all(col in latest_data.index for col in ['WR14', 'WR21']):
                        # 检查值是否为None
                        if None not in [latest_data['WR14'], latest_data['WR21']]:
                            # WR指标低于-80表示超卖，这里使用-20作为阈值
                            wr_bullish = latest_data['WR14'] < -80 and latest_data['WR21'] < -80
                    
                    # 筛选条件3: 均线多头排列
                    ma_bullish = False
                    if all(col in latest_data.index for col in ['MA5', 'MA10', 'MA20', 'MA60']):
                        # 检查值是否为None
                        if None not in [latest_data['MA5'], latest_data['MA10'], latest_data['MA20'], latest_data['MA60']]:
                            ma_bullish = latest_data['MA5'] > latest_data['MA10'] > latest_data['MA20'] > latest_data['MA60']
                    
                    # 筛选条件4: 成交量增长 20% 以上
                    volume_bullish = False
                    if all(col in latest_data.index for col in ['volume', 'MA_VOL5']):
                        # 检查值是否为None
                        if None not in [latest_data['volume'], latest_data['MA_VOL5']]:
                            # 成交量大于5日均量的120%
                            volume_bullish = latest_data['volume'] > latest_data['MA_VOL5'] * 1.2
                    
                    # 筛选条件5: 股价突破压力位（突破布林带上轨）
                    breakout_bullish = False
                    if all(col in latest_data.index for col in ['close', 'BBU_5_2.0']):
                        # 检查值是否为None
                        if None not in [latest_data['close'], latest_data['BBU_5_2.0']]:
                            breakout_bullish = latest_data['close'] > latest_data['BBU_5_2.0']
                    
                    # 计算KDJ和RSI的看涨条件
                    kdj_bullish = False
                    if all(col in latest_data.index for col in ['STOCHk_14_3_3', 'STOCHd_14_3_3']):
                        # 检查值是否为None
                        if None not in [latest_data['STOCHk_14_3_3'], latest_data['STOCHd_14_3_3']]:
                            kdj_bullish = latest_data['STOCHk_14_3_3'] > latest_data['STOCHd_14_3_3']
                    
                    rsi_bullish = False
                    if 'RSI' in latest_data.index:
                        # 检查值是否为None
                        if latest_data['RSI'] is not None:
                            rsi_bullish = 30 < latest_data['RSI'] < 70  # RSI在正常区间
                    
                    # 综合判断：MACD金叉和WR超卖同时出现形成共振，再加上其他条件
                    if macd_bullish and wr_bullish and (ma_bullish or volume_bullish or breakout_bullish):
                        stock_info = {
                            'code': stock_code,
                            'name': stock_name,
                            'price': latest_data.get('close', 0),
                            'change': row.get('涨跌幅', 0),
                            'indicators': {
                                'macd_bullish': macd_bullish,
                                'wr_bullish': wr_bullish,
                                'ma_bullish': ma_bullish,
                                'volume_bullish': volume_bullish,
                                'breakout_bullish': breakout_bullish,
                                'kdj_bullish': kdj_bullish,
                                'rsi_bullish': rsi_bullish
                            }
                        }
                        filtered_stocks.append(stock_info)
                        
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"处理股票 {row.get('代码', '未知')} 失败: {str(e)}")
                    continue
            
            logger.info(f"筛选出 {len(filtered_stocks)} 只符合条件的股票")
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