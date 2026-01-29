# Render 部署指南

## 前置条件

1. ✅ 代码已提交到本地Git仓库
2. ✅ GitHub仓库: https://github.com/Liu1119/stockAny.git
3. ✅ 配置文件已准备完成（Procfile, render.yaml）
4. ⚠️ 需要手动推送到GitHub（网络问题）

## 步骤1：推送代码到GitHub

### 方案A：等待网络恢复后推送（推荐）

```bash
# 在项目目录执行
cd /Users/liuqiang/Documents/trae_projects/stockAny
git push origin main
```

### 方案B：检查网络配置

```bash
# 测试GitHub连接
ping github.com

# 检查代理设置
git config --global http.proxy
git config --global https.proxy

# 如果有代理，清除代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 方案C：使用SSH推送（如果有SSH密钥）

```bash
# 切换到SSH URL
git remote set-url origin git@github.com:Liu1119/stockAny.git

# 推送
git push origin main
```

## 步骤2：在Render上创建Web Service

### 2.1 登录Render

1. 访问 https://dashboard.render.com
2. 使用GitHub账号登录
3. 授权Render访问您的GitHub仓库

### 2.2 创建新的Web Service

1. 点击 **"New +"** 按钮
2. 选择 **"Web Service"**
3. 连接GitHub仓库
4. 选择 `Liu1119/stockAny` 仓库
5. 选择 `main` 分支

### 2.3 配置Web Service

#### 基本配置
```
Name: stock-analysis
Region: Singapore (推荐，延迟较低)
Branch: main
```

#### 构建配置
```
Build Command: pip install -r requirements.txt
Start Command: python3 app_http.py
```

#### 环境变量
点击 **"Advanced"** → **"Add Environment Variable"**：

| Key | Value | Sync |
|-----|-------|------|
| PORT | 5001 | No |
| SECRET_KEY | (自动生成或手动设置) | No |
| FLASK_ENV | production | No |

#### 实例配置
```
Instance Type: Free (免费版)
```

### 2.4 部署

1. 点击 **"Create Web Service"**
2. 等待构建完成（通常需要2-5分钟）
3. 部署成功后会获得一个URL，例如：
   - `https://stock-analysis.onrender.com`

## 步骤3：验证部署

### 3.1 检查部署状态

1. 在Render Dashboard查看Web Service状态
2. 确认状态为 **"Live"**
3. 查看部署日志，确认没有错误

### 3.2 测试API端点

使用浏览器或curl测试：

```bash
# 测试主页
curl https://stock-analysis.onrender.com/

# 测试状态API
curl https://stock-analysis.onrender.com/api/status

# 测试控制台输出API
curl https://stock-analysis.onrender.com/api/console_output
```

### 3.3 测试完整功能

1. 访问 https://stock-analysis.onrender.com
2. 测试手动刷新按钮
3. 测试自动刷新功能
4. 测试股票分析功能
5. 查看控制台输出

## 步骤4：配置自定义域名（可选）

### 4.1 在Render中添加自定义域名

1. 进入Web Service设置
2. 点击 **"Domains"**
3. 点击 **"Add Domain"**
4. 输入您的域名，例如：`stock.example.com`

### 4.2 配置DNS

在您的域名DNS提供商处添加记录：

| Type | Name | Value |
|------|------|-------|
| CNAME | stock | cname.render.com |

## 常见问题排查

### 问题1：部署失败

**检查项**：
- 查看构建日志
- 确认 `requirements.txt` 包含所有依赖
- 确认 `Procfile` 正确指向 `app_http.py`

**解决方案**：
```bash
# 本地测试构建
pip install -r requirements.txt
python3 app_http.py
```

### 问题2：应用启动失败

**检查项**：
- 查看部署日志
- 确认端口配置正确（PORT环境变量）
- 确认没有语法错误

**解决方案**：
- 在Render Dashboard查看实时日志
- 检查 `app_http.py` 是否有错误

### 问题3：API返回404

**检查项**：
- 确认使用的是 `app_http.py` 而不是 `app.py`
- 确认路由路径正确

**解决方案**：
- 检查 `Procfile` 内容
- 确认 `render.yaml` 的 `startCommand`

### 问题4：免费版限制

**限制**：
- 每月750小时的运行时间
- 15分钟无活动后休眠
- 唤醒需要30-60秒

**解决方案**：
- 升级到付费计划
- 使用外部ping服务保持活跃
- 接受唤醒延迟

## 性能优化

### 1. 添加健康检查

在 `render.yaml` 中配置：

```yaml
services:
  - type: web
    name: stock-analysis
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python3 app_http.py
    healthCheckPath: /
    envVars:
      - key: PORT
        value: 5001
      - key: SECRET_KEY
        generateValue: true
        sync: false
    plan: free
```

### 2. 启用缓存

在 `app_http.py` 中添加响应头：

```python
from flask import after_this_request

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'public, max-age=300'
    return response
```

### 3. 优化轮询间隔

在前端 `index_http.html` 中调整：

```javascript
// 减少服务器负载
statusPollingInterval = setInterval(() => {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            updateUI(data);
        });
}, 2000); // 从1秒改为2秒
```

## 监控和日志

### 查看实时日志

1. 进入Render Dashboard
2. 选择Web Service
3. 点击 **"Logs"**
4. 选择 **"Real-time"** 标签

### 查看部署历史

1. 进入Web Service设置
2. 点击 **"Events"**
3. 查看所有部署历史和状态

### 设置告警

1. 进入Web Service设置
2. 点击 **"Alerts"**
3. 配置错误率、响应时间等告警

## 成本估算

### 免费版（当前）
- **成本**: $0/月
- **限制**: 750小时/月
- **适用**: 个人使用、测试

### 标准版（$7/月）
- **成本**: $7/月
- **限制**: 无限运行时间
- **适用**: 生产环境

### 专业版（$25/月）
- **成本**: $25/月
- **限制**: 更多资源
- **适用**: 高流量应用

## 备份和恢复

### 备份数据

```bash
# 备份配置
git push origin main

# 备份日志（如果有）
# 在Render Dashboard下载日志
```

### 恢复部署

```bash
# 如果需要回滚
git checkout <previous-commit>
git push origin main

# Render会自动重新部署
```

## 下一步

1. ✅ 等待网络恢复后推送代码到GitHub
2. ✅ 在Render创建Web Service
3. ✅ 配置环境变量
4. ✅ 部署并测试
5. ✅ 配置自定义域名（可选）
6. ✅ 设置监控和告警

## 联系支持

如果遇到问题：
- Render文档: https://render.com/docs
- Render社区: https://community.render.com
- GitHub Issues: https://github.com/Liu1119/stockAny/issues

---

**部署完成后，您的应用将可以通过以下方式访问**：
- 主URL: https://stock-analysis.onrender.com
- API端点: https://stock-analysis.onrender.com/api/*
- 完全兼容HTTP轮询，无需WebSocket支持
