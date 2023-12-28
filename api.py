"""
Interact with Intense Pure Air API.

Based on:
https://github.com/Danielhiversen/pymill/blob/ce3d0658331b1ad7b6c0c9efe79c3cee1de1b06d/mill/__init__.py
And mitmproxy'ing the application.
"""

import hashlib
import json
import logging
import requests
import random
import string
import time
from enum import IntEnum

API_ENDPOINT = "https://eurouter.ablecloud.cn:9005"

REQUEST_TIMEOUT = "300"

logger = logging.getLogger(__name__)


class Mode(IntEnum):
    QUIET = 1
    NIGHT = 2
    DAY = 3
    BOOST = 4


class Light(IntEnum):
    OFF = 2
    LOW = 1
    HIGH = 0


class Api:
    def __init__(self):
        self.session = requests.Session()

        self._user_id = "0"
        self._token = ""
        self._dcp_token = ""
        self._dcp_uid = ""

    def request(self, path, payload, headers={}):
        payload["dcpMarket"] = "GS_US"
        payload["dcpUid"] = self._dcp_uid
        payload["dcpToken"] = self._dcp_token

        payload = json.dumps(payload)

        nonce = "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(16)
        )
        url = API_ENDPOINT + path
        timestamp = int(time.time())
        signature = hashlib.sha1(
            str(REQUEST_TIMEOUT + str(timestamp) + nonce + self._token).encode("utf-8")
        ).hexdigest()

        headers = {
            "Content-Type": "application/x-zc-object",
            "X-Zc-Content-Length": str(len(payload)),
            "X-Zc-Major-Domain": "groupeseb",
            "X-Zc-Sub-Domain": "rowentaxl",
            "X-Zc-Timestamp": str(timestamp),
            "X-Zc-Timeout": REQUEST_TIMEOUT,
            "X-Zc-Nonce": nonce,
            "X-Zc-User-Id": self._user_id,
            "X-Zc-User-Signature": signature,
            "X-Zc-Device-Os": "android",
            "X-Zc-Operation-Type": "app",
            **headers,
        }

        logger.debug(
            "About to send a request to %s with payload %s and headers %s",
            url,
            payload,
            headers,
        )

        response = self.session.post(url, data=payload, headers=headers)

        logger.debug("Response %s: %s", response, response.text)
        return response

    def connect(self, username, password):
        response = self.request(
            "/SEBService/v1/dcp-login",
            {"loginName": username, "password": password},
            headers={"X-Zc-Access-Mode": "1"},
        ).json()

        self._token = response["token"]
        self._dcp_token = response["dcpToken"]
        self._dcp_uid = response["dcpUid"]
        self._user_id = str(response["userId"])

        logger.info("Connected to API. Nickname is %s.", response["nickName"])

    def sync_content(self):
        assert self._token
        response = self.request(
            "/SEBService/v1/dcp-syncContent",
            {"contentType": "syncAppliances", "lang": "en"},
        )
        return response.json()["content"]["objects"]

    def list_devices(self):
        assert self._token
        response = self.request("/zc-bind/v1/listDevicesExt", {"status": True})
        return response.json()["devices"]

    def device_info(self, device_id: int):
        assert self._token
        response = self.request(
            "/SEBService/v1/queryDeviceInfo", {"deviceId": device_id}
        )
        return response.json()

    def set_power(self, device_id: int, power_on: bool):
        assert self._token
        response = self.request(
            "/SEBService/v1/controlDeviceInfo",
            {
                "deviceId": device_id,
                "value": int(power_on),
                "subDomainName": "rowentaxs",
                "sn": 1,
                "commend": "on_off",
            },
        )
        return response

    def set_mode(self, device_id: int, mode: Mode):
        assert self._token
        response = self.request(
            "/SEBService/v1/controlDeviceInfo",
            {
                "deviceId": device_id,
                "value": int(mode),
                "subDomainName": "rowentaxs",
                "sn": 1,
                "commend": "model",
            },
        )
        return response

    def set_light(self, device_id: int, mode: Light):
        assert self._token
        response = self.request(
            "/SEBService/v1/controlDeviceInfo",
            {
                "deviceId": device_id,
                "value": mode,
                "subDomainName": "rowentaxs",
                "sn": 1,
                "commend": "light",
            },
        )
        return response


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import argparse

    parser = argparse.ArgumentParser(
        prog="API",
        description="Test the intense pure air API, will turn on your purifiers and set to boost mode.",
    )
    parser.add_argument("username")
    parser.add_argument("password")
    args = parser.parse_args()
    api = Api()
    api.connect(args.username, args.password)
    devices = api.list_devices()
    for device in devices:
        print("Device {}: {}".format(device["deviceId"], device["name"]))
        device_id = device["deviceId"]
        print("Info:", json.dumps(api.device_info(device_id)))
        print("Setting it to boost mode.")
        api.set_power(device_id, power_on=True)
        api.set_light(device_id, Light.LOW)
        api.set_mode(device_id, Mode.BOOST)
