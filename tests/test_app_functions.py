# unittest for functions in app.py

import unittest
import os
import sys
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from app import Scopes


class TestAppFunctions(unittest.TestCase):
    
    def test_create1(self):                
        pass


if __name__ == '__main__':
    unittest.main()