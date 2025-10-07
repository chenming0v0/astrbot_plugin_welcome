import json
from pathlib import Path
from astrbot.api.event import filter, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.core import AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from typing import AsyncGenerator

@register(
    "astrbot_plugin_welcome",
    "chengming0v0",
    "新人入群自动发送欢迎消息，支持为不同群设置不同的欢迎语",
    "v1.0"
)
class WelcomePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config
        
        # 读取默认欢迎消息
        self.default_message = self.config.get("default_message", "欢迎新人~")
        
        # 存储每个群的自定义欢迎语 {group_id: welcome_message}
        self.group_welcomes = {}
        
        # 数据文件路径
        self.data_dir = StarTools.get_data_dir()
        self.data_file = self.data_dir / "group_welcomes.json"

    async def initialize(self):
        """插件初始化，加载数据"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._load_group_welcomes()
            logger.info("群欢迎插件已初始化")
        except Exception as e:
            logger.error(f"初始化群欢迎插件失败: {e}")

    async def terminate(self):
        """插件终止时保存数据"""
        try:
            self._save_group_welcomes()
            logger.info("群欢迎插件已终止，数据已保存")
        except Exception as e:
            logger.error(f"终止群欢迎插件时出错: {e}")

    def _load_group_welcomes(self):
        """从文件加载群欢迎配置"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.group_welcomes = json.load(f)
                logger.info(f"已加载 {len(self.group_welcomes)} 个群的欢迎配置")
            else:
                self.group_welcomes = {}
        except Exception as e:
            logger.error(f"加载群欢迎配置失败: {e}")
            self.group_welcomes = {}

    def _save_group_welcomes(self):
        """保存群欢迎配置到文件"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.group_welcomes, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.group_welcomes)} 个群的欢迎配置")
        except Exception as e:
            logger.error(f"保存群欢迎配置失败: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_group_increase(self, event: AiocqhttpMessageEvent):
        """处理新成员入群事件"""
        try:
            if not hasattr(event, "message_obj") or not hasattr(event.message_obj, "raw_message"):
                return
            
            raw_message = event.message_obj.raw_message
            if not raw_message or not isinstance(raw_message, dict):
                return
            
            # 检查是否为群成员增加通知
            if (raw_message.get("post_type") == "notice" and
                raw_message.get("notice_type") == "group_increase"):
                
                group_id = str(raw_message.get("group_id", ""))
                user_id = int(raw_message.get("user_id", 0))
                
                if not group_id or not user_id:
                    return
                
                # 获取该群的欢迎语，如果没有则使用默认欢迎语
                welcome_msg = self.group_welcomes.get(group_id, self.default_message)
                
                # 构建欢迎消息
                chain = [
                    Comp.At(qq=user_id),
                    Comp.Plain(text=f" {welcome_msg}")
                ]
                
                logger.info(f"新成员 {user_id} 加入群 {group_id}，发送欢迎消息")
                yield event.chain_result(chain)
                
        except Exception as e:
            logger.error(f"处理入群事件失败: {e}")

    @filter.command("设置欢迎")
    async def set_welcome(self, event: AiocqhttpMessageEvent, message: str) -> AsyncGenerator[MessageEventResult, None]:
        """设置本群欢迎语: /设置欢迎 欢迎内容（仅Bot管理员）"""
        try:
            # 检查是否为群聊
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("此命令仅在群聊中可用")
                return
            
            # 检查权限：只允许Bot管理员
            if event.role != "admin":
                yield event.plain_result("抱歉，你的权限不足")
                return
            
            # 检查欢迎语是否为空
            if not message.strip():
                yield event.plain_result("欢迎语不能为空")
                return
            
            # 设置新的欢迎语
            self.group_welcomes[group_id] = message
            self._save_group_welcomes()
            
            yield event.plain_result(f"已设置本群欢迎语:\n{message}")
            logger.info(f"群 {group_id} 设置了新的欢迎语")
            
        except Exception as e:
            logger.error(f"设置欢迎语命令执行失败: {e}")
            yield event.plain_result(f"设置失败: {str(e)}")

    @filter.command("查看欢迎")
    async def view_welcome(self, event: AiocqhttpMessageEvent) -> AsyncGenerator[MessageEventResult, None]:
        """查看本群当前欢迎语: /查看欢迎"""
        try:
            # 检查是否为群聊
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("此命令仅在群聊中可用")
                return
            
            # 检查权限：只允许Bot管理员
            if event.role != "admin":
                yield event.plain_result("抱歉，你的权限不足")
                return
            
            # 获取当前欢迎语
            current = self.group_welcomes.get(group_id, self.default_message)
            yield event.plain_result(f"当前欢迎语:\n{current}")
            
        except Exception as e:
            logger.error(f"查看欢迎语命令执行失败: {e}")
            yield event.plain_result(f"查看失败: {str(e)}")