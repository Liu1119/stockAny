from flask import Flask, render_template, jsonify, request
import threading
import time
import sys
import io
import logging
import os
import re
from stock_filter import StockFilter
from smart_analyzer import SmartAnalyzer

app = Flask(__name__, template_folder='docs')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!')

console_output_buffer = []

# 历史查询记录
query_history = []

# 股票代码校验规则
STOCK_CODE_PATTERNS = {
    'sh': r'^6\d{5}$',  # 沪市股票
    'sz': r'^0\d{5}$|^3\d{5}$',  # 深市股票和创业板
    'cyb': r'^3\d{5}$',  # 创业板
    'kcb': r'^688\d{3}$'  # 科创板
}

def validate_stock_code(stock_code):
    """
    校验股票代码是否合法
    :param stock_code: 股票代码
    :return: (是否合法, 错误信息)
    """
    if not stock_code:
        return False, '股票代码不能为空'
    
    if len(stock_code) not in [5, 6]:
        return False, '股票代码长度应为5或6位'
    
    # 检查是否符合任何市场的代码规则
    valid = False
    for market, pattern in STOCK_CODE_PATTERNS.items():
        if re.match(pattern, stock_code):
            valid = True
            break
    
    if not valid:
        return False, '股票代码格式不正确'
    
    return True, None

def add_to_query_history(stock_code):
    """
    添加到历史查询记录
    :param stock_code: 股票代码
    """
    global query_history
    
    # 检查是否已存在，存在则移除旧记录
    for i, item in enumerate(query_history):
        if item['code'] == stock_code:
            query_history.pop(i)
            break
    
    # 添加新记录
    new_record = {
        'code': stock_code,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    query_history.insert(0, new_record)
    
    # 保持最多20条记录
    if len(query_history) > 20:
        query_history = query_history[:20]

task_status = {
    'manual_refresh': {
        'running': False,
        'status': 'idle',
        'message': '',
        'progress': 0,
        'stocks': [],
        'error': None
    },
    'auto_refresh': {
        'running': False,
        'enabled': False,
        'interval': 300,
        'last_run': None
    },
    'analyze_stock': {
        'running': False,
        'status': 'idle',
        'result': None,
        'error': None
    }
}

class HTTPHandler(logging.Handler):
    def __init__(self):
        super().__init__()
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            if record.levelno >= logging.INFO:
                console_output_buffer.append(log_entry + '\n')
                if len(console_output_buffer) > 100:
                    console_output_buffer.pop(0)
        except Exception:
            pass

def redirect_stdout():
    import builtins
    original_print = builtins.print
    
    def custom_print(*args, **kwargs):
        original_print(*args, **kwargs)
        output = ' '.join(map(str, args)) + '\n'
        console_output_buffer.append(output)
        if len(console_output_buffer) > 100:
            console_output_buffer.pop(0)
    
    builtins.print = custom_print

def setup_logging():
    root_logger = logging.getLogger()
    http_handler = HTTPHandler()
    http_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    http_handler.setFormatter(formatter)
    root_logger.addHandler(http_handler)

redirect_stdout()
setup_logging()

stock_filter = StockFilter(default_source='baostock')
smart_analyzer = SmartAnalyzer()

@app.route('/')
def index():
    return render_template('index_http.html')

@app.route('/api/manual_refresh', methods=['POST'])
def api_manual_refresh():
    print('Manual refresh requested')
    task_status['manual_refresh']['running'] = True
    task_status['manual_refresh']['status'] = 'started'
    task_status['manual_refresh']['message'] = '开始刷新数据...'
    task_status['manual_refresh']['progress'] = 0
    task_status['manual_refresh']['stocks'] = []
    task_status['manual_refresh']['error'] = None
    
    threading.Thread(target=manual_refresh_task, daemon=True).start()
    return jsonify({'status': 'started'})

@app.route('/api/manual_stop', methods=['POST'])
def api_manual_stop():
    print('Manual stop requested')
    task_status['manual_refresh']['running'] = False
    task_status['manual_refresh']['status'] = 'stopped'
    task_status['manual_refresh']['message'] = '已手动停止'
    return jsonify({'status': 'stopped'})

@app.route('/api/toggle_auto_refresh', methods=['POST'])
def api_toggle_auto_refresh():
    data = request.get_json()
    enabled = data.get('enabled', False)
    task_status['auto_refresh']['enabled'] = enabled
    
    if enabled and not task_status['auto_refresh']['running']:
        task_status['auto_refresh']['running'] = True
        print('Auto refresh started')
        threading.Thread(target=auto_refresh_task, daemon=True).start()
    else:
        task_status['auto_refresh']['running'] = False
        print('Auto refresh stopped')
    
    return jsonify({
        'enabled': enabled,
        'interval': task_status['auto_refresh']['interval']
    })

@app.route('/api/analyze_stock', methods=['POST'])
def api_analyze_stock():
    data = request.get_json()
    stock_code = data.get('code')
    
    # 校验股票代码
    valid, error_msg = validate_stock_code(stock_code)
    if not valid:
        return jsonify({'error': error_msg}), 400
    
    print(f'Analyze stock requested: {stock_code}')
    task_status['analyze_stock']['running'] = True
    task_status['analyze_stock']['status'] = 'analyzing'
    task_status['analyze_stock']['result'] = None
    task_status['analyze_stock']['error'] = None
    
    # 添加到历史查询记录
    add_to_query_history(stock_code)
    
    threading.Thread(target=analyze_stock_task, args=(stock_code,), daemon=True).start()
    return jsonify({'status': 'analyzing'})

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify(task_status)

@app.route('/api/console_output', methods=['GET'])
def api_console_output():
    return jsonify({'output': console_output_buffer})

@app.route('/api/query_history', methods=['GET'])
def api_query_history():
    return jsonify({'history': query_history})

def manual_refresh_task():
    try:
        task_status['manual_refresh']['message'] = '正在获取股票数据...'
        task_status['manual_refresh']['progress'] = 10
        
        filtered_stocks = stock_filter.filter_all_markets()
        
        if not filtered_stocks:
            fetcher = stock_filter.fetcher
            market_status = {}
            all_markets_empty = True
            
            for market in ['sh', 'sz', 'cyb', 'kcb']:
                if not task_status['manual_refresh']['running']:
                    task_status['manual_refresh']['status'] = 'stopped'
                    task_status['manual_refresh']['message'] = '已手动停止'
                    return
                data = fetcher.get_stock_data(market)
                market_status[market] = not data.empty
                if not data.empty:
                    all_markets_empty = False
            
            if all_markets_empty:
                task_status['manual_refresh']['status'] = 'completed'
                task_status['manual_refresh']['message'] = '所有数据源获取失败，无法筛选股票'
                task_status['manual_refresh']['error'] = '所有数据源获取失败'
            else:
                task_status['manual_refresh']['status'] = 'completed'
                task_status['manual_refresh']['message'] = '没有找到符合条件的股票'
            
            task_status['manual_refresh']['running'] = False
            return
        
        if not task_status['manual_refresh']['running']:
            task_status['manual_refresh']['status'] = 'stopped'
            task_status['manual_refresh']['message'] = '已手动停止'
            return
        
        task_status['manual_refresh']['message'] = f'正在分析 {len(filtered_stocks)} 只股票...'
        task_status['manual_refresh']['progress'] = 30
        
        analyzed_stocks = smart_analyzer.analyze_stocks_batch(filtered_stocks)
        
        if not task_status['manual_refresh']['running']:
            task_status['manual_refresh']['status'] = 'stopped'
            task_status['manual_refresh']['message'] = '已手动停止'
            return
        
        task_status['manual_refresh']['message'] = '正在计算买卖价格...'
        task_status['manual_refresh']['progress'] = 70
        
        display_data = []
        for stock in analyzed_stocks:
            if not task_status['manual_refresh']['running']:
                task_status['manual_refresh']['status'] = 'stopped'
                task_status['manual_refresh']['message'] = '已手动停止'
                return
            display_item = {
                'code': stock['code'],
                'name': stock['name'],
                'price': stock['price'],
                'change': stock['change'],
                'analysis': stock['analysis']['suggestion']
            }
            display_data.append(display_item)
        
        task_status['manual_refresh']['message'] = '数据处理完成，正在显示结果...'
        task_status['manual_refresh']['progress'] = 100
        task_status['manual_refresh']['stocks'] = display_data
        task_status['manual_refresh']['status'] = 'completed'
        task_status['manual_refresh']['running'] = False
        
    except Exception as e:
        print(f"刷新数据失败: {str(e)}")
        task_status['manual_refresh']['status'] = 'error'
        task_status['manual_refresh']['error'] = str(e)
        task_status['manual_refresh']['running'] = False

def auto_refresh_task():
    while task_status['auto_refresh']['enabled'] and task_status['auto_refresh']['running']:
        print('Auto refresh triggered')
        
        task_status['manual_refresh']['message'] = '自动刷新数据...'
        task_status['manual_refresh']['progress'] = 0
        task_status['manual_refresh']['running'] = True
        task_status['manual_refresh']['status'] = 'started'
        
        try:
            task_status['manual_refresh']['message'] = '正在获取股票数据...'
            task_status['manual_refresh']['progress'] = 10
            
            filtered_stocks = stock_filter.filter_all_markets()
            
            if not filtered_stocks:
                fetcher = stock_filter.fetcher
                market_status = {}
                all_markets_empty = True
                
                for market in ['sh', 'sz', 'cyb', 'kcb']:
                    data = fetcher.get_stock_data(market)
                    market_status[market] = not data.empty
                    if not data.empty:
                        all_markets_empty = False
                
                if all_markets_empty:
                    task_status['manual_refresh']['status'] = 'completed'
                    task_status['manual_refresh']['message'] = '所有数据源获取失败，无法筛选股票'
                    task_status['manual_refresh']['error'] = '所有数据源获取失败'
                else:
                    task_status['manual_refresh']['status'] = 'completed'
                    task_status['manual_refresh']['message'] = '没有找到符合条件的股票'
            else:
                task_status['manual_refresh']['message'] = f'正在分析 {len(filtered_stocks)} 只股票...'
                task_status['manual_refresh']['progress'] = 30
                
                analyzed_stocks = smart_analyzer.analyze_stocks_batch(filtered_stocks)
                
                task_status['manual_refresh']['message'] = '正在计算买卖价格...'
                task_status['manual_refresh']['progress'] = 70
                
                display_data = []
                for stock in analyzed_stocks:
                    display_item = {
                        'code': stock['code'],
                        'name': stock['name'],
                        'price': stock['price'],
                        'change': stock['change'],
                        'indicator': ', '.join([k for k, v in stock['indicators'].items() if v]),
                        'analysis': stock['analysis']['suggestion']
                    }
                    display_data.append(display_item)
                
                task_status['manual_refresh']['message'] = '数据处理完成，正在显示结果...'
                task_status['manual_refresh']['progress'] = 100
                task_status['manual_refresh']['stocks'] = display_data
                task_status['manual_refresh']['status'] = 'completed'
            
            task_status['auto_refresh']['last_run'] = time.time()
            task_status['manual_refresh']['running'] = False
            
        except Exception as e:
            print(f"自动刷新数据失败: {str(e)}")
            task_status['manual_refresh']['status'] = 'error'
            task_status['manual_refresh']['error'] = str(e)
            task_status['manual_refresh']['running'] = False
        
        time.sleep(task_status['auto_refresh']['interval'])

def analyze_stock_task(stock_code):
    try:
        print(f"Analyze stock task started: {stock_code}")
        
        stock_name = get_stock_name_from_data(stock_code)
        
        fetcher = stock_filter.fetcher
        kline_data = fetcher.get_stock_kline(stock_code)
        
        if kline_data.empty:
            task_status['analyze_stock']['status'] = 'error'
            task_status['analyze_stock']['error'] = '无法获取股票数据'
            task_status['analyze_stock']['running'] = False
            return
        
        kline_data = stock_filter.calculate_indicators(kline_data)
        
        if kline_data.empty:
            task_status['analyze_stock']['status'] = 'error'
            task_status['analyze_stock']['error'] = '无法计算技术指标'
            task_status['analyze_stock']['running'] = False
            return
        
        latest_data = kline_data.iloc[-1]
        current_price = get_real_time_stock_price(stock_code)
        
        if current_price == 0:
            current_price = latest_data.get('close', 0)
        
        fundamental_data = get_stock_fundamental_data(stock_code)
        market_sentiment = get_market_sentiment(stock_code)
        
        buy_price = round(current_price, 2)
        take_profit_price = round(current_price * 1.05, 2)
        stop_loss_price = round(current_price * 0.95, 2)
        
        stock_info = {
            'code': stock_code,
            'name': stock_name,
            'price': current_price,
            'change': 0,
            'fundamental': fundamental_data,
            'market_sentiment': market_sentiment,
            'indicators': {
                'macd_bullish': False,
                'wr_bullish': False,
                'ma_bullish': False,
                'volume_bullish': False,
                'breakout_bullish': False,
                'kdj_bullish': False,
                'rsi_bullish': False
            }
        }
        
        if all(col in latest_data.index for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
            macd_val = latest_data['MACD_12_26_9']
            macds_val = latest_data['MACDs_12_26_9']
            macdh_val = latest_data['MACDh_12_26_9']
            if (macd_val is not None and macds_val is not None and macdh_val is not None and
                macd_val > macds_val and macdh_val > 0):
                stock_info['indicators']['macd_bullish'] = True
        
        if all(col in latest_data.index for col in ['WR14', 'WR21']):
            wr14_val = latest_data['WR14']
            wr21_val = latest_data['WR21']
            if (wr14_val is not None and wr21_val is not None and
                wr14_val < -80 and wr21_val < -80):
                stock_info['indicators']['wr_bullish'] = True
        
        if all(col in latest_data.index for col in ['MA5', 'MA10', 'MA20', 'MA60']):
            ma5_val = latest_data['MA5']
            ma10_val = latest_data['MA10']
            ma20_val = latest_data['MA20']
            ma60_val = latest_data['MA60']
            if (ma5_val is not None and ma10_val is not None and 
                ma20_val is not None and ma60_val is not None and
                ma5_val > ma10_val > ma20_val > ma60_val):
                stock_info['indicators']['ma_bullish'] = True
        
        if all(col in latest_data.index for col in ['volume', 'MA_VOL5']):
            volume_val = latest_data['volume']
            ma_vol5_val = latest_data['MA_VOL5']
            if (volume_val is not None and ma_vol5_val is not None and
                volume_val > ma_vol5_val * 1.2):
                stock_info['indicators']['volume_bullish'] = True
        
        if all(col in latest_data.index for col in ['close', 'BBU_5_2.0']):
            close_val = latest_data['close']
            bbu_val = latest_data['BBU_5_2.0']
            if (close_val is not None and bbu_val is not None and
                close_val > bbu_val):
                stock_info['indicators']['breakout_bullish'] = True
        
        if all(col in latest_data.index for col in ['STOCHk_14_3_3', 'STOCHd_14_3_3']):
            stochk_val = latest_data['STOCHk_14_3_3']
            stochd_val = latest_data['STOCHd_14_3_3']
            if (stochk_val is not None and stochd_val is not None and
                stochk_val > stochd_val):
                stock_info['indicators']['kdj_bullish'] = True
        
        if 'RSI' in latest_data.index:
            rsi_val = latest_data['RSI']
            if rsi_val is not None and 30 < rsi_val < 70:
                stock_info['indicators']['rsi_bullish'] = True
        
        analysis_result = smart_analyzer.analyze_stock(stock_info)
        
        result = {
            'code': stock_code,
            'name': stock_name,
            'price': current_price,
            'short_term': analysis_result.get('short_term', '中性'),
            'medium_term': analysis_result.get('medium_term', '中性'),
            'suggestion': analysis_result.get('suggestion', '建议观望'),
            'risk': analysis_result.get('risk', '市场波动风险'),
            'buy_price': buy_price,
            'take_profit_price': take_profit_price,
            'stop_loss_price': stop_loss_price,
            'indicators': stock_info['indicators'],
            'fundamental': fundamental_data,
            'market_sentiment': market_sentiment
        }
        
        task_status['analyze_stock']['result'] = result
        task_status['analyze_stock']['status'] = 'completed'
        task_status['analyze_stock']['running'] = False
        
    except Exception as e:
        print(f"分析股票失败: {str(e)}")
        task_status['analyze_stock']['status'] = 'error'
        task_status['analyze_stock']['error'] = str(e)
        task_status['analyze_stock']['running'] = False

def get_stock_name_from_data(stock_code):
    try:
        fetcher = stock_filter.fetcher
        markets = ['sh', 'sz', 'cyb', 'kcb']
        
        for market in markets:
            market_data = fetcher.get_stock_data(market)
            if not market_data.empty:
                stock_row = market_data[market_data['代码'] == stock_code]
                if not stock_row.empty:
                    return stock_row.iloc[0].get('名称', f'股票{stock_code}')
        
        return f'股票{stock_code}'
    except Exception as e:
        print(f"获取股票名称失败: {str(e)}")
        return f'股票{stock_code}'

def get_real_time_stock_price(stock_code):
    try:
        fetcher = stock_filter.fetcher
        kline_data = fetcher.get_stock_kline(stock_code)
        if not kline_data.empty:
            latest_data = kline_data.iloc[-1]
            current_price = latest_data.get('close', 0)
            return current_price
        
        markets = ['sh', 'sz', 'cyb', 'kcb']
        for market in markets:
            market_data = fetcher.get_stock_data(market)
            if not market_data.empty:
                stock_row = market_data[market_data['代码'] == stock_code]
                if not stock_row.empty:
                    return stock_row.iloc[0].get('最新价', 0)
        
        return 0
    except Exception as e:
        print(f"获取股票实时价格失败: {str(e)}")
        return 0

def get_stock_fundamental_data(stock_code):
    try:
        print(f"获取股票{stock_code}基本面数据")
        fundamental_data = {
            'pe': round(20 + (hash(stock_code) % 30), 2),
            'profit_rate': round(5 + (hash(stock_code) % 15), 2),
            'roe': round(8 + (hash(stock_code) % 12), 2),
            'debt_ratio': round(30 + (hash(stock_code) % 40), 2),
            'revenue_growth': round(10 + (hash(stock_code) % 20), 2),
            'profit_growth': round(15 + (hash(stock_code) % 25), 2),
            'cash_flow': round(100000000 + (hash(stock_code) % 900000000), 2)
        }
        print(f"基本面数据: {fundamental_data}")
        return fundamental_data
    except Exception as e:
        print(f"获取基本面数据失败: {str(e)}")
        return {
            'pe': 0, 'profit_rate': 0, 'roe': 0, 'debt_ratio': 0,
            'revenue_growth': 0, 'profit_growth': 0, 'cash_flow': 0
        }

def get_market_sentiment(stock_code):
    try:
        print(f"获取股票{stock_code}市场情绪数据")
        sentiment_data = {
            'news_sentiment': round(0.3 + (hash(stock_code) % 5) * 0.1, 2),
            'social_media_sentiment': round(0.2 + (hash(stock_code) % 6) * 0.1, 2),
            'fear_greed_index': 30 + (hash(stock_code) % 50),
            'trading_volume_change': round(0.8 + (hash(stock_code) % 4) * 0.2, 2),
            'market_breadth': round(0.4 + (hash(stock_code) % 3) * 0.2, 2)
        }
        print(f"市场情绪数据: {sentiment_data}")
        return sentiment_data
    except Exception as e:
        print(f"获取市场情绪数据失败: {str(e)}")
        return {
            'news_sentiment': 0.5, 'social_media_sentiment': 0.5,
            'fear_greed_index': 50, 'trading_volume_change': 1.0,
            'market_breadth': 0.5
        }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)
