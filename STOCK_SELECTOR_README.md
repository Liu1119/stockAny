# 股票定时选股系统

## 功能说明

本系统实现了基于技术形态的股票筛选功能，每天下午2点半自动执行选股任务，并将结果发送到飞书。

## 选股策略

### 核心筛选条件
1. **阴线筛选**：只选择阴线股票（收盘价 < 开盘价）
2. **跌幅适中**：跌幅在合理范围内（可配置）
3. **量能分析**：量比在合理范围内（可配置）
4. **换手率筛选**：换手率适中，避免过度投机
5. **价格区间**：价格在合理区间内
6. **成交量筛选**：确保有足够的流动性

### 优先级评分
- 量比越小，优先级越高
- 换手率适中，优先级越高
- 跌幅适中，优先级越高
- 委比为正，优先级越高

## 文件说明

### 核心文件
- `stock_selector.py`：选股核心逻辑
  - `StockSelector`：股票筛选类
  - `FeishuNotifier`：飞书消息发送类
  - `ScheduledStockSelector`：定时选股任务类

- `scheduler.py`：定时任务调度器
  - 每天下午14:30自动执行选股任务
  - 支持测试模式

### 数据获取
- `data_fetcher.py`：数据获取模块
- 使用腾讯财经API获取实时股票数据

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置飞书Webhook

在 `stock_selector.py` 和 `scheduler.py` 中修改飞书Webhook地址：

```python
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK"
```

### 3. 测试运行

```bash
# 测试选股功能（使用少量股票）
python3 stock_selector.py

# 测试定时任务（立即执行一次）
python3 scheduler.py --test
```

### 4. 启动定时任务

```bash
# 启动定时任务（每天下午14:30执行）
python3 scheduler.py
```

### 5. 后台运行（推荐）

使用 `nohup` 或 `screen` 在后台运行：

```bash
# 使用nohup
nohup python3 scheduler.py > scheduler.log 2>&1 &

# 或使用screen
screen -S stock_selector
python3 scheduler.py
# 按 Ctrl+A+D 分离会话
```

## 配置说明

### 修改筛选条件

在 `stock_selector.py` 的 `select_stocks` 方法中修改筛选条件：

```python
# 阴线筛选
if not stock['is_yin_line']:
    continue

# 跌幅筛选（当前：跌幅 <= 0）
if stock['change_percent'] > 0:
    continue

# 量比筛选（当前：量比 <= 2.0）
if stock['volume_ratio'] > 2.0:
    continue

# 换手率筛选（当前：换手率 <= 20%）
if stock['turnover_rate'] > 20:
    continue

# 价格筛选（当前：3元 <= 价格 <= 200元）
if stock['price'] < 3 or stock['price'] > 200:
    continue

# 成交量筛选（当前：成交量 >= 50000）
if stock['volume'] < 50000:
    continue
```

### 修改执行时间

在 `scheduler.py` 中修改执行时间：

```python
# 当前：每天下午14:30执行
schedule.every().day.at("14:30").do(job)

# 修改为其他时间，例如下午15:00
schedule.every().day.at("15:00").do(job)
```

### 修改股票范围

在 `scheduler.py` 的 `get_all_stock_codes` 函数中修改市场范围：

```python
# 当前：获取上证、深证、创业板股票
markets = ['sh', 'sz', 'cyb']

# 可以添加科创板
markets = ['sh', 'sz', 'cyb', 'kcb']
```

## 飞书消息格式

选股结果将以文本形式发送到飞书，包含以下信息：

```
股票筛选结果

筛选时间: 2026-03-23 14:30:00
筛选条件:
• 阴线（收盘价 < 开盘价）
• 缩量回调（量比 < 1.0）
• 跌幅适中（-5% ~ -2%）
• 换手率适中（1% ~ 15%）
• 价格适中（5元 ~ 100元）

共筛选出 X 只股票:

1. 600000 浦发银行 | 价格: 10.28 | 跌幅: -0.39% | 量比: 1.74 | 换手率: 0.22% | 优先级: 1
2. 600036 招商银行 | 价格: 39.75 | 跌幅: -0.05% | 量比: 0.85 | 换手率: 0.15% | 优先级: 2
...
```

## 日志说明

系统运行日志将保存到 `stock_selector_scheduler.log` 文件中，包含：

- 选股任务执行时间
- 股票数据获取情况
- 筛选结果统计
- 飞书消息发送状态
- 错误信息

## 注意事项

1. **数据源**：使用腾讯财经API，可能存在访问限制
2. **执行时间**：建议在交易时间内执行（9:30-15:00）
3. **网络连接**：确保服务器网络稳定
4. **飞书配置**：确保飞书Webhook地址正确且有权限发送消息
5. **资源占用**：处理大量股票时可能需要较长时间，建议控制股票数量

## 故障排查

### 1. 未筛选出股票
- 检查筛选条件是否过于严格
- 查看日志中的数据获取情况
- 确认当前市场是否有符合条件的股票

### 2. 飞书消息发送失败
- 检查Webhook地址是否正确
- 确认网络连接正常
- 查看飞书机器人是否有权限

### 3. 数据获取失败
- 检查网络连接
- 确认API是否可访问
- 查看日志中的错误信息

## 扩展功能

### 添加更多筛选条件

可以在 `StockSelector.select_stocks` 方法中添加更多筛选条件：

```python
# 例如：添加行业筛选
if stock['industry'] not in ['银行', '保险', '证券']:
    continue

# 例如：添加市值筛选
if stock['market_cap'] < 10000000000:  # 100亿
    continue
```

### 添加更多通知渠道

可以扩展 `FeishuNotifier` 类，添加其他通知渠道：

```python
class DingTalkNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_message(self, selected_stocks: List[Dict]) -> bool:
        # 实现钉钉消息发送逻辑
        pass
```

## 技术架构

```
┌─────────────────┐
│   定时任务调度   │
│  (scheduler.py) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   选股核心逻辑   │
│(stock_selector) │
└────────┬────────┘
         │
         ├──────────┐
         ▼          ▼
┌─────────────┐ ┌─────────────┐
│  数据获取   │ │  消息通知   │
│(data_fetcher)│ │  (feishu)   │
└─────────────┘ └─────────────┘
```

## 许可证

MIT License
