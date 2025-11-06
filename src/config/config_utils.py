from dataclasses import fields, Field
from typing import Any, get_args, get_origin, TYPE_CHECKING, Literal
from tomlkit import items
import tomlkit

from .config_base import ConfigBase

if TYPE_CHECKING:
    from .config import AttributeData


def recursive_parse_item_to_table(config: ConfigBase, is_inline_table: bool = False) -> items.Table | items.InlineTable:
    # sourcery skip: merge-else-if-into-elif, reintroduce-else
    """递归解析配置项为表格"""
    config_table = tomlkit.table()
    if is_inline_table:
        config_table = tomlkit.inline_table()
    for config_item in fields(config):
        if not config_item.repr:
            continue
        value = getattr(config, config_item.name)
        if isinstance(value, ConfigBase):
            config_table.add(config_item.name, recursive_parse_item_to_table(value))
        else:
            config_table.add(config_item.name, convert_field(config_item, value))
        if not is_inline_table:
            config_table = comment_doc_string(config, config_item.name, config_table)
    return config_table


def comment_doc_string(
    config: ConfigBase, field_name: str, toml_table: items.Table | items.InlineTable
) -> items.Table | items.InlineTable:
    """将配置类中的注释加入toml表格中"""
    if doc_string := config.field_docs.get(field_name, ""):
        doc_string_splitted = doc_string.splitlines()
        if len(doc_string_splitted) == 1:
            if isinstance(toml_table[field_name], bool):
                # tomlkit 故意设计的行为，布尔值不能直接添加注释
                value = toml_table[field_name]
                item = tomlkit.item(value)
                item.comment(doc_string_splitted[0])
                toml_table[field_name] = item
            else:
                toml_table[field_name].comment(doc_string_splitted[0])
        else:
            for line in doc_string_splitted:
                toml_table.add(tomlkit.comment(line))
            toml_table.add(tomlkit.nl())
    return toml_table


def convert_field(config_item: Field[Any], value: Any):
    # sourcery skip: extract-method
    """将非可直接表达类转换为toml可表达类"""
    field_type_origin = get_origin(config_item.type)
    field_type_args = get_args(config_item.type)

    if not field_type_origin:  # 基础类型int,bool等直接添加
        return value
    elif field_type_origin in {list, set}:
        toml_list = tomlkit.array()
        if field_type_args and isinstance(field_type_args[0], type) and issubclass(field_type_args[0], ConfigBase):
            for item in value:
                toml_list.append(recursive_parse_item_to_table(item, True))
        else:
            for item in value:
                toml_list.append(item)
        return toml_list
    elif field_type_origin is tuple:
        toml_list = tomlkit.array()
        for field_arg, item in zip(field_type_args, value, strict=True):
            if isinstance(field_arg, type) and issubclass(field_arg, ConfigBase):
                toml_list.append(recursive_parse_item_to_table(item, True))
            else:
                toml_list.append(item)
        return toml_list
    elif field_type_origin is dict:
        if len(field_type_args) != 2:
            raise TypeError(f"Expected a dictionary with two type arguments for {config_item.name}")
        toml_sub_table = tomlkit.inline_table()
        key_type, value_type = field_type_args
        if key_type is not str:
            raise TypeError(f"TOML only supports string keys for tables, got {key_type} for {config_item.name}")
        for k, v in value.items():
            if isinstance(value_type, type) and issubclass(value_type, ConfigBase):
                toml_sub_table.add(k, recursive_parse_item_to_table(v, True))
            else:
                toml_sub_table.add(k, v)
        return toml_sub_table
    elif field_type_origin is Literal:
        if value not in field_type_args:
            raise ValueError(f"Value {value} not in Literal options {field_type_args} for {config_item.name}")
        return value
    else:
        raise TypeError(f"Unsupported field type for {config_item.name}: {config_item.type}")


def output_config_changes(attr_data: "AttributeData", logger, old_ver: str, new_ver: str, file_name: str):
    """输出配置变更信息"""
    logger.info("-------- 配置文件变更信息 --------")
    logger.info(f"新增配置数量: {len(attr_data.missing_attributes)}")
    for attr in attr_data.missing_attributes:
        logger.info(f"配置文件中新增配置项: {attr}")
    logger.info(f"移除配置数量: {len(attr_data.redundant_attributes)}")
    for attr in attr_data.redundant_attributes:
        logger.warning(f"移除配置项: {attr}")
    logger.info(
        f"{file_name}配置文件已经更新. Old: {old_ver} -> New: {new_ver} 建议检查新配置文件中的内容, 以免丢失重要信息"
    )


def compare_versions(old_ver: str, new_ver: str) -> bool:
    """比较版本号，返回是否有更新"""
    old_parts = [int(part) for part in old_ver.split(".")]
    new_parts = [int(part) for part in new_ver.split(".")]
    return new_parts > old_parts
