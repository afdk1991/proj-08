# -*- coding: utf-8 -*-
"""数据源抽象层与工厂。

不再内置任何示例/mock 数据源；所有平台源由 init_registry 动态发现。
"""
from .base import BaseSource, SourceFactory
from .registry import (
    ALL_PLATFORMS,
    PLATFORM_NAMES,
    PLATFORM_COMPANIES,
)

__all__ = [
    "BaseSource", "SourceFactory",
    "ALL_PLATFORMS", "PLATFORM_NAMES",
    "PLATFORM_COMPANIES", "get_source",
]


def get_source(platform: str, **kwargs) -> BaseSource:
    """按平台标识获取数据源实例（注册表未初始化时先初始化）。"""
    SourceFactory.init_registry()
    return SourceFactory.create(platform, **kwargs)
