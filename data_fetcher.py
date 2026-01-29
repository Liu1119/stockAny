import pandas as pd
import logging
import requests
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self, use_mock_data=False, default_source='tencent'):
        self.use_mock_data = False  # 强制禁用模拟数据
        self.default_source = 'tencent'  # 强制使用腾讯财经
        
        # 禁用所有其他数据源
        self.bs_init = False
        
        logger.info("仅使用腾讯财经API获取真实数据")
        logger.info("腾讯财经数据源初始化完成")
    
    def get_mock_stock_data(self, market):
        """
        生成模拟的股票数据
        :param market: 市场类型
        :return: 模拟的股票数据DataFrame
        """
        try:
            logger.info(f"生成{market}市场的模拟股票数据")
            
            # 定义市场对应的股票代码前缀
            code_prefix = {
                'sh': '600',    # 上证A股
                'sz': '000',    # 深证A股
                'cyb': '300',   # 创业板
                'kcb': '688'    # 科创板
            }
            
            if market not in code_prefix:
                logger.error(f"不支持的市场类型: {market}")
                return pd.DataFrame()
            
            prefix = code_prefix[market]
            
            # 生成模拟数据
            data = []
            for i in range(1, 11):
                if market == 'kcb':
                    # 科创板代码是688开头，4位数字
                    code = f"{prefix}{i:03d}"
                else:
                    # 其他市场代码是6位数字
                    code = f"{prefix}{i:03d}"
                
                # 生成模拟数据
                stock_data = {
                    '代码': code,
                    '名称': f"模拟股票{i}",
                    '最新价': round(10 + i * 2.5, 2),
                    '涨跌幅': round((i - 5) * 0.5, 2),
                    '成交量': 1000000 + i * 50000,
                    '成交额': round((10 + i * 2.5) * (1000000 + i * 50000), 2)
                }
                data.append(stock_data)
            
            df = pd.DataFrame(data)
            logger.info(f"生成{market}市场模拟数据成功，返回{len(df)}只股票")
            return df
            
        except Exception as e:
            logger.error(f"生成模拟股票数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_data_from_tencent(self, market):
        """
        使用腾讯财经API获取指定市场的股票数据
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 股票数据DataFrame
        """
        try:
            logger.info(f"使用腾讯财经获取{market}市场的股票数据")
            
            # 腾讯财经API格式：http://qt.gtimg.cn/q=sh600000,sz000001
            # 定义市场对应的前缀
            market_prefix = {
                'sh': 'sh',  # 上证
                'sz': 'sz',  # 深证
                'cyb': 'sz',  # 创业板
                'kcb': 'sh'   # 科创板
            }
            
            if market not in market_prefix:
                logger.error(f"不支持的市场类型: {market}")
                return pd.DataFrame()
            
            # 定义市场对应的股票代码前缀
            code_prefix = {
                'sh': '60',    # 上证A股
                'sz': '00',    # 深证A股
                'cyb': '300',  # 创业板
                'kcb': '688'   # 科创板
            }
            
            # 生成股票代码列表（每个市场取前10只股票）
            stock_codes = []
            prefix = code_prefix[market]
            
            if market == 'kcb':
                # 科创板代码是688开头，4位数字（688001-688010）
                for i in range(1, 11):
                    code = f"{prefix}{i:03d}"
                    stock_codes.append(code)
            elif market == 'cyb':
                # 创业板代码是300开头，3位数字（300001-300010）
                for i in range(1, 11):
                    code = f"{prefix}{i:03d}"
                    stock_codes.append(code)
            else:
                # 上证和深证代码是6位数字
                # 上证：600001-600010
                # 深证：000001-000010
                for i in range(1, 11):
                    code = f"{prefix}{i:04d}"
                    stock_codes.append(code)
            
            # 构建腾讯财经API URL
            tencent_prefix = market_prefix[market]
            stock_symbols = [f"{tencent_prefix}{code}" for code in stock_codes]
            symbols_str = ",".join(stock_symbols)
            url = f"http://qt.gtimg.cn/q={symbols_str}"
            
            logger.info(f"调用腾讯财经API: {url}")
            
            # 发送HTTP请求
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'  # 腾讯财经返回GBK编码
            
            if response.status_code != 200:
                logger.error(f"腾讯财经API请求失败: {response.status_code}")
                return pd.DataFrame()
            
            # 解析响应数据
            data = {
                '代码': [],
                '名称': [],
                '最新价': [],
                '涨跌幅': [],
                '成交量': [],
                '成交额': []
            }
            
            lines = response.text.strip().split(';')
            
            for line in lines:
                if not line:
                    continue
                
                try:
                    # 解析腾讯财经返回格式：v_sh600000="1~浦发银行~600000~..."
                    parts = line.split('=')
                    if len(parts) != 2:
                        continue
                    
                    symbol_part = parts[0].strip()
                    data_part = parts[1].strip().strip('"')
                    
                    # 提取股票代码
                    if symbol_part.startswith('v_'):
                        symbol = symbol_part[2:]
                        stock_code = symbol[2:]  # 去掉市场前缀，如sh600000 -> 600000
                        
                        # 解析数据部分
                        fields = data_part.split('~')
                        if len(fields) < 34:
                            continue
                        
                        name = fields[1]      # 股票名称
                        price = float(fields[3])  # 最新价
                        change = float(fields[32])  # 涨跌幅
                        volume = int(float(fields[8]))  # 成交量
                        amount = float(fields[9])  # 成交额
                        
                        # 添加到数据中
                        data['代码'].append(stock_code)
                        data['名称'].append(name)
                        data['最新价'].append(price)
                        data['涨跌幅'].append(change)
                        data['成交量'].append(volume)
                        data['成交额'].append(amount)
                
                except Exception as e:
                    logger.error(f"解析腾讯财经数据失败: {str(e)}")
                    continue
            
            # 构建DataFrame
            df = pd.DataFrame(data)
            
            if df.empty:
                logger.warning(f"腾讯财经API返回空数据")
                return pd.DataFrame()
            
            logger.info(f"腾讯财经API获取{market}市场数据成功，返回{len(df)}只股票")
            return df
            
        except Exception as e:
            logger.error(f"使用腾讯财经API获取股票数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_data(self, market):
        """
        获取指定市场的股票数据，仅使用腾讯财经API获取实时数据
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 股票数据DataFrame
        """
        try:
            logger.info(f"开始获取{market}市场的股票数据")
            
            # 仅使用腾讯财经API获取实时数据
            data = self.get_stock_data_from_tencent(market)
            
            if not data.empty:
                # 检查是否有有效的价格数据
                if '最新价' in data.columns and not (data['最新价'] == 0).all():
                    logger.info(f"腾讯财经API获取{market}市场数据成功")
                    return data
                else:
                    logger.warning(f"腾讯财经数据价格无效")
            else:
                logger.warning(f"腾讯财经获取{market}市场数据失败")
            
            logger.warning(f"所有数据源获取{market}市场数据失败，返回空数据")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取{market}市场数据失败: {str(e)}")
            # 当所有数据源都失败时，返回空数据
            return pd.DataFrame()
    
    def get_single_stock_data(self, stock_code):
        """
        获取单只股票的实时数据，使用腾讯财经API
        :param stock_code: 股票代码
        :return: 包含股票名称和价格的字典，或None
        """
        try:
            logger.info(f"开始获取股票{stock_code}的实时数据")
            
            # 确定市场前缀
            if stock_code.startswith('60'):
                market_prefix = 'sh'
            elif stock_code.startswith('00'):
                market_prefix = 'sz'
            elif stock_code.startswith('300'):
                market_prefix = 'sz'
            elif stock_code.startswith('688'):
                market_prefix = 'sh'
            else:
                logger.error(f"未知的股票代码格式: {stock_code}")
                return None
            
            # 构建腾讯财经API URL
            symbol = f"{market_prefix}{stock_code}"
            url = f"http://qt.gtimg.cn/q={symbol}"
            
            logger.info(f"调用腾讯财经API获取单只股票数据: {url}")
            
            # 发送HTTP请求
            response = requests.get(url, timeout=10)
            response.encoding = 'gbk'  # 腾讯财经返回GBK编码
            
            if response.status_code != 200:
                logger.error(f"腾讯财经API请求失败: {response.status_code}")
                return None
            
            # 解析响应数据
            lines = response.text.strip().split(';')
            
            for line in lines:
                if not line:
                    continue
                
                try:
                    # 解析腾讯财经返回格式：v_sh600000="1~浦发银行~600000~..."
                    parts = line.split('=')
                    if len(parts) != 2:
                        continue
                    
                    symbol_part = parts[0].strip()
                    data_part = parts[1].strip().strip('"')
                    
                    # 提取股票代码
                    if symbol_part.startswith('v_'):
                        symbol = symbol_part[2:]
                        extracted_code = symbol[2:]  # 去掉市场前缀，如sh600000 -> 600000
                        
                        if extracted_code == stock_code:
                            # 解析数据部分
                            fields = data_part.split('~')
                            if len(fields) < 34:
                                continue
                            
                            name = fields[1]      # 股票名称
                            price = float(fields[3])  # 最新价
                            change = float(fields[32])  # 涨跌幅
                            volume = int(float(fields[8]))  # 成交量
                            amount = float(fields[9])  # 成交额
                            
                            logger.info(f"获取股票{stock_code}数据成功: {name}, 价格: {price}")
                            return {
                                '代码': stock_code,
                                '名称': name,
                                '最新价': price,
                                '涨跌幅': change,
                                '成交量': volume,
                                '成交额': amount
                            }
                
                except Exception as e:
                    logger.error(f"解析单只股票数据失败: {str(e)}")
                    continue
            
            logger.warning(f"无法获取股票{stock_code}的数据")
            return None
            
        except Exception as e:
            logger.error(f"获取单只股票数据失败: {str(e)}")
            return None
    
    def get_all_markets_data(self):
        """
        获取所有市场的股票数据
        :return: 包含所有市场股票数据的字典
        """
        markets = ['sh', 'sz', 'cyb', 'kcb']
        all_data = {}
        
        for market in markets:
            data = self.get_stock_data(market)
            all_data[market] = data
        
        return all_data
    
    def get_stock_kline(self, symbol, period='1d', start_date=None, end_date=None):
        """
        获取单个股票的K线数据
        :param symbol: 股票代码
        :param period: 周期，可选值：'1d'（日线）、'1w'（周线）、'1M'（月线）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: K线数据DataFrame
        """
        try:
            logger.info(f"开始获取股票 {symbol} 的K线数据")
            
            # 由于我们不再使用其他数据源，这里返回空数据
            # 实际应用中可以添加腾讯财经的K线数据获取
            logger.warning("K线数据获取功能已禁用，返回空数据")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取股票K线数据失败: {str(e)}")
            return pd.DataFrame()