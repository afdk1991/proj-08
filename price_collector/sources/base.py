# -*- coding: utf-8 -*-
"""数据源抽象基类与工厂。

所有数据源都实现相同接口，流水线只依赖接口，做到「可插拔真实数据源」。
- 每个平台一个 sources/<key>.py，实现 BaseSource
- SourceFactory.init_registry 动态发现并注册所有已安装源
- 未知平台直接抛错（不再有任何示例/mock 兜底），宁缺毋假
"""
from abc import ABC, abstractmethod
from typing import List

from ..models import Product


class BaseSource(ABC):
    """数据源统一接口。"""

    platform: str = ""      # 平台标识
    platform_name: str = ""  # 平台中文名

    @abstractmethod
    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        """抓取指定关键词下的一页商品原始数据（未清洗）。实现方必须吞掉一切异常返回 []。"""
        raise NotImplementedError

    def can_live(self) -> bool:
        """该类是否具备真实联网抓取能力。"""
        return False


class SourceFactory:
    """根据平台标识创建数据源实例。"""

    _registry = {}

    @classmethod
    def register(cls, platform: str, source_cls):
        cls._registry[platform] = source_cls

    @classmethod
    def create(cls, platform: str, **kwargs) -> BaseSource:
        if platform not in cls._registry:
            raise ValueError(f"unknown platform: {platform}")
        return cls._registry[platform](**kwargs)

    @classmethod
    def available(cls) -> List[str]:
        """已注册的平台键列表（注册表初始化后调用）。"""
        return sorted(cls._registry.keys())

    @classmethod
    def init_registry(cls):
        """动态发现 sources 包下所有真实数据源模块并注册。

        每个模块应当定义恰好一个继承 BaseSource 的类（带 platform 类属性）。
        单个模块导入失败不会拖垮整体——该平台被跳过，其余正常。
        """
        if cls._registry:
            return
        import importlib
        import inspect
        from . import registry as _reg  # 权威键名清单
        for key in _reg.ALL_PLATFORMS:
            try:
                mod = importlib.import_module(f".{key}", package=__package__)
            except Exception:
                continue
            for _name, obj in inspect.getmembers(mod, inspect.isclass):
                if obj is BaseSource:
                    continue
                if obj.__module__ != mod.__name__:
                    continue  # 只取本模块定义的类，不取被 import 进来的
                if issubclass(obj, BaseSource) and getattr(obj, "platform", ""):
                    cls.register(obj.platform, obj)
