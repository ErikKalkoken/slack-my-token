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
from app import Authorization, Scopes

# database connection
DATABASE_URL = os.environ['DATABASE_URL']

class TestAuthorization(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.connection = psycopg2.connect(DATABASE_URL)


    @classmethod
    def tearDownClass(cls):
        # remove test objects from DB
        TestAuthorization.remove_test_data()
        
        # close DB connection
        cls.connection.close()


    @classmethod
    def remove_test_data(cls):
        with cls.connection.cursor() as cursor:
            sql_query = """DELETE FROM mytoken_auths 
                WHERE team_id = 'TEST01'
                OR team_id = 'TEST01'
                """
            cursor.execute(sql_query)
            cls.connection.commit()

    def test_create_minimal(self):        
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1",
            "user1",
            Scopes("scope1"), 
            "token1"
        )
    

    def test_getters(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1",
            "user1",
            Scopes("scope1"), 
            "token1",         
            dt
        )
        self.assertEqual(x.team_id, "TEST01")
        self.assertEqual(x.user_id, "U101")
        self.assertEqual(x.team_name, "team1")        
        self.assertEqual(x.scopes, Scopes("scope1"))
        self.assertEqual(x.token, "token1")        
        self.assertEqual(x.last_update, dt)


    def test_store_1(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1",
            "user1", 
            Scopes("scope1"), 
            "token1",          
            dt
        )
        
        x.store(self.connection)
        # store again to verify overwriting existing works
        x.store(self.connection)
        
        y = Authorization(
            "TEST01", 
            "U102", 
            "team2",
            "user2", 
            Scopes("scope2"), 
            "token2",             
            dt
        )        
        y.store(self.connection)


    def test_store_2(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "TEST01", 
            "U102", 
            "team1",
            "user2", 
            Scopes("scope1"), 
            "token1"
        )
        
        x.store(self.connection)

    def test_fetch_normal(self):        
        """store and then fetch same record. check if its identical"""
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1",
            "user2", 
            Scopes("scope1"), 
            "token1"
        )        
        x.store(self.connection)
        
        y = Authorization.fetchFromDb(self.connection, "TEST01", "U101")
        self.assertEqual(x.team_id, y.team_id)
        self.assertEqual(x.user_id, y.user_id)
        self.assertEqual(x.team_name, y.team_name)        
        self.assertEqual(x.scopes, y.scopes)
        self.assertEqual(x.token, y.token)        
        self.assertEqual(x.last_update, y.last_update)
    

    def test_fetch_unknown(self):
        y = Authorization.fetchFromDb(
            self.connection, 
            "does_not_exist", 
            "does_not_exist"
        )
        self.assertIsNone(y)

    def test_delete(self):
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1", 
            "user1",
            Scopes("scope1"), 
            "token1",
            pytz.utc.localize(datetime.utcnow())
        )        
        x.store(self.connection)

        y = Authorization.fetchFromDb(self.connection, "TEST01", "U101")
        self.assertEqual(x.team_id, y.team_id)
        self.assertEqual(x.user_id, y.user_id)
        self.assertEqual(x.team_name, y.team_name)        
        self.assertEqual(x.scopes, y.scopes)
        self.assertEqual(x.token, y.token)

        x.delete(self.connection)
        y = Authorization.fetchFromDb(self.connection, "TEST01", "U101")
        self.assertIsNone(y)

    def test_count(self):
        TestAuthorization.remove_test_data()        
        
        # first should be zero
        self.assertEqual(Authorization.get_count_for_team(
            self.connection,
            "TEST01"
            ),
            0
        )
        # now lets create and store two objects
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1",
            "user1", 
            Scopes("scope1"), 
            "token1"
        )
        
        x.store(self.connection)
                
        y = Authorization(
            "TEST01", 
            "U102", 
            "team2", 
            "user1",
            Scopes("scope2"), 
            "token2"
        )        
        y.store(self.connection)

        # should be 2
        self.assertEqual(Authorization.get_count_for_team(
            self.connection,
            "TEST01"
            ),
            2
        )

    def test_is_owner_true(self):
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1", 
            "user1",
            Scopes(["scope1", Scopes.SCOPE_COMMANDS]), 
            "token1"
        )        
        self.assertTrue(x.is_owner())

    def test_is_owner_false(self):
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1", 
            "user1",
            Scopes(["scope1"]), 
            "token1"
        )        
        self.assertFalse(x.is_owner())

    def test_json_serialization(self):
        dt = pytz.utc.localize(datetime.utcnow())
        x = Authorization(
            "TEST01", 
            "U101", 
            "team1", 
            "user1",
            Scopes(["scope1"]), 
            "token1",
            dt
        )
        json_str = x.json_dumps()
        y = Authorization.json_loads(json_str)
        self.assertEqual(x, y)

if __name__ == '__main__':
    unittest.main()