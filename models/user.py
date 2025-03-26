from tortoise import fields
from tortoise.models import Model
from enum import IntEnum

class UserRole(IntEnum):
    NORMAL = 1
    VIP = 2
    ADMIN = 3

class UserStatus(IntEnum):
    ACTIVE = 1
    INACTIVE = 0

class SessionStatus(IntEnum):
    ACTIVE = 1    # 活跃状态
    INACTIVE = 2  # 已退出或被挤退

class LoginType(str):
    WEB = "web"          # 网页端
    MINI_PROGRAM = "mini" # 小程序端
    APP = "app"          # APP端

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True, description="用户名")
    password = fields.CharField(max_length=128, description="密码")
    email = fields.CharField(max_length=255, null=True, description="邮箱")
    credits = fields.IntField(default=0, description="积分")
    role = fields.IntEnumField(UserRole, default=UserRole.NORMAL, description="角色")
    status = fields.IntEnumField(UserStatus, default=UserStatus.ACTIVE, description="状态")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "users"
        table_description = "用户表"

    def __str__(self):
        return self.username 

class UserSession(Model):
    """用户登录会话表"""
    id = fields.IntField(pk=True, description="会话ID")
    user = fields.ForeignKeyField(
        "models.User", 
        related_name="sessions", 
        description="关联用户"
    )
    token = fields.TextField(description="登录token")
    login_type = fields.CharField(
        max_length=20, 
        description="登录类型",
        default=LoginType.WEB
    )
    ip_address = fields.CharField(max_length=45, description="登录IP")
    device_id = fields.CharField(max_length=100, null=True, description="设备ID")
    status = fields.IntEnumField(
        SessionStatus,
        default=SessionStatus.ACTIVE,
        description="会话状态"
    )
    last_active_time = fields.DatetimeField(
        auto_now=True,
        description="最后活跃时间"
    )
    created_at = fields.DatetimeField(
        auto_now_add=True,
        description="创建时间"
    )

    class Meta:
        table = "user_sessions"
        table_description = "用户登录会话表"
        
    @classmethod
    async def deactivate_other_sessions(cls, user_id: int, login_type: str, current_token: str):
        """使同类型的其他会话失效"""
        await cls.filter(
            user_id=user_id,
            login_type=login_type,
            token__not=current_token,
            status=SessionStatus.ACTIVE
        ).update(status=SessionStatus.INACTIVE)

    def __str__(self):
        return f"{self.user.username}的{self.login_type}登录会话({self.ip_address})"