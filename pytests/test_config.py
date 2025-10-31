# 本文件为测试文件，请忽略Lint error，内含大量的ignore标识

# 依赖导入
from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path
import tomlkit
import pytest
import sys
import copy

# 测试对象导入
PROJECT_ROOT: Path = Path(__file__).parent.parent.absolute().resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "config"))

from src.config.config_base import ConfigBase  # noqa: E402
from src.config.config import AttributeData  # noqa: E402

standard_config_data = {
    "int_field": 42,
    "float_field": 3.14,
    "str_field": "example",
    "bool_field": True,
    "list_field": [1, 2, 3],
    "set_field": ["a", "b", "c"],
    "tuple_field": [7, "seven"],
    "dict_field": {"key1": 1, "key2": 2},
    "sub_class": {"sub_field": "sub_value"},
}


@dataclass
class SubClass(ConfigBase):
    sub_field: str
    """sub_field is a string field in SubClass"""


@dataclass
class ConfigExample(ConfigBase):
    int_field: int
    """The value is integer type"""
    float_field: float
    """The value is float type"""
    str_field: str
    """
    multi-line annotation

    The value is string type
    """
    bool_field: bool
    """
    The value is boolean type
    """
    list_field: list[int]
    set_field: set[str]
    tuple_field: tuple[int, str]
    sub_class: SubClass
    dict_field: dict[str, int] = field(default_factory=dict)
    optional_field: Optional[str] = "default_value"


@dataclass
class ErrorConfig(ConfigBase):
    value: int

    def a_method(self):  # 应该抛出异常
        pass


@dataclass
class GoodConfig(ConfigBase):
    value: int

    def __post_init__(self):  # 唯一允许的方法
        super().__post_init__()


@dataclass
class SubConfigWithValues(ConfigBase):
    value2: int = 20
    text2: str = "default2"


@dataclass
class ConfigWithValues(ConfigBase):
    sub_config: SubConfigWithValues = field(default_factory=SubConfigWithValues)
    value: int = 10
    text: str = "default"


def assert_values(config: ConfigExample):
    assert config.int_field == 42, "wrong int_field value"
    assert config.float_field == 3.14, "wrong float_field value"
    assert config.str_field == "example", "wrong str_field value"
    assert config.bool_field is True, "wrong bool_field value"
    assert config.list_field == [1, 2, 3], "wrong list_field value"
    assert config.set_field == {"a", "b", "c"}, "wrong set_field value"
    assert config.tuple_field == (7, "seven"), "wrong tuple_field value"
    assert config.dict_field == {"key1": 1, "key2": 2}, "wrong dict_field value"
    assert config.optional_field == "default_value", "wrong optional_field value"
    assert config.sub_class.sub_field == "sub_value", "wrong sub_class.sub_field value"
    assert isinstance(config.int_field, int)
    assert isinstance(config.float_field, float)
    assert isinstance(config.str_field, str)
    assert isinstance(config.bool_field, bool)
    assert isinstance(config.list_field, list)
    assert isinstance(config.set_field, set)
    assert isinstance(config.tuple_field, tuple)
    assert isinstance(config.tuple_field[0], int)
    assert isinstance(config.tuple_field[1], str)
    assert isinstance(config.dict_field, dict)
    assert isinstance(config.optional_field, str)
    assert isinstance(config.sub_class.sub_field, str)


def test_config_base_from_dict():
    config = ConfigExample.from_dict(standard_config_data, AttributeData())
    assert_values(config)


def test_config_base_from_file():
    file_path = Path(__file__).parent / "test_config.toml"
    with open(file_path.resolve().absolute(), "r", encoding="utf-8") as f:
        toml_content = tomlkit.load(f)

    config = ConfigExample.from_dict(toml_content, AttributeData())
    assert_values(config)


e_int_config_data = copy.deepcopy(standard_config_data)
e_int_config_data["int_field"] = "40"  # 会被转换，应该报AssertionError
e_list_config_data = copy.deepcopy(standard_config_data)
e_list_config_data["list_field"] = []  # 列表为空，应该被覆盖并报AssertionError
e_set_config_data = copy.deepcopy(standard_config_data)
e_set_config_data["set_field"] = ("a", "b", "c")  # 错误类型
e_subclass_config_data = copy.deepcopy(standard_config_data)
e_subclass_config_data.pop("sub_class")  # 缺少关键字
e_list_type_config_data = copy.deepcopy(standard_config_data)
e_list_type_config_data["list_field"] = ["nan", 2, 3]  # 元素类型错误
e_bool_config_data = copy.deepcopy(standard_config_data)
e_bool_config_data["bool_field"] = "False"  # 会被转换，应该报AssertionError
multiline_str_config_data = copy.deepcopy(standard_config_data)
multiline_str_config_data["str_field"] = """
line1
line2
line3
"""


@pytest.mark.parametrize(
    "config_data, expected_exception, expected_message",
    [
        (e_int_config_data, AssertionError, "wrong int_field value"),
        (e_list_config_data, AssertionError, "wrong list_field value"),
        (e_set_config_data, TypeError, "Expected a list for set"),
        (e_subclass_config_data, ValueError, "Missing required field: 'sub_class'"),
        (e_list_type_config_data, TypeError, "Cannot convert str to int"),
        (e_bool_config_data, AssertionError, "wrong bool_field value"),
    ],
)
def test_multiple_exceptions(config_data, expected_exception, expected_message):
    with pytest.raises(expected_exception) as exc_info:
        config = ConfigExample.from_dict(config_data, AttributeData())
        assert_values(config)
    # 确保异常类型正确
    assert exc_info.type == expected_exception
    # 确保异常消息包含预期内容
    assert expected_message in str(exc_info.value)


def test_multiline_string():
    config = ConfigExample.from_dict(multiline_str_config_data, AttributeData())
    assert config.str_field == "\nline1\nline2\nline3\n", "wrong multiline str_field value"


def test_doc_strings():
    config_data = {
        "int_field": 42,
        "float_field": 3.14,
        "str_field": "example",
        "bool_field": True,
        "list_field": [1, 2, 3],
        "set_field": ["a", "b", "c"],
        "tuple_field": [7, "seven"],
        "dict_field": {"key1": 1, "key2": 2},
        "sub_class": {"sub_field": "sub_value"},
    }

    config = ConfigExample.from_dict(config_data, AttributeData())
    field_docs = config.field_docs
    assert field_docs["int_field"] == "The value is integer type"
    assert field_docs["float_field"] == "The value is float type"
    assert field_docs["str_field"] == "multi-line annotation\n\nThe value is string type"
    assert field_docs["bool_field"] == "The value is boolean type"
    field_docs_sub = config.sub_class.field_docs
    assert field_docs_sub["sub_field"] == "sub_field is a string field in SubClass"


@pytest.mark.parametrize(
    "target_class, config_data, expected_exception, expected_message",
    [
        (
            ErrorConfig,
            {"value": 10},
            AttributeError,
            "Methods are not allowed in AttrDocBase subclasses except __post_init__",
        ),
        (GoodConfig, {"value": 10}, None, ""),
    ],
)
def test_method_exception(target_class, config_data, expected_exception, expected_message):
    if expected_exception:
        with pytest.raises(expected_exception) as exc_info:
            _ = target_class.from_dict(config_data, AttributeData())
        # 确保异常类型正确
        assert exc_info.type == expected_exception
        # 确保异常消息包含预期内容
        assert expected_message in str(exc_info.value)
    else:
        target_class.from_dict(config_data, AttributeData())


def test_config_with_values_defaults():
    config_data = {"text": "custom", "bool_field": False, "sub_config": {"value2": 50, "bool_field2": True}}
    attr_data = AttributeData()
    _ = ConfigWithValues.from_dict(config_data, attr_data)
    assert attr_data.missing_attributes == ["text2", "value"]  # 先里后外的说
    assert attr_data.redundant_attributes == ["bool_field2", "bool_field"]
