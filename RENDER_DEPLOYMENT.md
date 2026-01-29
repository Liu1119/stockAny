# 股票分析系统 - Render部署指南

## 快速部署到Render

### 前置要求
- GitHub账号
- Render账号（免费注册：https://render.com）

### 部署步骤

#### 第1步：推送到GitHub
```bash
# 添加所有文件到Git
git add .

# 提交更改
git commit -m "准备Render部署"

# 推送到GitHub
git remote add origin https://github.com/你的用户名/stockAny.git
git push -u origin main
```

#### 第2步：在Render部署
1. 访问 https://dashboard.render.com 并登录
2. 点击 "New +" → "Web Service"
3. 填写配置：
   - Name: `stock-analysis`
   - Region: 选择离您最近的区域（如Singapore）
   - Branch: `main`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python3 app.py`
4. 点击 "Create Web Service"
5. Render会自动从GitHub拉取代码并部署

#### 第3步：配置环境变量
在Render控制台的Environment部分添加：
- `PORT=5001`
- `SECRET_KEY=your-secret-key-here`（可选）

### 访问应用
部署完成后，Render会提供一个URL，例如：
- `https://stock-analysis.onrender.com`

### 监控和管理
- 在Render控制台查看实时日志
- 监控CPU和内存使用情况
- 查看部署历史和版本

### 本地测试
```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
python3 app.py
```

访问 http://localhost:5001

## 技术栈
- Flask（Web框架）
- Flask-SocketIO（实时通信）
- baostock（数据源）
- pandas_ta（技术指标计算）

## 功能特点
- 实时股票数据获取
- 基本面选股法筛选
- 技术指标分析
- DeepSeek智能分析
- WebSocket实时更新

## Render免费额度
- ✅ 512MB RAM
- ✅ 0.1 CPU
- ✅ 每月750小时免费
- ✅ 支持WebSocket
- ✅ 自动休眠（无流量时）
- ✅ 自动重启

## 注意事项
1. Render免费服务会在15分钟无流量后自动休眠
2. 首次访问可能需要1-2分钟启动
3. 建议配置外部数据库（如PostgreSQL）
4. API密钥建议通过环境变量设置
5. 可以设置定时任务保持应用活跃

## 优化建议
### 减少启动时间
- 使用requirements.txt精确安装依赖
- 优化导入语句
- 减少初始化时的API调用

### 保持应用活跃
- 配置健康检查端点
- 使用外部监控服务
- 设置定时访问任务

### 数据持久化
- 使用Render PostgreSQL
- 配置Redis缓存
- 实现数据备份机制