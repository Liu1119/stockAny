from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import time
import sys
import io
import logging
from stock_filter import StockFilter
from smart_analyzer import SmartAnalyzer

app = Flask(__name__, template_folder='docs')
app.config['SECRET_KEY'] = 'secret!'
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
        current_price = latest_data.get('close', 0)
        
        # 5. 计算买入价格、止盈和止损位
        # 买入价格：当前价格
        buy_price = round(current_price, 2)
        
        # 止盈价格：当前价格 + 5%
        take_profit_price = round(current_price * 1.05, 2)
        
        # 止损价格：当前价格 - 5%
        stop_loss_price = round(current_price * 0.95, 2)
        
        # 6. 构建股票信息
        stock_info = {
            'code': stock_code,
            'name': stock_name,
            'price': current_price,
            'change': 0,
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
        
        # 7. 检查技术指标
        if all(col in latest_data.index for col in ['MACD_12_26_9', 'MACDs_12_26_9', 'MACDh_12_26_9']):
            if latest_data['MACD_12_26_9'] > latest_data['MACDs_12_26_9'] and latest_data['MACDh_12_26_9'] > 0:
                stock_info['indicators']['macd_bullish'] = True
        
        if all(col in latest_data.index for col in ['WR14', 'WR21']):
            if latest_data['WR14'] < -80 and latest_data['WR21'] < -80:
                stock_info['indicators']['wr_bullish'] = True
        
        if all(col in latest_data.index for col in ['MA5', 'MA10', 'MA20', 'MA60']):
            if latest_data['MA5'] > latest_data['MA10'] > latest_data['MA20'] > latest_data['MA60']:
                stock_info['indicators']['ma_bullish'] = True
        
        if all(col in latest_data.index for col in ['volume', 'MA_VOL5']):
            if latest_data['volume'] > latest_data['MA_VOL5'] * 1.2:
                stock_info['indicators']['volume_bullish'] = True
        
        if all(col in latest_data.index for col in ['close', 'BBU_5_2.0']):
            if latest_data['close'] > latest_data['BBU_5_2.0']:
                stock_info['indicators']['breakout_bullish'] = True
        
        if all(col in latest_data.index for col in ['STOCHk_14_3_3', 'STOCHd_14_3_3']):
            if latest_data['STOCHk_14_3_3'] > latest_data['STOCHd_14_3_3']:
                stock_info['indicators']['kdj_bullish'] = True
        
        if 'RSI' in latest_data.index:
            if 30 < latest_data['RSI'] < 70:
                stock_info['indicators']['rsi_bullish'] = True
        
        # 8. 使用SmartAnalyzer进行详细分析
        analysis_result = smart_analyzer.analyze_stock(stock_info)
        
        # 9. 构建返回结果
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
            'indicators': stock_info['indicators']
        }
        
        socketio.emit('analyze_completed', {'result': result})
        
    except Exception as e:
        print(f"分析股票失败: {str(e)}")
        socketio.emit('analyze_completed', {'error': str(e)})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)
