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

from pixiegateway.notebookMgr import ast_parse, get_symbol_table, RewriteGlobals
import astunparse
from nose.tools import assert_equals
import six
import pkg_resources

ipython_version = pkg_resources.get_distribution("ipython").parsed_version._version.release

def either(cond, stat1, stat2):
    return stat1 if cond is True else stat2

classdef = ''
uni = 'u'
if six.PY3:
    classdef = '()'
    uni = ''

code_map = [
{
    "src": """
var1 = foo()
for v in someList:
    var1 = bar(var1)
for v in someList:
    for k in deeperList:
        var1 = bar(var1)
""",
    "target": """
ns_var1 = foo()
for v in someList:
    ns_var1 = bar(ns_var1)
for v in someList:
    for k in deeperList:
        ns_var1 = bar(ns_var1)
"""
},{
    "src": """
!pip install something
%autoreload 2
var1 = foo()
var2 = "some string with percent % in the middle"
""",
    "target": either(ipython_version > (6, 2, 0), """
get_ipython().system(""" + uni + """'pip install something')
get_ipython().run_line_magic(""" + uni + """'autoreload', '2')""", """
get_ipython().system(""" + uni + """'pip install something')
get_ipython().magic(""" + uni + """'autoreload 2')""") + """
ns_var1 = foo()
ns_var2 = 'some string with percent % in the middle'
"""
}, {
    "src":"""
class Test""" + classdef + """:
    def foo(self):
        pass
a = Test()
a.foo()
""",
    "target":"""
class ns_Test""" + classdef + """:
    def foo(self):
        pass
ns_a = ns_Test()
ns_a.foo()
"""
},{
    "src":"""
var1 = "var1"
var2 = "var2"
from pixiedust.display.app import *
@PixieApp
class TestApp""" + classdef + """:
    def setup(self):
        self.contents = [var1, var2]
TestApp().run()
    """,
    "target":"""
ns_var1 = 'var1'
ns_var2 = 'var2'
from pixiedust.display.app import *
@PixieApp
class TestApp""" + classdef + """:
    def setup(self):
        self.contents = [ns_var1, ns_var2]
        self.__pd_gateway_namespace__ = 'ns_'
TestApp().run()
    """
},{
    "src":"""
from pixiedust.display.app import *
@PixieApp
class TestAppWithoutSetup""" + classdef + """:
    pass
TestApp().run()
    """,
    "target":"""
from pixiedust.display.app import *
@PixieApp
class TestAppWithoutSetup""" + classdef + """:
    pass
    def setup(self):
        self.__pd_gateway_namespace__ = 'ns_'
TestApp().run()
    """
}
]

def compare_multiline(src, target):
    assert_equals(
        "\n".join([l for l in src.split('\n') if l.strip()!='']), 
        "\n".join([l for l in target if l.strip()!=''])
    )

def test_rewrite():
    for code in code_map:
        symbols = get_symbol_table(ast_parse( code['src'].strip() ) )
        rewrite_code = astunparse.unparse( RewriteGlobals(symbols, "ns_").visit(ast_parse(code['src'])) )
        compare_multiline(code["target"].strip(), [l for l in rewrite_code.split('\n') if l.strip() != ""])
