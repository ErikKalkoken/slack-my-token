# unittest for Authorization class
# requires a postgres DB with an existing table

import unittest
import psycopg2
import os
import sys
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from datetime import datetime
import pytz
from app import Authorization

# database connection
DATABASE_URL = os.environ['DATABASE_URL']

class TestAuthorization(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls._connection = psycopg2.connect(DATABASE_URL)

    @classmethod
    def tearDownClass(cls):
        # remove test objects from DB
        
        # close DB connection
        cls._connection.close()


    def test_getters(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "T0TEST01", 
            "U101", 
            "team1", 
            "scope1", 
            "token1", 
            True, 
            dt
        )
        self.assertEqual(x.team_id, "T0TEST01")
        self.assertEqual(x.user_id, "U101")
        self.assertEqual(x.team_name, "team1")        
        self.assertEqual(x.scopes, "scope1")
        self.assertEqual(x.token, "token1")
        self.assertEqual(x.is_owner, True)
        self.assertEqual(x.last_update, dt)


    def test_store_1(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "T0TEST01", 
            "U101", 
            "team1", 
            "scope1", 
            "token1", 
            True, 
            dt
        )
        
        x.store(self._connection)
        # store again to verify overwriting existing works
        x.store(self._connection)
        
        y = Authorization(
            "T0TEST02", 
            "U102", 
            "team2", 
            "scope2", 
            "token2", 
            False, 
            dt
        )
        self.assertIsInstance(y, Authorization)
        y.store(self._connection)


    def test_store_2(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "T0TEST01", 
            "U102", 
            "team1", 
            "scope1", 
            "token1", 
            True
        )
        
        x.store(self._connection)

    def test_fetch_normal(self):        
        """store and then fetch same record. check if its identical"""
        x = Authorization(
            "T0TEST01", 
            "U101", 
            "team1", 
            "scope1", 
            "token1", 
            True
        )
        self.assertIsInstance(x, Authorization)        
        x.store(self._connection)
        
        y = Authorization.fetchFromDb(self._connection, "T0TEST01", "U101")
        self.assertEqual(x.team_id, y.team_id)
        self.assertEqual(x.user_id, y.user_id)
        self.assertEqual(x.team_name, y.team_name)        
        self.assertEqual(x.scopes, y.scopes)
        self.assertEqual(x.token, y.token)
        self.assertEqual(x.is_owner, y.is_owner)
        self.assertEqual(x.last_update, y.last_update)
    

    def test_fetch_unknown(self):
        y = Authorization.fetchFromDb(
            self._connection, 
            "does_not_exist", 
            "does_not_exist"
        )
        self.assertIsNone(y)

    def test_delete(self):
        x = Authorization(
            "T0TEST01", 
            "U101", 
            "team1", 
            "scope1", 
            "token1", 
            True, 
            pytz.utc.localize(datetime.utcnow())
        )        
        x.store(self._connection)

        y = Authorization.fetchFromDb(self._connection, "T0TEST01", "U101")
        self.assertEqual(x.team_id, y.team_id)
        self.assertEqual(x.user_id, y.user_id)
        self.assertEqual(x.team_name, y.team_name)        
        self.assertEqual(x.scopes, y.scopes)
        self.assertEqual(x.token, y.token)

        x.delete(self._connection)
        y = Authorization.fetchFromDb(self._connection, "T0TEST01", "U101")
        self.assertIsNone(y)


if __name__ == '__main__':
    unittest.main()