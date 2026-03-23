import schedule
import time
import logging
from datetime import datetime
from stock_selector import ScheduledStockSelector
from data_fetcher import DataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stock_selector_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/d6930274-cf9f-48d9-80d9-b1f735c43fc2"

def get_all_stock_codes():
    logger.info("开始获取所有股票代码")
    fetcher = DataFetcher()
    
    all_codes = []
    markets = ['sh', 'sz', 'cyb']
    
    for market in markets:
        logger.info(f"获取 {market} 市场股票数据")
        data = fetcher.get_stock_data(market)
        
        if not data.empty:
            codes = data['代码'].tolist()
            all_codes.extend(codes)
            logger.info(f"{market} 市场获取到 {len(codes)} 只股票")
        else:
            logger.warning(f"{market} 市场未获取到数据")
    
    logger.info(f"总共获取到 {len(all_codes)} 只股票代码")
    return all_codes

def job():
    logger.info("=" * 60)
    logger.info(f"开始执行定时选股任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        stock_codes = get_all_stock_codes()
        
        if not stock_codes:
            logger.error("未获取到股票代码，任务终止")
            return
        
        scheduler = ScheduledStockSelector(FEISHU_WEBHOOK)
        result = scheduler.run_selection(stock_codes)
        
        logger.info(f"选股任务完成，共筛选出 {len(result)} 只股票")
        
    except Exception as e:
        logger.error(f"定时任务执行失败: {str(e)}", exc_info=True)

def run_scheduler():
    logger.info("启动股票筛选定时任务")
    logger.info("执行时间: 每天下午 14:30")
    
    schedule.every().day.at("14:30").do(job)
    
    logger.info("定时任务已启动，等待执行...")
    logger.info("按 Ctrl+C 停止程序")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        logger.info("测试模式：立即执行一次选股任务")
        job()
    else:
        run_scheduler()
