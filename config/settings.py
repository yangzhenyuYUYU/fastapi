import os
from typing import Dict, Any
from functools import cached_property

class Settings:
    def __init__(self):
        # 基础配置
        self.API_BASE_URL = 'http://localhost:8000/api'

        # Adapay支付信息
        self.ADAPAY_API_KEY = ''
        self.ADAPAY_MOCK_API_KEY = ''
        self.ADAPAY_PRIVATE_KEY = ''
        self.ADAPAY_APP_ID = ''
        self.ADAPAY_NOTIFY_URL = f'{self.API_BASE_URL}/trade/notify'

        # 微信小程序配置
        self.WX_APPID = ""
        self.WX_SECRET = ""

        # 微信公众号配置
        self.WX_GZH_TOKEN = ""
        self.WX_GZH_APPID = ""
        self.WX_GZH_SECRET = ""

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
        self.ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 30  # 30天
        
        # 验证码配置
        self.VERIFY_CODE_EXPIRE = 300  # 验证码有效期（秒）
        self.VERIFY_CODE_RESEND_INTERVAL = 60  # 重发间隔（秒）

        # 短信配置
        self.SMS_SECRET_ID = ""
        self.SMS_SECRET_KEY = ""
        self.SMS_SDK_APP_ID = ""
        self.SMS_SIGN_NAME = ""
        self.SMS_TEMPLATE_ID = ""

        # Redis配置
        self.REDIS_HOST = "localhost"
        self.REDIS_PORT = 6379
        self.REDIS_DB = 0
        self.REDIS_PASSWORD = "123456"

        # OSS配置
        self.OSS_ACCESS_KEY_ID = ''
        self.OSS_ACCESS_KEY_SECRET = ''
        
        # 修改这里：区分内外网 endpoint
        self.OSS_INTERNAL_ENDPOINT = 'oss-cn-hangzhou-internal.aliyuncs.com'  # 内网地址
        self.OSS_ENDPOINT = 'oss-cn-hangzhou.aliyuncs.com'  # 外网地址
        self.OSS_BUCKET_NAME = 'your-bucket-name'  # Changed to a more unique name
    

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