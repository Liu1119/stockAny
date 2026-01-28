from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import time
from stock_filter import StockFilter
from smart_analyzer import SmartAnalyzer

app = Flask(__name__, template_folder='docs')
app.config['SECRET_KEY'] = 'secret!'
# 直接指定使用threading模式，避免eventlet的兼容性问题
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局变量控制自动刷新
auto_refresh_running = False
refresh_interval = 300  # 5分钟

# 初始化筛选器和分析器
# 使用baostock作为默认数据源
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
    print('Manual refresh requested')
    socketio.emit('refresh_started', {'data': '开始刷新数据...'})
    
    # 执行股票筛选流程
    try:
        # 1. 筛选所有市场的股票
        socketio.emit('processing_progress', {'data': '正在获取股票数据...'})
        filtered_stocks = stock_filter.filter_all_markets()
        
        # 2. 检查是否有数据获取失败的情况
        if not filtered_stocks:
            # 检查各个市场的数据获取情况
            fetcher = stock_filter.fetcher
            market_status = {}
            all_markets_empty = True
            
            for market in ['sh', 'sz', 'cyb', 'kcb']:
                data = fetcher.get_stock_data(market)
                market_status[market] = not data.empty
                if not data.empty:
                    all_markets_empty = False
            
            if all_markets_empty:
                # 所有市场数据都获取失败
                socketio.emit('refresh_completed', {'data': '刷新完成', 'stocks': [], 'message': '所有数据源获取失败，无法筛选股票'})
            else:
                # 数据获取成功但没有符合条件的股票
                socketio.emit('refresh_completed', {'data': '刷新完成', 'stocks': [], 'message': '没有找到符合条件的股票'})
            return
        
        # 3. 对筛选结果进行智能分析
        socketio.emit('processing_progress', {'data': f'正在分析 {len(filtered_stocks)} 只股票...'})
        analyzed_stocks = smart_analyzer.analyze_stocks_batch(filtered_stocks)
        
        # 4. 准备前端显示的数据
        socketio.emit('processing_progress', {'data': '正在计算买卖价格...'})
        display_data = []
        for stock in analyzed_stocks:
            display_item = {
                'code': stock['code'],
                'name': stock['name'],
                'price': stock['price'],
                'change': stock['change'],
                'analysis': stock['analysis']['suggestion']
            }
            display_data.append(display_item)
        
        # 5. 发送筛选结果
        socketio.emit('processing_progress', {'data': '数据处理完成，正在显示结果...'})
        socketio.emit('refresh_completed', {'data': '刷新完成', 'stocks': display_data})
        
    except Exception as e:
        print(f"刷新数据失败: {str(e)}")
        socketio.emit('refresh_completed', {'data': '刷新失败', 'error': str(e)})

@socketio.on('toggle_auto_refresh')
def handle_toggle_auto_refresh(data):
    global auto_refresh_running
    auto_refresh_running = data['enabled']
    if auto_refresh_running:
        print('Auto refresh started')
        socketio.emit('auto_refresh_status', {'enabled': True, 'interval': refresh_interval})
        # 启动自动刷新线程
        threading.Thread(target=auto_refresh_task, daemon=True).start()
    else:
        print('Auto refresh stopped')
        socketio.emit('auto_refresh_status', {'enabled': False})

def auto_refresh_task():
    global auto_refresh_running
    while auto_refresh_running:
        print('Auto refresh triggered')
        socketio.emit('refresh_started', {'data': '自动刷新数据...'})
        
        # 执行股票筛选流程
        try:
            # 1. 筛选所有市场的股票
            socketio.emit('processing_progress', {'data': '正在获取股票数据...'})
            filtered_stocks = stock_filter.filter_all_markets()
            
            # 2. 检查是否有数据获取失败的情况
            if not filtered_stocks:
                # 检查各个市场的数据获取情况
                fetcher = stock_filter.fetcher
                market_status = {}
                all_markets_empty = True
                
                for market in ['sh', 'sz', 'cyb', 'kcb']:
                    data = fetcher.get_stock_data(market)
                    market_status[market] = not data.empty
                    if not data.empty:
                        all_markets_empty = False
                
                if all_markets_empty:
                    # 所有市场数据都获取失败
                    socketio.emit('refresh_completed', {'data': '自动刷新完成', 'stocks': [], 'message': '所有数据源获取失败，无法筛选股票'})
                else:
                    # 数据获取成功但没有符合条件的股票
                    socketio.emit('refresh_completed', {'data': '自动刷新完成', 'stocks': [], 'message': '没有找到符合条件的股票'})
            else:
                # 3. 对筛选结果进行智能分析
                socketio.emit('processing_progress', {'data': f'正在分析 {len(filtered_stocks)} 只股票...'})
                analyzed_stocks = smart_analyzer.analyze_stocks_batch(filtered_stocks)
                
                # 4. 准备前端显示的数据
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
                
                # 5. 发送筛选结果
                socketio.emit('processing_progress', {'data': '数据处理完成，正在显示结果...'})
                socketio.emit('refresh_completed', {'data': '自动刷新完成', 'stocks': display_data})
            
        except Exception as e:
            print(f"自动刷新数据失败: {str(e)}")
            socketio.emit('refresh_completed', {'data': '自动刷新失败', 'error': str(e)})
        
        # 等待下一次刷新
        time.sleep(refresh_interval)

@socketio.on('analyze_stock')
def handle_analyze_stock(data):
    print(f"Analyze stock requested: {data['code']}")
    
    try:
        stock_code = data['code']
        
        # 1. 获取股票K线数据
        fetcher = stock_filter.fetcher
        kline_data = fetcher.get_stock_kline(stock_code)
        
        if kline_data.empty:
            socketio.emit('analyze_completed', {'error': '无法获取股票数据'})
            return
        
        # 2. 计算技术指标
        kline_data = stock_filter.calculate_indicators(kline_data)
        
        if kline_data.empty:
            socketio.emit('analyze_completed', {'error': '无法计算技术指标'})
            return
        
        # 3. 获取最新数据
        latest_data = kline_data.iloc[-1]
        
        # 4. 构建股票信息
        stock_info = {
            'code': stock_code,
            'name': f'股票{stock_code}',  # 实际应用中应该从数据源获取名称
            'price': latest_data.get('close', 0),
            'change': 0,  # 实际应用中应该计算涨跌幅
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
        
        # 5. 使用SmartAnalyzer进行分析
        analysis_result = smart_analyzer.analyze_stock(stock_info)
        
        # 6. 构建返回结果
        result = {
            'code': stock_code,
            'name': stock_info['name'],
            'price': stock_info['price'],
            'short_term': analysis_result.get('short_term', '中性'),
            'medium_term': analysis_result.get('medium_term', '中性'),
            'suggestion': analysis_result.get('suggestion', '建议观望'),
            'risk': analysis_result.get('risk', '市场波动风险')
        }
        
        socketio.emit('analyze_completed', {'result': result})
        
    except Exception as e:
        print(f"分析股票失败: {str(e)}")
        socketio.emit('analyze_completed', {'error': str(e)})

if __name__ == '__main__':
    # 使用threading模式替代eventlet，解决Python 3.12兼容性问题
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)