# -------------------------------------------------------------------------------
# Copyright IBM Corp. 2017
# 
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -------------------------------------------------------------------------------
import base64
import os
from collections import namedtuple
from six import string_types
from tornado import gen
from tornado.escape import json_decode, json_encode
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from .base import BaseKernelManager

class RemoteKernelManager(BaseKernelManager):
    def __init__(self, config):
        print("Remote gateway config is: {}".format(config))
        self.config = config
        self.http_client = AsyncHTTPClient()

    @gen.coroutine
    def start_kernel(self, kernel_name, iopub_handler=None, **kwargs):
        kernel_env = {k: v for (k, v) in dict(os.environ).items() if k.startswith('KERNEL_')
                    or k in os.environ.get('KG_ENV_WHITELIST', '').split(",")}
        json_body = json_encode({'name': kernel_name, 'env': kernel_env})
        payload = yield self.do_request("api/kernels", method='POST', body=json_body)
        kernel_handle = self._get_kernel_handle(payload['id'])
        raise gen.Return(kernel_handle)

    def _get_kernel_handle(self, kernel_id):
        print("kernel client initialized")
        return namedtuple("KernelHandle", ['kernel_id'])(
            kernel_id
        )

    def get_kernel_spec(self, kernel_handle):
        pass

    def get_kernel_name(self, kernel_handle):
        pass

    def get_kernel_id(self, kernel_handle):
        pass

    def shutdown(self, kernel_handle):
        """
        Shuts down the kernel
        Kernel_handle must have been obtained by a call to start_kernel
        """
        pass

    def execute(self, kernel_handle, code, silent=False, store_history=True,
                user_expressions=None, allow_stdin=None, 
                stop_on_error=True):
        pass

    def to_json(self, payload):
        if not isinstance(payload, string_types):
            import codecs
            payload = codecs.decode(payload, 'utf-8')
        return json_decode(payload)

    def get_url(self, path, ws=False):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        if "notebook_gateway" in self.config:
            url = "{}/{}".format(self.config["notebook_gateway"].strip("/"), path.strip("/"))
            headers['Authorization'] = 'Basic {}'.format(
                base64.b64encode('{}:{}'.format(self.config['user'], self.config['password']).encode()).decode()
            )
        else:
            url = "{protocol}://{host}:{port}/{path}?token={token}".format(
                protocol=self.config.get("protocol"),
                host=self.config.get("host"),
                port=self.config.get("port"),
                path=path.strip("/"),
                token=self.config.get("auth_token")
            )
        if ws is True:
            url = url.replace('http://', 'ws://').replace('https://', 'wss://')
        return (url, headers)

    @gen.coroutine
    def do_request(self, path, method='GET', body=None):
        url, headers = self.get_url(path)
        response = yield self.http_client.fetch(
            HTTPRequest(url, method=method, headers=headers, body=body)
        )
        if response.error is not None:
            raise response.error
        raise gen.Return(self.to_json(response.body))

    @gen.coroutine
    def list_kernel_specs(self):
        payload = yield self.do_request("api/kernelspecs")
        if "kernelspecs" in payload:
            payload = payload["kernelspecs"]
        raise gen.Return(payload)