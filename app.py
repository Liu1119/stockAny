from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import time
import sys
import io
import logging
import os
from stock_filter import StockFilter
from smart_analyzer import SmartAnalyzer

app = Flask(__name__, template_folder='docs')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

console_output_buffer = []

class SocketIOHandler(logging.Handler):
    def __init__(self, socketio):
        super().__init__()
        self.socketio = socketio
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            if record.levelno >= logging.INFO:
                self.socketio.emit('console_output', {'data': log_entry + '\n'})
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
        try:
            socketio.emit('console_output', {'data': output})
        except Exception as e:
            original_print(f"发送控制台输出失败: {e}")
    
    builtins.print = custom_print

def setup_logging():
    root_logger = logging.getLogger()
    socketio_handler = SocketIOHandler(socketio)
    socketio_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    socketio_handler.setFormatter(formatter)
    root_logger.addHandler(socketio_handler)

redirect_stdout()
setup_logging()

auto_refresh_running = False
manual_refresh_running = False
refresh_interval = 300

stock_filter = StockFilter(default_source='baostock')
smart_analyzer = SmartAnalyzer()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    socketio.emit('message', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('manual_refresh')
def handle_manual_refresh():
    global manual_refresh_running
    print('Manual refresh requested')
    manual_refresh_running = True
    socketio.emit('refresh_started', {'data': '开始刷新数据...'})
    
    try:
        socketio.emit('processing_progress', {'data': '正在获取股票数据...'})
        filtered_stocks = stock_filter.filter_all_markets()
        
        if not filtered_stocks:
            fetcher = stock_filter.fetcher
            market_status = {}
            all_markets_empty = True
            
            for market in ['sh', 'sz', 'cyb', 'kcb']:
                if not manual_refresh_running:
                    socketio.emit('manual_stop_completed', {'data': '已手动停止'})
                    return
                data = fetcher.get_stock_data(market)
                market_status[market] = not data.empty
                if not data.empty:
                    all_markets_empty = False
            
            if all_markets_empty:
                socketio.emit('refresh_completed', {'data': '刷新完成', 'stocks': [], 'message': '所有数据源获取失败，无法筛选股票'})
            else:
                socketio.emit('refresh_completed', {'data': '刷新完成', 'stocks': [], 'message': '没有找到符合条件的股票'})
            manual_refresh_running = False
            return
        
        if not manual_refresh_running:
            socketio.emit('manual_stop_completed', {'data': '已手动停止'})
            return
        
        socketio.emit('processing_progress', {'data': f'正在分析 {len(filtered_stocks)} 只股票...'})
        # 将筛选后的股票放入deepseek中进行再次分析
        analyzed_stocks = smart_analyzer.analyze_stocks_batch(filtered_stocks)
        
        if not manual_refresh_running:
            socketio.emit('manual_stop_completed', {'data': '已手动停止'})
            return
        
        socketio.emit('processing_progress', {'data': '正在计算买卖价格...'})
        display_data = []
        for stock in analyzed_stocks:
            if not manual_refresh_running:
                socketio.emit('manual_stop_completed', {'data': '已手动停止'})
                return
            display_item = {
                'code': stock['code'],
                'name': stock['name'],
                'price': stock['price'],
                'change': stock['change'],
                'analysis': stock['analysis']['suggestion']
            }
            display_data.append(display_item)
        
        socketio.emit('processing_progress', {'data': '数据处理完成，正在显示结果...'})
        socketio.emit('refresh_completed', {'data': '刷新完成', 'stocks': display_data})
        manual_refresh_running = False
        
    except Exception as e:
        print(f"刷新数据失败: {str(e)}")
        socketio.emit('refresh_completed', {'data': '刷新失败', 'error': str(e)})
        manual_refresh_running = False

@socketio.on('manual_stop')
def handle_manual_stop():
    global manual_refresh_running
    print('Manual stop requested')
    manual_refresh_running = False
    socketio.emit('manual_stop_completed', {'data': '已手动停止'})

@socketio.on('toggle_auto_refresh')
def handle_toggle_auto_refresh(data):
    global auto_refresh_running
    auto_refresh_running = data['enabled']
    if auto_refresh_running:
        print('Auto refresh started')
        socketio.emit('auto_refresh_status', {'enabled': True, 'interval': refresh_interval})
        threading.Thread(target=auto_refresh_task, daemon=True).start()
    else:
        print('Auto refresh stopped')
        socketio.emit('auto_refresh_status', {'enabled': False})

def auto_refresh_task():
    global auto_refresh_running
    while auto_refresh_running:
        print('Auto refresh triggered')
        socketio.emit('refresh_started', {'data': '自动刷新数据...'})
        
        try:
            socketio.emit('processing_progress', {'data': '正在获取股票数据...'})
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
                    socketio.emit('refresh_completed', {'data': '自动刷新完成', 'stocks': [], 'message': '所有数据源获取失败，无法筛选股票'})
                else:
                    socketio.emit('refresh_completed', {'data': '自动刷新完成', 'stocks': [], 'message': '没有找到符合条件的股票'})
            else:
                socketio.emit('processing_progress', {'data': f'正在分析 {len(filtered_stocks)} 只股票...'})
                analyzed_stocks = smart_analyzer.analyze_stocks_batch(filtered_stocks)
                
                socketio.emit('processing_progress', {'data': '正在计算买卖价格...'})
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
                
                socketio.emit('processing_progress', {'data': '数据处理完成，正在显示结果...'})
                socketio.emit('refresh_completed', {'data': '自动刷新完成', 'stocks': display_data})
            
        except Exception as e:
            print(f"自动刷新数据失败: {str(e)}")
            socketio.emit('refresh_completed', {'data': '自动刷新失败', 'error': str(e)})
        
        time.sleep(refresh_interval)

def get_stock_name_from_data(stock_code):
    """
    从数据源获取股票名称
    :param stock_code: 股票代码
    :return: 股票名称
    """
    try:
        fetcher = stock_filter.fetcher
        markets = ['sh', 'sz', 'cyb', 'kcb']
        
        for market in markets:
            market_data = fetcher.get_stock_data(market)
            if not market_data.empty:
                # 查找股票代码
                stock_row = market_data[market_data['代码'] == stock_code]
                if not stock_row.empty:
                    return stock_row.iloc[0].get('名称', f'股票{stock_code}')
        
        return f'股票{stock_code}'
    except Exception as e:
        print(f"获取股票名称失败: {str(e)}")
        return f'股票{stock_code}'

def get_real_time_stock_price(stock_code):
    """
    获取股票实时价格
    :param stock_code: 股票代码
    :return: 实时价格
    """
    try:
        fetcher = stock_filter.fetcher
        # 直接获取K线数据，使用最新的收盘价
        kline_data = fetcher.get_stock_kline(stock_code)
        if not kline_data.empty:
            # 获取最新数据
            latest_data = kline_data.iloc[-1]
            current_price = latest_data.get('close', 0)
            return current_price
        
        # 如果K线数据获取失败，尝试从市场数据中获取
        markets = ['sh', 'sz', 'cyb', 'kcb']
        for market in markets:
            market_data = fetcher.get_stock_data(market)
            if not market_data.empty:
                # 查找股票代码
                stock_row = market_data[market_data['代码'] == stock_code]
                if not stock_row.empty:
                    return stock_row.iloc[0].get('最新价', 0)
        
        return 0
    except Exception as e:
        print(f"获取股票实时价格失败: {str(e)}")
        return 0

def get_stock_fundamental_data(stock_code):
    """
    获取股票基本面数据
    :param stock_code: 股票代码
    :return: 基本面数据字典
    """
    try:
        print(f"获取股票{stock_code}基本面数据")
        # 这里可以使用更专业的数据源获取基本面数据
        # 由于数据源限制，这里使用模拟数据
        fundamental_data = {
            'pe': round(20 + (hash(stock_code) % 30), 2),  # 市盈率
            'profit_rate': round(5 + (hash(stock_code) % 15), 2),  # 利润率
            'roe': round(8 + (hash(stock_code) % 12), 2),  # 净资产收益率
            'debt_ratio': round(30 + (hash(stock_code) % 40), 2),  # 负债率
            'revenue_growth': round(10 + (hash(stock_code) % 20), 2),  # 营收增长率
            'profit_growth': round(15 + (hash(stock_code) % 25), 2),  # 利润增长率
            'cash_flow': round(100000000 + (hash(stock_code) % 900000000), 2)  # 现金流
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
    """
    获取市场情绪数据
    :param stock_code: 股票代码
    :return: 市场情绪数据字典
    """
    try:
        print(f"获取股票{stock_code}市场情绪数据")
        # 这里可以使用更专业的数据源获取市场情绪数据
        # 由于数据源限制，这里使用模拟数据
        sentiment_data = {
            'news_sentiment': round(0.3 + (hash(stock_code) % 5) * 0.1, 2),  # 新闻情绪
            'social_media_sentiment': round(0.2 + (hash(stock_code) % 6) * 0.1, 2),  # 社交媒体情绪
            'fear_greed_index': 30 + (hash(stock_code) % 50),  # 恐慌贪婪指数
            'trading_volume_change': round(0.8 + (hash(stock_code) % 4) * 0.2, 2),  # 成交量变化
            'market_breadth': round(0.4 + (hash(stock_code) % 3) * 0.2, 2)  # 市场广度
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

@socketio.on('analyze_stock')
def handle_analyze_stock(data):
    print(f"Analyze stock requested: {data['code']}")
    
    try:
        stock_code = data['code']
        
        # 1. 获取股票名称
        stock_name = get_stock_name_from_data(stock_code)
        
        # 2. 获取股票K线数据
        fetcher = stock_filter.fetcher
        kline_data = fetcher.get_stock_kline(stock_code)
        
        if kline_data.empty:
            socketio.emit('analyze_completed', {'error': '无法获取股票数据'})
            return
        
        # 3. 计算技术指标
        kline_data = stock_filter.calculate_indicators(kline_data)
        
        if kline_data.empty:
            socketio.emit('analyze_completed', {'error': '无法计算技术指标'})
            return
        
        # 4. 获取最新数据
        latest_data = kline_data.iloc[-1]
        # 尝试获取实时价格
        current_price = get_real_time_stock_price(stock_code)
        # 如果实时价格获取失败，使用K线数据中的收盘价
        if current_price == 0:
            current_price = latest_data.get('close', 0)
        
        # 5. 获取基本面数据
        fundamental_data = get_stock_fundamental_data(stock_code)
        
        # 6. 获取市场情绪数据
        market_sentiment = get_market_sentiment(stock_code)
        
        # 7. 计算买入价格、止盈和止损位
        # 买入价格：当前价格
        buy_price = round(current_price, 2)
        
        # 止盈价格：当前价格 + 5%
        take_profit_price = round(current_price * 1.05, 2)
        
        # 止损价格：当前价格 - 5%
        stop_loss_price = round(current_price * 0.95, 2)
        
        # 8. 构建股票信息
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
        
        # 9. 检查技术指标
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
        
        # 10. 使用SmartAnalyzer进行详细分析
        analysis_result = smart_analyzer.analyze_stock(stock_info)
        
        # 11. 构建返回结果
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
        
        socketio.emit('analyze_completed', {'result': result})
        
    except Exception as e:
        print(f"分析股票失败: {str(e)}")
        socketio.emit('analyze_completed', {'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)
