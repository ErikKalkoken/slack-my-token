# unittest for Token class
# requires a postgres DB with an existing table

import unittest
import psycopg2
import os
import sys
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from app import Token

# database connection
DATABASE_URL = os.environ['DATABASE_URL']

class TestToken(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls._connection = psycopg2.connect(DATABASE_URL)

    @classmethod
    def tearDownClass(cls):
        # remove test objects from DB
        cursor = cls._connection.cursor()               
        sql_query = """DELETE FROM mytoken_tokens 
            WHERE team_id IN ('T0TEST01', 'T0TEST02')"""        
        cursor.execute(sql_query)
        cls._connection.commit()
        cursor.close()
        # close DB connection
        cls._connection.close()

    def test_getters(self):
        x = Token("T0TEST01", "U101", "team1", "scope1", "token1")
        self.assertIsInstance(x, Token)
        self.assertEqual(x.team_id, "T0TEST01")
        self.assertEqual(x.user_id, "U101")
        self.assertEqual(x.team_name, "team1")        
        self.assertEqual(x.scopes, "scope1")
        self.assertEqual(x.token, "token1")
        

    def test_store(self):
        x = Token("T0TEST01", "U101", "team1", "scope1", "token1")
        self.assertIsInstance(x, Token)
        
        x.store(self._connection)
        # store again to verify overwriting existing works
        x.store(self._connection)

        y = Token("T0TEST02", "U102", "team2", "scope2", "token2")
        self.assertIsInstance(y, Token)
        y.store(self._connection)


    def test_fetch_normal(self):
        x = Token("T0TEST01", "U101", "team1", "scope1", "token1")
        self.assertIsInstance(x, Token)        
        x.store(self._connection)
        
        y = Token.fetchFromDb(self._connection, "T0TEST01", "U101")
        self.assertEqual(x.team_id, y.team_id)
        self.assertEqual(x.user_id, y.user_id)
        self.assertEqual(x.team_name, y.team_name)        
        self.assertEqual(x.scopes, y.scopes)
        self.assertEqual(x.token, y.token)
    

    def test_fetch_unknown(self):
        y = Token.fetchFromDb(
            self._connection, 
            "does_not_exist", 
            "does_not_exist"
        )
        self.assertIsNone(y)

if __name__ == '__main__':
    unittest.main()