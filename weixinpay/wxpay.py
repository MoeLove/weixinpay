#!/usr/bin/env python
# coding=utf-8
import json
import time
import uuid
from collections import defaultdict
from hashlib import md5

import dicttoxml
import requests
import xmltodict


class Wxpay(object):

    UNIFIEDORDER_URL = 'https://api.mch.weixin.qq.com/pay/unifiedorder'
    ORDERQUERY_URL = 'https://api.mch.weixin.qq.com/pay/orderquery'

    def __init__(self, appid, mch_id, key):
        self.appid = appid
        self.mch_id = mch_id
        self.key = key
        self.default_params = {
            'appid': appid,
        }

    def _generate_nonce_str(self):
        """生成随机字符串
        """
        return str(uuid.uuid4()).replace('-', '')

    def generate_sign(self, params):
        """生成md5签名的参数
        """
        src = '&'.join(['%s=%s' % (key, value) for key,
                        value in sorted(params.items())]) + '&key=%s' % self.key
        return md5(src.encode('utf-8')).hexdigest().upper()

    def generate_request_data(self, **kwargs):
        """生成统一下单请求所需要提交的数据

        https://pay.weixin.qq.com/wiki/doc/api/app/app.php?chapter=9_1

        """
        params = self.default_params.copy()
        params['mch_id'] = self.mch_id
        params['fee_type'] = 'CNY'  # 货币类型 默认是人民币
        params['device_info'] = 'WEB'
        params['trade_type'] = 'APP'
        params['nonce_str'] = self._generate_nonce_str()
        params.update(kwargs)

        params['sign'] = self.generate_sign(params)

        return '<xml>%s</xml>' % dicttoxml.dicttoxml(params, root=False)

    def generate_prepay_order(self, **kwargs):
        """生成预支付交易单

        签名后的数据请求 URL地址：https://api.mch.weixin.qq.com/pay/unifiedorder
        """
        headers = {'Content-Type': 'application/xml'}
        data = self.generate_request_data(**kwargs)

        res = requests.post(self.UNIFIEDORDER_URL, data=data, headers=headers)

        if res.status_code != 200:
            return defaultdict(str)

        result = json.loads(json.dumps(xmltodict.parse(res.content)))

        if result['xml']['return_code'] == 'SUCCESS':
            return result['xml']
        else:
            return result['xml']['return_msg']

    def generate_call_app_data(self, prepayid):
        """"生成调起客户端签名
        args:
            prepayid 预支付交易单
        https://pay.weixin.qq.com/wiki/doc/api/app/app.php?chapter=9_12&index=2
        """
        params = self.default_params.copy()
        params['partnerid'] = self.mch_id
        params['package'] = 'Sign=WXPay'
        params['noncestr'] = self._generate_nonce_str()
        params['timestamp'] = str(int(time.time()))
        params['prepayid'] = prepayid
        params['sign'] = self.generate_sign(params)

        return params

    def generate_query_data(self, transaction_id='', out_trade_no=''):
        """生成查询订单的数据
        """
        params = self.default_params.copy()
        params['mch_id'] = self.mch_id
        params['nonce_str'] = self._generate_nonce_str()

        if transaction_id:
            params['transaction_id'] = transaction_id
        elif out_trade_no:
            params['out_trade_no'] = out_trade_no
        else:
            raise Exception(
                'generate_query_data need transaction_id or out_trade_no')

        params['sign'] = self.generate_sign(params)

        return '<xml>%s</xml>' % dicttoxml.dicttoxml(params, root=False)

    def order_query_result(self, transaction_id='', out_trade_no=''):
        """查询订单

        https://pay.weixin.qq.com/wiki/doc/api/app/app.php?chapter=9_2&index=4

        需要传递微信订单号/商户订单号
        """
        headers = {'Content-Type': 'application/xml'}
        data = self.generate_query_data(
            transaction_id=transaction_id, out_trade_no=out_trade_no)

        res = requests.post(self.ORDERQUERY_URL, data=data, headers=headers)

        if res.status_code != 200:
            return defaultdict(str)

        result = json.loads(json.dumps(xmltodict.parse(res.content)))

        if result['xml']['return_code'] == 'SUCCESS':
            return result['xml']
        else:
            return result['xml']['return_msg']

    def verify_notify(self, **kwargs):
        """验证通知的有效性
        """
        sign = kwargs.pop('sign', '')

        if self.generate_sign(kwargs) == sign:
            # 签名验证通过
            return True
        else:
            return False

    def parse_notify_request(self, body):
        """通知请求的解析
        """
        if not isinstance(body, str):
            raise Exception('body is not an xml str')

        result = json.loads(json.dumps(xmltodict.parse(body)))
        return result

