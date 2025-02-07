#
# Copyright (c) Michael Kelly. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for details.
#

import json
import time
import requests
from loguru import logger


class MosyleAPI():
    def __init__(self, token: str, email: str, password: str, base_url : str = "https://managerapi.mosyle.com/v2"):
        """
        Creates a new instance of the Mosyle API.
        :param token: Access token provided by the Mosyle integration
        :param email: Email address for a Mosyle admin account with API permission
        :param password: Password for the Mosyle admin account
        :param base_url: Optional, Base URL for the Mosyle API, this usually is not required to be changed
        """
        self.base_url = base_url
        self.token = token
        self.email = email
        self.password = password
        self.bearer_token = None
        self.last_token_update = 0

    def retrieve_jwt(self) -> bool:
        """
        Retrieves an updated JWT bearer token from Mosyle using the API access token.
        :return: Boolean, True if successful
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "pymosyle"
        }
        data = {
            "accessToken": self.token,
            "email": self.email,
            "password": self.password
        }
        logger.debug(f"Trying to obtain a bearer token as {self.email}")
        response = requests.post(f"{self.base_url}/login", headers=headers, data=json.dumps(data))
        if response.status_code != 200:
            logger.error(f"An attempt to obtain a bearer token failed, received HTTP {response.status_code}")
            logger.debug(response.content)
            self.bearer_token = None
            self.last_token_update = 0
            return False

        if 'Authorization' not in response.headers.keys():
            logger.error("An attempt to obtain a bearer token failed, received 200, but no Authorization header")
            logger.debug(response.content)
            self.bearer_token = None
            self.last_token_update = 0
            return False

        self.bearer_token = response.headers.get("Authorization")
        self.last_token_update = time.time()
        logger.info(f"Obtained a new bearer token for {self.email} successfully")
        return True

    def execute_request(self, method: str, url: str, data: dict = {}) -> dict:
        """
        Executes a web request against the Mosyle API, provides headers and authentication as required.
        :param method: HTTP method, usually POST for Mosyle
        :param url: URL of the API endpoint
        :param data: JSON data to send with the request
        :return: Response data from the Mosyle API, raises Exception on error
        """
        if self.bearer_token is None or time.time() - self.last_token_update > 86400:
            # Mosyle tokens are only valid for 24 hours
            if not self.retrieve_jwt():
                logger.error("Canceling API operation as I am unable to get a bearer token.")
                raise Exception("No bearer token available")

        headers = {
            "User-Agent": "pymosyle",
            "Authorization": self.bearer_token
        }

        full_url = f"{self.base_url}/{url}"
        logger.debug(f"Request: {method} {full_url}")

        if method != "GET":
            data['accessToken'] = self.token
            if data is not None and len(data.keys()) > 0:
                headers['Content-Type'] = 'application/json'

        if method == "GET":
            response = requests.get(full_url, headers=headers)
        elif method == "POST":
            response = requests.post(full_url, headers=headers, data=json.dumps(data))
        elif method == "PATCH":
            response = requests.patch(full_url, headers=headers, data=json.dumps(data))
        elif method == "DELETE":
            response = requests.delete(full_url, headers=headers, data=json.dumps(data))
        elif method == "PUT":
            response = requests.put(full_url, headers=headers, data=json.dumps(data))
        else:
            raise Exception(f"Unsupported request method: {method}")

        if response.status_code != 200:
            logger.error(f"Web request failed with HTTP code {response.status_code}")
            logger.debug(response.content)
            raise Exception(f"Did not receive success from Mosyle, instead {response.status_code}")

        try:
            response_json = json.loads(response.content)
        except:
            logger.error("Web request could not decode as JSON")
            logger.debug(response.content)
            raise Exception(f"Received not JSON from Mosyle")

        if 'status' not in response_json.keys() or response_json['status'] != "OK":
            logger.error("Web request decoded as JSON, but did not return success")
            logger.debug(response_json)
            raise Exception(f"Received not OK from Mosyle")

        if 'response' in response_json.keys():
            return response_json['response']
        elif 'devices' in response_json.keys():
            return response_json['devices']
        else:
            return {}

    def get_device(self, os_type: str, serial_number: str) -> dict:
        """
        Gets data about a specific device from Mosyle.
        :param os_type: OS type of device, i.e. ios, macos, or tvos
        :param serial_number: Serial number of the device
        :return: Device data or None if not found
        """
        filters = {
            'serial_numbers': [serial_number]
        }
        devices = self.get_devices(os_type, max_results=1, additional_filters=filters)
        if len(devices) == 1:
            return devices[0]
        else:
            return None

    def get_devices(self, os_type: str, tags: list = [], max_results: int = -1,
                    additional_filters: dict = {}) -> list[dict]:
        """
        Gets a list of devices and data from the Mosyle API.
        :param os_type: OS type of device, i.e. ios, macos, or tvos
        :param tags: Optional, filter device list to devices that have these tags, default all
        :param max_results: Optional, maximum number of devices to return, default no limit
        :param additional_filters: Additional filters for the device list, see Mosyle API docs for more details.
        :return: List of devices
        """
        data = {
            'options': {
                'os': os_type,
                'page': 0
            }
        }
        for additional_filter_key in additional_filters.keys():
            data['options'][additional_filter_key] = additional_filters[additional_filter_key]
        if len(tags) > 0:
            data['options']['tags'] = tags

        devices = []
        page = 0
        has_more = True

        while has_more:
            if max_results != -1 and len(devices) >= max_results:
                has_more = False
                break
            data['options']['page'] = page
            logger.debug(f"Retrieving list of devices, page {page}")
            response = self.execute_request("POST", "listdevices", data)
            for device in response['devices']:
                devices.append(device)
            page = page + 1
            if len(devices) >= int(response['rows']):
                has_more = False

        return devices

    def update_device(self, os_type: str, serial_number: str, attributes: dict) -> dict:
        """
        Updates one or more attributes in Mosyle for a device.
        :param os_type: OS type of device, i.e. ios, macos, or tvos
        :param serial_number: Serial number of the device to update
        :param attributes: Dictionary of attributes to update and their new values
        :return: New device data after the update
        """
        data = {
            "elements": [
                {
                    "serialnumber": serial_number
                }
            ]
        }
        for attribute_key in attributes.keys():
            data['elements'][0][attribute_key] = attributes[attribute_key]
        logger.debug(f"Updating device {serial_number}, new data {attributes}")
        response = self.execute_request("POST", "devices", data)

        return response[0]
