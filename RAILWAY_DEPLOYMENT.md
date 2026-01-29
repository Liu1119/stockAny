# 股票分析系统 - Railway部署指南

## 快速部署到Railway

### 前置要求
- GitHub账号
- Railway账号（免费注册：https://railway.app）

### 部署步骤

#### 1. 推送代码到GitHub
```bash
# 初始化Git仓库（如果还没有）
git init

# 添加所有文件
git add .

# 提交更改
git commit -m "准备Railway部署"

# 推送到GitHub
git remote add origin https://github.com/你的用户名/stockAny.git
git push -u origin main
```

#### 2. 在Railway部署
1. 访问 https://railway.app 并登录
2. 点击 "New Project" -> "Deploy from GitHub repo"
3. 选择您的 stockAny 仓库
4. Railway会自动检测配置并部署

### 环境变量配置
Railway会自动设置以下环境变量：
- `PORT=5001`（自动设置）
- `SECRET_KEY=your-secret-key`（建议设置）

### 访问应用
部署完成后，Railway会提供一个URL，例如：
- `https://your-app-name.up.railway.app`

### 监控和管理
- 在Railway控制台查看日志
- 监控资源使用情况
- 自动扩展功能

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

## 注意事项
1. Railway免费额度：$5/月
2. 自动扩展：根据负载自动调整
3. 数据持久化：建议配置外部数据库
4. API密钥：DeepSeek API密钥建议通过环境变量设置