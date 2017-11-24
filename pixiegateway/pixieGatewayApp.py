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
import uuid
import os
from tornado.log import app_log
from tornado.options import options
from kernel_gateway.gatewayapp import KernelGatewayApp
from traitlets import Unicode, default

class PixieGatewayApp(KernelGatewayApp):
    def initialize(self, argv=None):
        self.api = 'pixiegateway'
        #self.api = 'notebook-http'
        options.log_file_prefix = self.log_path
        super(PixieGatewayApp, self).initialize(argv)        

    def init_webapp(self):
        super(PixieGatewayApp, self).init_webapp()
        self.web_app.settings["cookie_secret"] = base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes).decode("UTF-8")
        self.web_app.settings['compiled_template_cache'] = False
        self.web_app.settings['login_url'] = "/login"
        self.web_app.settings['admin_password'] = self.admin_password

    @property
    def log_path(self):
        return os.path.join(
            os.environ.get("PIXIEDUST_HOME", os.path.join(os.path.expanduser('~'), "pixiedust")),
            "pixiegateway.log"
        )

    prepend_execute_code = Unicode(None, config=True, allow_none=True,
                                   help="""Code to prepend before each execution""")

    admin_user_id = Unicode("admin", config=True, allow_none=True,
                            help="User id for administrator")

    admin_password = Unicode(None, config=True, allow_none=False,
                             help="Admin password")

    @default('prepend_execute_code')
    def prepend_execute_code_default(self):
        return ""

    @default('admin_password')
    def admin_password_default(self):
        return os.getenv("ADMIN_PASSWORD", '')

    @default('admin_user_id')
    def admin_user_id_default(self):
        return os.getenv("ADMIN_USERID", 'admin')