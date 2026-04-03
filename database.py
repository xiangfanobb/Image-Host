import sqlite3
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "database.db"

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT 0
        )
    ''')
    
    # 创建文件表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            size INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            url TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 创建唯一索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_uploaded_at ON files(uploaded_at DESC)')
    
    # 创建默认管理员账户（如果不存在）
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE username = 'admin'")
    if cursor.fetchone()['count'] == 0:
        # 默认密码：admin123
        password_hash = hash_password('admin123')
        cursor.execute(
            'INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
            ('admin', 'admin@localhost', password_hash, 1)
        )
        print("创建默认管理员账户: admin / admin123")
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """哈希密码"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return f"{salt}:{hash_obj.hexdigest()}"

def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    if ':' not in password_hash:
        return False
    salt, stored_hash = password_hash.split(':', 1)
    hash_obj = hashlib.sha256((password + salt).encode())
    return hash_obj.hexdigest() == stored_hash

def create_user(username: str, email: str, password: str, is_admin: bool = False) -> int:
    """创建新用户"""
    password_hash = hash_password(password)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
            (username, email, password_hash, 1 if is_admin else 0)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError as e:
        raise ValueError("用户名或邮箱已存在") from e
    finally:
        conn.close()

def get_user_by_username(username: str):
    """根据用户名获取用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id: int):
    """根据ID获取用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def add_file(filename: str, original_name: str, user_id: int, size: int, url: str) -> int:
    """添加文件记录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO files (filename, original_name, user_id, size, url) VALUES (?, ?, ?, ?, ?)',
        (filename, original_name, user_id, size, url)
    )
    file_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return file_id

def get_user_files(user_id: int, limit: int = 100, offset: int = 0):
    """获取用户文件列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, filename, original_name, user_id, size, 
               CAST(strftime('%s', uploaded_at) AS INTEGER) as uploaded_at, 
               url 
        FROM files 
        WHERE user_id = ? 
        ORDER BY uploaded_at DESC 
        LIMIT ? OFFSET ?
    ''', (user_id, limit, offset))
    files = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return files

def get_all_files(limit: int = 100, offset: int = 0):
    """获取所有文件列表（管理员用）"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT f.id, f.filename, f.original_name, f.user_id, f.size, 
               CAST(strftime('%s', f.uploaded_at) AS INTEGER) as uploaded_at, 
               f.url, u.username 
        FROM files f 
        LEFT JOIN users u ON f.user_id = u.id 
        ORDER BY f.uploaded_at DESC 
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    files = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return files

def get_all_users(limit: int = 100, offset: int = 0):
    """获取所有用户列表（管理员用）"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, email, 
               CAST(strftime('%s', created_at) AS INTEGER) as created_at, 
               is_admin 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def delete_file(file_id: int, user_id: int = None) -> bool:
    """删除文件记录，如果指定user_id则只删除该用户的文件"""
    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        cursor.execute('DELETE FROM files WHERE id = ? AND user_id = ?', (file_id, user_id))
    else:
        cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def delete_user(user_id: int) -> bool:
    """删除用户及其所有文件"""
    conn = get_db()
    cursor = conn.cursor()
    # 先删除用户的文件
    cursor.execute('DELETE FROM files WHERE user_id = ?', (user_id,))
    # 再删除用户
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def update_user_admin_status(user_id: int, is_admin: bool) -> bool:
    """更新用户管理员状态"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_admin = ? WHERE id = ?', (1 if is_admin else 0, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

# 初始化数据库
if __name__ == "__main__":
    init_db()
    print("数据库初始化完成")