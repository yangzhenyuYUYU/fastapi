from fastapi import APIRouter, Request, Depends, Body, Query, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from models.user import User, UserSession, LoginType, UserRole
from models.trade import Trade, TradeType, PaymentStatus, PaymentChannel
import httpx
import hashlib
from tools.redis import Redis  # 确保正确导入 Redis 实例
import time
import uuid
import random
import string
import json
from config.settings import Settings
import logging
import urllib.parse
import adapay
from datetime import datetime
from decimal import Decimal
from middleware.auth import get_current_user

settings = Settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wx")


# 初始化 Adapay SDK 配置 - 测试环境
config_info = {
    'api_key': settings.ADAPAY_API_KEY,
    'private_key': settings.ADAPAY_PRIVATE_KEY,
    'mock_mode': True  # 启用测试模式
}

adapay.mer_config = {
    'merchant_key': config_info
}

@router.get("/gzh/verify")
async def gzh_verify(
    code: str = None,
    state: str = None,
    signature: str = None,
    timestamp: str = None,
    nonce: str = None,
    echostr: str = None,
    request: Request = None
):
    """处理公众号验证和支付授权回调"""
    logger.info(f"收到微信请求：method={request.method}, params={request.query_params}")
    # 处理支付授权回调
    if code and state:
        try:
            # 获取用户信息
            success, user_info = await wx_gzh.get_gzh_user_info(code)
            logger.info(f"获取用户信息: success={success}, info={user_info}")
            
            if not success or not user_info:
                return JSONResponse(
                    status_code=400, 
                    content={'code': 1, 'msg': '获取用户信息失败'}
                )
                
            # 获取用户openid
            openid = user_info.get('openid')
            if not openid:
                return JSONResponse(
                    status_code=400,
                    content={'code': 1, 'msg': '获取用户openid失败'}
                )
                
            # 更新用户信息
            user = await User.get_or_none(id=state)
            if user:
                user.openid_gzh = openid
                await user.save()
                return JSONResponse(
                    status_code=200,
                    content={'code': 0, 'msg': 'success', 'data': {'openid': openid}}
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={'code': 1, 'msg': '用户不存在'}
                )
                
        except Exception as e:
            logger.error(f"处理支付授权回调失败: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={'code': 1, 'msg': f'处理失败: {str(e)}'}
            )
    
    # 处理服务器验证
    try:
        # GET 请求处理服务器验证
        if request and request.method == "GET" and all([signature, timestamp, nonce, echostr]):
            # 获取配置的 token
            token = "digitalhuman"  # 替换为您的 token
            
            logger.info(f"验证参数: signature={signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr}")
            
            # 1. 将 token、timestamp、nonce 三个参数进行字典序排序
            temp_list = [token, timestamp, nonce]
            temp_list.sort()
            
            # 2. 将三个参数字符串拼接成一个字符串进行 sha1 加密
            temp_str = ''.join(temp_list)
            sign = hashlib.sha1(temp_str.encode('utf-8')).hexdigest()
            
            # 3. 开发者获得加密后的字符串可与 signature 对比，标识该请求来源于微信
            if sign == signature:
                return PlainTextResponse(content=echostr)
            return PlainTextResponse(content="验证失败")
    except Exception as e:
        logger.error(f"处理服务器验证失败: {str(e)}")
        return PlainTextResponse(content="验证失败")
        
    return JSONResponse(
        status_code=400,
        content={'code': 1, 'msg': '无效的请求参数'}
    )

@router.post("/gzh/verify")
async def wx_gzh_post_handler(request: Request):
    """处理公众号消息和事件推送"""
    logger.info(f"收到微信请求：method={request.method}, params={request.query_params}")
    try:
        # 获取并解析消息数据
        body = await request.body()
        xml_data = body.decode('utf-8')
        logger.info(f"收到的XML数据: {xml_data}")
        
        xml_dict = wx_gzh.parse_xml(xml_data)
        logger.info(f"解析后的数据: {xml_dict}")
        
        # 处理事件消息
        if xml_dict.get('MsgType') == 'event':
            event_type = xml_dict.get('Event', '').lower()
            openid = xml_dict.get('FromUserName')
            logger.info(f"收到事件：{event_type}，openid：{openid}")
            
            if event_type == 'subscribe':  # 关注事件
                # 更新用户关注状态
                success, user_info = await wx_gzh.get_gzh_user_info(openid)
                logger.info(f"获取用户信息: success={success}, info={user_info}")
                unionid = user_info.get('unionid', None) if user_info else None
                user = await User.filter(unionid=unionid).first()
                if user:
                    user.openid_gzh = openid
                    await user.save()
                    logger.info(f"更新用户关注状态成功: {user.id}")
                else:
                    # 创建新用户记录
                    await User.create(
                        unionid=unionid,
                        openid_gzh=openid,
                        nickname=f"用户_{openid[-4:]}",
                    )
                    logger.info("创建新用户成功")
                        
            elif event_type == 'unsubscribe':  # 取消关注事件
                await User.filter(openid_gzh=openid).update(openid_gzh=None)
                logger.info(f"用户 {openid} 取消关注，已更新状态")
                
        return PlainTextResponse(content="success")
        
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
        # 即使处理失败也要返回 success，避免微信服务器重试
        return PlainTextResponse(content="success")

@router.get("/gzh/qrcode")
async def get_gzh_qrcode():
    """获取公众号二维码"""
    try:
        logger.info("开始处理获取二维码请求")
        
        QRCODE_CACHE_KEY = "wx_gzh_qrcode"
        QRCODE_EXPIRE_SECONDS = 2592000  # 30天

        # 尝试从缓存获取
        logger.info(f"尝试从Redis获取缓存的二维码: {QRCODE_CACHE_KEY}")
        cached_qrcode = Redis.get(QRCODE_CACHE_KEY)
        
        if cached_qrcode:
            logger.info("成功从缓存获取二维码")
            return JSONResponse(
                content={
                    "code": 0,
                    "msg": "获取成功(cached)",
                    "data": {"qrcode": cached_qrcode}
                }
            )

        logger.info("缓存中没有二维码，开始生成新的二维码")
        # 生成新的二维码
        access_token = wx_gzh._get_access_token()
        if not access_token:
            logger.error("获取access_token失败")
            return JSONResponse(
                status_code=500,
                content={"code": -1, "msg": "获取access_token失败"}
            )
        
        # 创建二维码
        url = f"https://api.weixin.qq.com/cgi-bin/qrcode/create?access_token={access_token}"
        data = {
            "expire_seconds": QRCODE_EXPIRE_SECONDS,
            "action_name": "QR_STR_SCENE",
            "action_info": {
                "scene": {"scene_str": f"follow_gzh_{int(time.time())}"}
            }
        }
        
        logger.info("开始请求微信接口生成二维码")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=data)
            result = response.json()
            logger.info(f"微信接口返回结果: {result}")
            
            if 'ticket' in result:
                qrcode_url = f"https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={result['ticket']}"
                
                # 缓存二维码
                logger.info("开始缓存二维码")
                cache_result = Redis.set(QRCODE_CACHE_KEY, qrcode_url, ex=QRCODE_EXPIRE_SECONDS)
                logger.info(f"缓存结果: {cache_result}")
                
                return JSONResponse(
                    content={
                        "code": 0,
                        "msg": "获取成功(new)",
                        "data": {"qrcode": qrcode_url}
                    }
                )
            else:
                raise Exception(f"获取二维码ticket失败: {result}")
                
    except Exception as e:
        logger.error(f"获取二维码失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"code": -1, "msg": f"获取二维码失败：{str(e)}"}
        )

@router.get("/gzh/status")
async def check_gzh_status(user: User = Depends(get_current_user)):
    """检查用户是否关注了公众号"""
    try:
        if not user:
            return JSONResponse(
                status_code=401,
                content={"code": -1, "msg": "请先登录"}
            )
            
        user_obj = await User.get(user_id=user.get('user_id'))
        if not user_obj:
            return JSONResponse(
                status_code=404,
                content={"code": -1, "msg": "用户不存在"}
            )
            
        # 如果已经有公众号openid，再次验证关注状态
        if user_obj.openid_gzh:
            success, user_info = await wx_gzh.get_gzh_user_info(user_obj.openid_gzh)
            logger.info(f"获取用户信息: success={success}, info={user_info}")
            if success and user_info:
                is_subscribed = user_info.get('subscribe', 0) == 1
                await user_obj.save()
            else:
                is_subscribed = True if user_obj.openid_gzh else False
        else:
            is_subscribed = False
            
        return JSONResponse(
            content={
                "code": 0,
                "msg": "获取成功",
                "data": {
                    "is_subscribed": is_subscribed,
                    "openid_gzh": user_obj.openid_gzh
                }
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "code": -1,
                "msg": f"获取状态失败：{str(e)}"
            }
        )
        
@router.get('/get_payment_h5', summary="获取公众号支付H5页面")
async def get_payment_h5(
    product_type: str = Query(..., description="产品类型: credits-积分充值, membership-会员充值, template-数字商品"), 
    product_id: int = Query(..., description="产品ID"),
    payment_channel: str = Query(..., description="支付渠道"),
    current_user: User = Depends(get_current_user)
):
    try:
        # 获取产品信息
        if product_type == "credits":
            product = await CreditProduct.get_or_none(id=product_id, status=True)
            if not product:
                raise HTTPException(status_code=404, detail="积分产品不存在或已下架")
            product_name = product.name
            product_price = float(product.price)  # 转换为 float
        elif product_type == "membership":
            product = await MembershipPlan.get_or_none(id=product_id, status=True)
            if not product:
                raise HTTPException(status_code=404, detail="会员方案不存在或已下架")
            product_name = product.name
            product_price = float(product.price)  # 转换为 float
        elif product_type == "template":
            product = await Template.get_or_none(id=product_id, status=True)
            if not product:
                raise HTTPException(status_code=404, detail="数字商品不存在或已下架")
            product_name = product.name
            product_price = float(product.price)  # 转换为 float
        else:
            raise HTTPException(status_code=404, detail="产品类型不存在")
            
        # 使用时间戳和随机字符生成唯一标识符
        timestamp = int(time.time())
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        unique_id = f"{timestamp}{random_chars}_{current_user.id}"

        # 创建要存储到Redis的JSON数据
        redis_data = {
            "session_id": "",  # 创建订单时设置
            "openid_gzh": "",
            "trade_no": "",
            "product_type": product_type,
            "product_name": product_name,
            "product_price": product_price * 100,  # 已转换为 float
            "product_id": product_id,
            "payment_channel": payment_channel,
            "order_status": "pending",  # 初始状态
            "user_id": current_user.id
        }

        # 存储到Redis并设置过期时间
        Redis.set(unique_id, json.dumps(redis_data), ex=60)
        sessionId = unique_id
        paymentChannel = payment_channel or "wx_pub"
        productId = product_id
        productType = product_type
        # 公众号配置
        appid = settings.WX_GZH_APPID
        redirect_uri = urllib.parse.quote(f'{settings.API_BASE_URL}/wx-payment')
        scope = 'snsapi_base'
        state = sessionId
        auth_url = f'https://open.weixin.qq.com/connect/oauth2/authorize?appid={appid}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&state={state}#wechat_redirect'
        return JSONResponse(content={
            "msg": "get success", 
            "code": 0,
            "data": {
                "auth_url": auth_url,
                "url": f"https://shunyouai.com/wx-payment?sessionId={sessionId}&paymentChannel={payment_channel}&productId={product_id}&productType={product_type}",
                "sessionId": sessionId
            }
        })
    
    except Exception as e:
        logger.error(f"get_payment_h5 error: {str(e)}")
        return JSONResponse(status_code=400, content={
            "msg": f"fail: {str(e)}",
            "code": 1,
            "data": None
        })

@router.get("/query_payment_status/{session_id}", summary="查询微信公众号扫码支付的状态")
async def query_payment_status(session_id: str):
    try:
        session = Redis.get(session_id)
        if not session:
            raise Exception("已过期")

        payment_session = json.loads(session)
        trade_no = payment_session["trade_no"]
        trade = await Trade.get_or_none(trade_no=trade_no)
        if trade and trade.payment_status == PaymentStatus.PENDING:
            user = await User.get_or_none(id=trade.user_id)
            result = adapay.Payment.query(payment_id=trade.payment_id, mer_key='merchant_key')
            logger.info(f"查询支付状态结果: {result}")
            if result.get("status") == "succeeded":
                payment_session["order_status"] = "paid"
                Redis.set(session_id, json.dumps(payment_session), ex=60)
                trade.payment_status = PaymentStatus.SUCCESS
                trade.paid_at = datetime.now()
                logger.info(f"更新用户信息: {user}")
                await trade.save()
                # TODO: 根据交易记录对应的商品类型，更新用户积分或会员信息
                if trade.metadata.get("product_type") == "credits":
                    credit_product = await CreditProduct.get_or_none(id=trade.metadata.get("product_id"))
                    user.credits += credit_product.credits
                    # 记录积分变动
                    await CreditRecord.create(
                        user=user,
                        record_type=CreditRecordType.RECHARGE.value,
                        credits=credit_product.credits,
                        balance=user.credits,
                        description=f"充值{credit_product.credits}积分"
                    )
                    await CreditRechargeOrder.create(
                        user=user,
                        product=credit_product,
                        trade=trade
                    )

                await user.save()
                await trade.save()


        return JSONResponse(content={
            "msg": "success",
            "code": 0,
            "data": payment_session
        })
    except Exception as e:
        return JSONResponse(status_code=400, content={
            "msg": str(e),
            "code": 1,
        })

@router.put("/payment_status_update/{session_id}", summary="更新支付状态")
async def payment_status_update(
    session_id: str,
    body: dict = Body(..., description="订单状态, scaned-已扫码, authorized-已授权, paid-已支付, canceled-已取消, failed-支付失败")
):
    try:
        session = Redis.get(session_id)
        if not session:
            raise Exception("已过期")
            
        order_status = body.get("order_status")
        if not order_status:
            raise Exception("缺少订单状态")
            
        payment_session = json.loads(session)
        payment_session["order_status"] = order_status
        Redis.set(session_id, json.dumps(payment_session), ex=60)
        logger.info(f"更新支付状态: {payment_session}")

        if order_status == "paid":
            # 查询支付状态
            trade_no = payment_session["trade_no"]
            trade = await Trade.get_or_none(trade_no=trade_no)
            if trade and trade.payment_status == 'pending':
                result = adapay.Payment.query(payment_id=trade_no, mer_key='merchant_key')
                logger.info(f"查询支付状态结果: {result}")
                user = await User.get_or_none(id=trade.user_id)
                if result.get("status") == "succeeded":
                    trade.payment_status = PaymentStatus.SUCCESS
                    trade.paid_at = datetime.now()
                    logger.info(f"更新用户信息: {user}")
                    await trade.save()
                    # TODO: 根据交易记录对应的商品类型，更新用户积分或会员信息
                    if trade.metadata.get("product_type") == "credits":
                        credit_product = await CreditProduct.get_or_none(id=trade.metadata.get("product_id"))
                        user.credits += credit_product.credits
                        # 记录积分变动
                        await CreditRecord.create(
                            user=user,
                            record_type=CreditRecordType.RECHARGE.value,
                            credits=credit_product.credits,
                            balance=user.credits,
                            description=f"充值{credit_product.credits}积分"
                        )
                        await CreditRechargeOrder.create(
                            user=user,
                            product=credit_product,
                            trade=trade
                        )

                    await user.save()
                    await trade.save()

                    # 判断该用户的邀请人是谁
                    inviteRelation = await InvitationRelation.filter(invitee=user).prefetch_related('inviter').first()
                    logger.info(f"邀请人: {inviteRelation and {'inviter': inviteRelation.inviter.username} or None}, current_user: {user.username}")
                    # 如果有的话，就找到这个邀请人，并给他相应的佣金奖励
                    if inviteRelation and inviteRelation.inviter:
                        # 佣金的计算，默认按15%来算，保留2位小数
                        commission = trade.amount * Decimal('0.15')
                        # TODO: 生成佣金订单
                        await CommissionRecord.create(
                            user=inviteRelation.inviter,
                            relation=inviteRelation,
                            from_user=user,
                            order=trade,
                            status=CommissionStatus.PENDING.value,
                            amount=commission,
                            description=f"邀请{user.username}充值{trade.amount}元获取佣金",
                            issue_time=datetime.now()
                        )
        elif order_status == "canceled":
            # 取消订单
            trade_no = payment_session["trade_no"]
            trade = await Trade.get_or_none(trade_no=trade_no)
            if trade:
                await trade.delete()

        return JSONResponse(content={
            "msg": "success",
            "data": payment_session,
            "code": 0
        })

    except Exception as e:
        return JSONResponse(status_code=400, content={
            "msg": str(e),
            "code": 1,
        })

@router.get("/payment_callback", summary="支付回调接口")
async def payment_callback(request: Request):
    try:
        # 获取所有查询参数
        params = dict(request.query_params)
        logger.info(f"收到支付回调参数: {params}")
        
        # 获取必要的参数
        code = params.get('code')
        state = params.get('state')
        
        if not code or not state:
            return JSONResponse(
                status_code=400,
                content={
                    "msg": "缺少必要参数",
                    "code": 1,
                    "data": None
                }
            )
            
        # 处理支付回调逻辑
        payment_session = Redis.get(state)
        if not payment_session:
            return JSONResponse(
                status_code=400,
                content={
                    "msg": "支付会话已过期",
                    "code": 1,
                    "data": None
                }
            )
            
        session_data = json.loads(payment_session)
        session_data.update({
            "code": code,
            "state": state,
            "order_status": "processing"
        })
        
        # 更新Redis中的支付状态
        Redis.set(state, json.dumps(session_data), ex=60)
        
        return JSONResponse(content={
            "msg": "success",
            "code": 0,
            "data": {
                "code": code,
                "state": state,
                "order_status": "processing"
            }
        })
        
    except Exception as e:
        logger.error(f"支付回调处理失败: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "msg": f"处理失败: {str(e)}",
                "code": 1,
                "data": None
            }
        )

@router.get('/sync_trade_no', summary="同步交易订单号")
async def sync_trade_no(
    session_id: str = Query(..., description="会话ID"),
    trade_no: str = Query(..., description="交易订单号")
):
    try:
        payment_session = Redis.get(session_id)
        if not payment_session:
            raise Exception("已过期")
        session_data = json.loads(payment_session)
        session_data["trade_no"] = trade_no
        Redis.set(session_id, json.dumps(session_data), ex=60)
        return JSONResponse(content={
            "msg": "success",
            "code": 0,
            "data": session_data
        })
    except Exception as e:
        return JSONResponse(status_code=400, content={
            "msg": str(e),
            "code": 1,
        })

@router.get("/get_wx_openid", summary="静默授权获取公众号openid")
async def getWxOpenid(request: Request):
    try:
        # 获取查询参数
        params = dict(request.query_params)
        code = params.get('code')
        state = params.get('state')
        
        if not code or not state:
            return JSONResponse(
                status_code=400,
                content={
                    "msg": "缺少必要参数",
                    "code": 1,
                    "data": None
                }
            )
            
        # 获取Redis中的支付会话信息
        payment_session = Redis.get(state)
        if not payment_session:
            return JSONResponse(
                status_code=400,
                content={
                    "msg": "支付会话已过期",
                    "code": 1,
                    "data": None
                }
            )
        
        # 调用微信接口获取access_token和openid
        url = 'https://api.weixin.qq.com/sns/oauth2/access_token'
        params = {
            'appid': settings.WX_GZH_APPID,
            'secret': settings.WX_GZH_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            result = response.json()
            
            if 'errcode' in result:
                logger.error(f"获取access_token失败: {result}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "msg": f"获取access_token失败: {result.get('errmsg', '未知错误')}",
                        "code": 1,
                        "data": None
                    }
                )
                
            openid = result.get('openid')
            if not openid:
                return JSONResponse(
                    status_code=400,
                    content={
                        "msg": "获取openid失败",
                        "code": 1,
                        "data": None
                    }
                )
                
            # 更新Redis中的支付会话信息
            session_data = json.loads(payment_session)
            session_data.update({
                "openid_gzh": openid,
                "order_status": "authorized"
            })
            Redis.set(state, json.dumps(session_data), ex=60)

            # 更新用户openid
            user = await User.get(id=session_data["user_id"])
            user.openid_gzh = openid
            await user.save()

            # 获取用户session
            user_session = await UserSession.filter(user=user, login_type=LoginType.WEB).order_by("-created_at").first()
            if not user_session:
                raise Exception("用户session不存在")
            
            # 获取用户token
            token = user_session.token
            
            # 返回支付参数
            return JSONResponse(content={
                "msg": "success",
                "code": 0,
                "data": {
                    "appid": settings.WX_GZH_APPID,
                    "openid": openid,
                    "order_status": "authorized",
                    "state": state,
                    "token": token
                }
            })
            
    except Exception as e:
        logger.error(f"静默授权处理失败: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "msg": f"处理失败: {str(e)}",
                "code": 1,
                "data": None
            }
        )

