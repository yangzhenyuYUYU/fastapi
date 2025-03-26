from fastapi import APIRouter, Depends, Body, Query, status
from fastapi.responses import JSONResponse
from models.card import ActivationCode, CardType
from models.trade import Trade, TradeType, PaymentChannel, PaymentStatus
from models.credits import CreditProduct, CreditRecord, CreditRecordType, CreditRechargeOrder
from models.user import User, UserRole
from middleware.auth import get_current_user
from datetime import datetime
import time
from tools.crud import CRUDRouter
from decimal import Decimal
import random
import string
from pydantic import BaseModel

router = APIRouter(prefix="/active", tags=["激活码"])

# 后台管理CRUD路由
activation_code_crud = CRUDRouter(
    model=ActivationCode,
    prefix="/manager",
    tags=["激活码管理"],
    search_fields=["code", "remark"]
)

async def generate_activation_code():
    """生成激活码"""
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return code

router.include_router(activation_code_crud.router)

@router.get('/list', summary="获取激活码列表")
async def get_activation_code_list(
    page: int = Query(1, description="页码"), 
    page_size: int = Query(10, description="每页数量")
):
    """获取激活码列表"""
    try:
        total = await ActivationCode.all().count()
        activation_codes = await ActivationCode.all().order_by('-created_at').offset((page - 1) * page_size).limit(page_size)
        list = []
        for activation_code in activation_codes:
            user = await User.get_or_none(id=activation_code.used_by_id)
            if user:
                user_info = {
                    "id": user.id,
                    "avatar": user.avatar,
                    "phone": user.phone,
                    "username": user.username
                }
            else:
                user_info = None

            product_description = ""

            if activation_code.card_type == CardType.CREDITS.value:
                product = await CreditProduct.get_or_none(id=activation_code.product_id)
                product_description = f"{product.name}, 积分: {product.credits}"

            list.append({
                "id": activation_code.id,
                "code": activation_code.code,
                "card_type": activation_code.card_type,
                "product_id": activation_code.product_id,
                "created_at": activation_code.created_at,
                "used_by": user_info,
                "is_used": activation_code.is_used,
                "remark": activation_code.remark,
                "product_description": product_description
            })
        return {
            "code": 0,
            "msg": "获取激活码列表成功",
            "data": {
                "items": list,
                "total": total
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "msg": f"服务器内部错误: {str(e)}"
        }


@router.post('/create', summary="创建激活码")
async def create_activation_code(
    card_type: CardType = Body(...),
    product_id: int = Body(...),
    remark: str = Body(None)
):
    """创建激活码"""
    try:
        code = await generate_activation_code()
        activation_code = await ActivationCode.create(
            code=code,
            card_type=card_type,
            product_id=product_id
        )
        if remark:
            activation_code.remark = remark
            await activation_code.save()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 0,
                "msg": "激活码创建成功", 
                "data": {
                    "id": activation_code.id,
                    "code": code,
                    "card_type": card_type.value,
                    "product_id": product_id,
                    "created_at": str(activation_code.created_at),
                    "used_by": None,
                    "is_used": activation_code.is_used,
                    "remark": activation_code.remark
                }
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": 1,
                "msg": f"服务器内部错误: {str(e)}"
            }
        )

# 添加请求模型
class ActivateCodeRequest(BaseModel):
    code: str

@router.post("/activate", summary="使用激活码")
async def activate_code(
    request: ActivateCodeRequest,
    current_user: User = Depends(get_current_user)
):
    """使用激活码获取会员或积分"""
    try:
        # 查找激活码
        activation = await ActivationCode.get_or_none(
            code=request.code,
            is_used=False
        )
        
        if not activation:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "code": 1,
                    "msg": "无效的激活码"
                }
            )
            
        # 根据类型处理不同业务
        if activation.card_type == CardType.CREDITS.value:
            # 积分卡
            product = await CreditProduct.get_or_none(id=activation.product_id)
            if not product: 
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "code": 1,
                        "msg": "积分产品不存在"
                    }
                )
                
            # 创建交易记录
            trade = await Trade.create(
                trade_no=f"ACT{int(time.time())}",
                user=current_user,
                amount=Decimal(product.price),  # 激活码兑换时金额为0
                trade_type=TradeType.RECHARGE.value,
                payment_channel=PaymentChannel.ACTIVATION.value,
                payment_status=PaymentStatus.SUCCESS.value,
                title=f"激活码兑换{product.credits}积分",
                metadata={
                    "activation_code": request.code,
                    "product_id": product.id,
                    "product_name": product.name,
                    "credits": product.credits
                },
                paid_at=datetime.now()
            )

            # 创建积分充值订单
            order = await CreditRechargeOrder.create(
                user=current_user,
                trade=trade,
                product=product
            )
            # 充值积分
            current_user.credits += product.credits
            await current_user.save()
            
            # 记录积分变动
            await CreditRecord.create(
                user=current_user,
                record_type=CreditRecordType.RECHARGE,
                credits=product.credits,
                balance=current_user.credits,
                description=f"激活码充值积分 +{product.credits}"
            )
        
        # 更新激活码状态
        activation.is_used = True
        activation.used_at = datetime.now()
        activation.used_by = current_user
        activation.trade = trade
        await activation.save()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 0,
                "msg": "激活成功",
                "data": {
                    "trade_no": trade.trade_no,
                    "amount": float(trade.amount),
                    "title": trade.title
                }
            }
        )
        
    except Exception as e:
        print(f"Activation error: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "code": 1,
                "msg": f"服务器内部错误: {str(e)}"
            }
        ) 