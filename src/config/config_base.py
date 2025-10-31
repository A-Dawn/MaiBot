from dataclasses import dataclass, fields, MISSING
from typing import TypeVar, Type, Any, get_origin, get_args, Literal
from pathlib import Path
import ast
import inspect

T = TypeVar("T", bound="ConfigContentBase")

TOML_DICT_TYPE = {
    int,
    float,
    str,
    bool,
    list,
    dict,
}


@dataclass
class ConfigContentBase:
    """配置类内容控制的基类"""

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """从字典加载配置字段"""
        if not isinstance(data, dict):
            raise TypeError(f"Expected a dictionary, got {type(data).__name__}")

        init_args: dict[str, Any] = {}

        for f in fields(cls):
            field_name = f.name

            if field_name.startswith("_"):
                # 跳过以 _ 开头的字段
                continue

            if field_name not in data:
                if f.default is not MISSING or f.default_factory is not MISSING:
                    # 跳过未提供且有默认值/默认构造方法的字段
                    continue
                else:
                    raise ValueError(f"Missing required field: '{field_name}'")

            value = data[field_name]
            field_type = f.type

            try:
                assert not isinstance(field_type, str)
                init_args[field_name] = cls._convert_field(value, field_type)
            except TypeError as e:
                raise TypeError(f"Field '{field_name}' has a type error: {e}") from e
            except AssertionError:
                raise TypeError(f"Field '{field_name}' has an unsupported type: {field_type}") from None
            except Exception as e:
                raise RuntimeError(f"Failed to convert field '{field_name}' to target type: {e}") from e

        return cls(**init_args)

    @classmethod
    def _convert_field(cls, value: Any, field_type: Type[Any]) -> Any:
        # sourcery skip: low-code-quality
        """
        转换字段值为指定类型

        1. 对于嵌套的 dataclass，递归调用相应的 from_dict 方法
        2. 对于泛型集合类型（list, set, tuple），递归转换每个元素
        3. 对于基础类型（int, str, float, bool），直接转换
        4. 对于其他类型，尝试直接转换，如果失败则抛出异常
        """

        # 如果是嵌套的 dataclass，递归调用 from_dict 方法
        if isinstance(field_type, type) and issubclass(field_type, ConfigContentBase):
            if not isinstance(value, dict):
                raise TypeError(f"Expected a dictionary for {field_type.__name__}, got {type(value).__name__}")
            return field_type.from_dict(value)

        # 处理泛型集合类型（list, set, tuple）
        field_origin_type = get_origin(field_type)
        field_type_args = get_args(field_type)

        if field_origin_type in {list, set, tuple}:
            # 检查提供的value是否为list
            if not isinstance(value, list):
                raise TypeError(f"Expected a list for {field_type.__name__}, got {type(value).__name__}")

            if field_origin_type is list:
                # 如果列表元素类型是ConfigBase的子类，则对每个元素调用from_dict
                if (
                    field_type_args
                    and isinstance(field_type_args[0], type)
                    and issubclass(field_type_args[0], ConfigContentBase)
                ):
                    return [field_type_args[0].from_dict(item) for item in value]
                return [cls._convert_field(item, field_type_args[0]) for item in value]
            elif field_origin_type is set:
                return {cls._convert_field(item, field_type_args[0]) for item in value}
            elif field_origin_type is tuple:
                # 检查提供的value长度是否与类型参数一致
                if len(value) != len(field_type_args):
                    raise TypeError(
                        f"Expected {len(field_type_args)} items for {field_type.__name__}, got {len(value)}"
                    )
                return tuple(cls._convert_field(item, arg) for item, arg in zip(value, field_type_args, strict=True))

        if field_origin_type is dict:
            # 检查提供的value是否为dict
            if not isinstance(value, dict):
                raise TypeError(f"Expected a dictionary for {field_type.__name__}, got {type(value).__name__}")

            # 检查字典的键值类型
            if len(field_type_args) != 2:
                raise TypeError(f"Expected a dictionary with two type arguments for {field_type.__name__}")
            key_type, value_type = field_type_args

            return {cls._convert_field(k, key_type): cls._convert_field(v, value_type) for k, v in value.items()}

        # 处理Optional类型
        if field_origin_type is type(None) and value is None:
            return None

        # 处理基础类型，例如 int, str 等
        if field_type is bool and isinstance(value, str):
            lowered = value.lower()
            if lowered in {"true", "1", "enabled", "yes"}:
                return True
            elif lowered in {"false", "0", "disabled", "no"}:
                return False
            else:
                raise TypeError(f"Cannot convert string '{value}' to bool")

        # 处理Literal类型
        if field_origin_type is Literal or get_origin(field_type) is Literal:
            # 获取Literal的允许值
            allowed_values = get_args(field_type)
            if value in allowed_values:
                return value
            else:
                raise TypeError(f"Value '{value}' is not in allowed values {allowed_values} for Literal type")

        if field_type is Any or isinstance(value, field_type):
            return value

        # 其他类型，尝试直接转换
        try:
            return field_type(value)
        except (ValueError, TypeError) as e:
            raise TypeError(f"Cannot convert {type(value).__name__} to {field_type.__name__}") from e


@dataclass
class AttrDocBase:
    """解析字段说明的基类"""

    def __post_init__(self):
        self.field_docs = self._get_field_docs()  # 全局仅获取一次并保留

    @classmethod
    def _get_field_docs(cls) -> dict[str, str]:
        """
        获取字段的说明字符串

        :param cls: 配置类
        :return: 字段说明字典，键为字段名，值为说明字符串
        """
        # 获取类的源代码文本
        class_source = cls._get_class_source()
        # 解析源代码，找到对应的类定义节点
        class_node = cls._find_class_node(class_source)
        # 从类定义节点中提取字段文档
        return cls._extract_field_docs(class_node)

    @classmethod
    def _get_class_source(cls) -> str:
        """获取类定义所在文件的完整源代码"""
        # 使用 inspect 模块获取类定义所在的文件路径
        class_file = inspect.getfile(cls)
        # 读取文件内容并以 UTF-8 编码返回
        return Path(class_file).read_text(encoding="utf-8")

    @classmethod
    def _find_class_node(cls, class_source: str) -> ast.ClassDef:
        """在源代码的 AST 中查找当前类的定义节点"""
        # 将源代码解析为抽象语法树 (AST)
        tree = ast.parse(class_source)
        # 遍历 AST 中的所有节点
        for node in ast.walk(tree):
            # 查找类定义节点，且类名与当前类名匹配
            if isinstance(node, ast.ClassDef) and node.name == cls.__name__:
                return node
        # 如果没有找到匹配的类定义，抛出异常
        raise AttributeError(f"Class {cls.__name__} not found in source.")

    @classmethod
    def _extract_field_docs(cls, class_node: ast.ClassDef) -> dict[str, str]:
        """从类的 AST 节点中提取字段的文档字符串"""
        doc_dict: dict[str, str] = {}
        # 获取类体中的所有语句
        class_body = class_node.body
        
        # 遍历类体中的每个语句
        for i in range(len(class_body)):
            body_item = class_body[i]
            
            # 检查是否有非 __post_init__ 的方法定义，如果有则抛出异常
            # 这个限制确保 AttrDocBase 子类只包含字段定义和 __post_init__ 方法
            if isinstance(body_item, ast.FunctionDef) and body_item.name != "__post_init__":
                raise AttributeError(
                    f"Methods are not allowed in AttrDocBase subclasses except __post_init__, found {str(body_item.name)}"
                ) from None
            
            # 检查当前语句是否为带注解的赋值语句 (类型注解的字段定义)
            # 并且下一个语句存在
            if (
                i + 1 < len(class_body)
                and isinstance(body_item, ast.AnnAssign)  # 例如: field_name: int = 10
                and isinstance(body_item.target, ast.Name)  # 目标是一个简单的名称
            ):
                # 获取下一个语句
                expr_item = class_body[i + 1]
                
                # 检查下一个语句是否为字符串常量表达式 (文档字符串)
                if (
                    isinstance(expr_item, ast.Expr)  # 表达式语句
                    and isinstance(expr_item.value, ast.Constant)  # 常量值
                    and isinstance(expr_item.value.value, str)  # 字符串常量
                ):
                    # 获取文档字符串并去除首尾空白
                    doc_string = expr_item.value.value.strip()
                    
                    # 将文档字符串按行分割，并去除每行的首尾空白
                    processed_doc_lines = [line.strip() for line in doc_string.splitlines()]
                    
                    # 删除开头的所有空行
                    while processed_doc_lines and not processed_doc_lines[0]:
                        processed_doc_lines.pop(0)
                    
                    # 删除结尾的所有空行
                    while processed_doc_lines and not processed_doc_lines[-1]:
                        processed_doc_lines.pop()
                    
                    # 将处理后的行重新组合，并存入字典
                    # 键是字段名，值是清理后的文档字符串
                    doc_dict[body_item.target.id] = "\n".join(processed_doc_lines)
        
        return doc_dict


@dataclass
class ConfigBase(ConfigContentBase, AttrDocBase):
    """继承自ConfigContentBase和AttrDocBase的基类，方便类型检查"""
