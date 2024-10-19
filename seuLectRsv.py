import time
import json
import re
import requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import base64

import ddddocr

def logprint(log):
    currTime = time.strftime('[%H:%M:%S] ')
    print(currTime + log)

def logerrorExit(log):
    logprint(log)
    # input('Press Enter to quit...\n')
    exit(1)

def loadConfig(configPath):
    try:
        configFile = open(configPath, 'r', encoding='UTF-8')
        config = json.loads(configFile.read())
        configFile.close()
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        logerrorExit('Missing or corrupted config file!')
    for key in ['username', 'passwd', 'onlineOnly', 'district', 'filter']:
        if key not in config.keys():
            logerrorExit('Missing config entry "%s"!' % key)
    if type(config['username']) != str:
        logerrorExit('Wrong config format: "username" must be string!')
    if type(config['passwd']) != str:
        logerrorExit('Wrong config format: "passwd" must be string!')
    if config['username'] == '' or config['passwd'] == '':
        logerrorExit('Wrong config format: "username" and "passwd" must not be blank!')
    if type(config['onlineOnly']) != bool:
        logerrorExit('Wrong config format: "onlineOnly" must be boolean!')
    if config['district'] not in ['四牌楼校区', '九龙湖校区', '丁家桥校区', '苏州校区', '无锡分校']:
        logerrorExit('Wrong config format: "district" must be one of the following:\n四牌楼校区\n九龙湖校区\n丁家桥校区\n苏州校区\n无锡分校')
    if type(config['filter']) != list:
        logerrorExit('Wrong config format: "preferences" must be list!')
    for entity in config['filter']:
        if entity not in ['心理', '法律', '艺术', '其他', '非讲座'] :
            logerrorExit('Wrong config format: "preferences" contains unknown entity "%s"' % entity)
    if len(config['filter']) == 0:
        logerrorExit('Wrong config format: "preferences" must not be left blank!')
    
    config['district'] = str(['四牌楼校区', '九龙湖校区', '丁家桥校区', '苏州校区', '无锡分校'].index(config['district']) + 1)

    return config

def searchCasLoginInfo(html):
    reSearchTxt = r'<input type="hidden" name="lt" value="(.*)"/>\s*<input type="hidden" name="dllt" value="(.*)"/>\s*<input type="hidden" name="execution" value="(.*)"/>\s*<input type="hidden" name="_eventId" value="(.*)"/>\s*<input type="hidden" name="rmShown" value="(.*)">\s*<input type="hidden" id="pwdDefaultEncryptSalt" value="(.*)"/>'
    rePattern = re.compile(reSearchTxt)
    result = rePattern.search(html)
    casLoginInfo = {
        'lt': result.group(1),
        'dllt': result.group(2),
        'execution': result.group(3),
        '_eventId': result.group(4),
        'rmShown': result.group(5),
        'pwdDefaultEncryptSalt': result.group(6)
    }
    return casLoginInfo

def seuLogin(username, passwd):
    logprint('Logging in as user "%s"...' % username)
    sess = requests.session()

    getHeaders = {
        'accept': '*/*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
    }
    postHeaders = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
    }

    logprint('Requesting authentication RSA Public key...')
    authGetPubKeyUrl = 'https://auth.seu.edu.cn/auth/casback/getChiperKey'
    sess.headers = postHeaders
    resp = sess.post(authGetPubKeyUrl)
    pubKeyText = '-----BEGIN RSA PUBLIC KEY-----\n' + json.loads(resp.text)['publicKey'].replace('-', '+').replace('_', '/') + '\n-----END RSA PUBLIC KEY-----'
    pubKey = RSA.import_key(pubKeyText)
    encModule = PKCS1_v1_5.new(pubKey)
    encPasswd = base64.b64encode(encModule.encrypt(passwd.encode())).decode()
    
    logprint('CAS logging in...')
    authLoginUrl = 'https://auth.seu.edu.cn/auth/casback/casLogin'
    data = {
        'captcha': '',
        'loginType': 'account',
        'mobilePhoneNum': '',
        'mobileVerifyCode': '',
        'password': encPasswd,
        'rememberMe': False,
        'service': '',
        'username': username,
        'wxBinded': False
    }
    resp = sess.post(authLoginUrl, json.dumps(data))
    if not json.loads(resp.text)['success']:
        logerrorExit('Wrong username or password!')

    logprint('Requesting CAS Ticket...')
    authVerifyTgtUrl = 'https://auth.seu.edu.cn/auth/casback/verifyTgt'
    data = {
        'service': 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/*default/index.do'
    }
    resp = sess.post(authVerifyTgtUrl, json.dumps(data))
    rdUrl = json.loads(resp.text)['redirectUrl']
    sess.post(rdUrl, data)

    return sess

def getLectData(sess):
    logprint('Refreshing lecture data...')
    data = {
        'pageIndex': 1,
        'pageSize': 1000
    }

    lectDataUrl = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/hdyy/queryActivityList.do'
    resp = sess.post(lectDataUrl, data)

    while True:
        resp = sess.post(lectDataUrl, data)
        if resp.status_code == 200:
            return json.loads(resp.text)['datas']
        else:
            logprint('Unable to refresh lecture data!')

def sessRsvLect(sess, ocr, wid):
    captchaUrl = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/hdyy/vcode.do'
    regUrl = 'http://ehall.seu.edu.cn/gsapp/sys/jzxxtjapp/hdyy/yySave.do'

    captchaFalse = True
    while captchaFalse:
        logprint('Retriving captcha pic...')
        resp = sess.post(captchaUrl)
        imageStr = json.loads(resp.text)['result']
        rawdata = base64.b64decode(imageStr.split('64,')[1])
        captcha = ocr.classification(rawdata)
        data = {
            'HD_WID': wid,
            'vcode': captcha
        }
        form = {'paramJson': json.dumps(data)}
        logprint('Delivering reservation request...')
        resp = sess.get(regUrl, params=form)
        respdata = json.loads(resp.text)
        if respdata['success'] == True:
            captchaFalse = False
        elif respdata['msg'] != '验证码错误，请重试！注意不要同时使用多台设备进行预约操作。':
            captchaFalse = False
        if captchaFalse:
            logprint('Wrong captcha code, retrying...')
    return respdata

def rsvLect():
    logprint('Loading config file...')
    config = loadConfig('config.json')
    ocr = ddddocr.DdddOcr(show_ad=False)
    sessLectRsv = seuLogin(config['username'], config['passwd'])

    rsvSuccess = False
    
    while not rsvSuccess:
        lectData = getLectData(sessLectRsv)
        if lectData == None:
            logprint('Session timeout!')
            sessLectRsv = seuLogin(config['username'], config['passwd'])
            lectData = getLectData(sessLectRsv)
        elif lectData == []:
            logprint('List empty, currently no active lectures! Retrying in 10 min...')
            time.sleep(600)
            continue
        
        logprint('Filtering lecture list...')
        lectData = list(filter(lambda x: time.mktime(time.strptime(x['YYJSSJ'], "%Y-%m-%d %H:%M:%S")) >= time.time(), lectData))
        if lectData == []:
            logprint('All lectures reservation due! Retrying in 10 min...')
            time.sleep(600)
            continue

        if config['onlineOnly'] == True:
            lectData = list(filter(lambda x: x['JZDD'] in ['腾讯会议', '钉钉'], lectData))
        else:
            lectData = list(filter(lambda x: x['JZDD'] in ['腾讯会议', '钉钉'] or x['SZXQ'] == config['district'], lectData))

        lectTargets = []
        for entity in config['filter']:
            if entity == '心理':
                lectTargets += list(filter(lambda x: x['JZXL_DISPLAY'] == '人文与科学素养系列讲座_心理健康', lectData))
            elif entity == '法律':
                lectTargets += list(filter(lambda x: x['JZXL_DISPLAY'] == '人文与科学素养系列讲座_法律', lectData))
            elif entity == '艺术':
                lectTargets += list(filter(lambda x: x['JZXL_DISPLAY'] == '人文与科学素养系列讲座-艺术类', lectData))
            elif entity == '其他':
                lectTargets += list(filter(lambda x: x['JZXL_DISPLAY'] == '人文与科学素养系列讲座_其他', lectData))
            else:
                lectTargets += list(filter(lambda x: x['JZXL_DISPLAY'] not in ['人文与科学素养系列讲座_心理健康', '人文与科学素养系列讲座_法律', '人文与科学素养系列讲座-艺术类', '人文与科学素养系列讲座_其他'], lectData))
        lectData = lectTargets

        if lectData == []:
            logprint('No matching lecture! Change config filter advised. Retrying in 10 min...')
            time.sleep(600)
            continue
        
        logprint('Matching %d lecture(s), checking reservation status...' % len(lectData))
        lectData = list(filter(lambda x: int(x['YYRS']) < int(x['HDZRS']), lectData))
        if lectData == []:
            logprint('All lectures fully reserved! Retrying in 10 sec...')
            time.sleep(10)
            continue

        lectTargets = list(filter(lambda x: time.mktime(time.strptime(x['YYKSSJ'], "%Y-%m-%d %H:%M:%S")) <= time.time(), lectData))
        if lectTargets == []:
            mostRecentTime = float('inf')
            for lect in lectData:
                lectRsvStartTime = time.mktime(time.strptime(lect['YYKSSJ'], "%Y-%m-%d %H:%M:%S"))
                if mostRecentTime > lectRsvStartTime:
                    mostRecentTime = lectRsvStartTime
            diffTime = mostRecentTime - time.time()
            if diffTime > 10:
                logprint('No lecture available! Retrying in 10 sec...')
                time.sleep(10)
                continue
            else:
                logprint('Incoming reservation in %.2f sec' % diffTime)
                time.sleep(diffTime)
                continue
        lectData = lectTargets
        
        for lect in lectData:
            logtext = 'Reservation in bound!\n           %s-%s\t%s\t%s' % (lect['JZSJ'], lect['HDJSSJ'], lect['JZXL_DISPLAY'], lect['JZMC'])
            logprint(logtext)
            respdata = sessRsvLect(sessLectRsv, ocr, lect['WID'])
            if respdata['success'] == True:
                logprint('Reservation success!')
                rsvSuccess = True
                break
            else:
                logprint('Reservation failed! Error log: %s' % respdata['msg'])
                if respdata['msg'] == '请求过于频繁，请稍后重试':
                    logprint('Awaiting for reservation ban lift, countdown 1 min...')
                    time.sleep(60)

    logprint('Exiting...')
    exit(0)

if __name__ == '__main__':
    while True:
        try:
            rsvLect()
        except requests.exceptions.ConnectionError: 
            logprint('Connection error! If this message appears again, Make sure you are connected to the God d**n SEU-WLAN thing!\nRestarting script in 10 sec...')
            time.sleep(10)
