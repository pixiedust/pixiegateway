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
from collections import OrderedDict, deque
from six import iteritems, PY3
import tornado
from tornado import gen, web
from tornado.util import import_object
from pixiegateway.notebookMgr import NotebookMgr
from pixiegateway.handlers import BaseHandler
from pixiegateway.pixieGatewayApp import PixieGatewayApp
from pixiegateway.managedClient import ManagedClientPool
from pixiegateway.session import SessionManager

class StatsHandler(BaseHandler):
    """
    Provides various stats about the running kernels
    """
    @gen.coroutine
    def get(self, command):
        if command == "kernels":
            specs = yield gen.maybe_future(ManagedClientPool.instance().list_kernel_specs())
            specs = {k:v for k, v in iteritems(specs) if v['spec']['language'] == 'python'}
            for key, value in iteritems(specs):
                value['default'] = True if key == ('python3' if PY3 else 'python2') else False
            self.write(specs)
            self.finish()
        else:
            yield self._process_command(command)

    @gen.coroutine
    @tornado.web.authenticated
    def _process_command(self, command):
        if command is None:
            stats = yield gen.maybe_future(ManagedClientPool.instance().get_stats())
            for mc_id in stats:
                stats[mc_id]['users'] = SessionManager.instance().get_users_stats(mc_id)
            self.write(stats)
            self.finish()
        else:
            raise web.HTTPError(400, u'Unknown stat command: {}'.format(command))

class AdminCommandHandler(BaseHandler):
    "Handles admin commands"
    @tornado.web.authenticated
    def get(self, command):
        command_map = {
            "delete_app": self.delete_app
        }
        parts = command.split('/')
        command = parts[0:1][0]
        args = parts[1:]
        if command not in command_map:
            raise web.HTTPError(400, u'Unknown admin command: {}'.format(command))
        command_map[command](*args)

    @gen.coroutine
    def delete_app(self, appName):
        try:
            results = yield NotebookMgr.instance().delete_notebook_pixieapp(appName)
            self.set_status(results["status_code"])
            self.write(results)
            self.flush()
        except Exception as exc:
            self._handle_request_exception(exc)

class AdminHandler(BaseHandler):
    "End point handler for the Admin Console"
    def fetch_logs(self):
        with open( PixieGatewayApp.instance().log_path) as log_file:
            return "\n".join(deque(log_file, 100))
    @tornado.web.authenticated
    def get(self, tab_id):
        tab_definitions = OrderedDict([
            ("apps", {"name": "PixieApps", "path": "admin/pixieappList.html", "description": "Published PixieApps",
                      "args": lambda: {"pixieapp_list":NotebookMgr.instance().notebook_pixieapps()}}),
            ("charts", {"name": "Charts", "path": "admin/chartsList.html", "description": "Shared Charts"}),
            ("stats", {
                "default": {"name": "Kernel Stats", "path": "admin/adminStats.html", "description": "PixieGateway Statistics"},
                "app": {
                    "name": "PixieApp Details", "path": "admin/pixieappDetails.html", 
                    "description": "PixieApp Details", "manager":"pixiegateway.admin.AppController"
                },
                "kernel":{
                    "name": "Kernel Details", "path": "admin/kernelDetails.html",
                    "description": "Kernel Details", "manager": "pixiegateway.admin.KernelController"
                }
            }
            ),
            ("logs", {"name": "Server Logs", "path": "admin/adminLogs.html", "description": "Server logs",
                      "args": lambda: {"logs": self.fetch_logs()}})
        ])
        tab_id, content_definition = self.compute_tab_id(tab_definitions, tab_id or "apps")
        self.render(
            "/template/admin/adminConsole.html",
            tab_definitions=tab_definitions,
            selected_tab_id=tab_id,
            content_definition=content_definition
        )

    def compute_tab_id(self, tab_definitions, tab_id):
        parts = tab_id.split("/")
        tab_id = parts[0]
        if tab_id not in tab_definitions:
            raise Exception("Invalid url")

        content_definition = tab_definitions[tab_id]
        if "default" in content_definition:
            content_definition = content_definition[parts[1] if len(parts) > 1 else 'default']
            if len(parts) > 2:
                parts = parts[1:]
                if len(parts) % 2 != 0:
                    raise Exception("Invalid url")
                content_definition = content_definition.copy()
                orgs_arg_callable = content_definition.get("args", None)
                def args_wrapper():
                    results = orgs_arg_callable() if orgs_arg_callable is not None else {}
                    ite = iter(parts)
                    results.update({p:next(ite) for p in ite})
                    if "manager" in content_definition:
                        results['manager'] = import_object(content_definition['manager'])(results)
                    return results
                content_definition["args"] = args_wrapper
        return tab_id, content_definition