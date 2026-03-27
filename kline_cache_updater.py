import logging
import schedule
import time
from datetime import datetime, timezone, timedelta
from stock_selector import KLineDataFetcher, StockSelector
from data_fetcher import DataFetcher

# 设置时区为北京时间（东八区）
BEIJING_TZ = timezone(timedelta(hours=8))

class BeijingFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=BEIJING_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

# 配置日志
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = BeijingFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

class KLineCacheUpdater:
    def __init__(self):
        self.kline_fetcher = KLineDataFetcher()
        self.data_fetcher = DataFetcher()
    
    def update_all_stocks_cache(self):
        """更新所有股票的K线缓存"""
        try:
            logger.info("开始更新所有股票的K线缓存")
            
            # 获取所有股票列表
            all_stocks = self.data_fetcher.get_all_stocks()
            
            if not all_stocks:
                logger.warning("未获取到股票列表")
                return
            
            stock_codes = [stock['code'] for stock in all_stocks]
            logger.info(f"共 {len(stock_codes)} 只股票需要更新缓存")
            
            # 批量获取K线数据（会自动更新缓存）
            self.kline_fetcher.get_kline_data_batch(stock_codes, days=60)
            
            logger.info("K线缓存更新完成")
            
        except Exception as e:
            logger.error(f"更新K线缓存时发生错误: {str(e)}")
    
    def start(self):
        """启动定时任务"""
        logger.info("K线缓存更新器启动")
        
        # 每天凌晨2点更新一次缓存
        schedule.every().day.at("02:00").do(self.update_all_stocks_cache)
        
        # 启动时立即执行一次
        self.update_all_stocks_cache()
        
        # 运行定时任务
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    updater = KLineCacheUpdater()
    updater.start()