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
__all__ = [
    'PixieDustHandler', 'PixieDustLogHandler', 'ExecuteCodeHandler', 'PixieAppHandler',
    'PixieAppListHandler', 'PixieAppPublishHandler', 'ChartShareHandler', 'StatsHandler',
    'AdminHandler', 'ChartEmbedHandler', 'ChartsHandler', 'OEmbedChartHandler', 'LoginHandler',
    'AdminCommandHandler'
]

import inspect
import json
import os
import traceback
from uuid import uuid4
import tornado
from tornado.log import app_log
import pixiegateway
from pixiegateway.exceptions import CodeExecutionError, AppAccessError
from pixiegateway.session import SessionManager

class BaseHandler(tornado.web.RequestHandler):
    """Base class for all PixieGateway handler"""
    def initialize(self):
        self.output_json_error = False

    def _handle_request_exception(self, exc):
        print("Got an exception: {}".format(exc))
        if isinstance(exc, AppAccessError):
            return self.send_error(401)

        html_error = "<div>Unexpected error:</div><pre>{}</pre>".format(
            str(exc) if isinstance(exc, CodeExecutionError) else traceback.format_exc()
        )
        if self.output_json_error:
            msg = {
                "buffers": [],
                "channel": "iopub",
                "content": {
                    "data": {
                        "text/html": html_error
                    },
                    "metadata": {},
                    "transient": {}
                },
                "header": {
                    "username": "pixiegateway",
                    "msg_type": "display_data",
                    "msg_id": uuid4().hex,
                    "version": "5.2"
                },
                "metadata": {},
                "msg_id": "",
                "msg_type":"display_data",
                "parent_header": {}
            }
            self.write(json.dumps([msg]))
        else:
            self.write(html_error)
        self.finish()

    # def create_template_loader2(self, template_path):
    #     print("Create template loader: {}".format(template_path))
    #     file = None
    #     if template_path.startswith("/"):
    #         file = pixiegateway.__file__
    #         print("resolving: {}".format(file))
    #     else:
    #         file = inspect.getfile(inspect.currentframe())

    #     template_path = os.path.dirname(
    #         os.path.abspath(
    #             file
    #         )
    #     )
    #     settings = self.application.settings
    #     kwargs = {}
    #     if "autoescape" in settings:
    #         # autoescape=None means "no escaping", so we have to be sure
    #         # to only pass this kwarg if the user asked for it.
    #         kwargs["autoescape"] = settings["autoescape"]
    #     if "template_whitespace" in settings:
    #         kwargs["whitespace"] = settings["template_whitespace"]
    #     return tornado.template.Loader(template_path, **kwargs)

    def render_string(self, template_name, **kwargs):
        try:
            self.template_name = template_name
            return super(BaseHandler, self).render_string(template_name.strip("/"), **kwargs)
        finally:
            self.template_name = None

    def get_template_path(self):
        if self.template_name.startswith("/"):
            file_path = pixiegateway.__file__
        else:
            file_path = inspect.getfile(inspect.currentframe())
        return os.path.dirname(os.path.abspath(file_path))

    def prepare(self):
        """
        Retrieve session for current user
        """
        self.session = SessionManager.instance().get_session(self)
        app_log.debug("session %s", self.session)

    def get_current_user(self):
        return self.get_secure_cookie("pd_user")

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

from .adminHandlers import AdminHandler, StatsHandler, AdminCommandHandler
from .handlers import (PixieDustHandler, PixieDustLogHandler, ExecuteCodeHandler, PixieAppHandler,
    PixieAppListHandler, PixieAppPublishHandler, ChartShareHandler,
    ChartEmbedHandler, ChartsHandler, OEmbedChartHandler, LoginHandler)