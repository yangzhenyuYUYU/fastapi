from tortoise import fields
from tortoise.models import Model
from enum import Enum
from datetime import datetime

class CardType(str, Enum):
    MEMBERSHIP = "membership"   # 会员卡
    CREDITS = "credits"        # 积分卡

class ActivationCode(Model):
    """激活码表"""
    id = fields.IntField(pk=True, description="ID")
    code = fields.CharField(max_length=32, unique=True, description="激活码")
    card_type = fields.CharField(max_length=32, description="类型")
    product_id = fields.IntField(description="关联产品ID")  # 会员方案ID或积分产品ID
    is_used = fields.BooleanField(default=False, description="是否已使用")
    remark = fields.CharField(max_length=256, null=True, description="备注")
    used_by = fields.ForeignKeyField("models.User", null=True, related_name="used_codes", description="使用用户")
    trade = fields.ForeignKeyField("models.Trade", null=True, related_name="activation_trades", description="关联交易")
    created_at = fields.DatetimeField(null=True, default=datetime.now, description="创建时间")

    class Meta:
        table = "activation_codes"
        table_description = "【贝】激活码表"

    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        if not self.created_at:
            return False
        return (datetime.now() - self.created_at).days > self.duration