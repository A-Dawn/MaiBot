"""
SQLModel 数据库使用示例

本文件展示如何在重构后的代码中使用 SQLModel 进行数据库操作。

Session 管理说明:
- 方式1 (推荐): 使用 get_session() - 自动提交,无需手动 commit
- 方式2 (高级): 使用 get_session(auto_commit=False) 或 get_session_manual() - 手动控制事务
"""

from src.common.database.database import get_session, get_session_manual
from src.common.database.database_model import (
    ChatStreams,
    Messages,
    PersonInfo,
    Emoji,
)
from sqlmodel import select
import time


def example_create_chat_stream():
    """示例: 创建聊天流记录 (自动提交模式 - 推荐)"""
    with get_session() as session:
        chat_stream = ChatStreams(
            stream_id="example_stream_001",
            create_time=time.time(),
            platform="qq",
            user_platform="qq",
            user_id="123456",
            user_nickname="测试用户",
            last_active_time=time.time(),
        )
        session.add(chat_stream)
        # 无需 session.commit() - 退出时自动提交
        
        # 如果需要获取自增 ID,在退出前刷新
        session.flush()  # 刷新以获取 ID,但不提交
        print(f"创建聊天流成功,ID: {chat_stream.id}")
        return chat_stream


def example_query_chat_streams():
    """示例: 查询聊天流"""
    with get_session() as session:
        # 查询所有
        statement = select(ChatStreams)
        all_streams = session.exec(statement).all()
        print(f"共有 {len(all_streams)} 个聊天流")
        
        # 条件查询
        statement = select(ChatStreams).where(ChatStreams.platform == "qq")
        qq_streams = session.exec(statement).all()
        print(f"QQ 平台聊天流: {len(qq_streams)} 个")
        
        # 获取单条记录
        statement = select(ChatStreams).where(
            ChatStreams.stream_id == "example_stream_001"
        )
        stream = session.exec(statement).first()
        if stream:
            print(f"找到聊天流: {stream.user_nickname}")


def example_update_chat_stream():
    """示例: 更新聊天流 (自动提交)"""
    with get_session() as session:
        # 查询记录
        statement = select(ChatStreams).where(
            ChatStreams.stream_id == "example_stream_001"
        )
        stream = session.exec(statement).first()
        
        if stream:
            # 更新字段
            stream.user_nickname = "更新后的昵称"
            stream.last_active_time = time.time()
            
            # 保存更改 (无需 commit,自动提交)
            session.add(stream)
            print("聊天流更新成功")


def example_delete_chat_stream():
    """示例: 删除聊天流 (自动提交)"""
    with get_session() as session:
        statement = select(ChatStreams).where(
            ChatStreams.stream_id == "example_stream_001"
        )
        stream = session.exec(statement).first()
        
        if stream:
            session.delete(stream)
            # 无需 commit,自动提交
            print("聊天流删除成功")


def example_batch_insert():
    """示例: 批量插入 (自动提交)"""
    with get_session() as session:
        emojis = [
            Emoji(
                full_path=f"/path/to/emoji{i}.png",
                format="png",
                emoji_hash=f"hash_{i}",
                description=f"表情{i}",
                record_time=time.time(),
            )
            for i in range(5)
        ]
        
        session.add_all(emojis)
        # 无需 commit,自动提交
        print(f"批量插入 {len(emojis)} 个表情包")


def example_complex_query():
    """示例: 复杂查询"""
    with get_session() as session:
        # 连接查询 (如果有外键关系)
        # 这里展示基本的过滤和排序
        statement = (
            select(Messages)
            .where(Messages.is_command.is_(False))
            .order_by(Messages.time.desc())
            .limit(10)
        )
        recent_messages = session.exec(statement).all()
        print(f"最近 {len(recent_messages)} 条非命令消息")


def example_transaction():
    """示例: 事务处理 (手动提交模式)"""
    # 方式1: 使用 auto_commit=False
    with get_session(auto_commit=False) as session:
        try:
            # 创建多个相关记录
            person = PersonInfo(
                person_id="person_001",
                platform="qq",
                user_id="123456",
                is_known=True,
                person_name="张三",
            )
            session.add(person)
            
            # 如果这里发生错误,所有更改都会回滚
            chat_stream = ChatStreams(
                stream_id="stream_002",
                create_time=time.time(),
                platform="qq",
                user_platform="qq",
                user_id="123456",
                user_nickname="张三",
                last_active_time=time.time(),
            )
            session.add(chat_stream)
            
            # 手动提交所有更改
            session.commit()
            print("事务提交成功 (方式1: auto_commit=False)")
            
        except Exception as e:
            # 发生错误时会自动回滚
            print(f"事务回滚: {e}")
            raise


def example_transaction_manual():
    """示例: 事务处理 (使用 get_session_manual)"""
    # 方式2: 使用 get_session_manual() - 更明确的语义
    with get_session_manual() as session:
        try:
            person = PersonInfo(
                person_id="person_002",
                platform="qq",
                user_id="654321",
                is_known=False,
                person_name="李四",
            )
            session.add(person)
            
            # 手动提交
            session.commit()
            print("事务提交成功 (方式2: get_session_manual)")
            
        except Exception as e:
            session.rollback()
            print(f"事务回滚: {e}")
            raise


def example_count_and_aggregation():
    """示例: 计数和聚合"""
    from sqlalchemy import func
    
    with get_session() as session:
        # 计数
        statement = select(func.count(Messages.id))
        total_messages = session.exec(statement).one()
        print(f"总消息数: {total_messages}")
        
        # 按平台分组计数
        statement = select(
            ChatStreams.platform,
            func.count(ChatStreams.id).label("count")
        ).group_by(ChatStreams.platform)
        
        results = session.exec(statement).all()
        for platform, count in results:
            print(f"平台 {platform}: {count} 个聊天流")


def example_pagination():
    """示例: 分页查询"""
    with get_session() as session:
        page = 1
        page_size = 20
        
        statement = (
            select(Messages)
            .order_by(Messages.time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        messages = session.exec(statement).all()
        print(f"第 {page} 页,共 {len(messages)} 条消息")


if __name__ == "__main__":
    print("=== SQLModel 使用示例 ===\n")
    print("Session 管理模式:")
    print("- 自动提交 (推荐): 大部分示例使用此模式,无需手动 commit")
    print("- 手动提交 (高级): example_transaction() 和 example_transaction_manual()\n")
    
    # 运行示例 (谨慎使用,会修改数据库)
    # example_create_chat_stream()
    # example_query_chat_streams()
    # example_update_chat_stream()
    # example_batch_insert()
    # example_complex_query()
    # example_transaction()
    # example_transaction_manual()
    # example_count_and_aggregation()
    # example_pagination()
    
    print("\n请取消注释相应的函数调用来运行示例")
