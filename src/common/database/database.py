"""
数据库连接模块

本模块使用 SQLModel (基于 SQLAlchemy) 管理 SQLite 数据库连接。
提供全局的数据库引擎和会话管理功能。
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from rich.traceback import install

install(extra_lines=3)


# 定义数据库文件路径
ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB_DIR = os.path.join(ROOT_PATH, "data")
_DB_FILE = os.path.join(_DB_DIR, "MaiBot.db")

# 确保数据库目录存在
os.makedirs(_DB_DIR, exist_ok=True)

# 构建 SQLite 数据库 URL
DATABASE_URL = f"sqlite:///{_DB_FILE}"


# SQLite 特定的配置 - 启用 WAL 模式和其他性能优化
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    为每个新的数据库连接设置 SQLite PRAGMA。
    
    这些设置优化了并发性能和数据安全性:
    - journal_mode=WAL: 启用预写式日志,提高并发性能
    - cache_size: 设置缓存大小为 64MB
    - foreign_keys: 启用外键约束
    - synchronous=NORMAL: 平衡性能和数据安全
    - busy_timeout: 设置1秒超时,避免锁定冲突
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 负值表示KB,64000KB = 64MB
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")  # NORMAL 模式在WAL下是安全的
    cursor.execute("PRAGMA busy_timeout=1000")  # 1秒超时
    cursor.close()


# 创建全局数据库引擎
# echo=False 表示不打印SQL语句,生产环境建议关闭
# pool_pre_ping=True 确保连接池中的连接有效
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite 多线程支持
    pool_pre_ping=True,  # 在使用连接前检查连接是否有效
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@contextmanager
def get_session(auto_commit: bool = True) -> Generator[Session, None, None]:
    """
    获取数据库会话的上下文管理器 (推荐使用,自动提交)。
    
    使用示例:
        # 方式1: 自动提交 (推荐 - 默认行为)
        with get_session() as session:
            user = User(name="张三", age=25)
            session.add(user)
            # 退出时自动 commit,无需手动调用
        
        # 方式2: 手动控制事务 (高级用法)
        with get_session(auto_commit=False) as session:
            user1 = User(name="张三", age=25)
            user2 = User(name="李四", age=30)
            session.add_all([user1, user2])
            session.commit()  # 手动提交
    
    Args:
        auto_commit: 是否在退出上下文时自动提交。
                    True (默认): 自动提交,适合大多数场景
                    False: 手动控制,适合复杂事务
    
    Yields:
        Session: SQLAlchemy 数据库会话
        
    注意:
        - 会话会在退出上下文时自动关闭
        - 如果发生异常,会自动回滚事务
        - auto_commit=True 时,成功执行完会自动提交
        - auto_commit=False 时,需要手动调用 session.commit()
    """
    session = SessionLocal()
    try:
        yield session
        # 如果启用自动提交且没有异常,则提交事务
        if auto_commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_session_manual() -> Generator[Session, None, None]:
    """
    获取数据库会话的上下文管理器 (手动提交模式)。
    
    这是 get_session(auto_commit=False) 的便捷别名。
    适合需要精确控制事务的高级场景。
    
    使用示例:
        with get_session_manual() as session:
            try:
                user1 = User(name="张三")
                session.add(user1)
                
                # 中间可能有复杂的业务逻辑
                
                user2 = User(name="李四")
                session.add(user2)
                
                # 手动提交
                session.commit()
            except Exception:
                session.rollback()
                raise
    
    Yields:
        Session: SQLAlchemy 数据库会话
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的生成器函数。
    
    适用于依赖注入场景(如 FastAPI)。
    
    使用示例 (FastAPI):
        @app.get("/users/{user_id}")
        def read_user(user_id: int, db: Session = Depends(get_db)):
            return db.get(User, user_id)
    
    Yields:
        Session: SQLAlchemy 数据库会话
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# 向后兼容的别名 (如果其他代码使用 db 变量)
# 注意: SQLModel 不像 Peewee 那样使用单一的 db 对象
# 而是使用 engine 和 session,但为了平滑迁移,保留此引用
db = engine
