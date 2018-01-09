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
import traceback
import os
import json
from uuid import uuid4
from collections import namedtuple
from six import string_types
from tornado import gen
from tornado.log import app_log
from tornado.concurrent import Future
from tornado.escape import json_decode, json_encode, url_escape
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from .base import BaseKernelManager, BaseKernelInfo

#temporary: match any ssl certificate
import ssl
ssl.match_hostname = lambda cert, hostname: True

class KernelInfo(BaseKernelInfo):
    def __init__(self, future):
        super(KernelInfo, self).__init__()
        self.future = future
        self.running_futures = []
        self.retries = 0
        self.max_connection_retries = 5
        self.ws_conn = None

    def set_kernel_state(self, state = None, error = None):
        super(KernelInfo, self).set_kernel_state(state, error)
        log_message = state or error
        if log_message:
            self.log(log_message)
        if error is not None:
            for future in self.running_futures:
                if not future.done():
                    future.set_exception(Exception(error))
        self.running_futures = [future for future in self.running_futures if not future.done()]

    def clear(self):
        self.retries = self.retries + 1
        if self.retries > self.max_connection_retries:
            self.set_kernel_state(error = "Couldn't start kernel after {} retries".format(self.max_connection_retries))
            raise Exception("Exceeded max retries to start the kernel")
        if self.ws_conn is not None and self.ws_conn.protocol is not None:
            self.log("Closing the ws_conn")
            self.ws_conn.close()
        self.log("clearing kernel_info: {}".format(self.retries))
        self.ws_conn = None

class RemoteKernelManager(BaseKernelManager):
    """
    Manager for remote kernels
    """
    def __init__(self, config):
        app_log.info("Remote gateway config is: %s", config)
        self.config = config
        self.http_client = AsyncHTTPClient()

        #Delete any existing kernels
        self._delete_existing_kernels()

    @gen.coroutine
    def _delete_existing_kernels(self):
        kernels = yield self.list_kernels()
        for kernel in kernels:
            app_log.info("Deleting existing kernel: {}".format(kernel['id']))
            yield self.delete_kernel(kernel['id'])

    @gen.coroutine
    def start_kernel(self, kernel_name, iopub_handler=None, **kwargs):
        # kernel_env = {k: v for (k, v) in dict(os.environ).items() if k.startswith('KERNEL_')
        #               or k in os.environ.get('KG_ENV_WHITELIST', '').split(",")}
        # json_body = json_encode({'name': kernel_name, 'env': kernel_env})
        json_body = json_encode({'name': kernel_name})
        def message_callback(message):
            app_log.debug("got a message %s", message)
            try:
                msg = json.loads(message) if message is not None else None
                if msg is None or self.is_kernel_dead(msg):
                    ws_conn = kernel_handle.kernel_info.ws_conn
                    kernel_handle.kernel_info.retries = kernel_handle.kernel_info.retries + 1
                    if kernel_handle.kernel_info.retries < kernel_handle.kernel_info.max_connection_retries:
                        kernel_handle.kernel_info.set_kernel_state(
                            state = "Kernel died or connection closed unexpectedly: Trying to reconnect in 5 seconds"
                        )
                        IOLoop.current().call_later(5, self._connect_to_kernel, kernel_handle)
                    else:
                        kernel_handle.kernel_info.log(
                            "Connection Closed or dead!!!!! {} - {}".format(ws_conn.close_code, ws_conn.close_reason)
                        )
                        kernel_handle.kernel_info.set_kernel_state(
                            error = "kernel died or connection closed unexpectedly"
                        )
                    if not kernel_handle.kernel_info.future.done():
                        kernel_handle.kernel_info.future.set_exception(
                            Exception("Kernel died or connection closed unexpectedly")
                        )
                    else:
                        kernel_handle.kernel_info.log("Future already done in message_callback")
                    return
                if iopub_handler is not None:
                    iopub_handler(msg)
            except Exception as exc:
                kernel_handle.kernel_info.log("Got exception: {}".format(exc))
                try:
                    import traceback
                    traceback.print_exc()
                except Exception as exc2:
                    print("Exception within exception: {}".format(exc2))

        kernel_handle = self._get_kernel_handle(
            uuid4().hex,
            kernel_name,
            message_callback=message_callback,
            json_body=json_body,
            session=uuid4().hex,  #todo: get session from caller
            **kwargs
        )

        #start a new kernel
        yield self._start_new_kernel(kernel_handle)
        raise gen.Return(kernel_handle)

    def _get_kernel_handle(self, kernel_id, kernel_name, **kwargs):
        future = Future()
        kernel_handle = namedtuple(
            "KernelHandle", ['kernel_id', 'kernel_name', 'connect_args', 'kernel_info']
        )(
            kernel_id, kernel_name, kwargs, KernelInfo(future)
        )
        on_success = kwargs.get("on_success", None)
        on_failure = kwargs.get("on_failure", None)
        if on_success is not None or on_failure is not None:
            @gen.coroutine
            def done_callback(kernel_future):
                try:
                    if kernel_future.exception() is not None:
                        kernel_handle.kernel_info.log("kernel has exception: {}".format(kernel_future.exception()))
                        if on_failure is not None:
                            on_failure(kernel_future.exception())
                    elif on_success is not None:
                        on_success(kernel_handle)
                except Exception as exc:
                    kernel_handle.kernel_info.log("Unexpected exception: {}".format(exc))
                else:
                    kernel_handle.kernel_info.log("kernel future is done: {}".format(kernel_future))
            future.add_done_callback(done_callback)
        return kernel_handle

    def register_execute_future(self, kernel_handle, future):
        kernel_handle.kernel_info.running_futures.append(future)

    def get_kernel_execution_state(self, kernel_handle):
        return BaseKernelManager.KernelExecutionState(
            kernel_handle.kernel_info.state,
            kernel_handle.kernel_info.error,
            kernel_handle.kernel_info.log_messages
        )

    @gen.coroutine
    def _start_new_kernel(self, kernel_handle):
        kernel_handle.kernel_info.clear()
        kernel_handle.kernel_info.set_kernel_state(state = "Starting Kernel")
        json_body = kernel_handle.connect_args['json_body']
        payload = yield self.do_request("api/kernels", method='POST', body=json_body)
        kernel_handle.kernel_info.id = payload['id']
        kernel_handle.kernel_info.name = payload['name']
        kernel_handle.kernel_info.log("Successfully started a new kernel: {}".format(payload))

        #connect to the new kernel
        raise gen.Return((yield self._connect_to_kernel(kernel_handle)))

    def _connect_to_kernel(self, kernel_handle):
        kernel_handle.kernel_info.set_kernel_state(state = "Connecting to kernel")
        try:
            kernel_id = kernel_handle.kernel_info.id
            url, headers = self.get_url(
                '/api/kernels/{}/channels'.format(url_escape(kernel_id)),
                ws=True
            )
            request = HTTPRequest(url, headers=headers)
            message_callback = kernel_handle.connect_args['message_callback']
            ws_conn_future = websocket_connect(
                request,
                ping_interval=5,
                ping_timeout=15,
                on_message_callback=message_callback)
            @gen.coroutine
            def on_connected(ws_future):
                ws_conn = ws_future.result()
                kernel_handle.kernel_info.ws_conn = ws_conn
                kernel_handle.kernel_info.log("Web Socket connection to kernel established: {}".format(ws_conn))
                if kernel_handle.kernel_info.future.done():
                    kernel_handle.kernel_info.set_kernel_state()
                    return
                else:
                    kernel_handle.kernel_info.set_kernel_state()
                    kernel_handle.kernel_info.future.set_result(kernel_handle)
                    return
                self._write_message(kernel_handle, 'kernel_info_request')
                while True:
                    try:
                        if kernel_handle.kernel_info.future.done():
                            break
                        kernel_info = yield self.get_kernel_info(kernel_id)
                        execution_state = kernel_info['execution_state']
                        if execution_state == "idle":
                            kernel_handle.kernel_info.log("Kernel Ready: {}".format(kernel_info))
                            kernel_handle.kernel_info.set_kernel_state()
                            kernel_handle.kernel_info.future.set_result()
                            break
                        elif execution_state == "dead":
                            kernel_handle.kernel_info.log("Kernel Died: {}".format(kernel_info))
                            kernel_handle.kernel_info.future.set_exception(
                                Exception("Kernel died or connection closed unexpectedly")
                            )
                            break
                    except Exception as exc:
                        kernel_handle.kernel_info.log("Got an exception trying to get kernel info: {} - {}".format(kernel_id, exc))
                        if not kernel_handle.kernel_info.future.done():
                            kernel_handle.kernel_info.future.set_exception(
                                Exception("Kernel died or connection closed unexpectedly")
                            )
                        else:
                            kernel_handle.kernel_info.log("Future is already done")
                        break
            ws_conn_future.add_done_callback(on_connected)
        except HTTPError as exc:
            #create a new kernel
            kernel_handle.kernel_info.log(
                "Got an http error, creating a new kernel in 5 seconds: {} - {}".format(exc, exc.__class__)
            )
            kernel_handle.kernel_info.set_kernel_state(
                error = "Unable to access kernel: {}. Trying again in 5 seconds".format(exc)
            )
            IOLoop.current().call_later(5, self._start_new_kernel, kernel_handle)
        except Exception as exc:
            if isinstance(exc, gen.Return):
                raise
            print("Got an error trying to connect in 5 seconds: {} - {}".format(exc, exc.__class__))
            kernel_handle.kernel_info.set_kernel_state(
                error = "Unable to connect to kernel: {}. Trying again in 5 seconds".format(exc)
            )
            IOLoop.current().call_later(5, self._connect_to_kernel, kernel_handle)

        return kernel_handle.kernel_info.future

    def is_kernel_dead(self, message):
        return message['msg_type'] == "status" and 'content' in message and message['content']['execution_state'] == 'dead'

    @gen.coroutine
    def get_kernel_info(self, kernel_id):
        raise gen.Return((
            yield self.do_request("api/kernels/{}".format(kernel_id))
        ))

    def get_kernel_spec(self, kernel_handle):
        return {}

    def get_kernel_name(self, kernel_handle):
        return kernel_handle.kernel_info.name or kernel_handle.kernel_name

    def get_kernel_id(self, kernel_handle):
        return kernel_handle.kernel_id

    @gen.coroutine
    def shutdown(self, kernel_handle):
        """
        Shuts down the kernel
        Kernel_handle must have been obtained by a call to start_kernel
        """
        kernel_id = kernel_handle.kernel_info.id
        app_log.info("Deleting existing kernel: %s", kernel_id)
        yield self.delete_kernel(kernel_id)

    def _write_message(self, kernel_handle, msg_type, content=None):
        msg_id = uuid4().hex
        kernel_handle.kernel_info.ws_conn.write_message(json_encode({
            'header': {
                'username': 'pixiegateway',
                'version': '5.2',
                'session': kernel_handle.connect_args['session'],
                'msg_id': msg_id,
                'msg_type': msg_type
            },
            'parent_header': {},
            'channel': 'shell',
            'content': content if content is not None else {},
            'metadata': {},
            'buffers': {}
        }))
        print("Wrote message with type {} and msg_id: {}".format(msg_type, msg_id))
        return msg_id

    def execute(self, kernel_handle, code, silent=False, store_history=True,
                user_expressions=None, allow_stdin=False, stop_on_error=True):
        if kernel_handle.kernel_info.state != 'running':
            raise Exception(
                "Kernel not running: {} : {}".format(
                    kernel_handle.kernel_info.state,
                    kernel_handle.kernel_info.error
                )
            )
        return self._write_message(kernel_handle, 'execute_request', content={
            'code': code,
            'silent': silent,
            'store_history': store_history,
            'user_expressions' : user_expressions,
            'allow_stdin' : allow_stdin,
            "stop_on_error": stop_on_error
        })

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
        gateway_key = "notebook_gateway_websocket" if ws is True and "notebook_gateway_websocket" in self.config else "notebook_gateway" 
        if gateway_key in self.config:
            url = "{}/{}".format(self.config[gateway_key].strip("/"), path.strip("/"))
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
        if response.body:
            raise gen.Return(self.to_json(response.body))

    @gen.coroutine
    def list_kernel_specs(self):
        payload = yield self.do_request("api/kernelspecs")
        if "kernelspecs" in payload:
            payload = payload["kernelspecs"]
        raise gen.Return(payload)

    @gen.coroutine
    def list_kernels(self):
        raise gen.Return((
            yield self.do_request("api/kernels")
        ))
        
    @gen.coroutine
    def delete_kernel(self, kernel_id):
        yield self.do_request("api/kernels/{}".format(kernel_id), method='DELETE')
