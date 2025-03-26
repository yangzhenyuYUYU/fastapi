from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Type, Optional, List, Dict, Any, Callable
from tortoise import Model
from enum import Enum
from datetime import datetime
import json
from middleware.auth import verify_admin

class CRUDRouter:
    """通用CRUD路由基类"""
    
    @staticmethod
    async def _serialize_model(item: Model) -> dict:
        """通用的模型序列化方法"""
        result = {}
        for field_name, field in item._meta.fields_map.items():
            value = getattr(item, field_name)
            if value is None:
                result[field_name] = None
            elif isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, Enum):
                result[field_name] = value.value
            elif isinstance(value, (str, int, float, bool)):
                result[field_name] = value
            elif hasattr(value, "pk"):
                # 处理外键关系
                result[field_name] = value.pk
            else:
                try:
                    # 尝试 JSON 序列化
                    result[field_name] = json.dumps(value)
                except (TypeError, ValueError):
                    # 如果无法序列化，则转为字符串
                    result[field_name] = str(value)
        return result

    def __init__(self, model: Type[Model], prefix: str, tags: List[str], search_fields: List[str] = None,
                 default_ordering: str = None, require_admin: bool = False):
        """
        初始化CRUD路由
        
        Args:
            model: Tortoise ORM模型类
            prefix: 路由前缀
            tags: API标签列表
            search_fields: 可搜索字段列表
            default_ordering: 默认排序字段
            require_admin: 是否需要管理员权限，默认False
        """
        self.model = model
        self.router = APIRouter(prefix=prefix, tags=tags)
        self._pk_field = self._get_primary_key()
        self.search_fields = search_fields or []  # 可搜索字段列表
        self.default_ordering = default_ordering  # 默认排序字段
        self.require_admin = require_admin  # 是否需要管理员权限
        self.setup_routes()
        
    def __call__(self):
        """返回配置好的路由器"""
        return self.router

    def _get_primary_key(self) -> str:
        """获取模型的主键字段名"""
        for field_name, field in self.model._meta.fields_map.items():
            if field.pk:
                return field_name
        return "id"  # 默认返回id

    def setup_routes(self):
        # 定义依赖项
        dependencies = [Depends(verify_admin)] if self.require_admin else []
        
        @self.router.get("/list", dependencies=dependencies)
        async def get_list(
            page: int = Query(1, ge=1),
            page_size: int = Query(10, ge=1, le=9999),
            search: Optional[str] = None,
            order_by: Optional[str] = None,  
            order_direction: str = Query("desc", regex="^(asc|desc)$")  
        ):
            skip = (page - 1) * page_size
            query = self.model.all()
            
            if search and self.search_fields:
                from tortoise.expressions import Q
                q_filters = Q()
                for field in self.search_fields:
                    q_filters |= Q(**{f"{field}__icontains": search})
                query = query.filter(q_filters)
            
            ordering = order_by if order_by else self.default_ordering
            if ordering:
                if order_direction == "desc":
                    ordering = f"-{ordering}"
                query = query.order_by(ordering)
            
            total = await query.count()
            items = await query.offset(skip).limit(page_size)
            
            result = []
            for item in items:
                item_dict = await self._serialize_model(item)
                result.append(item_dict)
            
            return {
                "code": 0,
                "msg": "success",
                "data": {
                    "total": total,
                    "items": result,
                    "page": page,
                    "page_size": page_size,
                    "ordering": ordering,
                    "direction": order_direction
                }
            }

        @self.router.get("/{id}", dependencies=dependencies)
        async def get_detail(id: int):
            query_kwargs = {self._pk_field: id}
            item = await self.model.get_or_none(**query_kwargs)
            
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            
            result = await self._serialize_model(item)
            return {
                "code": 0,
                "msg": "success",
                "data": result
            }

        @self.router.post("", dependencies=dependencies)
        async def create(data: Dict[str, Any]):
            item = await self.model.create(**data)
            return {
                "code": 0,
                "msg": "success",
                "data": await self._serialize_model(item)
            }

        @self.router.put("/{id}", dependencies=dependencies)
        async def update(id: int, data: Dict[str, Any]):
            query_kwargs = {self._pk_field: id}
            item = await self.model.get_or_none(**query_kwargs)
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            await item.update_from_dict(data).save()
            return {
                "code": 0,
                "msg": "success",
                "data": await self._serialize_model(item)
            }

        @self.router.delete("/{id}", dependencies=dependencies)
        async def delete(id: int):
            query_kwargs = {self._pk_field: id}
            item = await self.model.get_or_none(**query_kwargs)
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            await item.delete()
            return {
                "code": 0,
                "msg": "success",
                "data": None
            }