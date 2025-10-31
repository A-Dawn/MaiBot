from dataclasses import dataclass, field
from typing import Literal
import re

from .config_base import ConfigBase

"""
须知：
1. 本文件中记录了所有的配置项
2. 所有新增的class都需要继承自ConfigBase, AttrDocConfigBase
3. 所有新增的class都应在official_configs.py中的Config类中添加字段
4. 对于新增的字段，若为可选项，则应在其后添加field()并设置default_factory或default
5. 所有的配置项都应该按照如下方法添加字段说明：
class ExampleConfig(ConfigBase, AttrDocConfigBase):
    example_field: str
    "This is an example field"
"""


@dataclass
class BotConfig(ConfigBase):
    """机器人配置类"""

    alias_names: list[str] = field(default_factory=lambda: [])
    """麦麦的别名列表"""


@dataclass
class PersonalityConfig(ConfigBase):
    """人格配置类"""

    personality: str = "是一个女大学生，现在在读大二，会刷贴吧。"
    """人格，建议120字以内，描述人格特质和身份特征"""

    reply_style: str = (
        "请回复的平淡一些，简短一些，说中文，不要刻意突出自身学科背景。可以参考贴吧，知乎和微博的回复风格。"
    )
    """表达风格，描述麦麦说话的表达风格，表达习惯"""

    interest: str = "对技术相关话题，游戏和动漫相关话题感兴趣，也对日常话题感兴趣，不喜欢太过沉重严肃的话题"
    """麦麦的兴趣，会影响麦麦对什么话题进行回复"""

    states: list[str] = field(
        default_factory=lambda: [
            "是一个女大学生，喜欢上网聊天，会刷小红书。",
            "是一个大二心理学生，会刷贴吧和中国知网。",
            "是一个赛博网友，最近很想吐槽人。",
        ]
    )
    """状态列表，可以理解为人格多样性，用于随机替换personality"""

    state_probability: float = 0.0
    """状态替换概率，每次构建人格时替换personality的概率（0.0-1.0）"""

    plan_style: str = """1.思考**所有**的可用的action中的**每个动作**是否符合当下条件，如果动作使用条件符合聊天内容就使用\n2.如果相同的内容已经被执行，请不要重复执行\n3.请控制你的发言频率，不要太过频繁的发言\n4.如果有人对你感到厌烦，请减少回复\n5.如果有人对你进行攻击，或者情绪激动，请你以合适的方法应对"""
    """麦麦的说话提示词，行为风格"""

    visual_style: str = "请用中文描述这张图片的内容。如果有文字，请把文字描述概括出来，请留意其主题，直观感受，输出为一段平文本，最多30字，请注意不要分点，就输出一段文本"
    """麦麦识图提示词，不建议修改"""

    private_plan_style: str = ""
    """私聊说话规则，行为风格"""


@dataclass
class RelationshipConfig(ConfigBase):
    """关系配置类"""

    enable_relationship: bool = True
    """是否启用关系系统"""


@dataclass
class ChatConfig(ConfigBase):
    """聊天配置类"""

    at_bot_inevitable_reply: float = 1.0
    """@bot 必然回复，1为100%回复，0为不额外增幅"""

    max_context_size: int = 25
    """最大上下文长度"""

    mentioned_bot_reply: bool = True
    """是否启用提及必回复"""

    planner_smooth: float = 3.0
    """规划器平滑，增大数值会减小planner负荷，略微降低反应速度，推荐2-5，0为关闭，必须大于等于0"""

    talk_value: float = 1
    """麦麦思考频率，越小越沉默，范围0-1"""

    enable_talk_value_rules: bool = True
    """是否启用动态发言频率规则"""

    talk_value_rules: list[tuple[str, str, float]] = field(
        default_factory=lambda: [
            ("", "00:00-08:59", 0.8),
            ("", "09:00-22:59", 1.0),
        ]
    )
    """
    发言思考频率规则调整，支持按聊天/按时段配置。
    规则格式：[target, time, value]

    target 字符串为空则表示全局，否则按照 "platform:id:type" 格式书写, type 可选 group/private。优先级为特定聊天 > 全局规则。
    time 按照格式 "HH:MM-HH:MM" 书写，支持跨夜区间，例如 "23:00-02:00"
    value 范围建议 0-1。

    示例:
    [
        ["", "00:00-08:59", 0.2],                  # 全局规则：凌晨到早上更安静
        ["", "09:00-22:59", 1.0],                  # 全局规则：白天正常
        ["qq:1919810:group", "20:00-23:59", 0.6],  # 指定群id为1919810的群在晚高峰降低发言
        ["qq:114514:private", "00:00-23:59", 0.3], # 指定用户id为114514的用户私聊全时段较安静
    ]
    """

    active_chat_value: float = 1
    """麦麦主动聊天频率，越小则主动聊天的概率越低"""

    enable_active_chat_value_rules: bool = True
    """是否启用动态主动聊天频率规则"""

    active_chat_value_rules: list[tuple[str, str, float]] = field(
        default_factory=lambda: [
            ("", "00:00-08:59", 0.3),
            ("", "09:00-22:59", 1.0),
        ]
    )
    """
    主动聊天频率规则列表，格式同 talk_value_rules
    """


@dataclass
class MessageReceiveConfig(ConfigBase):
    """消息接收配置类"""

    ban_words: set[str] = field(default_factory=lambda: set())
    """过滤词列表，匹配到的消息将被过滤"""

    ban_msgs_regex: set[str] = field(default_factory=lambda: set())
    """需要过滤的消息（原始消息）匹配的正则表达式，匹配到的消息将被过滤"""

    def __post_init__(self):
        for pattern in self.ban_msgs_regex:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern in ban_msgs_regex: '{pattern}'") from e
        return super().__post_init__()


@dataclass
class MemoryConfig(ConfigBase):
    """记忆配置类"""

    max_memory_number: int = 100
    """记忆最大数量"""

    memory_build_frequency: int = 1
    """记忆构建频率"""


@dataclass
class ExpressionConfig(ConfigBase):
    """表达配置类"""

    mode: str = "classic"
    """
    表达方式模式
    可选: classic 经典模式, exp_model 表达模型模式
    后者需要一定时间学习才有好效果
    """

    learning_list: list[tuple[str, bool, bool, float]] = field(default_factory=lambda: [("", True, True, 1.0)])
    """
    表达学习配置列表，支持按聊天配置
    格式: [(chat, use_expression, enable_learning, learning_intensity), ...]

    示例:
    [
        ["", true, true, 1.0],  # 全局配置：使用表达，启用学习，学习强度1.0
        ["qq:1919810:private", true, true, 1.5],  # 特定私聊配置：使用表达，启用学习，学习强度1.5
        ["qq:114514:private", true, false, 0.5],  # 特定私聊配置：使用表达，禁用学习，学习强度0.5
    ]

    说明:
    - 第一位: chat, 配置聊天, 格式同 talk_value, 空字符串表示全局配置
    - 第二位: 是否使用学到的表达
    - 第三位: 是否学习表达
    - 第四位: 学习强度（浮点数），影响学习频率，最短学习时间间隔 = 300/学习强度（秒）
    学习强度越高，学习越频繁；学习强度越低，学习越少
    """

    expression_groups: list[list[str]] = field(default_factory=list)
    """
    表达学习互通组, 所有在同一组内的聊天会共享表达学习成果
    格式: [ ["qq:12345:group", "qq:67890:private"], ... ]
    说明: chat配置格式同 talk_value, 若配置 [ "*" ] 则启用所有聊天共享, 优先级最高并覆盖其他设置
    """


@dataclass
class ToolConfig(ConfigBase):
    """工具配置类"""

    enable_tool: bool = False
    """是否在聊天中启用工具"""


@dataclass
class MoodConfig(ConfigBase):
    """情绪配置类"""

    enable_mood: bool = True
    """是否启用情绪系统"""

    mood_update_threshold: float = 1
    """情绪更新阈值,越高，更新越慢"""

    emotion_style: str = "情绪较为稳定，但遭遇特定事件的时候起伏较大"
    """情感特征，影响情绪的变化情况"""


@dataclass
class VoiceConfig(ConfigBase):
    """语音识别配置类"""

    enable_asr: bool = False
    """是否启用语音识别，启用后麦麦可以识别语音消息，启用该功能需要配置语音识别模型[model_task_config.voice]"""


@dataclass
class EmojiConfig(ConfigBase):
    """表情包配置类"""

    emoji_chance: float = 0.6
    """发送表情包的基础概率"""

    max_reg_num: int = 200
    """表情包最大注册数量"""

    do_replace: bool = True
    """达到最大注册数量时替换旧表情包"""

    check_interval: int = 120
    """检查表情包（注册，破损，删除）的时间间隔(分钟)"""

    steal_emoji: bool = True
    """是否偷取表情包，让麦麦可以将一些表情包据为己有"""

    content_filtration: bool = False
    """是否启用表情包过滤，只有符合该要求的表情包才会被保存"""

    filtration_prompt: str = "符合公序良俗"
    """表情包过滤要求，只有符合该要求的表情包才会被保存"""


@dataclass
class KeywordRuleConfig(ConfigBase):
    """关键词规则配置类"""

    keywords: list[str] = field(default_factory=lambda: [])
    """关键词列表，匹配到关键词则触发规则"""

    regex: list[str] = field(default_factory=lambda: [])
    """正则表达式列表"""

    reaction: str = ""
    """关键词触发的反应"""

    def __post_init__(self):
        """验证配置"""
        if not self.keywords and not self.regex:
            raise ValueError("关键词规则必须至少包含keywords或regex中的一个")

        if not self.reaction:
            raise ValueError("关键词规则必须包含reaction")

        # 验证正则表达式
        for pattern in self.regex:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"无效的正则表达式 '{pattern}'") from e

        return super().__post_init__()


@dataclass
class KeywordReactionConfig(ConfigBase):
    """关键词配置类"""

    keyword_rules: list[KeywordRuleConfig] = field(default_factory=lambda: [])
    """关键词规则列表"""

    regex_rules: list[KeywordRuleConfig] = field(default_factory=lambda: [])
    """正则表达式规则列表"""

    enable_keyword_reaction: bool = True
    """是否启用关键词反应系统"""

    def __post_init__(self):
        """验证配置"""
        # 验证所有规则
        for rule in self.keyword_rules + self.regex_rules:
            if not isinstance(rule, KeywordRuleConfig):
                raise ValueError(f"规则必须是KeywordRuleConfig类型，而不是{type(rule).__name__}")
        return super().__post_init__()


@dataclass
class ResponsePostProcessConfig(ConfigBase):
    """回复后处理配置类"""

    enable_response_post_process: bool = True
    """是否启用回复后处理，包括错别字生成器，回复分割器"""


@dataclass
class ChineseTypoConfig(ConfigBase):
    """中文错别字配置类"""

    enable: bool = True
    """是否启用中文错别字生成器"""

    error_rate: float = 0.01
    """单字替换概率"""

    min_freq: int = 9
    """最小字频阈值"""

    tone_error_rate: float = 0.1
    """声调错误概率"""

    word_replace_rate: float = 0.006
    """整词替换概率"""


@dataclass
class ResponseSplitterConfig(ConfigBase):
    """回复分割器配置类"""

    enable: bool = True
    """是否启用回复分割器"""

    max_length: int = 512
    """回复允许的最大长度"""

    max_sentence_num: int = 3
    """回复允许的最大句子数"""

    enable_kaomoji_protection: bool = False
    """是否启用颜文字保护"""


@dataclass
class TelemetryConfig(ConfigBase):
    """遥测配置类"""

    enable: bool = True
    """是否启用遥测"""


@dataclass
class DebugConfig(ConfigBase):
    """调试配置类"""

    show_prompt: bool = False
    """是否显示prompt"""


@dataclass
class ExperimentalConfig(ConfigBase):
    """实验功能配置类"""

    pass


@dataclass
class MaimMessageConfig(ConfigBase):
    """maim_message配置类"""

    host: str = "127.0.0.1"
    """主机地址"""

    port: int = 8080
    """主机端口号"""

    use_custom: bool = False
    """是否使用自定义的maim_message配置"""

    second_host: str = "127.0.0.1"
    """自定义第二主机地址"""

    second_port: int = 8090
    """"自定义第二端口号"""

    mode: Literal["ws", "tcp"] = "ws"
    """连接模式，支持ws和tcp"""

    use_wss: bool = False
    """是否使用WSS安全连接"""

    cert_file: str = ""
    """SSL证书文件路径，仅在use_wss=True时有效"""

    key_file: str = ""
    """SSL密钥文件路径，仅在use_wss=True时有效"""

    auth_token: list[str] = field(default_factory=lambda: [])
    """认证令牌，用于API验证，为空则不启用验证"""


@dataclass
class LPMMKnowledgeConfig(ConfigBase):
    """LPMM知识库配置类"""

    enable: bool = True
    """是否启用LPMM知识库"""

    rag_synonym_search_top_k: int = 10
    """RAG同义词搜索的Top K数量"""

    rag_synonym_threshold: float = 0.8
    """RAG同义词搜索的相似度阈值"""

    info_extraction_workers: int = 3
    """实体提取同时执行线程数，非Pro模型不要设置超过5"""

    qa_relation_search_top_k: int = 10
    """QA关系搜索的Top K数量"""

    qa_relation_threshold: float = 0.75
    """QA关系搜索的相似度阈值（相似度高于此阈值的关系会被认为是相关的关系）"""

    qa_paragraph_search_top_k: int = 1000
    """QA段落搜索的Top K数量（不能过小，可能影响搜索结果）"""

    qa_paragraph_node_weight: float = 0.05
    """QA段落节点权重（在图搜索&PPR计算中的权重，当搜索仅使用DPR时，此参数不起作用）"""

    qa_ent_filter_top_k: int = 10
    """QA实体过滤的Top K数量"""

    qa_ppr_damping: float = 0.8
    """QA PageRank阻尼系数"""

    qa_res_top_k: int = 10
    """QA最终结果的Top K数量"""

    embedding_dimension: int = 1024
    """嵌入向量维度，应该与模型的输出维度一致"""
