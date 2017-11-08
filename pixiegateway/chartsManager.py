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
from abc import ABCMeta, abstractmethod
from six import with_metaclass
from pixiedust.utils.storage import Storage

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

class SQLLiteChartStorage(ChartStorage, Storage):
    "Chart storage class for SQLLite PixieDust DB"
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
            payload['rendererId']
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

chart_storage = SQLLiteChartStorage()
