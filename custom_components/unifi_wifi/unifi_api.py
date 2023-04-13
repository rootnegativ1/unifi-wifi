import requests

# suppress warnings about not verifying SSL certs
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)


class Controller:
    def __init__(self, url, user, password, site, unifios):
        self.baseurl = url
        self.user = user
        self.password = password
        self.site = site
        self.unifios = unifios
        self.is_unifi_os()

    def is_unifi_os(self):
        if self.unifios:
            self.port = 443
            self.login_prefix = '/api/auth'
            self.api_prefix = '/proxy/network'
        else:
            self.port = 8443
            self.login_prefix = '/api'
            self.api_prefix = ''

    def login(self):
        #url = f"{self.baseurl}:{self.port}{self.login_prefix}/login"
        url = f"{self.baseurl}{self.login_prefix}/login"
        payload = {'username': self.user, 'password': self.password}
        headers = {}
        res = requests.post(url, data=payload, headers=headers, verify=False)

        self.cookie = res.cookies
        self.csrf_token = res.headers['X-CSRF-Token']

    def logout(self):
        #url = f"{self.baseurl}:{self.port}{self.login_prefix}/logout"
        url = f"{self.baseurl}{self.login_prefix}/logout"
        headers = {'X-CSRF-Token': self.csrf_token, 'content-length': '0'}
        res = requests.post(url, cookies=self.cookie, headers=headers, verify=False)

    def get_wlanconf(self):
        self.login()

        #url = f"{self.baseurl}:{self.port}{self.api_prefix}/api/s/{self.site}/rest/wlanconf"
        url = f"{self.baseurl}{self.api_prefix}/api/s/{self.site}/rest/wlanconf"
        res = requests.get(url, cookies=self.cookie, verify=False)
        self.wlanconf = res.json()['data']

        self.logout()

    def set_wlanconf(self, ssid, payload):
        self.login()

        wlanconf = self.wlanconf
        for networks in wlanconf:
            if networks['name'] == ssid:
                idno = networks['_id']

        #url = f"{self.baseurl}:{self.port}{self.api_prefix}/api/s/{self.site}/rest/wlanconf/{idno}"
        url = f"{self.baseurl}{self.api_prefix}/api/s/{self.site}/rest/wlanconf/{idno}"
        headers = {'X-CSRF-Token': self.csrf_token}
        res = requests.put(url, cookies=self.cookie, json=payload, headers=headers, verify=False)

        self.logout()