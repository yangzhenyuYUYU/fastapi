from tortoise import fields
from tortoise.models import Model
from enum import IntEnum
from datetime import datetime

class CreditProduct(Model):
    """积分产品表"""
    id = fields.IntField(pk=True, description="产品ID")
    name = fields.CharField(null=True, max_length=128, description="产品名称")
    credits = fields.IntField(null=True, description="积分数量")
    price = fields.DecimalField(null=True, max_digits=10, decimal_places=2, description="价格")
    status = fields.BooleanField(null=True, default=True, description="是否有效")
    created_at = fields.DatetimeField(null=True, default=datetime.now, description="创建时间")
    updated_at = fields.DatetimeField(null=True, default=datetime.now, description="更新时间")

    class Meta:
        table = "credit_products"
        table_description = "【贝】积分产品表"

class CreditRecordType(IntEnum):
    RECHARGE = 1   # 充值
    CONSUME = 2    # 消费
    REWARD = 3     # 奖励
    EXPIRED = 4    # 过期
    REFUND = 5     # 退款

class CreditRecord(Model):
    """积分消耗记录表"""
    id = fields.IntField(pk=True, description="记录ID")
    user = fields.ForeignKeyField("models.User", related_name="credit_records", description="关联用户")
    record_type = fields.IntEnumField(CreditRecordType, description="记录类型")
    credits = fields.IntField(null=True, description="积分变动数量")
    balance = fields.IntField(null=True, description="变动后余额")
    description = fields.CharField(null=True, max_length=256, description="变动描述")
    created_at = fields.DatetimeField(null=True, default=datetime.now, description="创建时间")

    class Meta:
        table = "credit_records"
        table_description = "【贝】积分消耗记录表"

class CreditRechargeOrder(Model):
    """积分充值订单表"""
    id = fields.IntField(pk=True, description="订单ID")
    user = fields.ForeignKeyField("models.User", related_name="credit_orders", description="关联用户")
    product = fields.ForeignKeyField("models.CreditProduct", related_name="orders", description="关联产品")
    trade = fields.ForeignKeyField("models.Trade", related_name="credit_orders", description="关联交易")
    created_at = fields.DatetimeField(null=True, default=datetime.now, description="创建时间")
    
    class Meta:
        table = "credit_recharge_orders"
        table_description = "【贝】积分充值订单表"

class ServiceUnit(IntEnum):
    COUNT = 1    # 按次数计费
    MINUTE = 2   # 按分钟计费
    CHAR = 3     # 按字符数计费
    SECOND = 4   # 按秒数计费
    TOKEN = 5    # 按token数计费

class CreditServicePrice(Model):
    """积分服务定价表"""
    id = fields.IntField(pk=True, description="ID")
    service_code = fields.CharField(max_length=64, unique=True, description="服务代号")
    name = fields.CharField(null=True, max_length=128, description="服务名称")
    credits = fields.IntField(null=True, description="消耗积分数/unit")
    unit = fields.IntEnumField(ServiceUnit, null=True, description="计费单位")
    description = fields.CharField(null=True, max_length=256, description="服务描述")
    status = fields.BooleanField(default=True, description="是否有效")
    created_at = fields.DatetimeField(null=True, default=datetime.now, description="创建时间")
    updated_at = fields.DatetimeField(null=True, default=datetime.now, description="更新时间")

    class Meta:
        table = "credit_service_prices"
        table_description = "【贝】积分服务定价表"

    def __str__(self):
        return f"{self.service_code}-{self.name}" 