# unittest for Token class
# requires a postgres DB with an existing table

import unittest
import os
import sys
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from app import Scopes


class TestScopes(unittest.TestCase):
    
    def test_create1(self):                
        x = Scopes()
        self.assertIsInstance(x, Scopes)
        self.assertEqual(x.scopes, set())

    def test_create2(self):                        
        x = Scopes(dict())
        self.assertIsInstance(x, Scopes)
        self.assertEqual(x.scopes, set())

    def test_create3(self):                        
        s = ["first:,xxx", "second:yyy", "third:zzz"]        
        with self.assertRaises(ValueError):
            x = Scopes(s)

    def test_create4(self):                        
        x = Scopes.create_from_string("first:xxx,second:yyy,third:zzz")
        self.assertIsInstance(x, Scopes)
        self.assertCountEqual(x.scopes, ["first:xxx", "second:yyy", "third:zzz"])

    def test_create5(self):                        
        x = Scopes.create_from_file("scopes")
        self.assertIsInstance(x, Scopes)
        self.assertTrue("channels:history" in x)
        
    def test_getters(self):        
        s = ["first:xxx", "second:yyy", "third:zzz"]
        x = Scopes(s)
        self.assertIsInstance(x, Scopes)
        self.assertCountEqual(x.scopes, s)
        self.assertEqual(x.get_string(), "first:xxx,second:yyy,third:zzz")
    
    def test_contains(self):  
        s = ["first:xxx", "second:yyy", "third:zzz"]
        self.assertTrue("second:yyy" in s)
        self.assertFalse("not-in-there" in s)

    """
        def test_iter(self):
        s = ["first:xxx", "second:yyy", "third:zzz"]
        x = Scopes(s)
        self.assertIsInstance(x, Scopes)
        for y in x:
            self.assertIsInstance(y, str)
    """

    def test_add(self):          
        s1 = ["a", "b", "c"]
        s2 = ["d", "e", "a"]
        x1 = Scopes(s1)
        self.assertIsInstance(x1, Scopes)
        x2 = Scopes(s2)
        self.assertIsInstance(x2, Scopes)
        x3 = x1 + x2
        self.assertIsInstance(x3, Scopes)
        self.assertCountEqual(x3.scopes, ["a", "b", "c", "d", "e"])

    
    def test_add_scope(self):                        
        s = ["a", "b", "c"]
        x = Scopes(s)   
        
        # add good scope
        x.add("d")
        self.assertCountEqual(x.scopes, ["a", "b", "c", "d"])
        
        # add bad scope
        with self.assertRaises(ValueError):
            x.add("b,")
    
    def test_diff(self):
        s1 = ["a", "b", "c", "d"]
        s2 = ["a", "c"]
        x1 = Scopes(s1)
        x2 = Scopes(s2)
        x3 = x1.diff(x2)
        self.assertCountEqual(x3.scopes, ["b", "d"])

    def test_get_sorted(self):                        
        s = ["a", "d", "c", "b"]
        x = Scopes(s)
        self.assertIsInstance(x, Scopes)
        self.assertEqual(x.get_sorted(), ["a", "b", "c", "d"])

if __name__ == '__main__':
    unittest.main()