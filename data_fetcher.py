import pandas as pd
import logging
import requests
import json
from datetime import datetime, timezone, timedelta

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

class DataFetcher:
    def __init__(self, use_mock_data=False, default_source='tencent'):
        self.use_mock_data = False  # 强制禁用模拟数据
        self.default_source = 'tencent'  # 强制使用腾讯财经
        self.use_datayes = False  # 禁用萝卜投研数据
        
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
            
            # 生成股票代码列表（获取每个市场的所有股票）
            stock_codes = []
            prefix = code_prefix[market]
            
            if market == 'kcb':
                # 科创板代码是688开头，4位数字（688001-688999）
                for i in range(1, 1000):
                    code = f"{prefix}{i:03d}"
                    stock_codes.append(code)
            elif market == 'cyb':
                # 创业板代码是300开头，3位数字（300001-300999）
                for i in range(1, 1000):
                    code = f"{prefix}{i:03d}"
                    stock_codes.append(code)
            elif market == 'sh':
                # 上证代码是60开头，4位数字（600001-609999）
                for i in range(1, 10000):
                    code = f"{prefix}{i:04d}"
                    stock_codes.append(code)
            elif market == 'sz':
                # 深证代码是00开头，4位数字（000001-009999）
                for i in range(1, 10000):
                    code = f"{prefix}{i:04d}"
                    stock_codes.append(code)
            
            # 构建腾讯财经API URL，分批请求以避免API限制
            tencent_prefix = market_prefix[market]
            stock_symbols = [f"{tencent_prefix}{code}" for code in stock_codes]
            
            # 解析响应数据
            data = {
                '代码': [],
                '名称': [],
                '最新价': [],
                '开盘价': [],
                '最高价': [],
                '最低价': [],
                '涨跌幅': [],
                '成交量': [],
                '成交额': [],
                '量比': [],
                '委比': [],
                '换手率': [],
                '总市值': [],
                '板块涨幅': []
            }
            
            # 分批请求，每批最多100只股票
            batch_size = 100
            total_batches = (len(stock_symbols) + batch_size - 1) // batch_size
            
            logger.info(f"开始分批获取{market}市场股票数据，共{total_batches}批")
            
            for i in range(0, len(stock_symbols), batch_size):
                batch_symbols = stock_symbols[i:i+batch_size]
                symbols_str = ",".join(batch_symbols)
                url = f"http://qt.gtimg.cn/q={symbols_str}"
                
                logger.info(f"调用腾讯财经API (批次 {i//batch_size + 1}/{total_batches}): {url[:100]}...")  # 只显示URL的前100个字符
                
                try:
                    # 发送HTTP请求
                    response = requests.get(url, timeout=10)
                    response.encoding = 'gbk'  # 腾讯财经返回GBK编码
                    
                    if response.status_code != 200:
                        logger.error(f"腾讯财经API请求失败 (批次 {i//batch_size + 1}): {response.status_code}")
                        continue
                    
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
                                stock_code = symbol[2:]  # 去掉市场前缀，如sh600000 -> 600000
                                
                                # 解析数据部分
                                fields = data_part.split('~')
                                if len(fields) < 34:
                                    continue
                                

                                
                                name = fields[1]      # 股票名称
                                price = float(fields[3])  # 最新价
                                open_price = float(fields[4]) if len(fields) > 4 else price  # 开盘价
                                high_price = float(fields[5]) if len(fields) > 5 else price  # 最高价
                                low_price = float(fields[6]) if len(fields) > 6 else price  # 最低价
                                change = float(fields[32])  # 涨跌幅
                                volume = int(float(fields[8]))  # 成交量
                                amount = float(fields[9])  # 成交额
                                
                                # 解析额外字段
                                try:
                                    # 量比 - 字段49
                                    if len(fields) > 49:
                                        volume_ratio = float(fields[49])
                                    else:
                                        # 量比数据缺失，跳过该股票
                                        continue
                                    
                                    # 委比 - 字段12
                                    order_ratio = float(fields[12]) if len(fields) > 12 else 0.0
                                    
                                    # 换手率 - 字段38
                                    turnover_rate = 0.0
                                    if len(fields) > 38:
                                        try:
                                            turnover_rate = float(fields[38])
                                        except:
                                            pass
                                    
                                    # 总市值 - 字段45
                                    market_cap = 0.0
                                    if len(fields) > 45:
                                        try:
                                            market_cap = float(fields[45])
                                        except:
                                            pass
                                    
                                    # 板块涨幅（使用行业涨跌幅作为替代）
                                    sector_change = float(fields[32]) * 0.8 if len(fields) > 32 else 0.0
                                except (ValueError, IndexError):
                                    # 量比数据解析失败，跳过该股票
                                    continue
                                
                                # 添加到数据中
                                data['代码'].append(stock_code)
                                data['名称'].append(name)
                                data['最新价'].append(price)
                                data['开盘价'].append(open_price)
                                data['最高价'].append(high_price)
                                data['最低价'].append(low_price)
                                data['涨跌幅'].append(change)
                                data['成交量'].append(volume)
                                data['成交额'].append(amount)
                                data['量比'].append(volume_ratio)
                                data['委比'].append(order_ratio)
                                data['换手率'].append(turnover_rate)
                                data['总市值'].append(market_cap)
                                data['板块涨幅'].append(sector_change)
                        
                        except Exception as e:
                            logger.error(f"解析腾讯财经数据失败: {str(e)}")
                            continue
                
                except Exception as e:
                    logger.error(f"请求腾讯财经API失败 (批次 {i//batch_size + 1}): {str(e)}")
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
            
            # 确定市场前缀
            if symbol.startswith('60'):
                market_prefix = 'sh'
            elif symbol.startswith('00'):
                market_prefix = 'sz'
            elif symbol.startswith('300'):
                market_prefix = 'sz'
            elif symbol.startswith('688'):
                market_prefix = 'sh'
            else:
                logger.error(f"未知的股票代码格式: {symbol}")
                return pd.DataFrame()
            
            # 使用腾讯财经的K线数据API
            # 注意：腾讯财经API可能有访问限制，返回空数据时使用降级方案
            import time
            import datetime
            
            # 构建API URL - 尝试多种格式
            full_symbol = f"{market_prefix}{symbol}"
            
            # 准备多种API格式
            end_date = datetime.datetime.now().strftime('%Y%m%d')
            start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')
            
            # 提取年份后两位用于新API格式
            year = datetime.datetime.now().strftime('%y')
            
            urls = [
                # 格式1: ifzq域名 + 天数参数
                f"http://ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,,30",
                # 格式2: ifzq域名 + 具体日期
                f"http://ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,{start_date},{end_date}",
                # 格式3: web子域名 + 天数参数
                f"http://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,,30",
                # 格式4: web子域名 + 具体日期
                f"http://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={full_symbol},day,{start_date},{end_date}",
                # 格式5: data子域名 + 新格式 (用户提供)
                f"https://data.gtimg.cn/flashdata/hushen/daily/{year}/{full_symbol}.js"
            ]
            
            # 尝试所有API格式
            kline_data = []
            for i, url in enumerate(urls):
                logger.info(f"尝试K线API格式 {i+1}: {url}")
                
                try:
                    response = requests.get(url, timeout=10)
                    response.encoding = 'utf-8'
                    
                    if response.status_code != 200:
                        logger.warning(f"K线API请求失败: {response.status_code}")
                        continue
                    
                    # 检查响应内容类型
                    response_text = response.text
                    
                    # 尝试解析为JSON
                    try:
                        data = response.json()
                        logger.debug(f"API响应数据结构: {list(data.keys())}")
                        
                        # 尝试不同的数据结构路径
                        if full_symbol in data:
                            # 格式1: {"sh600000": {"day": [...]}}
                            kline_data = data[full_symbol].get('day', [])
                            if kline_data:
                                logger.info(f"成功从格式1获取K线数据")
                                break
                        elif 'data' in data:
                            if isinstance(data['data'], dict) and full_symbol in data['data']:
                                # 格式2: {"data": {"sh600000": {"day": [...]}}}
                                kline_data = data['data'][full_symbol].get('day', [])
                                if kline_data:
                                    logger.info(f"成功从格式2获取K线数据")
                                    break
                            elif isinstance(data['data'], list):
                                # 格式3: {"data": [["sh600000", [...], [...]]]}
                                for item in data['data']:
                                    if isinstance(item, list) and len(item) > 0 and item[0] == full_symbol:
                                        kline_data = item[1:]
                                        if kline_data:
                                            logger.info(f"成功从格式3获取K线数据")
                                            break
                                if kline_data:
                                    break
                    except ValueError:
                        # 不是JSON格式，尝试解析为JavaScript文件格式 (格式5)
                        logger.info(f"尝试解析为JavaScript文件格式")
                        if 'daily_data_' in response_text:
                            # 格式5: JavaScript文件格式 (用户提供)
                            import re
                            match = re.search(r'daily_data_\d+="([\s\S]*?)"', response_text)
                            if match:
                                data_str = match.group(1)
                                # 按行分割数据
                                lines = data_str.strip().split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line:
                                        # 每行数据格式: 日期 开盘 收盘 最高 最低 成交量
                                        parts = line.split()
                                        if len(parts) >= 6:
                                            date = parts[0]
                                            open_price = parts[1]
                                            close_price = parts[2]
                                            high_price = parts[3]
                                            low_price = parts[4]
                                            volume = parts[5]
                                            # 构建K线数据
                                            kline_data.append([date, open_price, close_price, high_price, low_price, volume, 0])
                                if kline_data:
                                    logger.info(f"成功从格式5获取K线数据，共{len(kline_data)}条")
                                    break
                except Exception as e:
                    logger.warning(f"尝试API格式 {i+1} 失败: {str(e)}")
                    continue
            
            # 如果所有格式都失败，返回空DataFrame
            if not kline_data:
                logger.warning(f"所有K线API格式都返回空数据")
                return pd.DataFrame()
            
            # 构建DataFrame
            df = pd.DataFrame(kline_data, columns=['date', 'open', 'close', 'high', 'low', 'volume', 'amount'])
            
            # 转换数据类型
            df['date'] = pd.to_datetime(df['date'])
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            
            # 移除无效数据
            df = df.dropna()
            
            logger.info(f"获取股票{symbol}K线数据成功，返回{len(df)}条记录")
            return df
            
        except Exception as e:
            logger.error(f"获取股票K线数据失败: {str(e)}")
            return pd.DataFrame()