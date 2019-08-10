# utility script to create the table needed for the Slack app
# IMPORTANT: will drop an existing table and delete all data

import psycopg2
import os

# database connection
DATABASE_URL = os.environ['DATABASE_URL']

try:
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    sql = """
        DROP TABLE IF EXISTS public.mytoken_auths;
        CREATE TABLE public.mytoken_auths
        (
            team_id character varying(64) COLLATE pg_catalog."default" NOT NULL,
            user_id character varying(64) COLLATE pg_catalog."default" NOT NULL,
            team_name character varying(255) COLLATE pg_catalog."default" NOT NULL,
            user_name varchar(255) NOT NULL,
            scopes text COLLATE pg_catalog."default" NOT NULL,
            token character varying(255) COLLATE pg_catalog."default" NOT NULL,            
            last_update timestamp with time zone NOT NULL,
            CONSTRAINT mytoken_tokens_pkey PRIMARY KEY (team_id, user_id)
        )
        WITH (
            OIDS = FALSE
        )
        TABLESPACE pg_default
    """   
    cursor.execute(sql)
    connection.commit()
    print("New table created")
except (Exception, psycopg2.Error) as error :    
    print("ERROR: Failed to create new table: ", error)
finally:
    #closing database connection.
    if(connection):
        cursor.close()
        connection.close()
