from dataclasses import dataclass, field, fields
from pathlib import Path
import tomlkit


from .official_configs import (
    BotConfig,
    PersonalityConfig,
    RelationshipConfig,
    ChatConfig,
    MessageReceiveConfig,
    MemoryConfig,
    ExpressionConfig,
    ToolConfig,
    MoodConfig,
    VoiceConfig,
    EmojiConfig,
    KeywordReactionConfig,
    ResponsePostProcessConfig,
    ChineseTypoConfig,
    ResponseSplitterConfig,
    TelemetryConfig,
    DebugConfig,
    ExperimentalConfig,
    MaimMessageConfig,
    LPMMKnowledgeConfig
)
from .config_base import ConfigBase
from .config_utils import recursive_parse_item_to_table

MMC_VERSION: str = "0.12.0"
CONFIG_VERSION: str = "7.0.0"
PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.absolute().resolve()
CONFIG_DIR: Path = PROJECT_ROOT / "configs"

"""
如果你想要修改配置文件，请递增version的值

版本格式：主版本号.次版本号.修订号，版本号递增规则如下：
    主版本号：MMC版本更新
    次版本号：配置文件内容大更新
    修订号：配置文件内容小更新
"""


@dataclass
class Config(ConfigBase):
    """总配置类"""

    MMC_VERSION: str = field(default=MMC_VERSION, repr=False, init=False)
    """硬编码的版本信息"""

    bot: BotConfig
    """机器人配置类"""

    personality: PersonalityConfig
    """人格配置类"""

    relationship: RelationshipConfig
    """关系配置类"""

    chat: ChatConfig
    """聊天配置类"""
    
    message_receive: MessageReceiveConfig
    """消息接收配置类"""
    
    memory: MemoryConfig
    """记忆配置类"""
    
    expression: ExpressionConfig
    """表达配置类"""
    
    tool: ToolConfig
    """工具配置类"""
    
    mood: MoodConfig
    """情绪配置类"""
    
    voice: VoiceConfig
    """语音配置类"""
    
    emoji: EmojiConfig
    """表情包配置类"""
    
    keyword_reaction: KeywordReactionConfig
    """关键词反应配置类"""
    
    response_post_process: ResponsePostProcessConfig
    """回复后处理配置类"""
    
    chinese_typo: ChineseTypoConfig
    """中文错别字生成器配置类"""
    
    response_splitter: ResponseSplitterConfig
    """回复分割器配置类"""
    
    telemetry: TelemetryConfig
    """遥测配置类"""
    
    debug: DebugConfig
    """调试配置类"""
    
    experimental: ExperimentalConfig
    """实验性功能配置类"""
    
    maim_message: MaimMessageConfig
    """maim_message配置类"""
    
    lpmm_knowledge: LPMMKnowledgeConfig
    """LPMM知识库配置类"""

@dataclass
class AttributeData:
    missing_attributes: list[str] = field(default_factory=list)
    """缺失的属性列表"""
    redundant_attributes: list[str] = field(default_factory=list)
    """多余的属性列表"""

def load_config_from_file(config_path: Path) -> Config:
    """从文件加载配置

    :param config_path: 配置文件路径
    :return: 配置对象
    """
    attribute_data = AttributeData()
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = tomlkit.load(f)
    try:
        return Config.from_dict(config_data, attribute_data)
    except Exception as e:
        # logger.critical("配置文件解析失败")
        raise e


def write_config_to_file(config: Config, config_path: Path, override_repr: bool = False) -> None:
    """将配置写入文件

    :param config: 配置对象
    :param config_path: 配置文件路径
    """
    # 创建空TOMLDocument
    full_config_data = tomlkit.document()

    # 首先写入配置文件版本信息
    version_table = tomlkit.table()
    version_table.add("version", CONFIG_VERSION)
    full_config_data.add("inner", version_table)

    # 递归解析配置项为表格
    for config_item in fields(config):
        if not config_item.repr and not override_repr:
            continue
        config_field = getattr(config, config_item.name)
        if isinstance(config_field, ConfigBase):
            full_config_data.add(config_item.name, recursive_parse_item_to_table(config_field))
        else:
            raise TypeError("配置写入只支持ConfigBase子类")

    # 写入文件
    with open(config_path, "w", encoding="utf-8") as f:
        tomlkit.dump(full_config_data, f)
