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
from collections import namedtuple
from tornado import gen
from .base import BaseKernelManager, BaseKernelInfo

class KernelInfo(BaseKernelInfo):
    def __init__(self):
        super(KernelInfo, self).__init__()

class LocalKernelManager(BaseKernelManager):
    "Manager for local kernels"
    def __init__(self, kernel_manager):
        self.kernel_manager = kernel_manager

    @gen.coroutine
    def start_kernel(self, kernel_name, iopub_handler=None, **kwargs):
        on_success = kwargs.pop("on_success", None)
        on_failure = kwargs.pop("on_failure", None)
        try:
            kernel_id = yield self.kernel_manager.start_kernel(kernel_name=kernel_name, **kwargs)
            kernel_handle = self._get_kernel_handle(kernel_id)
            kernel_handle.kernel_info.log("kernel_Id is: {}".format(kernel_id))
            kernel_handle.kernel_info.log("kernel client successfully initialized")

            if iopub_handler is not None:
                iopub = self.kernel_manager.connect_iopub(kernel_id)
                def handler(msgList):
                    _, msgList = kernel_handle.session.feed_identities(msgList)
                    iopub_handler(kernel_handle.session.deserialize(msgList))
                iopub.on_recv(handler)
            if on_success is not None:
                yield on_success(kernel_handle)
        except Exception as exc:
            if on_failure is not None:
                yield on_failure(exc)
            raise
        else:
            raise gen.Return(kernel_handle)

    def get_kernel_execution_state(self, kernel_handle):
        return BaseKernelManager.KernelExecutionState(
            kernel_handle.kernel_info.state,
            kernel_handle.kernel_info.error,
            kernel_handle.kernel_info.log_messages
        )

    def _get_kernel_handle(self, kernel_id):
        kernel = self.kernel_manager.get_kernel(kernel_id)
        kernel_client = kernel.client()
        kernel_client.session = type(kernel_client.session)(
            config=kernel.session.config,
            key=kernel.session.key
        )

        # Start channels and wait for ready
        kernel_client.start_channels()
        kernel_client.wait_for_ready()

        session = type(kernel_client.session)(
            config=kernel_client.session.config,
            key=kernel_client.session.key,
        )
        return namedtuple("KernelHandle", ['kernel_id', 'kernel', 'kernel_client', 'session', 'kernel_info'])(
            kernel_id, kernel, kernel_client, session, KernelInfo()
        )

    def get_kernel_id(self, kernel_handle):
        return kernel_handle.kernel_id

    def get_kernel_spec(self, kernel_handle):
        return kernel_handle.kernel.kernel_spec.to_dict()

    def get_kernel_name(self, kernel_handle):
        return kernel_handle.kernel.kernel_name

    def list_kernel_specs(self):
        return self.kernel_manager.kernel_spec_manager.get_all_specs()

    def execute(self, kernel_handle, code, silent=False, store_history=True,
                user_expressions=None, allow_stdin=False,
                stop_on_error=True):
        return kernel_handle.kernel_client.execute(code, silent, store_history,
                                                   user_expressions, allow_stdin, stop_on_error)

    def shutdown(self, kernel_handle):
        if kernel_handle.kernel_client is not None:
            kernel_handle.kernel_info.log("Shutting down kernel")
            kernel_handle.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel(kernel_handle.kernel_id, now=True)
