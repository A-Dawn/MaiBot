from dataclasses import dataclass, field
from .config_base import ConfigBase


@dataclass
class APIProvider(ConfigBase):
    """API提供商配置类"""

    name: str = ""
    """API服务商名称 (可随意命名, 在models的api-provider中需使用这个命名)"""

    base_url: str = ""
    """API服务商的BaseURL"""

    api_key: str = field(default_factory=str, repr=False)
    """API密钥"""

    client_type: str = field(default="openai")
    """客户端类型 (可选: openai/google, 默认为openai)"""

    max_retry: int = 2
    """最大重试次数 (单个模型API调用失败, 最多重试的次数)"""

    timeout: int = 10
    """API调用的超时时长 (超过这个时长, 本次请求将被视为"请求超时", 单位: 秒)"""

    retry_interval: int = 10
    """重试间隔 (如果API调用失败, 重试的间隔时间, 单位: 秒)"""

    def __post_init__(self):
        """确保api_key在repr中不被显示"""
        if not self.api_key:
            raise ValueError("API密钥不能为空, 请在配置中设置有效的API密钥。")
        if not self.base_url and self.client_type != "gemini":  # TODO: 允许gemini使用base_url
            raise ValueError("API基础URL不能为空, 请在配置中设置有效的基础URL。")
        if not self.name:
            raise ValueError("API提供商名称不能为空, 请在配置中设置有效的名称。")
        return super().__post_init__()


@dataclass
class ModelInfo(ConfigBase):
    """单个模型信息配置类"""

    model_identifier: str = ""
    """模型标识符 (API服务商提供的模型标识符)"""

    name: str = ""
    """模型名称 (可随意命名, 在models中需使用这个命名)"""

    api_provider: str = ""
    """API服务商名称 (对应在api_providers中配置的服务商名称)"""

    price_in: float = field(default=0.0)
    """输入价格 (用于API调用统计, 单位：元/ M token) (可选, 若无该字段, 默认值为0)"""

    price_out: float = field(default=0.0)
    """输出价格 (用于API调用统计, 单位：元/ M token) (可选, 若无该字段, 默认值为0)"""

    force_stream_mode: bool = field(default=False)
    """强制流式输出模式 (若模型不支持非流式输出, 请设置为true启用强制流式输出, 默认值为false)"""

    extra_params: dict = field(default_factory=dict)
    """额外参数 (用于API调用时的额外配置)"""

    def __post_init__(self):
        if not self.model_identifier:
            raise ValueError("模型标识符不能为空, 请在配置中设置有效的模型标识符。")
        if not self.name:
            raise ValueError("模型名称不能为空, 请在配置中设置有效的模型名称。")
        if not self.api_provider:
            raise ValueError("API提供商不能为空, 请在配置中设置有效的API提供商。")
        return super().__post_init__()


@dataclass
class TaskConfig(ConfigBase):
    """任务配置类"""

    model_list: list[str] = field(default_factory=list)
    """使用的模型列表, 每个元素对应上面的模型名称(name)"""

    max_tokens: int = 1024
    """任务最大输出token数"""

    temperature: float = 0.3
    """模型温度"""


@dataclass
class ModelTaskConfig(ConfigBase):
    """模型配置类"""

    utils: TaskConfig = field(default_factory=TaskConfig)
    """组件使用的模型, 例如表情包模块, 取名模块, 关系模块, 麦麦的情绪变化等，是麦麦必须的模型"""

    utils_small: TaskConfig = field(default_factory=TaskConfig)
    """组件小模型配置, 消耗量较大, 建议使用速度较快的小模型"""

    replyer: TaskConfig = field(default_factory=TaskConfig)
    """首要回复模型配置, 还用于表达器和表达方式学习"""

    vlm: TaskConfig = field(default_factory=TaskConfig)
    """视觉模型配置"""

    voice: TaskConfig = field(default_factory=TaskConfig)
    """语音识别模型配置"""

    tool_use: TaskConfig = field(default_factory=TaskConfig)
    """工具使用模型配置, 需要使用支持工具调用的模型"""

    planner: TaskConfig = field(default_factory=TaskConfig)
    """规划模型配置"""

    embedding: TaskConfig = field(default_factory=TaskConfig)
    """嵌入模型配置"""

    lpmm_entity_extract: TaskConfig = field(default_factory=TaskConfig)
    """LPMM实体提取模型配置"""

    lpmm_rdf_build: TaskConfig = field(default_factory=TaskConfig)
    """LPMM RDF构建模型配置"""

    lpmm_qa: TaskConfig = field(default_factory=TaskConfig)
    """LPMM问答模型配置"""
