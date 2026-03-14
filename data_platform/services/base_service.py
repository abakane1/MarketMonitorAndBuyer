# -*- coding: utf-8 -*-
"""
基础服务类

所有数据服务的基类，定义统一接口。
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Tuple, Dict, Any
from datetime import datetime
import sqlite3

from ..models.base import BaseModel

T = TypeVar('T', bound=BaseModel)


class BaseService(ABC, Generic[T]):
    """
    基础数据服务
    
    所有数据服务必须继承此类，确保接口一致性。
    """
    
    DB_FILE = "user_data.db"
    
    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 5  # 默认缓存5秒
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn
    
    @abstractmethod
    def get(self, id: str, portfolio_id: str = "default") -> Optional[T]:
        """根据ID获取数据"""
        pass
    
    @abstractmethod
    def get_all(self, portfolio_id: str = "default") -> List[T]:
        """获取所有数据"""
        pass
    
    @abstractmethod
    def save(self, model: T) -> Tuple[bool, str]:
        """保存数据"""
        pass
    
    @abstractmethod
    def delete(self, id: str, portfolio_id: str = "default") -> bool:
        """删除数据"""
        pass
    
    def validate(self, model: T) -> Tuple[bool, str]:
        """数据校验"""
        return model.validate()
    
    def invalidate_cache(self, key: str = None):
        """使缓存失效"""
        if key:
            self._cache.pop(key, None)
            self._cache_time.pop(key, None)
        else:
            self._cache.clear()
            self._cache_time.clear()
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取"""
        if key in self._cache:
            cache_time = self._cache_time.get(key, 0)
            if datetime.now().timestamp() - cache_time < self._cache_ttl:
                return self._cache[key]
            else:
                # 缓存过期
                self._cache.pop(key, None)
                self._cache_time.pop(key, None)
        return None
    
    def _set_cache(self, key: str, value: Any):
        """设置缓存"""
        self._cache[key] = value
        self._cache_time[key] = datetime.now().timestamp()
