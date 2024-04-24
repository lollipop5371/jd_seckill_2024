import json
from jd_logger import logger
from urllib import parse
from urllib.parse import urlparse, parse_qs
import sys
import requests
from config import global_config
from sign.jdSign import getSignWithstv
import util


def url_params_to_json():
    # 期望的参数列表
    expected_params = ['functionId', 'clientVersion', 'build', 'client', 'partner',  'sdkVersion', 'lang',
                       'harmonyOs', 'networkType', 'uts', 'uemps', 'ext', 'eid', 'x-api-eid-token', 'ef', 'ep']

    api_jd_url = global_config.getRaw('config', 'api_jd_url')
    tmp_url = urlparse(api_jd_url)
    parad = parse_qs(tmp_url.query)

    # 获取 URL 中的参数名
    url_params = list(parad.keys())

    # 检查参数是否匹配
    if set(url_params) == set(expected_params):
        logger.info("api_jd_url参数校验正确")
    elif set(expected_params) - set(url_params):
        missing_params = set(expected_params) - set(url_params)
        logger.error("api_jd_url缺少以下参数:" + str(missing_params))
        input("api_jd_url错误，按 Enter 键退出...")
        sys.exit()
    else:
        unnecessary_params = set(url_params) - set(expected_params)
        logger.info("删除api_jd_url中多余的参数:" + str(unnecessary_params))
        for extra_param in unnecessary_params:
            del parad[extra_param]

    params_dict = {key: value[0] if len(value) == 1 else value for key, value in parad.items()}
    return params_dict


class SpiderSession:

    def __init__(self):
        self.ep_json = None
        self.client_version = None
        self.client = None
        self.user_agent = None
        self.payload = None
        self.uuid = None
        self.local_cookie = global_config.getRaw('config', 'local_cookies')
        self.local_jec = global_config.getRaw('config', 'local_jec')
        self.local_jeh = global_config.getRaw('config', 'local_jeh')
        self.local_jdgs = global_config.getRaw('config', 'local_jdgs')
        if self.local_cookie == '' or self.local_jec == '' or self.local_jdgs == '' or self.local_jdgs == '':
            logger.error('配置文件不完整，请补充cookie，jec，jdgs，jd_url等参数')
            input("配置文件不完整，按 Enter 键退出...")
        self.init_param()
        self.session = self._init_session()

    def init_param(self):
        result = url_params_to_json()
        try:
            self.payload = result
            self.client = result['client']
            self.client_version = result['clientVersion']
            self.ep_json = json.loads(self.payload['ep'])
            self.uuid = util.decode_base64(self.ep_json['cipher']['uuid'])
            self.user_agent = 'okhttp/3.12.16;jdmall;' + self.client + ';version/' + self.client_version + ';build/' + \
                              result['build'] + ';'
        except Exception as e:
            logger.error('api_jd_url参数中应包含client，clientVersion，build，ep等参数')
            input("配置文件错误，按 Enter 键退出...")
            sys.exit()

    def _init_session(self):
        session = requests.session()
        session.headers = self.get_headers()
        session.cookies = self.init_cookies()
        return session

    def get_headers(self):
        return {"User-Agent": self.user_agent,
                "x-rp-client": "android_3.0.0",
                "J-E-C": self.local_jec,
                "jdgs": self.local_jdgs,
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Connection": "keep-alive"}

    def get_user_agent(self):
        return self.user_agent

    def get_session(self):
        return self.session

    def get(self, url, **kwargs):
        """封装get方法"""
        # 获取请求参数
        params = kwargs.get("params")
        allow_redirects = kwargs.get("allow_redirects")
        try:
            result = self.session.get(url, params=params, allow_redirects=allow_redirects, verify=False)
            return result
        except Exception as e:
            logger.error("get请求错误: %s" % e)
            input("网络请求错误，按 Enter 键退出...")
            sys.exit()

    def post(self, url, **kwargs):
        """封装post方法"""
        # 获取请求参数
        params = kwargs.get("params")
        data = kwargs.get("data")
        allow_redirects = kwargs.get("allow_redirects")
        try:
            result = self.session.post(url, params=params, data=data, allow_redirects=allow_redirects, verify=False)
            return result
        except Exception as e:
            logger.error("post请求错误: %s" % e)
            input("网络请求错误，按 Enter 键退出...")
            sys.exit()

    def init_cookies(self):
        cookie_jar = requests.cookies.RequestsCookieJar()
        for cookie in self.local_cookie.split(';'):
            cookie_jar.set(cookie.split('=')[0], cookie.split('=')[-1])
        return cookie_jar

    def update_cookies(self, cookie_str):
        # print('更新cookie：'+ cookie_str)
        cookie_jar = self.session.cookies
        for cookie in cookie_str.split(';'):
            cookie_jar.set(cookie.split('=')[0], cookie.split('=')[-1])
        self.session.cookies.update(cookie_jar)
        # print (self.session.cookies.get_dict())

    def requestWithSign(self, function_id, body, data):
        url = 'https://api.m.jd.com/client.action?'
        sign_str = getSignWithstv(function_id, json.dumps(body, separators=(',', ':')), self.uuid, self.client,
                                  self.client_version)
        self.payload['functionId'] = function_id
        ts = util.local_time()
        self.payload['ep'] = self.gen_cipher_ep()

        url = url + parse.urlencode(self.payload) + '&' + sign_str
        resp = self.session.post(url=url, data=data, verify=False)
        return resp

    def gen_cipher_ep(self):
        ts = util.local_time()
        self.ep_json['ts'] = ts
        return json.dumps(self.ep_json, separators=(',', ':'))
