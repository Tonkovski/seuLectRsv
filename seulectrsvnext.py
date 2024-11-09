"""Utilties for easy SEU Lecture reservation.

Can be used out-of-the-box or imported for customization.

Scratched by t0nkov
Rev: 3
"""

import time
import json
import re
import base64

import requests
import urllib3
import ssl

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

import ddddocr



def _logprint_(log):
    currTime = time.strftime('[%H:%M:%S] ')
    print(currTime + log)

def _logErrorExit_(log):
    _logprint_(log)
    # input('Press Enter to quit...\n')
    exit(1)

class _CustomHttpAdapter (requests.adapters.HTTPAdapter):
    # "Transport adapter" that allows us to use custom ssl_context.

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)


def _get_legacy_session():
    ctx = ssl._create_unverified_context()
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount('https://', _CustomHttpAdapter(ctx))
    return session

class SeuLectHelper(object):
    """Helper object for automatic login, query and reservation."""

    _config_path = 'config.json'

    _district_list = ['四牌楼校区', '九龙湖校区', '丁家桥校区', '苏州校区',
                      '无锡分校']
    _lecture_category_list = ['心理', '法律', '艺术', '其他', '非讲座']

    _getHeaders = {
        'accept': '*/*',
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/102.0.0.0 Safari/537.36')
    }
    _postHeaders = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/102.0.0.0 Safari/537.36')
    }

    _auth_get_pubkey_url = 'https://auth.seu.edu.cn/auth/casback/getChiperKey'
    _auth_login_url = 'https://auth.seu.edu.cn/auth/casback/casLogin'
    _auth_verify_tgt_url = 'https://auth.seu.edu.cn/auth/casback/verifyTgt'
    _service_url = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/*default/index.do'
    _lect_data_url = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/hdyy/queryActivityList.do'
    _vcode_url = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/hdyy/vcode.do'
    _reg_url = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/hdyy/yySave.do'
    
    def __init__(self) -> None:
        """Init helper object with necessary widgets loaded."""

        self.config = self._loadConfig(self._config_path)
        self.lectlist = None
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.sess = _get_legacy_session()

    def _loadConfig(self, config_path: str) -> dict:
        """Read config from json file, verify integrety and return in dict
        form.
        
        Args:
            config_file:    String of config file path.
        """

        try:
            config_file = open(config_path, 'r', encoding='UTF-8')
            config = json.loads(config_file.read())
            config_file.close()
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            _logErrorExit_('Missing or corrupted config file!')
        for key in ['username', 'passwd', 'onlineOnly', 'district', 'filter']:
            if key not in config.keys():
                _logErrorExit_('Missing config entry "%s"!' % key)

        if type(config['username']) != str:
            _logErrorExit_('Wrong config format: "username" must be string!')
        if type(config['passwd']) != str:
            _logErrorExit_('Wrong config format: "passwd" must be string!')
        if config['username'] == '' or config['passwd'] == '':
            _logErrorExit_('Wrong config format: "username" and "passwd" must '
                           'not be blank!')
            
        if type(config['onlineOnly']) != bool:
            _logErrorExit_('Wrong config format: "onlineOnly" must be boolean!')

        if type(config['district']) != list:
            _logErrorExit_('Wrong config format: "district" must be list!')
        for entity in config['district']:
            if entity not in self._district_list :
                _logErrorExit_('Wrong config format: "district" contains '
                               'unknown entity "%s"' % entity)
        if len(config['filter']) == 0:
            _logErrorExit_('Wrong config format: "district" must not be '
                           'left blank!')
                
        if type(config['filter']) != list:
            _logErrorExit_('Wrong config format: "preferences" must be list!')
        for entity in config['filter']:
            if entity not in self._lecture_category_list :
                _logErrorExit_('Wrong config format: "preferences" contains '
                               'unknown entity "%s"' % entity)
        if len(config['filter']) == 0:
            _logErrorExit_('Wrong config format: "preferences" must not be '
                           'left blank!')
        
        district_list = []
        for dist in config['district']:
            district_list.append(str(self._district_list.index(dist) + 1))
        config['district'] = district_list

        return config
    

    # def _searchCasLoginInfo(self, html):
    #     """Deprecated, DO NOT USE."""
    #     reSearchTxt = r'<input type="hidden" name="lt" value="(.*)"/>\s*<input type="hidden" name="dllt" value="(.*)"/>\s*<input type="hidden" name="execution" value="(.*)"/>\s*<input type="hidden" name="_eventId" value="(.*)"/>\s*<input type="hidden" name="rmShown" value="(.*)">\s*<input type="hidden" id="pwdDefaultEncryptSalt" value="(.*)"/>'
    #     rePattern = re.compile(reSearchTxt)
    #     result = rePattern.search(html)
    #     casLoginInfo = {
    #         'lt': result.group(1),
    #         'dllt': result.group(2),
    #         'execution': result.group(3),
    #         '_eventId': result.group(4),
    #         'rmShown': result.group(5),
    #         'pwdDefaultEncryptSalt': result.group(6)
    #     }
    #     return casLoginInfo

    def authLoginApp(self) -> None:
        _logprint_('Logging in as user "%s"...' % self.config['username'])

        _logprint_('Requesting authentication RSA Public key...')
        resp = self.sess.post(self._auth_get_pubkey_url,
                              headers = self._postHeaders,
                              verify = False)
        raw_pubkey = json.loads(resp.text)['publicKey']
        raw_pubkey = raw_pubkey.replace('-', '+').replace('_', '/')
        pubkey_text = ('-----BEGIN RSA PUBLIC KEY-----\n%s'
                      '\n-----END RSA PUBLIC KEY-----' % raw_pubkey)
        pub_key = RSA.import_key(pubkey_text)
        enc_module = PKCS1_v1_5.new(pub_key)
        raw_enc_passwd = enc_module.encrypt(self.config['passwd'].encode())
        enc_passwd = base64.b64encode(raw_enc_passwd).decode()
        
        _logprint_('CAS logging in...')
        data = {
            'vcode': '',
            'loginType': 'account',
            'mobilePhoneNum': '',
            'mobileVerifyCode': '',
            'password': enc_passwd,
            'rememberMe': False,
            'service': '',
            'username': self.config['username'],
            'wxBinded': False
        }
        resp = self.sess.post(self._auth_login_url, json.dumps(data),
                              headers = self._postHeaders,
                              verify = False)
        if not json.loads(resp.text)['success']:
            _logErrorExit_('Wrong username or password!')

        _logprint_('Requesting CAS Ticket...')
        
        data = {
            'service': self._service_url
        }
        resp = self.sess.post(self._auth_verify_tgt_url, json.dumps(data),
                              headers = self._postHeaders,
                              verify = False)
        rd_url = json.loads(resp.text)['redirectUrl']
        self.sess.post(rd_url, data,
                       headers = self._postHeaders,
                       verify = False)

    def getLectData(self) -> list | None:
        """Refresh lecture list from API.

        Return a lecture list or None if server responds otherwise.
        """

        _logprint_('Refreshing lecture data...')
        data = {
            'pageIndex': '1',
            'pageSize': '100'
        }

        resp = self.sess.post(self._lect_data_url, params=data,
                            headers = self._postHeaders,
                            verify = False)
        if resp.headers['Server'] == 'openresty':
            return json.loads(resp.text)['datas']
        else:
            _logprint_('Login expired, unable to fetch lecture data.')
            return None

    def rsvLect(self, wid: str) -> dict:
        """Try reserve lecture with given wid, using ocr module for 
        verification codes.

        Return the response data only when the vcode challenge passes.

        Args:
            wid:    String of the given lecture's WID.
        """

        wrong_vcode = True
        while wrong_vcode:
            _logprint_('Retriving vcode pic...')
            resp = self.sess.post(self._vcode_url, verify=False)
            image_str = json.loads(resp.text)['result']
            rawdata = base64.b64decode(image_str.split('64,')[1])
            vcode = self.ocr.classification(rawdata)
            data = {
                'HD_WID': wid,
                'vcode': vcode
            }
            form = {'paramJson': json.dumps(data)}
            _logprint_('Delivering reservation request...')
            resp = self.sess.get(self._reg_url, params=form,
                                 headers = self._getHeaders,
                                 verify = False)
            respdata = json.loads(resp.text)
            if respdata['success'] == True:
                wrong_vcode = False
            elif respdata['msg'] != ('验证码错误，请重试！'
                                     '注意不要同时使用多台设备进行预约操作。'):
                wrong_vcode = False
            if wrong_vcode:
                _logprint_('Wrong vcode, retrying...')
        
        return respdata
    
    def matchLectTarget(self, lectlist: list) -> list:
        """Filter lectures using config, Exit when no lectures are available.
        
        Return filtered non-fully reserved lecture list.

        Args:
            lectlist:   List of all available lectures.
        """

        lect_data = list(
            filter(
                lambda x:
                    time.mktime(
                        time.strptime(x['YYJSSJ'], "%Y-%m-%d %H:%M:%S")
                    ) >= time.time() and\
                    # time.mktime(
                    #     time.strptime(x['YYKSSJ'], "%Y-%m-%d %H:%M:%S")
                    # ) <= time.time() and\
                    x['FBZT'] != "-1",
                lectlist
            )
        )

        if self.config['onlineOnly'] == True:
            lect_data = list(
                filter(lambda x: x['JZDD'] in ['腾讯会议', '钉钉'], lect_data)
            )
        else:
            lect_data = list(
                filter(
                    lambda x: x['JZDD'] in ['腾讯会议', '钉钉'] or\
                              x['SZXQ'] in self.config['district'],
                              lect_data
                )
            )

        lect_targets = []
        for entity in self.config['filter']:
            if entity == '心理':
                lect_targets += list(
                    filter(
                        lambda x: 
                        x['JZXL_DISPLAY'] == '人文与科学素养系列讲座_心理健康',
                        lect_data
                    )
                )
            elif entity == '法律':
                lect_targets += list(
                    filter(
                        lambda x:
                        x['JZXL_DISPLAY'] == '人文与科学素养系列讲座_法律',
                        lect_data
                    )
                )
            elif entity == '艺术':
                lect_targets += list(
                    filter(
                        lambda x: 
                        x['JZXL_DISPLAY'] == '人文与科学素养系列讲座-艺术类',
                        lect_data
                    )
                )
            elif entity == '其他':
                lect_targets += list(
                    filter(
                        lambda x:
                        x['JZXL_DISPLAY'] == '人文与科学素养系列讲座_其他',
                        lect_data
                    )
                )
            else:
                lect_targets += list(
                    filter(
                        lambda x: 
                        x['JZXL_DISPLAY'] not in [
                            '人文与科学素养系列讲座_心理健康',
                            '人文与科学素养系列讲座_法律',
                            '人文与科学素养系列讲座-艺术类',
                            '人文与科学素养系列讲座_其他'
                        ],
                        lect_data
                    )
                )
                
        if lect_targets == []:
            _logErrorExit_('No matching lecture! Change config filter advised.')
        else:
            _logprint_('Matching %d lecture(s), '
                       'filtering full reserving status...' %
                       len(lect_targets))
            lect_data = list(
                filter(lambda x: int(x['YYRS']) < int(x['HDZRS']), lect_data)
            )
            
        return lect_data

    def filterLectTime(self) -> list:
        """Filter open-for-reserve lectures on current time.

        Return filtered lecture list.
        """

        return list(
            filter(
                lambda x: 
                time.mktime(
                    time.strptime(x['YYKSSJ'], "%Y-%m-%d %H:%M:%S")
                ) <= time.time(),
                self.lectlist
            )
        )

    def automaticRsv(self) -> None:
        """Example for automatic lecture reservation.
        
        You can also DIY your own.   :)
        """
        print(
'-------------------------------------------------------------------------\n'
' ____             _              _   ____            _   _           _   \n'
'/ ___|  ___ _   _| |    ___  ___| |_|  _ \ _____   _| \ | | _____  _| |_ \n'
'\___ \ / _ \ | | | |   / _ \/ __| __| |_) / __\ \ / /  \| |/ _ \ \/ / __|\n'
' ___) |  __/ |_| | |__|  __/ (__| |_|  _ <\__ \\ V /| |\  |  __/>  <| |_ \n'
'|____/ \___|\__,_|_____\___|\___|\__|_| \_\___/ \_/ |_| \_|\___/_/\_\\__|\n'
'-------------------------------------------------------------------------\n'
        )
        print()
        print('Script scratched by t0nkov.')
        print('Warning, this script is only tested under SEU-WLAN.')
        _logprint_('Starting script in 3 sec...')
        # time.sleep(3)

        rsv_success = False
        rsv_incoming = False
        while not rsv_success:
            if not rsv_incoming:
                while self.lectlist == None:
                    self.authLoginApp()
                    self.lectlist = self.getLectData()
                self.lectlist = self.matchLectTarget(self.lectlist)
            
            for i in self.lectlist:
                print(i['JZMC'])

            lect_targets = self.filterLectTime()

            if lect_targets == []:
                most_recent_time = float('inf')
                for lect in lect_targets:
                    lect_rsv_start_time = time.mktime(
                        time.strptime(lect['YYKSSJ'], "%Y-%m-%d %H:%M:%S")
                    )
                    if most_recent_time > lect_rsv_start_time:
                        most_recent_time = lect_rsv_start_time
                difftime = most_recent_time - time.time()
                if difftime > 10:
                    _logprint_('No lecture available! Retrying in 10 sec...')
                    time.sleep(10)
                    continue
                else:
                    _logprint_('Incoming reservation in %.2f sec' % difftime)
                    time.sleep(difftime)
                    continue
            
            for lect in lect_targets:
                logtext = 'Reservation in bound!\n           %s-%s\t%s\t%s' % (
                    lect['JZSJ'],
                    lect['HDJSSJ'],
                    lect['JZXL_DISPLAY'],
                    lect['JZMC']
                )
                _logprint_(logtext)
                respdata = self.rsvLect(lect['WID'])
                if respdata['success'] == True:
                    _logprint_('Reservation success!')
                    rsv_success = True
                else:
                    _logprint_('Reservation failed! Error log: %s' % respdata['msg'])
                    if respdata['msg'] == '请求过于频繁，请稍后重试':
                        _logprint_('Rate limiting triggered!!! '
                                   'Awaiting for reservation ban lift, '
                                   'countdown 1 min...')
                        time.sleep(60)

if __name__ == '__main__':
    Helper = SeuLectHelper()
    Helper.automaticRsv()