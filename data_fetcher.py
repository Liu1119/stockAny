import akshare as ak
import pandas as pd
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 尝试导入tushare和baostock
try:
    import tushare as ts
except ImportError:
    ts = None
    logger.warning("tushare库未安装，将使用akshare作为默认数据源")

try:
    import baostock as bs
except ImportError:
    bs = None
    logger.warning("baostock库未安装，将使用akshare作为默认数据源")

class DataFetcher:
    def __init__(self, use_mock_data=False, default_source='akshare', tushare_token=None):
        self.use_mock_data = use_mock_data
        self.default_source = default_source
        self.tushare_token = tushare_token
        
        # 初始化tushare
        if ts and tushare_token:
            try:
                ts.set_token(tushare_token)
                self.ts_api = ts.pro_api()
                logger.info("tushare初始化成功")
            except Exception as e:
                logger.error(f"tushare初始化失败: {str(e)}")
                self.ts_api = None
        else:
            self.ts_api = None
        
        # 初始化baostock
        self.bs_init = False
        if bs:
            try:
                lg = bs.login()
                if lg.error_code == '0':
                    self.bs_init = True
                    logger.info("baostock初始化成功")
                else:
                    logger.error(f"baostock初始化失败: {lg.error_msg}")
            except Exception as e:
                logger.error(f"baostock初始化失败: {str(e)}")
    
    def get_mock_stock_data(self, market):
        """
        生成模拟的股票数据
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 模拟的股票数据DataFrame
        """
        try:
            logger.info(f"生成{market}市场的模拟股票数据")
            
            # 生成模拟数据
            data = {
                '代码': [],
                '名称': [],
                '最新价': [],
                '涨跌幅': [],
                '成交量': [],
                '成交额': []
            }
            
            # 根据市场类型生成不同的股票代码
            if market == 'sh':
                # 上证A股（代码以60开头）
                for i in range(1, 11):
                    code = f"60000{i}" if i < 10 else f"6000{i}"
                    data['代码'].append(code)
                    data['名称'].append(f"上证股票{i}")
                    data['最新价'].append(round(10 + i * 0.5, 2))
                    data['涨跌幅'].append(round((i - 5) * 0.5, 2))
                    data['成交量'].append(1000000 + i * 100000)
                    data['成交额'].append(10000000 + i * 1000000)
            
            elif market == 'sz':
                # 深证A股（代码以00开头）
                for i in range(1, 11):
                    code = f"00000{i}" if i < 10 else f"0000{i}"
                    data['名称'].append(f"深证股票{i}")
                    data['代码'].append(code)
                    data['最新价'].append(round(15 + i * 0.6, 2))
                    data['涨跌幅'].append(round((i - 5) * 0.6, 2))
                    data['成交量'].append(1200000 + i * 120000)
                    data['成交额'].append(12000000 + i * 1200000)
            
            elif market == 'cyb':
                # 创业板（代码以300开头）
                for i in range(1, 11):
                    code = f"30000{i}" if i < 10 else f"3000{i}"
                    data['代码'].append(code)
                    data['名称'].append(f"创业板股票{i}")
                    data['最新价'].append(round(20 + i * 0.7, 2))
                    data['涨跌幅'].append(round((i - 5) * 0.7, 2))
                    data['成交量'].append(1500000 + i * 150000)
                    data['成交额'].append(15000000 + i * 1500000)
            
            elif market == 'kcb':
                # 科创板（代码以688开头）
                for i in range(1, 11):
                    code = f"68800{i}" if i < 10 else f"6880{i}"
                    data['代码'].append(code)
                    data['名称'].append(f"科创板股票{i}")
                    data['最新价'].append(round(25 + i * 0.8, 2))
                    data['涨跌幅'].append(round((i - 5) * 0.8, 2))
                    data['成交量'].append(1800000 + i * 180000)
                    data['成交额'].append(18000000 + i * 1800000)
            
            # 创建DataFrame
            stock_list = pd.DataFrame(data)
            logger.info(f"生成{market}市场的模拟股票数据 {len(stock_list)} 只")
            return stock_list
            
        except Exception as e:
            logger.error(f"生成{market}市场模拟数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_data_from_akshare(self, market):
        """
        使用akshare获取指定市场的股票数据
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 股票数据DataFrame
        """
        try:
            logger.info(f"使用akshare获取{market}市场的股票数据")
            
            # 使用stock_zh_a_spot_em()获取所有A股数据
            stock_list = ak.stock_zh_a_spot_em()
            logger.info(f"获取到所有A股 {len(stock_list)} 只股票")
            
            if market == 'sh':
                # 筛选上证A股（代码以60开头）
                stock_list = stock_list[stock_list['代码'].str.startswith('60')]
                logger.info(f"筛选出上证A股 {len(stock_list)} 只股票")
                return stock_list
            
            elif market == 'sz':
                # 筛选深证A股（代码以00开头）
                stock_list = stock_list[stock_list['代码'].str.startswith('00')]
                logger.info(f"筛选出深证A股 {len(stock_list)} 只股票")
                return stock_list
            
            elif market == 'cyb':
                # 筛选创业板股票（代码以300开头）
                stock_list = stock_list[stock_list['代码'].str.startswith('300')]
                logger.info(f"筛选出创业板 {len(stock_list)} 只股票")
                return stock_list
            
            elif market == 'kcb':
                # 筛选科创板股票（代码以688开头）
                stock_list = stock_list[stock_list['代码'].str.startswith('688')]
                logger.info(f"筛选出科创板 {len(stock_list)} 只股票")
                return stock_list
            
            else:
                logger.error(f"不支持的市场类型: {market}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"使用akshare获取{market}市场数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_data_from_tushare(self, market):
        """
        使用tushare获取指定市场的股票数据
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 股票数据DataFrame
        """
        try:
            if not self.ts_api:
                logger.error("tushare API未初始化")
                return pd.DataFrame()
            
            logger.info(f"使用tushare获取{market}市场的股票数据")
            
            # 获取所有A股数据
            stock_list = self.ts_api.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date')
            logger.info(f"获取到所有A股 {len(stock_list)} 只股票")
            
            # 筛选市场
            if market == 'sh':
                # 上证A股（代码以60开头）
                stock_list = stock_list[stock_list['symbol'].str.startswith('60')]
                logger.info(f"筛选出上证A股 {len(stock_list)} 只股票")
            elif market == 'sz':
                # 深证A股（代码以00开头）
                stock_list = stock_list[stock_list['symbol'].str.startswith('00')]
                logger.info(f"筛选出深证A股 {len(stock_list)} 只股票")
            elif market == 'cyb':
                # 创业板股票（代码以300开头）
                stock_list = stock_list[stock_list['symbol'].str.startswith('300')]
                logger.info(f"筛选出创业板 {len(stock_list)} 只股票")
            elif market == 'kcb':
                # 科创板股票（代码以688开头）
                stock_list = stock_list[stock_list['symbol'].str.startswith('688')]
                logger.info(f"筛选出科创板 {len(stock_list)} 只股票")
            else:
                logger.error(f"不支持的市场类型: {market}")
                return pd.DataFrame()
            
            # 重命名列以保持与akshare一致
            stock_list.rename(columns={
                'symbol': '代码',
                'name': '名称'
            }, inplace=True)
            
            # 获取最新价格数据
            try:
                # 获取最新行情数据
                quote = self.ts_api.daily(trade_date=pd.Timestamp.now().strftime('%Y%m%d'))
                if not quote.empty:
                    # 合并价格数据
                    stock_list = stock_list.merge(quote, left_on='ts_code', right_on='ts_code', how='left')
                    # 计算涨跌幅
                    if 'close' in stock_list.columns and 'pre_close' in stock_list.columns:
                        stock_list['涨跌幅'] = ((stock_list['close'] - stock_list['pre_close']) / stock_list['pre_close'] * 100).round(2)
                        stock_list['最新价'] = stock_list['close']
                        stock_list['成交量'] = stock_list['vol']
                        stock_list['成交额'] = stock_list['amount']
            except Exception as e:
                logger.warning(f"获取tushare价格数据失败: {str(e)}")
            
            return stock_list
            
        except Exception as e:
            logger.error(f"使用tushare获取{market}市场数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_data_from_baostock(self, market):
        """
        使用baostock获取指定市场的股票数据
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 股票数据DataFrame
        """
        try:
            if not self.bs_init:
                logger.error("baostock未初始化")
                return pd.DataFrame()
            
            logger.info(f"使用baostock获取{market}市场的股票数据")
            
            # 构建查询条件
            if market == 'sh':
                code_prefix = 'sh.'
            elif market == 'sz':
                code_prefix = 'sz.'
            elif market == 'cyb':
                code_prefix = 'sz.300'
            elif market == 'kcb':
                code_prefix = 'sh.688'
            else:
                logger.error(f"不支持的市场类型: {market}")
                return pd.DataFrame()
            
            # 查询股票列表
            # baostock的query_stock_basic方法不接受code_prefix参数
            # 先获取所有股票，然后根据市场类型筛选
            rs = bs.query_stock_basic()
            
            # 解析结果
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            stock_list = pd.DataFrame(data_list, columns=rs.fields)
            
            # 根据市场类型筛选股票
            if market == 'sh':
                # 上证A股（代码以sh.60开头）
                stock_list = stock_list[stock_list['code'].str.startswith('sh.60')]
            elif market == 'sz':
                # 深证A股（代码以sz.00开头）
                stock_list = stock_list[stock_list['code'].str.startswith('sz.00')]
            elif market == 'cyb':
                # 创业板股票（代码以sz.300开头）
                stock_list = stock_list[stock_list['code'].str.startswith('sz.300')]
            elif market == 'kcb':
                # 科创板股票（代码以sh.688开头）
                stock_list = stock_list[stock_list['code'].str.startswith('sh.688')]
            
            logger.info(f"获取到{market}市场 {len(stock_list)} 只股票")
            
            # 重命名列以保持与akshare一致
            stock_list.rename(columns={
                'code': '代码',
                'code_name': '名称'
            }, inplace=True)
            
            # 处理股票代码格式，去除市场前缀（如sh.或sz.）
            if not stock_list.empty:
                stock_list['代码'] = stock_list['代码'].str.replace('sh.', '').str.replace('sz.', '')
            
            # 获取最新价格数据
            try:
                # baostock的实时行情API是query_stock_quick_rt，需要逐个股票查询
                # 这里简化处理，只获取股票列表，不获取实时价格
                # 实际应用中可以根据需要使用正确的API
                logger.info("baostock实时行情获取功能已禁用，仅返回股票列表")
                
                # 如果需要获取实时行情，可以使用以下方法：
                # 1. 对每个股票使用bs.query_stock_quick_rt(code=stock_code)
                # 2. 注意：频繁调用可能会被限制
                
                # 为了保持数据结构一致，添加默认列
                stock_list['最新价'] = 0.0
                stock_list['涨跌幅'] = 0.0
                stock_list['成交量'] = 0
                stock_list['成交额'] = 0.0
                
            except Exception as e:
                logger.warning(f"获取baostock价格数据失败: {str(e)}")
                # 添加默认列以保持数据结构一致
                if '最新价' not in stock_list.columns:
                    stock_list['最新价'] = 0.0
                if '涨跌幅' not in stock_list.columns:
                    stock_list['涨跌幅'] = 0.0
                if '成交量' not in stock_list.columns:
                    stock_list['成交量'] = 0
                if '成交额' not in stock_list.columns:
                    stock_list['成交额'] = 0.0
            
            return stock_list
            
        except Exception as e:
            logger.error(f"使用baostock获取{market}市场数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_data(self, market):
        """
        获取指定市场的股票数据，支持多数据源自动切换
        :param market: 市场类型，可选值：'sh'（上证）、'sz'（深证）、'cyb'（创业板）、'kcb'（科创板）
        :return: 股票数据DataFrame
        """
        try:
            # 如果使用模拟数据，直接返回模拟数据
            if self.use_mock_data:
                return self.get_mock_stock_data(market)
            
            logger.info(f"开始获取{market}市场的股票数据")
            
            # 尝试从默认数据源获取数据
            if self.default_source == 'tushare' and self.ts_api:
                data = self.get_stock_data_from_tushare(market)
                if not data.empty:
                    return data
                logger.warning(f"tushare获取{market}市场数据失败，尝试使用akshare")
            
            if self.default_source == 'baostock' and self.bs_init:
                data = self.get_stock_data_from_baostock(market)
                if not data.empty:
                    return data
                logger.warning(f"baostock获取{market}市场数据失败，尝试使用akshare")
            
            # 默认使用akshare
            data = self.get_stock_data_from_akshare(market)
            if not data.empty:
                return data
            
            logger.warning(f"所有数据源获取{market}市场数据失败，返回空数据")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取{market}市场数据失败: {str(e)}")
            # 当所有数据源都失败时，返回空数据
            return pd.DataFrame()
    
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
    
    def get_mock_stock_kline(self, symbol, period='1d', start_date=None, end_date=None):
        """
        生成模拟的股票K线数据
        :param symbol: 股票代码
        :param period: 周期，可选值：'1d'（日线）、'1w'（周线）、'1M'（月线）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: 模拟的K线数据DataFrame
        """
        try:
            logger.info(f"生成股票 {symbol} 的模拟K线数据")
            
            # 生成日期索引
            if period == '1d':
                # 生成最近60天的日线数据
                dates = pd.date_range(end=pd.Timestamp.now(), periods=60, freq='B')
            elif period == '1w':
                # 生成最近26周的周线数据
                dates = pd.date_range(end=pd.Timestamp.now(), periods=26, freq='W')
            elif period == '1M':
                # 生成最近12个月的月线数据
                dates = pd.date_range(end=pd.Timestamp.now(), periods=12, freq='M')
            else:
                logger.error(f"不支持的周期: {period}")
                return pd.DataFrame()
            
            # 生成模拟数据
            data = {
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
                'amount': []
            }
            
            # 初始价格
            base_price = 10.0
            if symbol.startswith('300'):
                base_price = 20.0
            elif symbol.startswith('688'):
                base_price = 30.0
            
            # 生成数据
            for i, date in enumerate(dates):
                # 价格波动
                change = (i - 30) * 0.1
                price = base_price + change
                
                # 生成OHLC数据
                open_price = round(price * (1 + (i % 3 - 1) * 0.01), 2)
                high_price = round(max(open_price, price * 1.02), 2)
                low_price = round(min(open_price, price * 0.98), 2)
                close_price = round(price, 2)
                
                # 生成成交量和成交额
                volume = 1000000 + i * 10000
                amount = volume * close_price
                
                # 添加数据
                data['open'].append(open_price)
                data['high'].append(high_price)
                data['low'].append(low_price)
                data['close'].append(close_price)
                data['volume'].append(volume)
                data['amount'].append(amount)
            
            # 创建DataFrame
            kline_data = pd.DataFrame(data, index=dates)
            
            # 如果指定了日期范围，进行筛选
            if start_date:
                kline_data = kline_data[kline_data.index >= start_date]
            if end_date:
                kline_data = kline_data[kline_data.index <= end_date]
            
            logger.info(f"生成股票 {symbol} 的模拟K线数据 {len(kline_data)} 条")
            return kline_data
            
        except Exception as e:
            logger.error(f"生成股票 {symbol} 模拟K线数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_kline_from_akshare(self, symbol, period='1d', start_date=None, end_date=None):
        """
        使用akshare获取单个股票的K线数据
        :param symbol: 股票代码
        :param period: 周期，可选值：'1d'（日线）、'1w'（周线）、'1M'（月线）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: K线数据DataFrame
        """
        try:
            logger.info(f"使用akshare获取股票 {symbol} 的K线数据")
            
            # 使用akshare获取K线数据
            if period == '1d':
                kline_data = ak.stock_zh_a_daily(symbol=symbol, adjust='qfq')
            elif period == '1w':
                kline_data = ak.stock_zh_a_weekly(symbol=symbol, adjust='qfq')
            elif period == '1M':
                kline_data = ak.stock_zh_a_monthly(symbol=symbol, adjust='qfq')
            else:
                logger.error(f"不支持的周期: {period}")
                return pd.DataFrame()
            
            # 如果指定了日期范围，进行筛选
            if start_date:
                kline_data = kline_data[kline_data.index >= start_date]
            if end_date:
                kline_data = kline_data[kline_data.index <= end_date]
            
            logger.info(f"获取到股票 {symbol} 的K线数据 {len(kline_data)} 条")
            return kline_data
            
        except Exception as e:
            logger.error(f"使用akshare获取股票 {symbol} K线数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_kline_from_tushare(self, symbol, period='1d', start_date=None, end_date=None):
        """
        使用tushare获取单个股票的K线数据
        :param symbol: 股票代码
        :param period: 周期，可选值：'1d'（日线）、'1w'（周线）、'1M'（月线）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: K线数据DataFrame
        """
        try:
            if not self.ts_api:
                logger.error("tushare API未初始化")
                return pd.DataFrame()
            
            logger.info(f"使用tushare获取股票 {symbol} 的K线数据")
            
            # 构建tushare代码格式
            if symbol.startswith('60'):
                ts_code = f"{symbol}.SH"
            elif symbol.startswith('00'):
                ts_code = f"{symbol}.SZ"
            elif symbol.startswith('300'):
                ts_code = f"{symbol}.SZ"
            elif symbol.startswith('688'):
                ts_code = f"{symbol}.SH"
            else:
                ts_code = symbol
            
            # 构建日期范围
            if not start_date:
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=60)).strftime('%Y%m%d')
            else:
                start_date = pd.Timestamp(start_date).strftime('%Y%m%d')
            
            if not end_date:
                end_date = pd.Timestamp.now().strftime('%Y%m%d')
            else:
                end_date = pd.Timestamp(end_date).strftime('%Y%m%d')
            
            # 获取K线数据
            if period == '1d':
                kline_data = self.ts_api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            elif period == '1w':
                kline_data = self.ts_api.weekly(ts_code=ts_code, start_date=start_date, end_date=end_date)
            elif period == '1M':
                kline_data = self.ts_api.monthly(ts_code=ts_code, start_date=start_date, end_date=end_date)
            else:
                logger.error(f"不支持的周期: {period}")
                return pd.DataFrame()
            
            if not kline_data.empty:
                # 整理数据格式
                kline_data['trade_date'] = pd.to_datetime(kline_data['trade_date'])
                kline_data.set_index('trade_date', inplace=True)
                kline_data.sort_index(inplace=True)
                
                # 重命名列以保持一致
                kline_data.rename(columns={
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'vol': 'volume',
                    'amount': 'amount'
                }, inplace=True)
                
                logger.info(f"获取到股票 {symbol} 的K线数据 {len(kline_data)} 条")
            
            return kline_data
            
        except Exception as e:
            logger.error(f"使用tushare获取股票 {symbol} K线数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_kline_from_baostock(self, symbol, period='1d', start_date=None, end_date=None):
        """
        使用baostock获取单个股票的K线数据
        :param symbol: 股票代码
        :param period: 周期，可选值：'1d'（日线）、'1w'（周线）、'1M'（月线）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: K线数据DataFrame
        """
        try:
            if not self.bs_init:
                logger.error("baostock未初始化")
                return pd.DataFrame()
            
            logger.info(f"使用baostock获取股票 {symbol} 的K线数据")
            
            # 构建baostock代码格式
            if symbol.startswith('60') or symbol.startswith('688'):
                bs_code = f"sh.{symbol}"
            else:
                bs_code = f"sz.{symbol}"
            
            # 构建日期范围
            if not start_date:
                start_date = (pd.Timestamp.now() - pd.Timedelta(days=60)).strftime('%Y-%m-%d')
            else:
                start_date = pd.Timestamp(start_date).strftime('%Y-%m-%d')
            
            if not end_date:
                end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            else:
                end_date = pd.Timestamp(end_date).strftime('%Y-%m-%d')
            
            # 构建周期参数
            if period == '1d':
                frequency = 'd'
            elif period == '1w':
                frequency = 'w'
            elif period == '1M':
                frequency = 'm'
            else:
                logger.error(f"不支持的周期: {period}")
                return pd.DataFrame()
            
            # 获取K线数据
            rs = bs.query_history_k_data_plus(
                code=bs_code,
                fields='date,open,high,low,close,volume,amount',
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag='3'  # 前复权
            )
            
            # 解析结果
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if data_list:
                kline_data = pd.DataFrame(data_list, columns=rs.fields)
                # 转换数据类型
                try:
                    # 转换日期
                    kline_data['date'] = pd.to_datetime(kline_data['date'], errors='coerce')
                    
                    # 转换数值列，处理空字符串和无效值
                    numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
                    for col in numeric_columns:
                        if col in kline_data.columns:
                            # 先替换空字符串为NaN
                            kline_data[col] = kline_data[col].replace('', pd.NA)
                            # 转换为数值类型
                            kline_data[col] = pd.to_numeric(kline_data[col], errors='coerce')
                    
                    # 移除包含NaN值的行
                    kline_data = kline_data.dropna(subset=['date', 'open', 'high', 'low', 'close'])
                    
                    if not kline_data.empty:
                        kline_data.set_index('date', inplace=True)
                        kline_data.sort_index(inplace=True)
                        logger.info(f"获取到股票 {symbol} 的K线数据 {len(kline_data)} 条")
                    else:
                        logger.warning(f"股票 {symbol} 的K线数据为空或包含无效值")
                        kline_data = pd.DataFrame()
                except Exception as e:
                    logger.error(f"处理股票 {symbol} K线数据失败: {str(e)}")
                    kline_data = pd.DataFrame()
            else:
                kline_data = pd.DataFrame()
            
            return kline_data
            
        except Exception as e:
            logger.error(f"使用baostock获取股票 {symbol} K线数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_kline(self, symbol, period='1d', start_date=None, end_date=None):
        """
        获取单个股票的K线数据，支持多数据源自动切换
        :param symbol: 股票代码
        :param period: 周期，可选值：'1d'（日线）、'1w'（周线）、'1M'（月线）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: K线数据DataFrame
        """
        try:
            # 如果使用模拟数据，直接返回模拟数据
            if self.use_mock_data:
                return self.get_mock_stock_kline(symbol, period, start_date, end_date)
            
            logger.info(f"开始获取股票 {symbol} 的K线数据")
            
            # 尝试从默认数据源获取数据
            if self.default_source == 'tushare' and self.ts_api:
                data = self.get_stock_kline_from_tushare(symbol, period, start_date, end_date)
                if not data.empty:
                    return data
                logger.warning(f"tushare获取{symbol}K线数据失败，尝试使用akshare")
            
            if self.default_source == 'baostock' and self.bs_init:
                data = self.get_stock_kline_from_baostock(symbol, period, start_date, end_date)
                if not data.empty:
                    return data
                logger.warning(f"baostock获取{symbol}K线数据失败，尝试使用akshare")
            
            # 默认使用akshare
            data = self.get_stock_kline_from_akshare(symbol, period, start_date, end_date)
            if not data.empty:
                return data
            
            logger.warning(f"所有数据源获取{symbol}K线数据失败，返回空数据")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} K线数据失败: {str(e)}")
            # 当所有数据源都失败时，返回空数据
            return pd.DataFrame()