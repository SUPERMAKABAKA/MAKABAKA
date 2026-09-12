"""模拟画像源。

定义画像源接口契约（``ProfileSourceInterface``）与从预置 JSON 数据集读取的
模拟实现（``MockProfileSource``）。

Profile_Agent 依赖模拟画像源按 ``user_id`` 加载用户画像（Req 3.1, 3.3）：命中
则返回 ``UserProfile`` 供预填偏好/预算/用途，未命中或未提供 ``user_id`` 时返回
``None``，供上层据此标记冷启动（Req 3.2）。``UserProfile`` 复用自
``app.orchestrator.models``，保持数据模型一致。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from app.orchestrator.models import UserProfile

__all__ = ["ProfileSourceInterface", "MockProfileSource"]


class ProfileSourceInterface(ABC):
    """画像源接口抽象，定义按 ``user_id`` 加载用户画像的契约（Req 2.1, 3.3）。

    调用方（如 Profile_Agent）仅依赖本抽象类型，替换实现无需修改调用代码
    （Req 2.4）。
    """

    @abstractmethod
    def load(self, user_id: Optional[str]) -> Optional[UserProfile]:
        """按 ``user_id`` 加载用户画像（Req 3.3）。

        Args:
            user_id: 用户标识；为 ``None`` 表示未提供画像标识。

        Returns:
            命中时返回对应的 ``UserProfile``；未命中或未提供标识时返回
            ``None``（Req 3.2 由调用方据此标记冷启动）。
        """
        raise NotImplementedError


class MockProfileSource(ProfileSourceInterface):
    """Profile_Source 的模拟实现。

    从预置的 JSON 数据集读取模拟用户画像，按 ``user_id`` 返回对应画像
    （Req 3.3）。数据集在实例化时并不要求已存在；仅在首次调用 ``load`` 时读取
    并缓存，若文件缺失或格式非法则给出清晰错误。

    数据集结构：``UserProfile`` 对象的数组，每个对象含 ``user_id``、
    ``preferences``、``budget``、``purpose`` 字段。
    """

    def __init__(self, dataset_path: str) -> None:
        """初始化模拟画像源。

        Args:
            dataset_path: 预置画像数据集（profiles.json）的路径。此处不校验
                文件是否存在，读取延迟到 ``load`` 调用时进行。
        """
        self._path = Path(dataset_path)
        self._profiles: dict[str, UserProfile] | None = None

    def load(self, user_id: Optional[str]) -> Optional[UserProfile]:
        """从预置数据集按 ``user_id`` 加载用户画像（Req 3.3）。

        Args:
            user_id: 用户标识；为 ``None`` 时直接返回 ``None``。

        Returns:
            命中时返回对应的 ``UserProfile``；``user_id`` 为 ``None`` 或数据集中
            无对应画像时返回 ``None``（Req 3.2）。
        """
        if user_id is None:
            return None
        self._ensure_loaded()
        assert self._profiles is not None
        return self._profiles.get(user_id)

    def _ensure_loaded(self) -> None:
        """延迟加载并解析数据集，结果缓存以避免重复读取。

        Raises:
            FileNotFoundError: 数据集文件不存在时抛出，附带路径信息。
            ValueError: 数据集不是合法 JSON，或顶层结构不是画像数组，
                或某条记录不是对象时抛出。
        """
        if self._profiles is not None:
            return

        if not self._path.is_file():
            raise FileNotFoundError(
                f"画像数据集不存在：{self._path}。"
                "请先生成预置数据集（data/profiles.json）后再加载用户画像。"
            )

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"画像数据集不是合法 JSON：{self._path}（{exc}）"
            ) from exc

        if not isinstance(raw, list):
            raise ValueError(
                f"画像数据集顶层结构应为数组，实际为 {type(raw).__name__}：{self._path}"
            )

        profiles: dict[str, UserProfile] = {}
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(
                    f"画像数据集第 {index} 条记录应为对象，"
                    f"实际为 {type(item).__name__}：{self._path}"
                )
            profile = self._parse_profile(item)
            profiles[profile.user_id] = profile
        self._profiles = profiles

    @staticmethod
    def _parse_profile(item: dict[str, Any]) -> UserProfile:
        """将单条 JSON 记录解析为 ``UserProfile``。

        Args:
            item: 单条用户画像的 JSON 对象。

        Returns:
            解析后的画像模型。

        Raises:
            ValueError: 记录缺少必填字段或字段类型非法时抛出。
        """
        return UserProfile.model_validate(item)
