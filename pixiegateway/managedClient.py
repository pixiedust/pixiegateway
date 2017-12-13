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
import json
from datetime import datetime
from time import time
from six import iteritems
from tornado import locks, gen
from tornado.log import app_log
from tornado.concurrent import Future
from traitlets.config.configurable import SingletonConfigurable
from traitlets import Dict, default
from .kernel import LocalKernelManager, RemoteKernelManager
from .pixieGatewayApp import PixieGatewayApp
from .utils import sanitize_traceback

class ManagedClient(object):
    """
    Managed access to a kernel client
    """
    def __init__(self, kernel_manager, kernel_name=None):
        self.kernel_manager = kernel_manager
        self.current_iopub_handler = None
        self.installed_modules = []
        self.app_stats = None
        self.run_stats = None
        #auto-start
        self.start(kernel_name)

    def get_app_stats(self, pixieapp_def, stat_name = None):
        name = pixieapp_def.name
        if not name in self.app_stats or (stat_name is not None and stat_name not in self.app_stats[name]):
            return None
        return self.app_stats[name][stat_name] if stat_name is not None else self.app_stats[name]

    def set_app_stats(self, pixieapp_def, stat_name, stat_value):
        name = pixieapp_def.name
        if not name in self.app_stats:
            self.app_stats[name] = {}
        self.app_stats[name][stat_name] = stat_value

    def get_run_stats(self, stat_name, def_value=None):
        return self.run_stats.get(stat_name, def_value )

    def set_run_stats(self, stat_name, stat_value):
        self.run_stats[stat_name] = stat_value

    def get_stats(self):
        return {
            "run_stats": self.run_stats.external_repr(),
            "app_stats": self.app_stats.external_repr()
        }

    @gen.coroutine
    def start(self, kernel_name=None):
        self.app_stats = ManagedClientAppMetrics()
        self.run_stats = ManagedClientRunMetrics()
        self.kernel_handle = yield gen.maybe_future(self.kernel_manager.start_kernel(
            kernel_name=kernel_name,
            iopub_handler=self.iopub_handler
        ))

        #start the stats
        self.run_stats.start(
            self.kernel_manager.get_kernel_name(self.kernel_handle), 
            self.kernel_manager.get_kernel_spec(self.kernel_handle)
        )

        self.lock = locks.Lock()

        #Initialize PixieDust
        future = self.execute_code("""
import pixiedust
import pkg_resources
import json
from pixiedust.display.app import pixieapp
class Customizer():
    def __init__(self):
        self.gateway = 'true'
    def customizeOptions(self, options):
        options.update( {'cell_id': 'dummy', 'showchrome':'false', 'gateway':self.gateway})
        options.update( {'nostore_pixiedust': 'true', 'runInDialog': 'false'})
pixieapp.pixieAppRunCustomizer = Customizer()
print(json.dumps( {"installed_modules": list(pkg_resources.AvailableDistributions())} ))
            """, lambda acc: json.dumps([msg['content']['text'] for msg in acc if msg['header']['msg_type'] == 'stream'], default=self._date_json_serializer))
    
        def done(fut):
            results = json.loads(fut.result())
            for result in results:
                try:
                    val = json.loads(result)
                    if isinstance(val, dict) and "installed_modules" in val:
                        self.installed_modules = val["installed_modules"]
                        break
                except:
                    pass
            app_log.debug("Installed modules %s", self.installed_modules)
        future.add_done_callback(done)
        raise gen.Return(future)

    def iopub_handler(self, msg):
        if msg['header']['msg_type'] == 'status':
            self.run_stats.update_status(msg['content']['execution_state'])

        if self.current_iopub_handler:
            self.current_iopub_handler(msg)

    @property
    def kernel_id(self):
        return self.kernel_manager.get_kernel_id(self.kernel_handle)

    def shutdown(self):
        self.kernel_manager.shutdown(self.kernel_handle)

    @gen.coroutine
    def install_dependencies(self, pixieapp_def, log_messages):
        restart = False
        for dep, info in [ (d,i) for d,i in iteritems(pixieapp_def.deps) if not any(a for a in [d,d.replace("-","_"),d.replace("_","-")] if a in self.installed_modules)]:
            log_messages.append("Installing module: {} from {}".format(dep, info))
            pip_dep = dep
            if info.get("install", None) is not None:
                pip_dep = info.get("install")
            yield self.execute_code("!pip install {}".format(pip_dep))
            restart = True
        raise gen.Return(restart)

    @gen.coroutine
    def on_publish(self, pixieapp_def, log_messages):
        future = Future()
        restart = yield self.install_dependencies(pixieapp_def, log_messages)
        if restart or self.get_app_stats(pixieapp_def) is not None:
            log_messages.append("Restarting kernel {}...".format(self.kernel_id))
            yield gen.maybe_future(self.restart())
            log_messages.append("Kernel successfully restarted...")
        future.set_result("OK")
        raise gen.Return(future)

    @gen.coroutine
    def restart(self):
        with (yield self.lock.acquire()):
            yield gen.maybe_future(self.shutdown())
            self.installed_modules = []
            yield gen.maybe_future(self.start(self.run_stats["kernel_name"]))

    def _date_json_serializer(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat().replace('+00:00', 'Z')
        raise TypeError("{} is not JSON serializable".format(obj))

    def _result_extractor(self, result_accumulator):
        return json.dumps(result_accumulator, default=self._date_json_serializer)

    def execute_code(self, code, result_extractor = None, done_callback = None):
        """
        Asynchronously execute the given code using the underlying managed kernel client
        Note: this method is not synchronized, it is the responsibility of the caller to synchronize using the lock member variable
        e.g.
            with (yield managed_client.lock.acquire()):
                yield managed_client.execute_code( code )

        Parameters
        ----------
        code : String
            Python code to be executed

        result_extractor : function [Optional]
            Called when the code has finished executing to extract the results into the returned Future

        Returns
        -------
        Future
        
        """
        app_log.debug("executing code: {}".format(code))
        if result_extractor is None:
            result_extractor = self._result_extractor
        code = PixieGatewayApp.instance().prepend_execute_code + "\n" + code
        app_log.debug("Executing Code: %s", code)
        future = Future()
        parent_header = self.kernel_manager.execute(self.kernel_handle, code)
        result_accumulator = []
        def on_reply(msg):
            if 'msg_id' in msg['parent_header'] and msg['parent_header']['msg_id'] == parent_header:
                if not future.done():
                    if "channel" not in msg:
                        msg["channel"] = "iopub"
                    result_accumulator.append(msg)
                    # Complete the future on idle status
                    if msg['header']['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                        future.set_result(result_extractor(result_accumulator))
                    elif msg['header']['msg_type'] == 'error':
                        error_name = msg['content']['ename']
                        error_value = msg['content']['evalue']
                        trace = sanitize_traceback(msg['content']['traceback'])
                        future.set_exception(
                            Exception(
                                'Code execution Error {}: {} \nTraceback: {}\nRunning code: {}'.format(
                                    error_name, error_value, trace, code
                                )
                            )
                        )
            else:
                app_log.warning("Got an orphan message %s", msg['parent_header'])

        self.current_iopub_handler = on_reply

        if done_callback is not None:
            future.add_done_callback(done_callback)
        return future

class ManagedClientAppMetrics(dict):
    def __init__(self, *args):
        super(ManagedClientAppMetrics, self).__init__(args)

    def external_repr(self):
        return [
            {
                "appName":key,
                "status":"error" if value.get("warmup_exception") is not None else "running"
            } for key, value in iteritems(self)
        ]

class ManagedClientRunMetrics(dict):
    def __init__(self, *args):
        super(ManagedClientRunMetrics, self).__init__(args)

    @property
    def kernel_spec(self):
        return self["kernel_spec"] if "kernel_spec" in self else None

    def start(self, kernel_name, kernel_spec):
        self["status"] = "idle"
        self["kernel_name"] = kernel_name
        self["kernel_spec"] = kernel_spec
        self.time_checkpoint = time()
        self.time_idle = 0
        self.time_busy = 0

    def update_status(self, status = None):
        current_status = self.get("status", "idle")
        delta = time() - self.time_checkpoint
        self.time_checkpoint = time()
        if current_status == "idle":
            self.time_idle += delta
        else:
            self.time_busy += delta
        if status is not None:
            self["status"] = status

    def external_repr(self):
        self.update_status()
        ret_value = dict(self)
        ret_value["busy_ratio"] = (self.time_busy/(self.time_busy+self.time_idle))*100
        return ret_value

class ManagedClientPool(SingletonConfigurable):
    remote_gateway_config = Dict(config=True, help="Remote Gateway configuration in JSON format")

    @default('remote_gateway_config')
    def remote_gateway_config_default(self):
        return {}

    """
    Orchestrates a Pool of ManagedClients, load-balancing based on user load
    """
    def __init__(self, kernel_manager, **kwargs):
        kwargs['parent'] = PixieGatewayApp.instance()
        super(ManagedClientPool, self).__init__(**kwargs)
        if self.remote_gateway_config is None or len(self.remote_gateway_config) == 0:
            self.kernel_manager = LocalKernelManager(kernel_manager)
        else:
            self.kernel_manager = RemoteKernelManager(self.remote_gateway_config)
        self.managed_clients = []
        #start a client
        #self.get()

    def shutdown(self):
        for managed_client in self.managed_clients:
            managed_client.shutdown()

    def on_publish(self, pixieapp_def, log_messages):
        #find all the affect clients
        try:
            log_messages.append("Validating Kernels for publishing...")
            return [managed_client.on_publish(pixieapp_def, log_messages) for managed_client in self.managed_clients]
        finally:
            log_messages.append("Done Validating Kernels...")

    def get(self, pixieapp_def=None):
        kernel_name = None if pixieapp_def is None else pixieapp_def.pref_kernel
        if kernel_name is not None:
            kernel_name = None if kernel_name.strip() == "" else kernel_name.strip()
        if (pixieapp_def is None or kernel_name is None) and len(self.managed_clients)>0:
            return self.managed_clients[0]
        #do we already have a ManagedClient for the pref_kernel
        clients = list(filter(lambda mc: mc.run_stats["kernel_name"] == kernel_name, self.managed_clients))
        if len(clients) > 0:
            return clients[0]
        print("Creating a new Managed client for kernel: {}".format(kernel_name))
        # client = self.kernel_manager.start_kernel(kernel_name=kernel_name)
        client = ManagedClient( self.kernel_manager, kernel_name)
        self.managed_clients.append(client)
        return client

    def get_by_kernel_id(self, kernel_id):
        clients = list(filter(lambda mc: mc.kernel_id == kernel_id, self.managed_clients))
        return None if len(clients) == 0 else clients[0]

    @gen.coroutine
    def list_kernel_specs(self):
        payload = yield gen.maybe_future(self.kernel_manager.list_kernel_specs())
        raise gen.Return(payload)

    def get_stats(self, kernel_id=None):
        return {mc.kernel_id:mc.get_stats() for mc in self.managed_clients
                if kernel_id is None or mc.kernel_id == kernel_id}
