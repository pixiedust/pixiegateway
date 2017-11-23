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
import tempfile
import sys
import base64
import os
from tornado import template, gen
from traitlets.config.configurable import SingletonConfigurable
from selenium import webdriver
from selenium.webdriver.chrome import service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import pixiegateway
from .pixieGatewayApp import PixieGatewayApp
from .chartsManager import SingletonChartStorage

class Thumbnail(SingletonConfigurable):

    def __init__(self, **kwargs):
        kwargs['parent'] = PixieGatewayApp.instance()
        self.exception = None
        self.chart_template = None
        self.service = None
        self.initialize()
        super(Thumbnail, self).__init__(**kwargs)

    def initialize(self):
        print("Initializing ChromeDriver Service")
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        chromedriver_path = None
        if sys.platform == "linux" or sys.platform == "linux2":
            from pixiegateway.webdriver import linux
            chromedriver_path = os.path.join(os.path.dirname(linux.__file__), "chromedriver")
        elif sys.platform == "darwin":
            from pixiegateway.webdriver import mac
            chromedriver_path = os.path.join(os.path.dirname(mac.__file__), "chromedriver")
        if chromedriver_path is None:
            raise Exception("Unable to generate chart thumbnail. Invalid platform: {}".format(sys.platform))

        try:
            self.service = service.Service(chromedriver_path)
            self.service.start()
            self.chart_template = template.Loader(
                os.path.join(os.path.dirname(pixiegateway.__file__), "template")
            ).load("genThumbnail.html")

            print("ChromeDriver Service successfully initialized")
        except Exception as exc:
            self.exception = exc

    @gen.coroutine
    def get_screenshot_as_png(self, chart_model):
        if self.exception is not None:
            raise self.exception  # pylint: disable=E0702

        driver = webdriver.Remote( self.service.service_url, self.chrome_options.to_capabilities())
        try:
            script = self.chart_template.generate(chart_model=chart_model)
            with tempfile.NamedTemporaryFile(delete=True) as f:
                f.write(script)
                driver.get("file://" + f.name)
            try:
                #wait some time for the chart to be fully loaded, import especially for mapbox
                WebDriverWait(driver, 5).until(lambda x: False)
            except:
                pass
            size = driver.execute_script("return document.body.getBoundingClientRect()")
            driver.set_window_size(size['width'],size['height'] + 20)
            ret_value = yield self.save_thumbnail_to_model(driver, chart_model)
            raise gen.Return(ret_value)
        finally:
            driver.quit()

    @gen.coroutine
    def save_thumbnail_to_model(self, driver, chart_model):
        b64_thumbnail = driver.get_screenshot_as_base64()
        chart_model["THUMBNAIL"] = b64_thumbnail
        yield gen.maybe_future(SingletonChartStorage.instance().update_chart(chart_model))
        raise gen.Return(base64.b64decode(b64_thumbnail))
