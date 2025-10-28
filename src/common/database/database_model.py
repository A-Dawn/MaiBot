"""
数据库模型定义模块

本模块使用 SQLModel (基于 Pydantic 和 SQLAlchemy) 定义所有数据库表模型。
SQLModel 提供了类型安全、数据验证和现代化的 ORM 功能。
"""

import datetime
import uuid
from typing import Optional

from sqlalchemy import Column, Float, inspect
from sqlmodel import Field, SQLModel

from .database import engine, get_session
from src.common.logger import get_logger

logger = get_logger("database_model")


# ==================== 数据库模型定义 ====================


class ChatStreams(SQLModel, table=True):
    """
    流式聊天记录模型。
    
    存储聊天流的基本信息,包括用户信息、群组信息和时间戳。
    """
    __tablename__ = "chat_streams"
    
    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # stream_id: 唯一的流标识符
    stream_id: str = Field(unique=True, index=True, max_length=255)
    
    # create_time: 创建时间戳 (浮点数,支持小数)
    create_time: float = Field(sa_column=Column(Float))
    
    # 群组信息 (可选)
    group_platform: Optional[str] = Field(default=None, max_length=255)
    group_id: Optional[str] = Field(default=None, max_length=255)
    group_name: Optional[str] = Field(default=None, max_length=255)
    
    # 最后活跃时间
    last_active_time: float = Field(sa_column=Column(Float))
    
    # 平台信息
    platform: str = Field(max_length=255)
    
    # 用户信息
    user_platform: str = Field(max_length=255)
    user_id: str = Field(max_length=255)
    user_nickname: str = Field(max_length=255)
    user_cardname: Optional[str] = Field(default=None, max_length=255)


class LLMUsage(SQLModel, table=True):
    """
    LLM API 使用日志模型。
    
    记录每次 API 调用的详细信息,包括 token 使用量、成本和性能数据。
    """
    __tablename__ = "llm_usage"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    model_name: str = Field(index=True, max_length=255)
    model_assign_name: Optional[str] = Field(default=None, max_length=255)
    model_api_provider: Optional[str] = Field(default=None, max_length=255)
    user_id: str = Field(index=True, max_length=255)
    request_type: str = Field(index=True, max_length=255)
    endpoint: str = Field(max_length=500)
    
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    cost: float = Field(sa_column=Column(Float))
    time_cost: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    
    status: str = Field(max_length=255)
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now, index=True)


class Emoji(SQLModel, table=True):
    """
    表情包模型。
    
    管理表情包资源,包括路径、描述、使用统计等信息。
    """
    __tablename__ = "emoji"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    full_path: str = Field(unique=True, index=True, max_length=500)
    format: str = Field(max_length=50)
    emoji_hash: str = Field(index=True, max_length=255)
    description: str
    
    query_count: int = Field(default=0)
    is_registered: bool = Field(default=False)
    is_banned: bool = Field(default=False)
    
    # 情感标签 (存储为文本,应用层序列化/反序列化)
    emotion: Optional[str] = Field(default=None)
    
    record_time: float = Field(sa_column=Column(Float))
    register_time: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    usage_count: int = Field(default=0)
    last_used_time: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))


class Messages(SQLModel, table=True):
    """
    消息记录模型。
    
    存储完整的消息数据,包括消息内容、发送者信息、处理信息等。
    """
    __tablename__ = "messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    message_id: str = Field(index=True, max_length=255)
    time: float = Field(sa_column=Column(Float))
    
    chat_id: str = Field(index=True, max_length=255)
    reply_to: Optional[str] = Field(default=None, max_length=255)
    
    interest_value: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    key_words: Optional[str] = Field(default=None)
    key_words_lite: Optional[str] = Field(default=None)
    
    is_mentioned: Optional[bool] = Field(default=None)
    is_at: Optional[bool] = Field(default=None)
    reply_probability_boost: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    
    # chat_info 扁平化字段
    chat_info_stream_id: str = Field(max_length=255)
    chat_info_platform: str = Field(max_length=255)
    chat_info_user_platform: str = Field(max_length=255)
    chat_info_user_id: str = Field(max_length=255)
    chat_info_user_nickname: str = Field(max_length=255)
    chat_info_user_cardname: Optional[str] = Field(default=None, max_length=255)
    chat_info_group_platform: Optional[str] = Field(default=None, max_length=255)
    chat_info_group_id: Optional[str] = Field(default=None, max_length=255)
    chat_info_group_name: Optional[str] = Field(default=None, max_length=255)
    chat_info_create_time: float = Field(sa_column=Column(Float))
    chat_info_last_active_time: float = Field(sa_column=Column(Float))
    
    # 用户信息
    user_platform: Optional[str] = Field(default=None, max_length=255)
    user_id: Optional[str] = Field(default=None, max_length=255)
    user_nickname: Optional[str] = Field(default=None, max_length=255)
    user_cardname: Optional[str] = Field(default=None, max_length=255)
    
    processed_plain_text: Optional[str] = Field(default=None)
    display_message: Optional[str] = Field(default=None)
    
    priority_mode: Optional[str] = Field(default=None, max_length=255)
    priority_info: Optional[str] = Field(default=None)
    
    additional_config: Optional[str] = Field(default=None)
    is_emoji: bool = Field(default=False)
    is_picid: bool = Field(default=False)
    is_command: bool = Field(default=False)
    is_notify: bool = Field(default=False)
    
    selected_expressions: Optional[str] = Field(default=None)


class ActionRecords(SQLModel, table=True):
    """
    动作记录模型。
    
    记录系统执行的各种动作及其详细信息。
    """
    __tablename__ = "action_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    action_id: str = Field(index=True, max_length=255)
    time: float = Field(sa_column=Column(Float))
    
    action_reasoning: Optional[str] = Field(default=None)
    action_name: str = Field(max_length=255)
    action_data: str
    action_done: bool = Field(default=False)
    
    action_build_into_prompt: bool = Field(default=False)
    action_prompt_display: str
    
    chat_id: str = Field(index=True, max_length=255)
    chat_info_stream_id: str = Field(max_length=255)
    chat_info_platform: str = Field(max_length=255)


class Images(SQLModel, table=True):
    """
    图像信息模型。
    
    管理图像资源的元数据和使用统计。
    """
    __tablename__ = "images"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    image_id: str = Field(default="", max_length=255)
    emoji_hash: str = Field(index=True, max_length=255)
    description: Optional[str] = Field(default=None)
    path: str = Field(unique=True, max_length=500)
    
    count: int = Field(default=1)
    timestamp: float = Field(sa_column=Column(Float))
    type: str = Field(max_length=50)
    vlm_processed: bool = Field(default=False)


class ImageDescriptions(SQLModel, table=True):
    """
    图像描述模型。
    
    存储图像的描述信息,用于图像检索和识别。
    """
    __tablename__ = "image_descriptions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    type: str = Field(max_length=50)
    image_description_hash: str = Field(index=True, max_length=255)
    description: str
    timestamp: float = Field(sa_column=Column(Float))


class OnlineTime(SQLModel, table=True):
    """
    在线时长记录模型。
    
    追踪系统的在线时长统计。
    """
    __tablename__ = "online_time"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    duration: int  # 时长,单位:分钟
    start_timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)
    end_timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now, index=True)


class PersonInfo(SQLModel, table=True):
    """
    个人信息模型。
    
    存储用户的个人资料和印象信息。
    """
    __tablename__ = "person_info"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    is_known: bool = Field(default=False)
    person_id: str = Field(unique=True, index=True, max_length=255)
    person_name: Optional[str] = Field(default=None, max_length=255)
    name_reason: Optional[str] = Field(default=None)
    
    platform: str = Field(max_length=255)
    user_id: str = Field(index=True, max_length=255)
    nickname: Optional[str] = Field(default=None, max_length=255)
    
    memory_points: Optional[str] = Field(default=None)
    know_times: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    know_since: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    last_know: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))


class GroupInfo(SQLModel, table=True):
    """
    群组信息模型。
    
    管理群组的基本信息和统计数据。
    """
    __tablename__ = "group_info"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    group_id: str = Field(unique=True, index=True, max_length=255)
    group_name: Optional[str] = Field(default=None, max_length=255)
    platform: str = Field(max_length=255)
    
    group_impression: Optional[str] = Field(default=None)
    member_list: Optional[str] = Field(default=None)  # JSON 格式
    topic: Optional[str] = Field(default=None)
    
    create_time: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    last_active: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    member_count: Optional[int] = Field(default=0)


class Expression(SQLModel, table=True):
    """
    表达风格模型。
    
    记录不同场景下的表达方式和风格。
    """
    __tablename__ = "expression"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    situation: str = Field(max_length=255)
    style: str
    count: float = Field(sa_column=Column(Float))
    
    # 新模式字段
    context: Optional[str] = Field(default=None)
    context_words: Optional[str] = Field(default=None)
    
    last_active_time: float = Field(sa_column=Column(Float))
    chat_id: str = Field(index=True, max_length=255)
    type: str = Field(max_length=50)
    create_date: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))


class MemoryChest(SQLModel, table=True):
    """
    记忆仓库模型。
    
    存储重要的记忆内容。
    """
    __tablename__ = "memory_chest"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    title: str = Field(max_length=255)
    content: str
    chat_id: Optional[str] = Field(default=None, max_length=255)
    locked: bool = Field(default=False)


class MemoryConflict(SQLModel, table=True):
    """
    记忆冲突模型。
    
    记录记忆整合过程中的冲突及其解决方案。
    """
    __tablename__ = "memory_conflicts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    conflict_content: str
    answer: Optional[str] = Field(default=None)
    create_time: float = Field(sa_column=Column(Float))
    update_time: float = Field(sa_column=Column(Float))
    context: Optional[str] = Field(default=None)
    chat_id: Optional[str] = Field(default=None, max_length=255)
    raise_time: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))


# ==================== 数据库初始化和维护函数 ====================


def create_tables() -> None:
    """
    创建所有在模型中定义的数据库表。
    
    使用 SQLModel 的元数据机制自动创建所有表结构。
    """
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("所有数据库表创建成功")
    except Exception as e:
        logger.exception(f"创建数据库表时出错: {e}")
        raise


def initialize_database(sync_constraints: bool = False) -> None:
    """
    初始化数据库,检查并创建缺失的表和字段。
    
    Args:
        sync_constraints: 是否同步字段约束。默认为 False。
                         如果为 True,会检查并修复字段的 NULL 约束不一致问题。
    
    功能:
        1. 检查所有模型对应的表是否存在
        2. 如果表不存在,则创建
        3. 检查现有表的字段是否完整
        4. 自动添加缺失的字段
        5. (可选) 同步字段约束
    """
    models = [
        ChatStreams,
        LLMUsage,
        Emoji,
        Messages,
        Images,
        ImageDescriptions,
        OnlineTime,
        PersonInfo,
        GroupInfo,
        Expression,
        ActionRecords,
        MemoryChest,
        MemoryConflict,
    ]

    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        for model in models:
            table_name = model.__tablename__
            
            # 检查表是否存在
            if table_name not in existing_tables:
                logger.warning(f"表 '{table_name}' 未找到,正在创建...")
                model.metadata.create_all(engine, tables=[model.__table__])
                logger.info(f"表 '{table_name}' 创建成功")
                continue
            
            # 检查字段
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            model_fields = set(model.__fields__.keys())
            
            # 移除 SQLModel 内部字段
            model_fields.discard('id')
            
            missing_fields = model_fields - existing_columns
            
            if missing_fields:
                logger.warning(f"表 '{table_name}' 缺失字段: {missing_fields}")
                _add_missing_columns(table_name, model, missing_fields)
            
            # 检查多余字段
            extra_fields = existing_columns - model_fields - {'id'}
            if extra_fields:
                logger.warning(f"表 '{table_name}' 存在多余字段: {extra_fields}")
                _remove_extra_columns(table_name, extra_fields)
        
        # 如果启用了约束同步
        if sync_constraints:
            logger.debug("开始同步数据库字段约束...")
            sync_field_constraints()
            logger.debug("数据库字段约束同步完成")
            
    except Exception as e:
        logger.exception(f"初始化数据库时出错: {e}")
        return
    
    logger.info("数据库初始化完成")


def _add_missing_columns(table_name: str, model: type[SQLModel], missing_fields: set[str]) -> None:
    """
    为表添加缺失的字段。
    
    Args:
        table_name: 表名
        model: SQLModel 模型类
        missing_fields: 缺失的字段名集合
    """
    with engine.begin() as conn:
        for field_name in missing_fields:
            if field_name not in model.__fields__:
                continue
                
            field_info = model.__fields__[field_name]
            field_type = field_info.type_
            
            # 获取 SQL 类型 (使用 is 进行类型比较)
            if field_type is str:
                sql_type = 'TEXT'
            elif field_type is int:
                sql_type = 'INTEGER'
            elif field_type is float:
                sql_type = 'REAL'
            elif field_type is bool:
                sql_type = 'INTEGER'
            elif field_type is datetime.datetime:
                sql_type = 'DATETIME'
            else:
                sql_type = 'TEXT'
            
            # 构建 ALTER TABLE 语句
            nullable = "NULL" if field_info.allow_none else "NOT NULL"
            
            # 获取默认值
            default_clause = ""
            if field_info.default is not None and not callable(field_info.default):
                if isinstance(field_info.default, str):
                    default_clause = f" DEFAULT '{field_info.default}'"
                elif isinstance(field_info.default, bool):
                    default_clause = f" DEFAULT {int(field_info.default)}"
                elif isinstance(field_info.default, (int, float)):
                    default_clause = f" DEFAULT {field_info.default}"
            
            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {field_name} {sql_type} {nullable}{default_clause}"
            
            try:
                conn.execute(alter_sql)
                logger.info(f"字段 '{field_name}' 添加到表 '{table_name}' 成功")
            except Exception as e:
                logger.error(f"添加字段 '{field_name}' 到表 '{table_name}' 失败: {e}")


def _remove_extra_columns(table_name: str, extra_fields: set[str]) -> None:
    """
    删除表中的多余字段。
    
    Args:
        table_name: 表名
        extra_fields: 多余的字段名集合
    
    注意:
        SQLite 不支持直接删除列,需要重建表。
        此功能仅记录警告,不执行实际删除操作。
    """
    for field_name in extra_fields:
        logger.warning(
            f"表 '{table_name}' 存在多余字段 '{field_name}'。"
            f"SQLite 不支持删除列,请手动处理或重建表。"
        )


def sync_field_constraints() -> None:
    """
    同步数据库字段约束,确保现有数据库字段的 NULL 约束与模型定义一致。
    
    如果发现不一致,会自动修复字段约束。
    """
    models = [
        ChatStreams,
        LLMUsage,
        Emoji,
        Messages,
        Images,
        ImageDescriptions,
        OnlineTime,
        PersonInfo,
        GroupInfo,
        Expression,
        ActionRecords,
        MemoryChest,
        MemoryConflict,
    ]

    try:
        inspector = inspect(engine)
        
        for model in models:
            table_name = model.__tablename__
            
            if table_name not in inspector.get_table_names():
                logger.warning(f"表 '{table_name}' 不存在,跳过约束检查")
                continue
            
            logger.debug(f"检查表 '{table_name}' 的字段约束...")
            
            # 获取当前表结构
            current_schema = {
                col['name']: col 
                for col in inspector.get_columns(table_name)
            }
            
            constraints_to_fix = []
            
            # 检查每个字段的约束
            for field_name, field_info in model.__fields__.items():
                if field_name not in current_schema:
                    continue
                
                current_nullable = current_schema[field_name]['nullable']
                model_allows_null = field_info.allow_none
                
                # 约束不一致
                if model_allows_null and not current_nullable:
                    constraints_to_fix.append({
                        'field_name': field_name,
                        'action': 'allow_null',
                        'current': 'NOT NULL',
                        'target': 'NULL'
                    })
                elif not model_allows_null and current_nullable:
                    constraints_to_fix.append({
                        'field_name': field_name,
                        'action': 'disallow_null',
                        'current': 'NULL',
                        'target': 'NOT NULL'
                    })
            
            if constraints_to_fix:
                logger.info(f"表 '{table_name}' 需要修复 {len(constraints_to_fix)} 个字段约束")
                _fix_table_constraints(table_name, model, constraints_to_fix)
            else:
                logger.debug(f"表 '{table_name}' 的字段约束已同步")
                
    except Exception as e:
        logger.exception(f"同步字段约束时出错: {e}")


def _fix_table_constraints(
    table_name: str, 
    model: type[SQLModel], 
    constraints_to_fix: list[dict]
) -> None:
    """
    修复表的字段约束。
    
    对于 SQLite,由于不支持直接修改列约束,需要重建表。
    
    Args:
        table_name: 表名
        model: SQLModel 模型类
        constraints_to_fix: 需要修复的约束列表
    """
    try:
        backup_table = f"{table_name}_backup_{int(datetime.datetime.now().timestamp())}"
        
        logger.info(f"开始修复表 '{table_name}' 的字段约束...")
        
        with engine.begin() as conn:
            # 1. 创建备份表
            conn.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM {table_name}")
            logger.info(f"已创建备份表 '{backup_table}'")
            
            # 2. 删除原表
            conn.execute(f"DROP TABLE {table_name}")
            logger.info(f"已删除原表 '{table_name}'")
        
        # 3. 重新创建表
        model.metadata.create_all(engine, tables=[model.__table__])
        logger.info(f"已重新创建表 '{table_name}'")
        
        # 4. 恢复数据
        fields = list(model.__fields__.keys())
        fields_str = ", ".join(fields)
        
        # 处理 NULL 到 NOT NULL 的字段
        null_to_notnull = [c['field_name'] for c in constraints_to_fix if c['action'] == 'disallow_null']
        
        with engine.begin() as conn:
            if null_to_notnull:
                logger.warning(f"字段 {null_to_notnull} 将从允许 NULL 改为不允许 NULL")
                
                # 构建 COALESCE 语句处理 NULL 值
                select_fields = []
                for field_name in fields:
                    if field_name in null_to_notnull:
                        field_info = model.__fields__[field_name]
                        field_type = field_info.type_
                        
                        if field_type is str:
                            default = "''"
                        elif field_type in (int, float):
                            default = "0"
                        elif field_type is bool:
                            default = "0"
                        elif field_type is datetime.datetime:
                            default = f"'{datetime.datetime.now()}'"
                        else:
                            default = "''"
                        
                        select_fields.append(f"COALESCE({field_name}, {default}) as {field_name}")
                    else:
                        select_fields.append(field_name)
                
                select_str = ", ".join(select_fields)
                insert_sql = f"INSERT INTO {table_name} ({fields_str}) SELECT {select_str} FROM {backup_table}"
            else:
                insert_sql = f"INSERT INTO {table_name} ({fields_str}) SELECT {fields_str} FROM {backup_table}"
            
            conn.execute(insert_sql)
            logger.info(f"已从备份表恢复数据到 '{table_name}'")
            
            # 5. 验证数据完整性
            original_count = conn.execute(f"SELECT COUNT(*) FROM {backup_table}").scalar()
            new_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").scalar()
            
            if original_count == new_count:
                logger.info(f"数据完整性验证通过: {original_count} 行数据")
                conn.execute(f"DROP TABLE {backup_table}")
                logger.info(f"已删除备份表 '{backup_table}'")
            else:
                logger.error(
                    f"数据完整性验证失败: 原始 {original_count} 行,新表 {new_count} 行。"
                    f"备份表 '{backup_table}' 已保留。"
                )
        
        # 记录修复的约束
        for constraint in constraints_to_fix:
            logger.info(
                f"已修复字段 '{constraint['field_name']}': "
                f"{constraint['current']} -> {constraint['target']}"
            )
            
    except Exception as e:
        logger.exception(f"修复表 '{table_name}' 约束时出错: {e}")
        raise


def check_field_constraints() -> dict[str, list[dict]]:
    """
    检查但不修复字段约束,返回不一致的字段信息。
    
    用于在修复前预览需要修复的内容。
    
    Returns:
        字典,键为表名,值为不一致字段的信息列表
    """
    models = [
        ChatStreams,
        LLMUsage,
        Emoji,
        Messages,
        Images,
        ImageDescriptions,
        OnlineTime,
        PersonInfo,
        GroupInfo,
        Expression,
        ActionRecords,
        MemoryChest,
        MemoryConflict,
    ]

    inconsistencies = {}

    try:
        inspector = inspect(engine)
        
        for model in models:
            table_name = model.__tablename__
            
            if table_name not in inspector.get_table_names():
                continue
            
            current_schema = {
                col['name']: col 
                for col in inspector.get_columns(table_name)
            }
            
            table_inconsistencies = []
            
            for field_name, field_info in model.__fields__.items():
                if field_name not in current_schema:
                    continue
                
                current_nullable = current_schema[field_name]['nullable']
                model_allows_null = field_info.allow_none
                
                if model_allows_null and not current_nullable:
                    table_inconsistencies.append({
                        'field_name': field_name,
                        'issue': 'model_allows_null_but_db_not_null',
                        'model_constraint': 'NULL',
                        'db_constraint': 'NOT NULL',
                        'recommended_action': 'allow_null'
                    })
                elif not model_allows_null and current_nullable:
                    table_inconsistencies.append({
                        'field_name': field_name,
                        'issue': 'model_not_null_but_db_allows_null',
                        'model_constraint': 'NOT NULL',
                        'db_constraint': 'NULL',
                        'recommended_action': 'disallow_null'
                    })
            
            if table_inconsistencies:
                inconsistencies[table_name] = table_inconsistencies
                
    except Exception as e:
        logger.exception(f"检查字段约束时出错: {e}")

    return inconsistencies


def fix_image_id() -> None:
    """
    修复图片表的 image_id 字段,为空的 image_id 生成 UUID。
    """
    try:
        with get_session() as session:
            # 查询所有 image_id 为空的记录
            images = session.query(Images).filter(
                (Images.image_id == "") | (Images.image_id.is_(None))
            ).all()
            
            for img in images:
                img.image_id = str(uuid.uuid4())
                logger.info(f"已为图片 {img.id} 生成新的 image_id: {img.image_id}")
            
            session.commit()
            logger.info(f"共修复 {len(images)} 条图片记录的 image_id")
            
    except Exception as e:
        logger.exception(f"修复 image_id 时出错: {e}")


# ==================== 模块初始化 ====================

# 模块加载时自动初始化数据库
try:
    initialize_database(sync_constraints=True)
    fix_image_id()
except Exception as e:
    logger.error(f"数据库模块初始化失败: {e}")
