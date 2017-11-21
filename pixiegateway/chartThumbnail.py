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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import pixiegateway
from .chartsManager import SingletonChartStorage

class Thumbnail(object):
    def __init__(self, chart_model):
        self.chart_model = chart_model

    @gen.coroutine
    def get_screenshot_as_png(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chromedriver_path = None
        if sys.platform == "linux" or sys.platform == "linux2":
            from pixiegateway.webdriver import linux
            chromedriver_path = os.path.join(os.path.dirname(linux.__file__), "chromedriver")
        elif sys.platform == "darwin":
            from pixiegateway.webdriver import mac
            chromedriver_path = os.path.join(os.path.dirname(mac.__file__), "chromedriver")
        if chromedriver_path is None:
            raise Exception("Unable to generate chart thumbnail. Invalid platform: {}".format(sys.platform))

        driver=webdriver.Chrome(
            chromedriver_path,
            chrome_options=chrome_options
        )
        try:
            template_path = os.path.join(os.path.dirname(pixiegateway.__file__), "template")
            print(template_path)
            script = template.Loader(template_path).load("genThumbnail.html").generate(
                chart_model=self.chart_model
            )
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
            ret_value = yield self.save_thumbnail_to_model(driver)
            raise gen.Return(ret_value)
        finally:
            print("Quitting driver")
            driver.quit()

    @gen.coroutine
    def save_thumbnail_to_model(self, driver):
        b64_thumbnail = driver.get_screenshot_as_base64()
        self.chart_model["THUMBNAIL"] = b64_thumbnail
        yield gen.maybe_future(SingletonChartStorage.instance().update_chart(self.chart_model))
        raise gen.Return(base64.b64decode(b64_thumbnail))