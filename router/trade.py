from fastapi import APIRouter, HTTPException, Depends, Body, Query
from fastapi.responses import JSONResponse
from models.trade import Trade, TradeType, PaymentStatus, PaymentChannel
from models.user import User, UserRole
from middleware.auth import get_current_user
import logging
import time
import math
import urllib.parse
from datetime import datetime, timedelta
from decimal import Decimal
import adapay
from config.settings import Settings
from typing import Optional, List
from tortoise.expressions import Q

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trade", tags=["支付交易"])


settings = Settings()

# 初始化 Adapay SDK 配置 - 测试环境
config_info = {
    'api_key': settings.ADAPAY_API_KEY,
    'private_key': settings.ADAPAY_PRIVATE_KEY,
    'mock_mode': True  # 启用测试模式
}

adapay.mer_config = {
    'merchant_key': config_info
}


@router.put('/credit/pay/{trade_no}', summary="积分支付")
async def credit_pay(
    trade_no: str,
    current_user: User = Depends(get_current_user)
):
    """积分支付"""
    try:
        trade = await Trade.get_or_none(trade_no=trade_no)
        if not trade:
            raise Exception("交易单号不存在")
        
        amount = trade.amount
        # 总计需要消耗积分，向上取整
        total_credits = math.ceil(amount * 10)

        if total_credits > current_user.credits:
            raise Exception("积分不足")
        
        title = trade.title
        metadata = trade.metadata
        
        # 确保从 metadata 中获取 product_type
        product_type = metadata.get("product_type")
        product_id = metadata.get("product_id")

        # 2. 更新用户积分
        current_user.credits -= total_credits
        await current_user.save()

        # 更新交易订单状态
        trade.payment_status = PaymentStatus.SUCCESS.value
        await trade.save()

        # 5. 返回结果
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "trade_no": trade.trade_no,
                "amount": trade.amount,
                "trade_type": trade.trade_type,
                "payment_channel": trade.payment_channel,
                "payment_status": trade.payment_status,
                "title": trade.title,
                "metadata": trade.metadata
            }
        }
    except Exception as e:
        logger.error(f"积分支付失败: {str(e)}")
        trade.payment_status = PaymentStatus.FAILED.value
        await trade.save()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/credit/order", summary="积分支付预下单")
async def credit_order(
    product_type: str = Body(..., description="产品类型: credits-积分充值, membership-会员充值, template-数字商品"),
    product_id: int = Body(..., description="产品ID"),
    current_user: User = Depends(get_current_user)
):
    """积分支付预下单"""
    try:
        # 1. 创建交易记录
        trade = await Trade.create(
            trade_no=f"T{int(time.time())}{current_user.id}",
            user=current_user,
            amount=amount,
            trade_type=TradeType.CONSUME.value,
            payment_channel=PaymentChannel.CREDIT.value,
            payment_status=PaymentStatus.PENDING.value,
            title="积分产品购买",
        )
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "trade_no": trade.trade_no,
                "amount": trade.amount
            }
        }
    except Exception as e:
        logger.error(f"积分支付预下单失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post('/credit/batch_order', summary="积分批量创建预支付订单")
async def credit_batch_order(
    total_amount: float = Body(..., description="总金额"),
    products: List[dict] = Body(..., description="产品列表"),
    current_user: User = Depends(get_current_user)
):
    """积分批量创建预支付订单"""
    try:
        title = "积分批量购买商品"

        if not products:
            raise Exception("未携带购物车数据")

        # 1. 创建交易记录
        trade = await Trade.create(
            trade_no=f"T{int(time.time())}{current_user.id}",
            user=current_user,
            amount=total_amount,
            trade_type=TradeType.CONSUME.value,
            payment_channel=PaymentChannel.CREDIT.value,
            payment_status=PaymentStatus.PENDING.value,
            title=title,
            metadata={
                "product_type": "batch",
                "products": products
            }
        )

        # 3. 创建积分记录
        await CreditRecord.create(
            user=current_user,
            record_type=CreditRecordType.CONSUME,
            credits=-total_amount,
            balance=current_user.credits,
            description=f"积分批量购买商品，总金额: {total_amount}"
        )

        # 4. 返回结果
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "trade_no": trade.trade_no,
                "amount": trade.amount,
                "notice": notice,
                "discount": discount,
                "products": products
            }
        }
    except Exception as e:
        logger.error(f"积分批量创建预支付订单失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create", summary="创建支付订单")
async def create_trade(
    product_type: str = Body(..., description="产品类型: credits-积分充值, membership-会员充值"),
    product_id: int = Body(..., description="产品ID"),
    payment_channel: PaymentChannel = Body(..., description="支付渠道"),
    expend_params: Optional[dict] = Body(None, description="扩展参数") or {},
    current_user: User = Depends(get_current_user)
):
    """创建支付订单"""
    try:
        # 1. 查询产品信息
        # 2. 创建交易记录
        trade = await Trade.create(
            trade_no=f"T{int(time.time())}{current_user.id}",
            user=current_user,
            amount=amount,
            trade_type=TradeType.RECHARGE.value,
            payment_channel=payment_channel,
            payment_status=PaymentStatus.PENDING.value,
            title=title,
            metadata=metadata
        )
        # 3. 创建订单记录
        # 4. 调用 Adapay SDK 创建支付
        try:
            if not expend_params:
                if payment_channel == PaymentChannel.ALIPAY.value:
                    expend_params = {
                        "service": "alipay.trade.app.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.ALIPAY_QR.value:
                    expend_params = {
                        "service": "alipay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.ALIPAY_WAP.value:
                    expend_params = {
                        "service": "alipay.trade.wap.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.ALIPAY_LITE.value:
                    expend_params = {
                        "service": "alipay.trade.create",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.ALIPAY_PUB.value:
                    expend_params = {
                        "service": "alipay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.ALIPAY_SCAN.value:
                    expend_params = {
                        "service": "alipay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.WX_QR.value:
                    expend_params = {
                        "wx_app_id": settings.WX_GZH_APPID,
                    }
                elif payment_channel == PaymentChannel.WX_PUB.value:
                    expend_params = {
                        "open_id": current_user.openid_gzh
                    }
                elif payment_channel == PaymentChannel.WX_LITE.value:
                    expend_params = {
                        "open_id": current_user.openid,
                    }
                elif payment_channel == PaymentChannel.WX_SCAN.value:
                    expend_params = {
                        "service": "wxpay.unified.order",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.UNION.value:
                    expend_params = {
                        "service": "unionpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.UNION_QR.value:
                    expend_params = {
                        "service": "unionpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.UNION_WAP.value:
                    expend_params = {
                        "service": "unionpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.UNION_SCAN.value:
                    expend_params = {
                        "service": "unionpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.UNION_ONLINE.value:
                    expend_params = {
                        "service": "unionpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.UNION_CHECKOUT.value:
                    expend_params = {
                        "service": "unionpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.FAST_PAY.value:
                    expend_params = {
                        "service": "fastpay.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.B2C.value:
                    expend_params = {
                        "service": "b2c.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.B2B.value:
                    expend_params = {
                        "service": "b2b.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.CARD_KEY.value:
                    expend_params = {
                        "service": "cardkey.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }
                elif payment_channel == PaymentChannel.ACTIVATION.value:
                    expend_params = {
                        "service": "activation.trade.page.pay",
                        "notify_url": settings.ADAPAY_NOTIFY_URL
                    }

            result = adapay.Payment.create(
                mer_key='merchant_key',
                order_no=trade.trade_no,
                app_id=settings.ADAPAY_APP_ID,
                pay_channel=payment_channel,
                pay_amt=f"{amount:.2f}",
                # pay_amt=str(0.01),
                goods_title=title,
                goods_desc=description,
                notify_url=settings.ADAPAY_NOTIFY_URL,
                device_info={       
                    "device_ip": settings.DB_HOST
                },
                expend=expend_params
            )
            
            logger.info(f"支付创建结果: {result}")
            logger.info(dict(result))
            
            if not result:
                raise Exception("支付接口返回为空")
                
            if result.get("status") != "succeeded":
                error_msg = result.get("error_msg", "创建支付订单失败")
                logger.error(f"支付创建失败: {error_msg}")
                raise Exception(error_msg)
            trade.payment_id = result.get("id")
            await trade.save()
        except Exception as e:
            logger.error(f"调用支付接口异常: {str(e)}", exc_info=True)  # 添加异常堆栈信息
            raise Exception(f"调用支付接口失败: {str(e)}")

        print(f"支付信息pay_info: {result.get('expend', {}).get('pay_info')}")
        logger.info(f"支付信息pay_info: {result.get('expend', {}).get('pay_info')}")
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "trade_no": trade.trade_no,
                "amount": trade.amount,
                "payment_channel": trade.payment_channel,
                "party_order_id": result.get("party_order_id"),
                "payment_id": result.get("id"),
                "expend": result.get("expend"),
                "pay_info": result.get("expend", {}).get("pay_info")
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"创建支付订单失败: {str(e)}")
        trade.payment_status = PaymentStatus.FAILED.value
        await trade.save()
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/batch_create', summary="购物车结算支付订单")
async def batch_create_trade(
    total_amount: float = Body(..., description="总金额"),
    payment_channel: PaymentChannel = Body(..., description="支付渠道"),
    products: Optional[list] = Body(..., description="购物车列表"),
    current_user: User = Depends(get_current_user)
):
    try:
        title = "数字商城批量购买数字商品"
        logger.info(title)

        if not products:
            raise Exception(f"未携带购物车数据")
        # 1. 创建交易记录
        trade = await Trade.create(
            trade_no=f"T{int(time.time())}{current_user.id}",
            user=current_user,
            amount=total_amount,
            trade_type=TradeType.RECHARGE.value,
            payment_channel=payment_channel,
            payment_status=PaymentStatus.PENDING.value,
            title=title,
            metadata={
                "product_type": "batch",
                "products": products
            }
        )

        # 2. 调用 Adapay SDK 创建支付
        try:
            description = ''
            current_index = 0
            cars_length = len(products)
            for item in products:
                current_index += 1
                description += f"{item['product_name']} * {item['quantity']}"
                description += '、' if  current_index < cars_length else "。"
                
            result = adapay.Payment.create(
                mer_key='merchant_key',
                order_no=trade.trade_no,
                app_id=settings.ADAPAY_APP_ID,
                pay_channel=payment_channel,
                pay_amt=f"{total_amount:.2f}",
                # pay_amt=str(0.01),
                goods_title=title,
                goods_desc=description,
                notify_url=settings.ADAPAY_NOTIFY_URL,
                device_info={       
                    "device_ip": settings.DB_HOST
                },
                expend=expend_params
            )
            
            logger.info(f"支付创建结果: {result}")
            
            if not result:
                raise Exception("支付接口返回为空")
                
            if result.get("status") != "succeeded":
                error_msg = result.get("error_msg", "创建支付订单失败")
                logger.error(f"支付创建失败: {error_msg}")
                raise Exception(error_msg)
            trade.payment_id = result.get("id")
            await trade.save()
        except Exception as e:
            logger.error(f"调用支付接口异常: {str(e)}", exc_info=True)  # 添加异常堆栈信息
            raise Exception(f"调用支付接口失败: {str(e)}")
        
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "trade_no": trade.trade_no,
                "amount": trade.amount,
                "payment_channel": trade.payment_channel,
                "party_order_id": result.get("party_order_id"),
                "payment_id": result.get("id"),
                "expend": result.get("expend"),
                "pay_info": result.get("expend", {}).get("pay_info")
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"创建支付订单失败: {str(e)}")
        trade.payment_status = PaymentStatus.FAILED.value
        await trade.save()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/notify", summary="支付回调通知")
async def payment_notify(data: dict = Body(...)):
    """支付回调通知处理"""
    try:
        logger.info(f"收到支付回调: {data}")
        
        # 1. 验证签名
        if not adapay.verify_sign(data, data.get("sign")):
            raise HTTPException(status_code=400, detail="签名验证失败")

        # 2. 查询交易记录
        trade = await Trade.get_or_none(trade_no=data.get("order_no"))
        if not trade:
            raise HTTPException(status_code=404, detail="交易记录不存在")
        
        if trade.payment_status == PaymentStatus.SUCCESS.value:
            raise HTTPException(status_code=400, detail="该订单已完成")
        # 3. 判断支付状态
        if data.get("status") == "succeeded":
            # 更新交易状态
            trade.payment_status = PaymentStatus.SUCCESS.value
            trade.paid_at = datetime.now()
            await trade.save()

        elif data.get("status") == "failed":
            trade.payment_status = PaymentStatus.FAILED.value
            await trade.save()

        return {"code": 0, "msg": "success"}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"处理支付回调失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/query/{trade_no}", summary="查询交易状态")
async def query_trade(
    trade_no: str,
    current_user: User = Depends(get_current_user)
):
    """查询交易状态"""
    try:
        trade = await Trade.get_or_none(
            trade_no=trade_no,
            user=current_user
        )
        if not trade:
            raise HTTPException(status_code=404, detail="交易记录不存在")

        # 查询支付状态
        if trade.payment_status == PaymentStatus.PENDING.value:
            result = adapay.Payment.query(payment_id=trade.payment_id, mer_key='merchant_key')
            logger.info(f"查询支付状态结果: {result}")
            if result.get("status") == "succeeded":
                trade.payment_status = PaymentStatus.SUCCESS.value
                trade.paid_at = datetime.now()
                await trade.save()

        return {
            "code": 0,
            "msg": "success",
            "data": {
                "trade_no": trade.trade_no,
                "amount": trade.amount,
                "status": trade.payment_status,
                "paid_at": trade.paid_at.strftime("%Y-%m-%d %H:%M:%S") if trade.paid_at else None
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"查询交易状态失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refund/{trade_no}", summary="申请退款")
async def create_refund(trade_no: str = "" ,body = Body(None)):
    """申请退款"""
    try:
        reason = body.get("reason", "")
        # 查询交易记录
        trade = await Trade.get_or_none(
            trade_no=trade_no,
            payment_status=PaymentStatus.SUCCESS.value
        ).prefetch_related("user")
        if not trade:
            raise HTTPException(status_code=404, detail="交易记录不存在或未支付成功")
        # 创建退款
        if trade.payment_channel == PaymentChannel.CREDIT.value:
            product_desc = ""
            # 获取当前交易商品
            trade_product_type = trade.metadata.get("product_type")

            # 积分退款
            user = await trade.user
            user.credits += int(trade.amount) * 10
            await user.save()
            await CreditRecord.create(
                user=user,
                record_type=CreditRecordType.REFUND.value,
                credits=int(trade.amount) * 10,
                balance=user.credits,
                description=f"{product_desc}，返还 {int(trade.amount) * 10} 积分"
            )
        elif trade.payment_channel == PaymentChannel.ACTIVATION.value:
            # 激活码退款
            active_code = await ActivationCode.get_or_none(trade=trade)
            if active_code:
                active_code.is_used = False
                active_code.used_by = None
                active_code.trade = None
                await active_code.save()
            # 对应产品回退
            product_desc = ""
            # 获取当前交易商品
            trade_product_type = trade.metadata.get("product_type")
            # 兑换积分
            if trade_product_type == "credit":
                trade_credits = trade.metadata.get("credits")
                # 批量购买模板
                product_desc = f"【兑换码】退订{trade_credits}积分"
                user = await trade.user
                 # 扣减积分
                if user.credits >= trade_credits:
                    user.credits -= trade_credits
                else:
                    user.credits = 0
                await user.save()
                # 记录积分变动
                await CreditRecord.create(
                    user=user,
                    record_type=CreditRecordType.REFUND.value,
                    credits=-trade_credits,
                    balance=user.credits,
                    description=f"退款扣减{trade_credits}积分"
                )

        else:
            result = adapay.Payment.refund(
                payment_id=trade.payment_id,
                refund_order_no=f"R{trade.trade_no}",
                refund_amt=str(trade.amount),
                reason=reason
            )
            logger.info(f"申请退款结果: {result}")
            if result.get("status") != "succeeded":
                raise Exception(result.get("error_msg", "Adapay SDK支付退款失败"))
            # 处理退款
            if trade.metadata.get("product_type") == "credit":
                # 扣减积分
                credit_order = await CreditRechargeOrder.get(trade=trade).prefetch_related("product")
                user = await trade.user
                
                user.credits -= credit_order.product.credits
                await user.save()
                
                # 记录积分变动
                await CreditRecord.create(
                    user=user,
                    record_type=CreditRecordType.REFUND.value,
                    credits=-credit_order.product.credits,
                    balance=user.credits,
                    description=f"退款扣减{credit_order.product.credits}积分"
                )

        
        # 更新交易状态
        trade.payment_status = PaymentStatus.REFUNDED.value
        await trade.save()

        return {
            "code": 0,
            "msg": "success",
            "data": {
                "id": trade.id,
                "amount": float(trade.amount),
                "status": trade.payment_status,
                "created_at": trade.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"申请退款失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/list", summary="获取交易记录列表")
async def get_trade_list(
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    trade_type: Optional[str] = Query(None, description="交易类型: recharge-充值, consume-消费, refund-退款, activation-激活码兑换"),
    payment_status: Optional[str] = Query(None, description="支付状态: pending-待支付, success-支付成功, failed-支付失败, refunded-已退款"),
    payment_channel: Optional[str] = Query(None, description="支付渠道"),
    min_amount: Optional[float] = Query(None, description="最小金额"),
    max_amount: Optional[float] = Query(None, description="最大金额"),
    order_by: str = Query("desc", description="排序方式: asc-正序, desc-逆序"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    current_user: User = Depends(get_current_user)
):
    """获取交易记录列表
    
    支持以下筛选条件:
    - 交易类型
    - 支付状态
    - 支付渠道
    - 金额范围
    - 时间范围
    - 排序方式
    """
    try:
        # 构建查询条件
        query = Q(user=current_user)
        
        # 添加筛选条件
        if trade_type:
            query = query & Q(trade_type=trade_type)
            
        if payment_status:
            query = query & Q(payment_status=payment_status)
            
        if payment_channel:
            query = query & Q(payment_channel=payment_channel)
            
        if min_amount is not None:
            query = query & Q(amount__gte=Decimal(str(min_amount)))
            
        if max_amount is not None:
            query = query & Q(amount__lte=Decimal(str(max_amount)))
            
        if start_time:
            query = query & Q(created_at__gte=start_time)
            
        if end_time:
            query = query & Q(created_at__lte=end_time)

        # 计算总数
        total = await Trade.filter(query).count()

        # 构建排序
        order_by_field = "-created_at" if order_by == "desc" else "created_at"

        # 获取分页数据
        trades = await Trade.filter(query)\
            .order_by(order_by_field)\
            .offset((page - 1) * page_size)\
            .limit(page_size)

        # 构建返回数据
        items = []
        for trade in trades:
            items.append({
                "id": trade.id,
                "trade_no": trade.trade_no,
                "amount": float(trade.amount),
                "trade_type": trade.trade_type,
                "payment_channel": trade.payment_channel,
                "payment_status": trade.payment_status,
                "payment_id": trade.payment_id,
                "title": trade.title,
                "metadata": trade.metadata,
                "created_at": trade.created_at.strftime("%Y-%m-%d %H:%M:%S") if trade.created_at else None,
                "paid_at": trade.paid_at.strftime("%Y-%m-%d %H:%M:%S") if trade.paid_at else None
            })

        return {
            "code": 0,
            "msg": "success",
            "data": {
                "total": total,
                "items": items,
                "page": page,
                "page_size": page_size,
                # 返回查询条件，方便前端回显
                "filters": {
                    "trade_type": trade_type,
                    "payment_status": payment_status,
                    "payment_channel": payment_channel,
                    "min_amount": min_amount,
                    "max_amount": max_amount,
                    "order_by": order_by,
                    "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S") if start_time else None,
                    "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S") if end_time else None
                }
            }
        }

    except Exception as e:
        logger.error(f"获取交易记录列表失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/delete/{trade_no}", summary="删除支付订单")
async def delete_trade(
    trade_no: str,
    current_user: User = Depends(get_current_user)
):
    """删除支付订单
    
    注意：
    1. 只能删除未支付的订单
    2. 只能删除自己的订单
    3. 删除后不可恢复
    """
    try:
        # 查询订单
        trade = await Trade.get_or_none(
            trade_no=trade_no,
            user=current_user
        )
        if not trade:
            return {
                "code": 1,
                "msg": "订单不存在",
                "data": {}
            }

        # 检查订单状态
        if trade.payment_status != PaymentStatus.PENDING.value:
            return {
                "code": 1,
                "msg": "只能删除未支付的订单",
                "data": {}
            }

        # 删除交易记录
        await trade.delete()

        return {
            "code": 0,
            "msg": "删除成功",
            "data": {}
        }

    except Exception as e:
        logger.error(f"删除订单失败: {str(e)}")
        return {
            "code": 1,
            "msg": f"删除失败: {str(e)}",
            "data": {}
        }
