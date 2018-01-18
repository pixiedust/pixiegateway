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

class CodeExecutionError(Exception):
    """
    Exception raised when python code fails to execute
    """
    def __init__(self, error_name, error_value, trace, code):
        self.error_name = error_name
        self.error_value = error_value
        self.trace = trace
        self.code = code
        message = 'Code execution Error {}: {} \nTraceback: {}\nRunning code: {}'.format(
            self.error_name, self.error_value, self.trace, self.code
        )
        super(CodeExecutionError, self).__init__(message)

class AppAccessError(Exception):
    """
    Exception thrown when access to a PixieApp has not been authorized
    """
    def __init__(self):
        super(AppAccessError, self).__init__("Unauthorized Access")
