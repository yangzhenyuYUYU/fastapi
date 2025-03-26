from tortoise import fields
from tortoise.models import Model
from enum import Enum
from datetime import datetime

class PaymentChannel(str, Enum):
    # 支付宝相关支付方式
    ALIPAY = "alipay"           # 支付宝APP支付
    ALIPAY_QR = "alipay_qr"     # 支付宝正扫
    ALIPAY_WAP = "alipay_wap"   # 支付宝H5支付
    ALIPAY_LITE = "alipay_lite" # 支付宝小程序支付
    ALIPAY_PUB = "alipay_pub"   # 支付宝生活号支付
    ALIPAY_SCAN = "alipay_scan" # 支付宝反扫

    # 微信相关支付方式
    WX_QR = "wx_qr"           # 微信正扫 
    WX_PUB = "wx_pub"           # 微信公众号支付
    WX_LITE = "wx_lite"         # 微信小程序支付
    WX_SCAN = "wx_scan"         # 微信反扫

    # 银联相关支付方式
    UNION = "union"             # 银联云闪付App支付
    UNION_QR = "union_qr"       # 银联云闪付正扫
    UNION_WAP = "union_wap"     # 银联云闪付H5支付
    UNION_SCAN = "union_scan"   # 银联云闪付反扫
    UNION_ONLINE = "union_online" # 银联H5支付
    UNION_CHECKOUT = "union_checkout" # 银联统一收银台支付

    # 其他支付方式
    FAST_PAY = "fast_pay"       # 快捷支付
    B2C = "b2c"                 # 个人网银支付
    B2B = "b2b"                 # 企业网银支付
    CARD_KEY = "card_key"       # 卡密激活
    ACTIVATION = "activation"    # 激活码兑换

    # 积分支付
    CREDIT = "credit" # 积分支付

class PaymentStatus(str, Enum):
    PENDING = "pending"    # 待支付
    SUCCESS = "success"    # 支付成功
    FAILED = "failed"     # 支付失败
    REFUNDED = "refunded"   # 已退款

class TradeType(str, Enum):
    RECHARGE = "recharge"   # 充值
    CONSUME = "consume"    # 消费
    REFUND = "refund"     # 退款
    ACTIVATION = "activation"  # 激活码兑换
    ACTIVATION_REFUND = "activation_refund"  # 激活码兑换退款
    COMMISSION = "commission"  # 佣金收入

class Trade(Model):
    """交易记录表"""
    id = fields.IntField(pk=True, description="交易ID")
    trade_no = fields.CharField(max_length=64, unique=True, description="交易流水号")
    user = fields.ForeignKeyField("models.User", related_name="trades", description="关联用户")
    amount = fields.DecimalField(max_digits=10, decimal_places=2, description="交易金额")
    trade_type = fields.CharField(max_length=64, description="交易类型")
    payment_channel = fields.CharField(max_length=64, description="支付渠道")
    payment_status = fields.CharField(max_length=64, default=PaymentStatus.PENDING.value, description="支付状态")
    payment_id = fields.CharField(null=True, max_length=64, description="支付ID")
    title = fields.CharField(max_length=128, description="交易标题")
    metadata = fields.JSONField(null=True, description="元数据，用于存储特定业务数据")
    
    created_at = fields.DatetimeField(null=True, default=datetime.now, description="创建时间")
    paid_at = fields.DatetimeField(null=True, description="支付时间")

    class Meta:
        table = "trades"
        table_description = "【贝】交易记录表"

    def __str__(self):
        return f"{self.trade_no}-{self.title}"
