# 全栈标准项目搭建（通用版）

## 项目简介
本项目是一个基于 FastAPI + React 的全栈应用开发框架，旨在帮助开发者快速搭建企业级 Web 应用。项目集成了常用的功能模块，包括用户认证、支付系统、资源管理等，让开发者能够专注于核心业务逻辑的开发。

## 技术栈
### 后端
- FastAPI (Python Web 框架)
- Tortoise ORM (异步 ORM)
- MySQL/SQLite (数据库)
- Redis (缓存)
- JWT (身份认证)
- 阿里云 OSS (对象存储)
- 微信/支付宝支付集成

### 前端
- React
- TypeScript
- Ant Design
- Redux/React Query
- Axios

## 项目结构
```
my-app-server/
├── config/           # 配置文件
├── middleware/       # 中间件
├── models/          # 数据模型
├── router/          # 路由
├── tools/           # 工具函数
├── main.py          # 主程序入口
└── requirements.txt # 依赖包
```

## 功能模块

### 1. 登录模块
- 手机号验证登录（腾讯 SMS）
- 邮箱登录
- 微信公众号登录
- Google 登录
- GitHub 登录
- 微信小程序登录
- 账号密码登录

### 2. 支付模块
- 微信扫码支付
- 支付宝扫码支付
- 兑换码（三方交易）
- 微信小程序支付

### 3. 交易模块
- 统一交易记录
- 商品订单信息记录
- 积分产品/礼包
- 积分购买虚拟产品/服务

### 4. 资源模块
- 阿里云 OSS 云存储
- 统一上传接口
- 统一删除接口
- 文件按标准自动划分归类

### 5. 用户模块
- 基础信息+身份+积分额度
- 登录会话监控机制
- 功能使用日志追踪

## 快速开始

### 环境要求
- Python 3.8+
- Node.js 16+
- MySQL 5.7+ / SQLite3
- Redis 6.0+

### 后端部署
1. 克隆项目
```bash
git clone -b trade --single-branch https://github.com/yangzhenyuYUYU/fastapi.git
```

2. 创建并激活虚拟环境
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
复制 `.env.example` 为 `.env`，并填写必要的配置信息：
- 数据库连接信息
- Redis 连接信息
- JWT 密钥
- 第三方服务密钥（微信、支付宝等）

5. 启动服务
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端部署
1. 进入前端目录
```bash
cd frontend
```

2. 安装依赖
```bash
npm install
```

3. 开发环境运行
```bash
npm run dev
```

4. 生产环境构建
```bash
npm run build
```

## API 文档
启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发规范
1. 代码风格
   - 后端遵循 PEP 8 规范
   - 前端使用 ESLint + Prettier

2. 提交规范
   - feat: 新功能
   - fix: 修复问题
   - docs: 文档修改
   - style: 代码格式修改
   - refactor: 代码重构
   - test: 测试用例修改
   - chore: 其他修改

## 注意事项
1. 本教程适用于有一定开发经验的开发者
2. 首次使用需要配置相关第三方服务的密钥
3. 生产环境部署前请确保：
   - 修改默认密钥
   - 配置正确的数据库连接
   - 设置适当的日志级别
   - 配置跨域设置
   - 启用 HTTPS

## 常见问题
1. 数据库连接失败
   - 检查数据库服务是否启动
   - 验证连接信息是否正确

2. Redis 连接失败
   - 确认 Redis 服务状态
   - 检查连接配置

3. 文件上传失败
   - 验证 OSS 配置
   - 检查文件大小限制

## 贡献指南
1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证
MIT License 