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
                    
                    # 获取股票基本面数据
                    fundamental_data = self.fetcher.get_stock_fundamental(stock_code)
                    
                    if not fundamental_data:
                        continue
                    
                    # 1. 检查赚钱能力
                    # 核心指标1: 净资产收益率（ROE）- 连续3年ROE≥15%
                    roe = fundamental_data.get('roe', 0)
                    roe_qualified = roe is not None and roe >= 15
                    
                    # 核心指标2: 毛利率 - 毛利率≥30%
                    profit_rate = fundamental_data.get('profit_rate', 0)
                    profit_rate_qualified = profit_rate is not None and profit_rate >= 30
                    
                    # 2. 检查财务健康
                    # 资产负债率: 低于60%
                    debt_ratio = fundamental_data.get('debt_ratio', 100)
                    debt_ratio_qualified = debt_ratio is not None and debt_ratio < 60
                    
                    # 现金流: 经营现金流≥净利润（这里简化处理，使用现金流指标）
                    cash_flow = fundamental_data.get('cash_flow', 0)
                    cash_flow_qualified = cash_flow is not None and cash_flow > 0
                    
                    # 3. 检查成长潜力
                    # 营收增长: 连续3年增长，每年增长≥10%
                    revenue_growth = fundamental_data.get('revenue_growth', 0)
                    revenue_growth_qualified = revenue_growth is not None and revenue_growth >= 10
                    
                    # 净利润增长: 连续3年增长，每年增长≥10%
                    profit_growth = fundamental_data.get('profit_growth', 0)
                    profit_growth_qualified = profit_growth is not None and profit_growth >= 10
                    
                    # 净利润增速≥营收增速
                    growth_ratio_qualified = (profit_growth is not None and revenue_growth is not None and 
                                         profit_growth >= revenue_growth)
                    
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
                    
                    # 综合判断：基本面条件全部满足
                    if (roe_qualified and profit_rate_qualified and 
                        debt_ratio_qualified and cash_flow_qualified and 
                        revenue_growth_qualified and profit_growth_qualified and 
                        growth_ratio_qualified):
                        
                        # 确保price和change不为None
                        price = latest_data.get('close', 0)
                        if price is None:
                            price = 0
                        
                        change = row.get('涨跌幅', 0)
                        if change is None:
                            change = 0
                        
                        stock_info = {
                            'code': stock_code,
                            'name': stock_name,
                            'price': price,
                            'change': change,
                            'fundamental_data': fundamental_data,
                            'indicators': {
                                'roe_qualified': roe_qualified,
                                'profit_rate_qualified': profit_rate_qualified,
                                'debt_ratio_qualified': debt_ratio_qualified,
                                'cash_flow_qualified': cash_flow_qualified,
                                'revenue_growth_qualified': revenue_growth_qualified,
                                'profit_growth_qualified': profit_growth_qualified,
                                'growth_ratio_qualified': growth_ratio_qualified
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