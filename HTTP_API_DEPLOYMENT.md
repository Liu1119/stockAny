# HTTP API 版本部署说明

## 概述

本版本使用HTTP轮询替代Socket.IO，完全兼容GitHub Pages、Render、Railway等所有托管平台，无需WebSocket支持。

## 文件说明

### 新增文件
- `app_http.py` - HTTP API版本后端（替代app.py）
- `docs/index_http.html` - HTTP轮询版本前端（替代index.html）

### 修改文件
- `Procfile` - 更新为使用 `app_http.py`
- `render.yaml` - 更新为使用 `app_http.py`

## API端点

### 1. 手动刷新
```http
POST /api/manual_refresh
```
启动手动刷新任务

### 2. 手动停止
```http
POST /api/manual_stop
```
停止当前刷新任务

### 3. 自动刷新切换
```http
POST /api/toggle_auto_refresh
Content-Type: application/json

{
  "enabled": true
}
```
切换自动刷新状态

### 4. 股票分析
```http
POST /api/analyze_stock
Content-Type: application/json

{
  "code": "sh.600000"
}
```
分析指定股票

### 5. 获取状态
```http
GET /api/status
```
获取所有任务状态，返回：
```json
{
  "manual_refresh": {
    "running": false,
    "status": "idle",
    "message": "",
    "progress": 0,
    "stocks": [],
    "error": null
  },
  "auto_refresh": {
    "running": false,
    "enabled": false,
    "interval": 300,
    "last_run": null
  },
  "analyze_stock": {
    "running": false,
    "status": "idle",
    "result": null,
    "error": null
  }
}
```

### 6. 获取控制台输出
```http
GET /api/console_output
```
获取服务器控制台日志，返回：
```json
{
  "output": ["日志行1", "日志行2", ...]
}
```

## 前端轮询机制

前端使用两个轮询间隔：
- **状态轮询**: 每1秒查询一次 `/api/status`
- **控制台轮询**: 每2秒查询一次 `/api/console_output`

这种机制确保了：
- 实时性：1-2秒延迟，用户体验良好
- 稳定性：完全基于HTTP，无WebSocket依赖
- 兼容性：支持所有Web托管平台

## 部署方式

### Render部署

1. 确保仓库包含以下文件：
   - `app_http.py`
   - `docs/index_http.html`
   - `Procfile` (内容: `web: python3 app_http.py`)
   - `render.yaml`
   - `requirements.txt`

2. 在Render上创建新的Web Service
   - 连接GitHub仓库
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python3 app_http.py`
   - 环境变量：
     - `PORT`: 5001
     - `SECRET_KEY`: 自动生成

### Railway部署

1. 确保仓库包含 `railway.toml`:
   ```toml
   [build]
   builder = "NIXPACKS"
   
   [deploy]
   healthcheckPath = "/"
   healthcheckTimeout = 180
   restartPolicyType = "ON_FAILURE"
   ```

2. 在Railway上创建新项目
   - 连接GitHub仓库
   - 自动检测Python环境
   - 设置环境变量

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动HTTP API版本
python3 app_http.py

# 访问
http://localhost:5001
```

## 与Socket.IO版本对比

| 特性 | Socket.IO版本 | HTTP API版本 |
|------|--------------|--------------|
| 实时性 | 毫秒级 | 1-2秒 |
| 兼容性 | 需要WebSocket支持 | 完全兼容 |
| 部署复杂度 | 需要特殊配置 | 标准Web部署 |
| 稳定性 | 依赖网络质量 | 高稳定性 |
| 资源消耗 | 较低 | 稍高（轮询） |

## 优势

1. **完全兼容** - 支持GitHub Pages、Render、Railway、Vercel等所有平台
2. **无需配置** - 标准Flask应用，无需特殊WebSocket配置
3. **稳定可靠** - 基于HTTP，无连接断开问题
4. **易于调试** - 可以直接使用浏览器或curl测试API
5. **向后兼容** - 保留了所有原有功能

## 注意事项

1. **轮询间隔** - 当前设置为1秒和2秒，可根据需要调整
2. **服务器负载** - 轮询会产生更多HTTP请求，确保服务器有足够资源
3. **并发限制** - 注意Render免费层的并发限制
4. **缓存策略** - 考虑添加HTTP缓存头减少负载

## 故障排除

### 问题：轮询失败
**解决方案**：
- 检查服务器是否正常运行
- 确认防火墙设置
- 查看浏览器控制台错误

### 问题：状态更新延迟
**解决方案**：
- 减少轮询间隔（修改前端JavaScript）
- 优化后端处理速度
- 检查网络连接

### 问题：部署后无法访问
**解决方案**：
- 确认Procfile正确指向 `app_http.py`
- 检查环境变量配置
- 查看部署日志

## 技术栈

- **后端**: Flask (无Socket.IO依赖)
- **前端**: 原生JavaScript (Fetch API)
- **通信**: HTTP REST API + 轮询
- **数据处理**: Pandas, pandas_ta
- **数据源**: Baostock, 腾讯财经

## 未来改进

1. 添加HTTP缓存头减少服务器负载
2. 实现增量更新减少数据传输
3. 添加WebSocket降级机制（如果平台支持）
4. 优化轮询策略（智能间隔调整）
5. 添加离线支持（Service Worker）

## 支持

如有问题，请查看：
- 服务器日志
- 浏览器控制台
- Render/Railway部署日志
