from pathlib import Path
from typing import Optional, Any
from collections.abc import Callable
from enum import Enum
from watchfiles import awatch, Change
import asyncio
import uuid

from src.common.logger import get_logger
from src.plugins_system.api.constants import PROJECT_ROOT, BOT_CONFIG_PATH, MODEL_CONFIG_PATH


logger = get_logger("FileWatcher")


class WatchType(Enum):
    """监视类型枚举类"""

    BOT_CONFIG_CHANGE = 0b0001
    MODEL_CONFIG_CHANGE = 0b0010
    PLUGIN_CONFIG_CHANGE = 0b0100
    ALL_CONFIG_CHANGE = 0b0111
    PLUGIN_CODE_CHANGE = 0b1000
    ALL_CODE_CHANGE = 0b1000
    ALL_FILE_CHANGE = 0b1111


class ChangeType(Enum):
    """文件变化类型枚举类"""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


hierarchy_map: dict[WatchType, list[WatchType]] = {}


def dynamic_construct_hierarchy_map():
    global hierarchy_map
    for wt in WatchType:
        hierarchy_map[wt] = []
        for other_wt in WatchType:
            if other_wt != wt and (other_wt.value & wt.value) == other_wt.value:
                hierarchy_map[wt].append(other_wt)


class FileWatcher:
    """文件监视器类，用于监视文件的更改"""

    def __init__(self):
        self.path_callbacks: dict[Path, set[Callable[[Path, ChangeType], Any]]] = {}
        """mapping from watched path -> set of callbacks (callables with Path and ChangeType args)"""
        self.type_callbacks: dict[WatchType, set[Callable[[Path, ChangeType], Any]]] = {wt: set() for wt in WatchType}
        """mapping from watch type -> set of callbacks (callables with Path and ChangeType args)"""
        self.callable_registration: dict[
            str, tuple[list[Path], list[WatchType], Callable[[Path, ChangeType], Any]]
        ] = {}
        """uuid -> (watch_path list, watch_type list, callback)"""

        self.bot_config_path: Path = BOT_CONFIG_PATH
        self.model_config_path: Path = MODEL_CONFIG_PATH

        self.watch_tasks: dict[Path, asyncio.Task] = {}

    async def register_callback(
        self,
        callback: Callable[[Path, ChangeType], Any],
        source_name: str,
        *,
        watch_path: Optional[list[Path]] = None,
        watch_type: Optional[list[WatchType]] = None,
    ) -> str:
        """
        注册回调函数

        Args:
            callback (Callable): 回调函数
            watch_path (Optional[list[Path]]): 监视的路径列表
            watch_type (Optional[list[WatchType]]): 监视的类型列表

        watch_path和watch_type至少指定一个
        """
        assert isinstance(callback, Callable), "✍️✍️✍️回调函数必须是可调用的✍️✍️✍️"
        assert watch_path or watch_type, "✍️✍️✍️监视路径或监视类型必须指定✍️✍️✍️"
        callback.__name__ = source_name
        if watch_type:
            for wt in watch_type:
                self.type_callbacks[wt].add(callback)
        if watch_path:
            for path in watch_path:
                path = path.resolve().absolute()
                await self._add_path(path)
                self.path_callbacks.setdefault(path, set()).add(callback)
        uuid_str = str(uuid.uuid4())
        self.callable_registration[uuid_str] = (watch_path or [], watch_type or [], callback)
        return uuid_str

    async def unregister_callback(self, uuid: str) -> None:
        """注销回调函数，移除所有与该回调函数相关的监视"""
        watch_path, watch_type, callback = self.callable_registration.get(uuid, ([], [], None))
        if not callback or not (watch_path or watch_type):
            logger.error(f"尝试注销不存在的回调函数或者函数监视为空，UUID: {uuid}")
            raise FileNotFoundError("尝试注销不存在的回调函数或者函数监视为空")
        for path in watch_path:
            path = path.resolve().absolute()
            if path in self.path_callbacks and callback in self.path_callbacks[path]:
                self.path_callbacks[path].remove(callback)
                if not self.path_callbacks[path]:
                    await self._remove_path(path)
                    del self.path_callbacks[path]
        for wt in watch_type:
            if wt in self.type_callbacks and callback in self.type_callbacks[wt]:
                self.type_callbacks[wt].remove(callback)
        return

    async def call_callbacks(
        self, changed_path: Path, change_type: ChangeType, watch_type: Optional[WatchType] = None
    ) -> None:
        """调用注册的回调函数"""
        if not changed_path.is_relative_to(PROJECT_ROOT):
            # 处理监视不在项目根目录下的路径
            for callback in self.path_callbacks.get(changed_path, []):
                await self._call_corresponding_callbacks(callback, changed_path, change_type)
            return

        while changed_path != PROJECT_ROOT.parent.resolve().absolute():
            # 逐级向上查找路径对应的回调函数
            for callback in self.path_callbacks.get(changed_path, []):
                await self._call_corresponding_callbacks(callback, changed_path, change_type)
            changed_path = changed_path.parent

        if watch_type:
            # 处理监视类型对应的回调函数
            for wt in hierarchy_map.get(watch_type, []):
                for callback in self.type_callbacks.get(wt, []):
                    await self._call_corresponding_callbacks(callback, changed_path, change_type)

    async def _call_corresponding_callbacks(
        self, callback: Callable[[Path, ChangeType], Any], changed_path: Path, change_type: ChangeType
    ) -> None:
        """调用对应的回调函数"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(changed_path, change_type)
            else:
                callback(changed_path, change_type)
        except Exception as e:
            logger.error(f"调用回调函数'{callback.__name__}'时出错: {e}")

    async def _add_path(self, path: Path) -> bool:
        """添加监视路径"""
        if path in self.watch_tasks:
            logger.warning(f"路径已在监视列表中: {path}")
            return False
        await self._watch_path(path)
        return True

    async def _remove_path(self, path: Path) -> bool:
        """移除监视路径"""
        if path not in self.watch_tasks:
            logger.warning(f"尝试移除未监视的路径: {path}")
            return False
        task = self.watch_tasks[path]
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=15.0)
        del self.watch_tasks[path]
        return True

    async def _watch_path(self, path: Path) -> None:
        """进行路径监视"""
        task = asyncio.create_task(self._path_observer(path))
        self.watch_tasks[path] = task

    async def _path_observer(self, path: Path):
        """使用watchfiles监视路径变化"""
        async for changes in awatch(path):
            for change, changed_path_str in changes:
                changed_path = Path(changed_path_str)
                wt: Optional[WatchType] = None
                resolved = changed_path.resolve().absolute()
                logger.info(f"检测到文件变化: {changed_path}，变化类型: {change.name}")
                if resolved == self.bot_config_path:
                    wt = WatchType.BOT_CONFIG_CHANGE
                elif resolved == self.model_config_path:
                    wt = WatchType.MODEL_CONFIG_CHANGE

                change_type: ChangeType = ChangeType.MODIFIED
                if change == Change.added:
                    change_type = ChangeType.CREATED
                elif change == Change.deleted:
                    change_type = ChangeType.DELETED
                await self.call_callbacks(changed_path, change_type, wt)


dynamic_construct_hierarchy_map()
