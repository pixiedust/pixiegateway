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
from abc import ABCMeta, abstractmethod
from collections import namedtuple, deque
from logging import Formatter, makeLogRecord
from six import with_metaclass

class BaseKernelInfo():
    def __init__(self):
        self.id = None
        self.name = None
        self.state = None
        self.error = None
        self.log_messages=deque([], 200)
        self.log_formatter = Formatter('%(asctime)s - %(name)s - %(message)s')

    def set_kernel_state(self, state = None, error = None):
        self.state = 'error' if error is not None else 'running' if state is None else state
        self.error = error

    def log(self, log_message):
        record = makeLogRecord({
            "name": self.id,
            "msg": log_message
        })
        self.log_messages.append(self.log_formatter.format(record))

class BaseKernelManager(with_metaclass(ABCMeta)):
    """
    Abstract class that provide interface level access to a kernel which can be local or remote
    """
    def __init__(self):
        pass

    @abstractmethod
    def start_kernel(self, kernel_name, iopub_handler=None, **kwargs):
        """
        Start a kernel and return a kernel_id
        """
        pass

    @abstractmethod
    def list_kernel_specs(self):
        pass

    @abstractmethod
    def get_kernel_spec(self, kernel_handle):
        pass

    @abstractmethod
    def get_kernel_name(self, kernel_handle):
        pass

    @abstractmethod
    def get_kernel_id(self, kernel_handle):
        pass

    @abstractmethod
    def shutdown(self, kernel_handle):
        """
        Shuts down the kernel
        Kernel_handle must have been obtained by a call to start_kernel
        """
        pass

    @abstractmethod
    def execute(self, kernel_handle, code, silent=False, store_history=True,
                user_expressions=None, allow_stdin=False, 
                stop_on_error=True):
        """
        Execute python code on the kernel
        """
        pass

    def register_execute_future(self, kernel_handle, future):
        """
        registers a code execution future for notification in case the kernel dies
        """
        pass

    KernelExecutionState = namedtuple('KernelExecutionState', ['status', 'error', 'log_messages'])
    @abstractmethod
    def get_kernel_execution_state(self, kernel_handle):
        """
        returns a KernelExecutionState instance
        """
        pass
