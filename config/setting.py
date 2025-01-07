import os
from typing import Dict, Any
from functools import cached_property

class Settings:
    def __init__(self):
        # 数据库基础配置
        self.DB_ENGINE = "mysql"
        self.DB_USER = 'root'
        self.DB_PASSWORD = '123456'
        self.DB_HOST = 'localhost'
        self.DB_PORT = '3306'
        self.DB_NAME = 'fastapi_demo'
        
        # JWT配置
        self.SECRET_KEY = "your-secret-key"
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

    @cached_property
    def DB_URL(self) -> str:
        return (
            f"{self.DB_ENGINE}://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @cached_property
    def TORTOISE_ORM(self) -> Dict[str, Any]:
        return {
            "connections": {"default": self.DB_URL},
            "apps": {
                "models": {
                    "models": ["models.user"],
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai"
        }

settings = Settings()
TORTOISE_ORM = settings.TORTOISE_ORM 