# -------------------------------------------------------------------------------
# Copyright IBM Corp. 2018
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
from uuid import uuid4
import json
from pixiegateway.managedClient import ManagedClientPool

class KernelController():
    def __init__(self, context):
        self.context = context
        managed_client = ManagedClientPool.instance().get_by_kernel_id(self.kernel_id)
        self.kernel_manager = managed_client.kernel_manager
        self.kernel_handle = managed_client.kernel_handle
        self.execution_state = self.kernel_manager.get_kernel_execution_state(self.kernel_handle)

    @property
    def kernel_id(self):
        return self.context.get("kernel", "N/A")

    @property
    def kernel_name(self):
        return self.kernel_manager.get_kernel_name(self.kernel_handle)

    @property
    def status(self):
        return self.execution_state.status
    
    @property
    def error(self):
        return self.execution_state.error

    @property
    def log_messages(self):
        return self.execution_state.log_messages

    @property
    def command(self):
        return json.dumps({
            "prefix": uuid4().hex,
            "command": "",
            "avoidMetadata": True,
            "options": {"gateway": self.kernel_id, "cellId":"dummy"}
        }).replace('&', '&amp;')\
            .replace("'", '&apos;')\
            .replace('"', '&quot;')\
            .replace('<', '&lt;')\
            .replace('>', '&gt;')