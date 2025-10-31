# 本文件为测试文件，请尽量忽略Lint error，内含大量的ignore标识

# 依赖导入
import sys
import tomlkit
import pytest
from pathlib import Path
from dataclasses import dataclass, field

# 路径依赖解决
PROJECT_ROOT: Path = Path(__file__).parent.parent.absolute().resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "config"))

from src.config.config_base import ConfigBase  # noqa: E402
from src.config.config import write_config_to_file  # noqa: E402


@dataclass
class SubConfig(ConfigBase):
    detail: str
    """Detail field for testing"""


@dataclass
class SubConfig2(ConfigBase):
    value: int
    """Value field for testing"""
    list_field: list[int]
    """List field for testing"""
    multi_comment_field: str = "example"
    """
    This is a multi-comment field for testing
    The comment spans multiple lines, which should appear as multi-line comments.
    """
    field_after_multi_comment: str = "after"
    """Field after multi-comment to test ordering, should have a whitespace above."""
    nested_list_config: list[SubConfig] = field(default_factory=lambda: [])
    """Nested list of SubConfig for testing"""
    nested_tuple_config: tuple[SubConfig, str] = field(default_factory=lambda: (SubConfig(detail="nested"), "nested"))
    nested_dict_config: dict[str, SubConfig] = field(default_factory=lambda: {"key": SubConfig(detail="dict_nested")})
    """Nested dict of SubConfig for testing"""


@dataclass
class SimpleConfig(ConfigBase):
    sub_config: SubConfig
    """Sub configuration for testing"""
    sub_config2: SubConfig2
    """Second sub configuration for testing"""


@dataclass
class SetFieldConfig(ConfigBase):
    set_field: set[str] = field(default_factory=lambda: {"a", "b", "c"})


@dataclass
class WrapperConfig(ConfigBase):
    simple_config: SetFieldConfig = field(default_factory=lambda: SetFieldConfig())


standard_config = {
    "name": "TestConfig",
    "sub_config": {"detail": "This is a detail field"},
    "sub_config2": {
        "value": 10,
        "list_field": [1, 2, 3],
        "multi_comment_field": "example",
        "nested_list_config": [{"detail": "nested1"}, {"detail": "nested2"}],
    },
}


def test_write_config_to_file(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "test_config.toml"
    config = SimpleConfig.from_dict(standard_config)
    write_config_to_file(config, config_path)  # type: ignore
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    target_toml = Path(__file__).parent / "target_toml.toml"
    with open(target_toml, "r", encoding="utf-8") as f:
        target_content = f.read()
    written_in_lines = [line.strip() for line in content.splitlines()]
    target_in_lines = [line.strip() for line in target_content.splitlines()]
    written_in_lines.pop(1)  # 防止配置文件内部版本的更改影响测试结果
    target_in_lines.pop(1)

    assert written_in_lines == target_in_lines


def test_write_set_field_config(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "set_field_config.toml"
    config = WrapperConfig()
    write_config_to_file(config, config_path)  # type: ignore
    with open(config_path, "r", encoding="utf-8") as f:
        written_config = tomlkit.load(f)
    simple_config_table = written_config["simple_config"]
    set_field = set(simple_config_table["set_field"])  # type: ignore
    assert set_field == {"a", "b", "c"}


def test_write_raise_exception_on_non_ConfigBase(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "invalid_config.toml"
    config = SetFieldConfig()
    with pytest.raises(TypeError) as exc_info:
        write_config_to_file(config, config_path)  # type: ignore
    assert exc_info.type is TypeError
    assert "配置写入只支持ConfigBase子类" in str(exc_info.value)
