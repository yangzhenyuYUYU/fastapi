from datetime import datetime
from typing import Any, Dict

def format_datetime(dt: datetime) -> str:
    """格式化日期时间"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_response(*, code: int = 200, message: str = "success", data: Any = None) -> Dict:
    """统一响应格式"""
    return {
        "code": code,
        "message": message,
        "data": data
    } 