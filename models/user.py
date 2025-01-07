from tortoise import fields
from tortoise.models import Model
from enum import IntEnum

class UserStatus(IntEnum):
    ACTIVE = 1
    INACTIVE = 0

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password = fields.CharField(max_length=128)
    email = fields.CharField(max_length=255, null=True)
    status = fields.IntEnumField(UserStatus, default=UserStatus.ACTIVE)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
        table_description = "用户表"

    def __str__(self):
        return self.username 