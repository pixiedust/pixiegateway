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
from pixiegateway.managedClient import ManagedClientPool
from pixiegateway.notebookMgr import NotebookMgr

class AppController():
    def __init__(self, context):
        self.context = context
        self.kernel_id = self.context['kernel']
        stats = ManagedClientPool.instance().get_stats(self.kernel_id)[self.kernel_id]
        self.run_stats = stats['run_stats']
        self.app_stats = [stat for stat in stats['app_stats'] if stat['appName'] == self.app_name][0]
        self.pixieapp_def = NotebookMgr.instance().get_notebook_pixieapp(self.app_name)

    @property
    def app_name(self):
        return self.context.get("app", "N/A")

    @property
    def kernel_name(self):
        return self.run_stats['kernel_name']

    @property
    def status(self):
        return self.app_stats['status']

    @property
    def warmup_code(self):        
        return self.pixieapp_def.warmup_code if self.pixieapp_def is not None else "<Warmup code Unavailable>"

    @property
    def run_code(self):
        return self.pixieapp_def.run_code if self.pixieapp_def is not None else "<Run code Unavailable>"

    @property
    def exception(self):
        if self.pixieapp_def is None:
            return None
        managed_client = ManagedClientPool.instance().get_by_kernel_id(self.kernel_id)
        return managed_client.get_app_stats(self.pixieapp_def, 'warmup_exception')
