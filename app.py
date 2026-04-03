import os
import uuid
import time
import hashlib
import hmac
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, BackgroundTasks, Depends, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import database

app = FastAPI(title="自用图床 - 增强版")

# 配置
SECRET_KEY = "your-secret-key-change-in-production"  # 生产环境请修改
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 存储目录
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# 最大文件大小：10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# 挂载静态目录（用于直接访问图片）
app.mount("/images", StaticFiles(directory=str(UPLOAD_DIR)), name="images")

# 挂载前端静态文件（index.html 所在目录）
app.mount("/static", StaticFiles(directory="static"), name="static")

# 认证相关
security = HTTPBearer()

def create_jwt_token(data: dict) -> str:
    """创建JWT令牌"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.utcnow()
    payload = {
        **data,
        "exp": int((now + timedelta(minutes=TOKEN_EXPIRE_MINUTES)).timestamp()),
        "iat": int(now.timestamp())
    }
    
    # 编码header和payload
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    
    # 创建签名
    message = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(SECRET_KEY.encode(), message, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()
    
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

def verify_jwt_token(token: str) -> Optional[dict]:
    """验证JWT令牌"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        encoded_header, encoded_payload, encoded_signature = parts
        
        # 验证签名
        message = f"{encoded_header}.{encoded_payload}".encode()
        expected_signature = hmac.new(SECRET_KEY.encode(), message, hashlib.sha256).digest()
        expected_encoded_signature = base64.urlsafe_b64encode(expected_signature).rstrip(b'=').decode()
        
        if not hmac.compare_digest(encoded_signature, expected_encoded_signature):
            return None
            
        # 解码payload
        payload_json = base64.urlsafe_b64decode(encoded_payload + '=' * (4 - len(encoded_payload) % 4))
        payload = json.loads(payload_json)
        
        # 检查过期时间
        exp = payload.get('exp')
        if exp and datetime.utcnow().timestamp() > exp:
            return None
            
        return payload
    except Exception:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")
    
    user_id = payload.get('user_id')
    username = payload.get('username')
    if not user_id or not username:
        raise HTTPException(status_code=401, detail="无效的令牌")
    
    user = database.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    
    return user

async def get_current_user_optional(request: Request) -> Optional[dict]:
    """获取当前用户（可选）"""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        if payload:
            user_id = payload.get('user_id')
            if user_id:
                user = database.get_user_by_id(user_id)
                if user:
                    return user
    return None

def require_admin(user: dict = Depends(get_current_user)):
    """要求管理员权限"""
    if not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user

# 辅助函数
def get_file_url(request: Request, filename: str) -> str:
    """构建文件URL"""
    host = request.headers.get("host")
    scheme = request.headers.get("x-forwarded-proto", "http")
    return f"{scheme}://{host}/images/{filename}"

# 路由
@app.get("/", response_class=FileResponse)
async def root():
    """返回首页"""
    return FileResponse("static/index.html")

@app.get("/login", response_class=FileResponse)
async def login_page():
    """返回登录页面"""
    return FileResponse("static/login.html")

@app.get("/register", response_class=FileResponse)
async def register_page():
    """返回注册页面"""
    return FileResponse("static/register.html")

@app.get("/manage", response_class=FileResponse)
async def manage_page():
    """返回管理页面"""
    return FileResponse("static/manage.html")

@app.get("/admin", response_class=FileResponse)
async def admin_page():
    """返回后台管理页面"""
    return FileResponse("static/admin.html")

# API路由
@app.post("/api/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """用户注册"""
    try:
        user_id = database.create_user(username, email, password)
        return JSONResponse(content={
            "success": True,
            "message": "注册成功",
            "user_id": user_id
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="注册失败")

@app.post("/api/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    """用户登录"""
    user = database.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if not database.verify_password(password, user['password_hash']):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    token = create_jwt_token({
        "user_id": user['id'],
        "username": user['username'],
        "is_admin": user['is_admin']
    })
    
    return JSONResponse(content={
        "success": True,
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "is_admin": user['is_admin']
        }
    })

@app.post("/api/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """上传单个文件"""
    # 检查文件扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件类型，请上传图片 (jpg/png/gif/bmp/webp)")

    # 读取文件内容并检查大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过 {MAX_FILE_SIZE // (1024*1024)}MB 限制")

    # 生成唯一文件名
    new_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / new_filename

    # 保存文件
    with open(file_path, "wb") as f:
        f.write(content)

    # 构建URL
    url = get_file_url(request, new_filename)
    
    # 记录到数据库
    database.add_file(new_filename, file.filename, current_user['id'], len(content), url)

    return JSONResponse(content={
        "success": True,
        "url": url,
        "filename": new_filename,
        "original_name": file.filename,
        "size": len(content)
    })

@app.post("/api/upload-multiple")
async def upload_multiple_files(
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """批量上传文件"""
    results = []
    errors = []
    
    for file in files:
        try:
            # 检查文件扩展名
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({
                    "filename": file.filename,
                    "error": "不支持的文件类型"
                })
                continue

            # 读取文件内容并检查大小
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                errors.append({
                    "filename": file.filename,
                    "error": f"文件大小超过 {MAX_FILE_SIZE // (1024*1024)}MB 限制"
                })
                continue

            # 生成唯一文件名
            new_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = UPLOAD_DIR / new_filename

            # 保存文件
            with open(file_path, "wb") as f:
                f.write(content)

            # 构建URL
            url = get_file_url(request, new_filename)
            
            # 记录到数据库
            file_id = database.add_file(new_filename, file.filename, current_user['id'], len(content), url)
            
            results.append({
                "id": file_id,
                "filename": new_filename,
                "original_name": file.filename,
                "url": url,
                "size": len(content)
            })
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    return JSONResponse(content={
        "success": True,
        "results": results,
        "errors": errors,
        "total": len(files),
        "success_count": len(results),
        "error_count": len(errors)
    })

@app.get("/api/files")
async def get_files(current_user: dict = Depends(get_current_user)):
    """获取当前用户的文件列表"""
    files = database.get_user_files(current_user['id'])
    return JSONResponse(content=files)

@app.delete("/api/files/{file_id}")
async def delete_file(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """删除用户自己的文件"""
    success = database.delete_file(file_id, current_user['id'])
    if not success:
        raise HTTPException(status_code=404, detail="文件不存在或无权限删除")
    
    return JSONResponse(content={"success": True, "message": "文件已删除"})

# 管理员API
@app.get("/api/admin/users")
async def admin_get_users(admin_user: dict = Depends(require_admin)):
    """获取所有用户（管理员）"""
    users = database.get_all_users()
    return JSONResponse(content=users)

@app.get("/api/admin/all-files")
async def admin_get_all_files(admin_user: dict = Depends(require_admin)):
    """获取所有文件（管理员）"""
    files = database.get_all_files()
    return JSONResponse(content=files)

@app.delete("/api/admin/files/{file_id}")
async def admin_delete_file(
    file_id: int,
    admin_user: dict = Depends(require_admin)
):
    """删除任意文件（管理员）"""
    success = database.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return JSONResponse(content={"success": True, "message": "文件已删除"})

@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    admin_user: dict = Depends(require_admin)
):
    """删除用户（管理员）"""
    if user_id == admin_user['id']:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    success = database.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return JSONResponse(content={"success": True, "message": "用户已删除"})

@app.post("/api/admin/users/{user_id}/admin")
async def admin_set_admin_status(
    user_id: int,
    is_admin: bool = Form(...),
    admin_user: dict = Depends(require_admin)
):
    """设置用户管理员状态（管理员）"""
    if user_id == admin_user['id']:
        raise HTTPException(status_code=400, detail="不能修改自己的管理员状态")
    
    success = database.update_user_admin_status(user_id, is_admin)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return JSONResponse(content={"success": True, "message": "用户权限已更新"})

# 统计信息
@app.get("/api/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """获取用户统计信息"""
    files = database.get_user_files(current_user['id'])
    total_size = sum(file['size'] for file in files)
    
    return JSONResponse(content={
        "file_count": len(files),
        "total_size": total_size,
        "total_size_formatted": f"{total_size / (1024*1024):.2f} MB"
    })

@app.get("/api/admin/stats")
async def get_admin_stats(admin_user: dict = Depends(require_admin)):
    """获取管理员统计信息"""
    users = database.get_all_users()
    files = database.get_all_files()
    
    total_size = sum(file['size'] for file in files)
    active_users = len(users)
    
    return JSONResponse(content={
        "user_count": active_users,
        "file_count": len(files),
        "total_size": total_size,
        "total_size_formatted": f"{total_size / (1024*1024):.2f} MB"
    })

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return JSONResponse(content={"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)