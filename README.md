# 自用图床

一个简洁、高效、安全的个人图床应用，支持批量上传、用户认证和后台管理。

## 功能特性

### 🚀 核心功能
- **图片上传**：支持单文件/批量上传，拖拽操作
- **多格式链接**：一键生成 URL、Markdown、HTML、BBCode 格式
- **用户系统**：注册/登录，JWT 令牌认证
- **文件管理**：个人文件列表，复制链接，删除文件

### 👑 管理员功能
- **后台面板**：系统统计（用户数、文件数、存储用量）
- **用户管理**：查看所有用户，设置管理员权限
- **文件管理**：查看全站文件，强制删除任意文件

### 🎨 界面设计
- **黑白主题**：简约专业，无过度装饰
- **响应式布局**：适配桌面/平板/手机
- **交互反馈**：实时进度条，Toast 通知，平滑动画

### 🔒 安全特性
- 密码哈希存储（SHA256 + Salt）
- JWT 令牌认证（7天有效期）
- API 权限校验（用户只能操作自己的文件）
- 文件路径遍历防护

## 技术栈

- **后端**：FastAPI + SQLite + JWT
- **前端**：原生 HTML/CSS/JavaScript
- **存储**：文件系统 + 数据库元数据
- **部署**：Uvicorn ASGI 服务器

## 快速开始

### 1. 安装依赖
```bash
pip install fastapi uvicorn
```

### 2. 启动服务
```bash
cd 图床
uvicorn app:app --reload
```

### 3. 访问应用
- 首页：`http://localhost:8000`
- 登录：`http://localhost:8000/login`
- 注册：`http://localhost:8000/register`
- 我的文件：`http://localhost:8000/manage`
- 后台管理：`http://localhost:8000/admin`（需管理员权限）

### 4. 默认账户
- 管理员：`admin` / `admin123`
- 首次启动自动创建

## 项目结构
```
图床/
├── app.py              # 主应用（FastAPI + 认证 + API）
├── database.py         # 数据库模块（SQLite CRUD）
├── static/
│   ├── index.html      # 主上传页（批量上传）
│   ├── login.html      # 登录页
│   ├── register.html   # 注册页
│   ├── manage.html     # 用户文件管理
│   └── admin.html      # 后台管理面板
├── uploads/            # 图片存储目录（自动创建）
├── database.db         # SQLite 数据库（自动生成）
└── .gitignore          # Git 忽略规则
```

## API 文档

### 认证相关
- `POST /api/register` - 用户注册
- `POST /api/login` - 用户登录
- `GET /api/files` - 获取用户文件列表（需认证）
- `DELETE /api/files/{id}` - 删除用户文件（需认证）

### 上传相关
- `POST /api/upload` - 上传单个文件（需认证）
- `POST /api/upload-multiple` - 批量上传文件（需认证）

### 管理员 API（需管理员权限）
- `GET /api/admin/users` - 获取所有用户
- `GET /api/admin/all-files` - 获取所有文件
- `DELETE /api/admin/files/{id}` - 删除任意文件
- `DELETE /api/admin/users/{id}` - 删除用户
- `POST /api/admin/users/{id}/admin` - 设置管理员权限

## 部署说明

### 生产环境建议
1. 修改 `app.py` 中的 `SECRET_KEY`
2. 使用反向代理（Nginx/Apache）
3. 配置 HTTPS 证书
4. 定期备份 `uploads/` 和 `database.db`

### 环境变量
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SECRET_KEY` | JWT 签名密钥 | `your-secret-key-change-in-production` |
| `TOKEN_EXPIRE_MINUTES` | Token 有效期（分钟） | `10080`（7天） |
| `MAX_FILE_SIZE` | 最大文件大小（字节） | `10485760`（10MB） |

## 开发指南

### 添加新功能
1. 在 `app.py` 中添加 API 路由
2. 在 `database.py` 中添加数据库操作
3. 在 `static/` 中添加前端页面
4. 测试后提交到 Git

### 数据库迁移
当前使用 SQLite，如需迁移到其他数据库：
1. 修改 `database.py` 中的连接逻辑
2. 调整 SQL 语句以适应目标数据库
3. 导出导入现有数据

## 许可证
MIT License - 详见 LICENSE 文件

## 贡献
欢迎提交 Issue 和 Pull Request！

## 更新日志
### v1.0.0 (2026-04-03)
- 初始版本发布
- 支持批量上传、用户认证、后台管理
- 黑白主题界面