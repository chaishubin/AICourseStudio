"""
人脸视频生成 API 注册中心

支持动态注册和获取不同厂商的实现
"""

from typing import Dict, Type, Optional, Any
from pathlib import Path

from .base import BaseFaceVideoProvider


class ProviderRegistry:
    """
    Provider 注册中心

    使用示例：
    ```python
    # 注册 Provider
    registry.register("sadtalker", SadTalkerProvider)

    # 获取 Provider 实例
    provider = registry.get("sadtalker", config={"api_key": "xxx"})

    # 列出所有已注册的 Provider
    registry.list_providers()
    ```
    """

    def __init__(self):
        self._providers: Dict[str, Type[BaseFaceVideoProvider]] = {}

    def register(self, name: str, provider_class: Type[BaseFaceVideoProvider]) -> None:
        """
        注册 Provider

        Args:
            name: Provider 名称（用于后续获取）
            provider_class: Provider 类（不是实例）
        """
        if not issubclass(provider_class, BaseFaceVideoProvider):
            raise TypeError(
                f"{provider_class} 必须继承自 BaseFaceVideoProvider"
            )
        self._providers[name] = provider_class
        print(f"[Registry] 已注册 Provider: {name}")

    def unregister(self, name: str) -> bool:
        """
        注销 Provider

        Args:
            name: Provider 名称

        Returns:
            是否成功注销
        """
        if name in self._providers:
            del self._providers[name]
            return True
        return False

    def get(
        self,
        name: str,
        config: Dict[str, Any] = None
    ) -> BaseFaceVideoProvider:
        """
        获取 Provider 实例

        Args:
            name: Provider 名称
            config: 配置参数

        Returns:
            Provider 实例

        Raises:
            KeyError: Provider 未注册
        """
        if name not in self._providers:
            available = list(self._providers.keys())
            raise KeyError(
                f"Provider '{name}' 未注册\n"
                f"可用 Provider: {available}"
            )
        provider_class = self._providers[name]
        return provider_class(config)

    def list_providers(self) -> Dict[str, str]:
        """
        列出所有已注册的 Provider

        Returns:
            {name: description} 字典
        """
        return {
            name: cls.description
            for name, cls in self._providers.items()
        }

    def is_registered(self, name: str) -> bool:
        """检查 Provider 是否已注册"""
        return name in self._providers


# 全局注册中心实例
registry = ProviderRegistry()


def register_provider(name: str):
    """
    装饰器：注册 Provider

    使用示例：
    ```python
    @register_provider("sadtalker")
    class SadTalkerProvider(BaseFaceVideoProvider):
        ...
    ```
    """
    def decorator(cls):
        registry.register(name, cls)
        return cls
    return decorator


def get_provider(name: str, config: Dict[str, Any] = None) -> BaseFaceVideoProvider:
    """获取 Provider 实例（便捷函数）"""
    return registry.get(name, config)


def list_providers() -> Dict[str, str]:
    """列出所有 Provider（便捷函数）"""
    return registry.list_providers()
