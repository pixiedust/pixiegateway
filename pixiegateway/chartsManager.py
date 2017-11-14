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
import uuid
import base64
import os
from abc import ABCMeta, abstractmethod
import requests
import time
import datetime
from six import with_metaclass, iteritems
from pixiedust.utils.storage import Storage
from traitlets.config.configurable import SingletonConfigurable
from traitlets import Unicode, default, Integer
from tornado.util import import_object
from tornado.log import app_log
from .pixieGatewayApp import PixieGatewayApp

class ChartStorage(with_metaclass(ABCMeta)):
    """
    Interface to the Chart Storage
    """
    @abstractmethod
    def store_chart(self, payload):
        "returns chart model"
        pass
    @abstractmethod
    def get_chart(self, chart_id):
        "returns chart model"
        pass
    @abstractmethod
    def delete_chart(self, chart_id):
        pass
    @abstractmethod
    def list_charts(self):
        pass
    @abstractmethod
    def get_charts(self, page_num=0, page_size=10):
        pass

class SQLLiteChartStorage(ChartStorage, Storage):
    "Chart storage class for SQLLite PixieDust DB (default)"
    CHARTS_TBL_NAME="CHARTS"
    def __init__(self):
        self._initTable( SQLLiteChartStorage.CHARTS_TBL_NAME,
        '''
            CHARTID        TEXT  NOT NULL PRIMARY KEY,
            AUTHOR         TEXT  NOT NULL,
            DATE           DATETIME  NOT NULL,
            DESCRIPTION    TEXT,
            CONTENT        BLOB,
            RENDERERID     TEXT
        ''')

    def store_chart(self, payload):
        chart_id = str(uuid.uuid4())
        self.insert("""
            INSERT INTO {0} (CHARTID,AUTHOR,DATE,DESCRIPTION,CONTENT,RENDERERID)
            VALUES (?,?,CURRENT_TIMESTAMP,?,?,?)
        """.format(SQLLiteChartStorage.CHARTS_TBL_NAME), (
            chart_id,
            "username",
            payload.get("description", ""),
            payload['chart'],
            payload.get("rendererId", "")
        ))
        #return the chart_model for this newly stored chart
        return self.get_chart(chart_id)

    def get_chart(self, chart_id):
        return self.fetchOne(
            """SELECT * from {0} WHERE CHARTID='{1}'""".format(
                SQLLiteChartStorage.CHARTS_TBL_NAME, chart_id
            )
        )

    def delete_chart(self, chart_id):
        rows_deleted = self.delete(
            """DELETE FROM {0} WHERE CHARTID='{1}'""".format(
                SQLLiteChartStorage.CHARTS_TBL_NAME, chart_id
            )
        )
        print("Row Deleted: {}".format(rows_deleted))
        return rows_deleted

    def list_charts(self):
        def walker(row):
            print(row['CHARTID'])
        self.execute("""
                SELECT * FROM {0}
            """.format(SQLLiteChartStorage.CHARTS_TBL_NAME),
            walker
        )

    def get_charts(self, page_num=0, page_size=10):
        limit = max(1, page_size)
        offset = limit * max(0, page_num)
        charts_list = self.fetchMany("""
                SELECT CHARTID,AUTHOR,DATE,DESCRIPTION,RENDERERID FROM {0} LIMIT {1} OFFSET {2}
            """.format(SQLLiteChartStorage.CHARTS_TBL_NAME, str(limit), str(offset))
        )

        total_count = self.fetchOne('SELECT COUNT(CHARTID) as count from {0}'.format(SQLLiteChartStorage.CHARTS_TBL_NAME))['count']

        return {"page_num": page_num, "page_size": page_size, "total_count": total_count, "charts_list": charts_list}

class CloudantChartStorage(ChartStorage):
    CHART_DB_NAME = "pixiegateway_chart"
    class CloudantConfig(SingletonConfigurable):
        def __init__(self, **kwargs):
            kwargs['parent'] = PixieGatewayApp.instance()
            super(CloudantChartStorage.CloudantConfig, self).__init__(**kwargs)

        host = Unicode(None, config=True, help="Cloudant Chart Storage hostname")
        protocol = Unicode("https", config=True, help="Cloudant Chart Storage protocol")
        port = Integer(443, config=True, help="Cloudant Chart Storage port")
        username = Unicode(None, config=True, help="Cloudant Chart Storage username")
        password = Unicode(None, config=True, help="Cloudant Chart Storage password")

        @default('host')
        def host_default(self):
            return os.getenv("PG_CLOUDANT_HOST", "")

        @default('protocol')
        def protocol_default(self):
            return os.getenv("PG_CLOUDANT_PROTOCOL", "https")

        @default('port')
        def port_default(self):
            return int(os.getenv("PG_CLOUDANT_PORT", 443))

        @default('username')
        def username_default(self):
            return os.getenv("PG_CLOUDANT_USERNAME", "")

        @default('password')
        def password_default(self):
            return os.getenv("PG_CLOUDANT_PASSWORD", "")

    def __init__(self):
        self.host = CloudantChartStorage.CloudantConfig.instance().host
        self.protocol = CloudantChartStorage.CloudantConfig.instance().protocol
        self.port = CloudantChartStorage.CloudantConfig.instance().port
        self.username = CloudantChartStorage.CloudantConfig.instance().username
        self.password = CloudantChartStorage.CloudantConfig.instance().password

        #make sure the database exists, if not create it
        response = requests.head(self.build_url(), headers=self.get_headers())
        if response.status_code == 404:
            response = requests.put( self.build_url(), headers=self.get_headers())

        if response.status_code != 200 and response.status_code != 201:
            app_log.error("Unexcepted error while connecting to cloudant: %s", response.text)
        else:
            app_log.info("Succesfully connected to Cloudant db: %s-%s", self.host, CloudantChartStorage.CHART_DB_NAME)

    def get_headers(self):
        return {
            'Authorization': 'Basic {}'.format(base64.b64encode('{}:{}'.format(self.username, self.password).encode()).decode()),
            'Accept': 'application/json'
        }

    def build_url(self, path="", **kwargs):
        url = "{}://{}:{}/{}/{}".format(self.protocol, self.host, self.port, CloudantChartStorage.CHART_DB_NAME, path)
        return url if len(kwargs)==0 else "{}?{}".format(url,"&".join(["{}={}".format(k,v) for k,v in iteritems(kwargs)]))

    def store_chart(self, payload):

        chart_id = str(uuid.uuid4())
        payload = {
            '_id': chart_id,
            'CHARTID': chart_id,
            'DATE': time.time(),
            'AUTHOR': "username",
            'DESCRIPTION': payload.get('description', ''),
            'CONTENT': payload['chart'],
            'RENDERERID': payload.get("rendererId", "")
        }

        response = requests.post(self.build_url(), json = payload, headers=self.get_headers())
        if not response.ok:
            raise Exception(response.text)
        #return the chart_model for this newly stored chart
        return payload

    def format_chart_model(self, chart_model):
        chart_model['DATE'] = datetime.datetime.fromtimestamp(chart_model['DATE']).strftime("%Y-%m-%d %H:%M:%S")
        return chart_model

    def get_chart(self, chart_id):
        return self.format_chart_model(requests.get(self.build_url(chart_id), headers=self.get_headers()).json())

    def delete_chart(self, chart_id):
        response = requests.delete(self.build_url(chart_id), headers = self.get_headers())
        if not response.ok:
            raise Exception(response.text)

    def list_charts(self):
        return self.get_charts()

    def get_charts(self, page_num=0, page_size=10):
        limit = max(1, page_size)
        offset = limit * max(0, page_num)
        url = self.build_url("_all_docs", limit=limit, skip=offset, include_docs="true")
        payload = requests.get(url, headers=self.get_headers()).json()
        return {
            "page_num": page_num, 
            "page_size": page_size, 
            "total_count": payload['total_rows'], 
            "charts_list": [self.format_chart_model(row['doc']) for row in payload['rows']]
        }

class SingletonChartStorage(SingletonConfigurable):
    """
    Singleton use to access concrete instance of chart storage
    """

    chart_storage_class = Unicode(None, config=True, help="Chart storage class")

    @default('chart_storage_class')
    def chart_storage_class_default(self):
        return os.getenv('PG_CHART_STORAGE', 'pixiegateway.chartsManager.SQLLiteChartStorage')

    def __init__(self, **kwargs):
        kwargs['parent'] = PixieGatewayApp.instance()
        super(SingletonChartStorage, self).__init__(**kwargs)

        self.chart_storage = import_object(self.chart_storage_class)()

    def __getattr__(self, name):
        if name == "chart_storage":
            raise AttributeError("{0} attribute not found".format(name))
        if self.chart_storage is not None and hasattr(self.chart_storage, name):
            return getattr(self.chart_storage, name)
        raise AttributeError("{0} attribute not found".format(name))
