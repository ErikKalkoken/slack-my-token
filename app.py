# main module with the Slack app

import os
import slack
from flask import Flask, json, request, render_template, session, Response, abort
import psycopg2
import urllib
import secrets
import requests
import hmac
import hashlib
from datetime import datetime
import pytz
from slack_objects import Blocks, ActionsBlock, Button, Section, ConfirmationDialog, ResponseMessage

# environment variables
DATABASE_URL = os.environ['DATABASE_URL']
SLACK_CLIENT_ID = os.environ["SLACK_CLIENT_ID"]
SLACK_CLIENT_SECRET = os.environ["SLACK_CLIENT_SECRET"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
FLASK_SECRET_KEY = os.environ["FLASK_SECRET_KEY"]

# Slack Oauth config
REQUIRED_SCOPES = "commands"

# Slack action IDs
AID_BUTTON_NEW = "button_new"
AID_BUTTON_REMOVE = "button_remove"
AID_BUTTON_DUMMY = "button_dummy"

class Authorization:
    """A token for a Slack team and user
    
    Public properties:
        id: team ID
        name: team name
        token: Slack token
    """
    def __init__(
            self, 
            team_id: str, 
            user_id: str, 
            team_name: str, 
            scopes: str, 
            token: str,
            is_owner: bool,
            last_update: datetime = None
        ):
        # validation
        if not isinstance(is_owner, bool):
            raise TypeError("is_owner must be of type bool")
        if last_update is None:
            last_update = pytz.utc.localize(datetime.utcnow())          
        if not isinstance(last_update, datetime):
            raise TypeError(
                "last_update must be of type datetime, but is: " 
                    + str(type(last_update))
            )
        # init
        self._team_id = str(team_id)[:64]
        self._user_id = str(user_id)[:64]
        self._team_name = str(team_name)[:255]        
        self._scopes = str(scopes)
        self._token = str(token)[:255]
        self._is_owner  = is_owner                
        self._last_update  = last_update

    @property
    def team_id(self) -> str:
        return self._team_id

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def team_name(self) -> str:
        return self._team_name

    @property
    def scopes(self) -> str:
        return self._scopes

    @property
    def token(self) -> str:
        return self._token

    @property
    def is_owner(self) -> bool:
        return self._is_owner

    @property
    def last_update(self) -> datetime:
        return self._last_update

    def store(self, connection):
        """stores the current object to database. will overwrite existing.

        Args:
            connection: current postgres connection

        Exceptions:
            on any error

        """
        try:                
            with connection.cursor() as cursor:                
                sql_query = """INSERT INTO mytoken_auths 
                    (
                        team_id, 
                        user_id, 
                        team_name, 
                        scopes, 
                        token, 
                        is_owner, 
                        last_update
                    ) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s) 
                    ON CONFLICT (team_id, user_id)
                    DO UPDATE SET 
                        team_name=%s, 
                        scopes=%s, 
                        token=%s, 
                        is_owner=%s, 
                        last_update=%s
                """
                record = (
                    self._team_id, 
                    self._user_id, 
                    self._team_name,                 
                    self._scopes, 
                    self._token, 
                    self._is_owner,
                    self._last_update,
                    self._team_name,                 
                    self._scopes, 
                    self._token,
                    self._is_owner,
                    self._last_update
                )
                cursor.execute(sql_query, record)
                connection.commit()
        except (Exception, psycopg2.Error) as error:            
            print("WARN: Failed to insert record into table", error)
            raise error
                
            
    def delete(self, connection):
        """deletes the current object in DB

        Args:
            connection: current postgres connection

        Exceptions:
            on any error

        """
        try:                
            with connection.cursor() as cursor:
                sql_query = """DELETE FROM mytoken_auths 
                    WHERE team_id = %s
                    AND user_id = %s                        
                """
                record = (
                    self._team_id, 
                    self._user_id
                )
                cursor.execute(sql_query, record)
                connection.commit()
        except (Exception, psycopg2.Error) as error:            
            print("WARN: Failed to delete record from table", error)
            raise error

    @classmethod
    def fetchFromDb(cls, connection, team_id, user_id):
        """fetches an object from database by its team ID
         
         Args:            
            connection: current postgres connection
            id: team ID of object to be fetched

        Returns:
            the Authorization object when found or None if not found
        
        Exceptions:
            on any error
        """
        try:            
            with connection.cursor() as cursor:
                sql_query = """SELECT 
                        team_id, 
                        user_id, 
                        team_name, 
                        scopes, 
                        token,
                        is_owner,
                        last_update
                    FROM mytoken_auths 
                    WHERE team_id = %s
                    AND user_id = %s"""                
                cursor.execute(sql_query, (team_id, user_id))            
                record = cursor.fetchone()
                if (record == None):
                    print(
                        f"WARN: Could not find a token for team {team_id} "
                            + f"and user {user_id}"
                    )
                    obj = None
                else:                
                    obj = cls(
                        record[0], 
                        record[1], 
                        record[2], 
                        record[3], 
                        record[4], 
                        record[5], 
                        record[6]
                    )
            
        except (Exception, psycopg2.Error) as error :
            print("Error while fetching data from PostgreSQL", error)
            raise

        return obj


class Scopes:
    
    DELIMITER = ","

    def __init__(self, scopes=None):                                
        if scopes is None:
            scopes = set()
        else:
            scopes = set(scopes)
                
        if any(self.DELIMITER in s for s in scopes):
            raise ValueError(
                f"strings in scopes can not contain {self.DELIMITER}"
            )
        
        self._scopes = scopes                    
        
    @property
    def scopes(self):
        return self._scopes

    def __str__(self):
        return self.get_string()

    def __contains__(self, key):
        return key in self._scopes

    def get_string(self):
        scopes_list = list(self._scopes)
        scopes_list.sort()
        return self.DELIMITER.join(scopes_list)

    def add(self, scope):        
        if not isinstance(scope, str):
            raise TypeError("scope must be of type string")
        if self.DELIMITER in scope:
            raise ValueError(f"scope can not contain {self.DELIMITER}")

        self._scopes.add(scope)

    def __add__(self, s2):        
        s_sum = self._scopes.union(s2.scopes)
        return Scopes(s_sum)

    def diff(self, scopes_second):
        if not isinstance(scopes_second, Scopes):
            raise TypeError("scopes_second must be of type Scopes")
        scopes_diff = self._scopes.difference(scopes_second.scopes)
        return Scopes(scopes_diff)

    def get_sorted(self):
        scopes_list = list(self._scopes)
        scopes_list.sort()
        return scopes_list
    
    @classmethod
    def create_from_string(cls, scopes_str):
        scopes = scopes_str.split(cls.DELIMITER)
        return cls(scopes)

    @classmethod
    def create_from_file(cls, filename):    
        """reads a json file and returns its contents as new object"""     
        filename += '.json'
        if not os.path.isfile(filename):
            raise RuntimeError(f"file does not exist: {filename}")
            
        else:
            try:
                with open(filename, 'r', encoding="utf-8") as f:
                    arr = json.load(f)            
            except Exception as e:
                raise RuntimeError(
                     f"WARN: failed to read from {filename}: {e} "
                )
            scopes = set()
            for scope in arr:
                if scope["enabled"]:
                    scopes.add(scope["scope"])    
            
        return cls(scopes)


def request_is_valid(request_raw, signing_secret):
    pass

# flask app
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

@app.route("/", methods=["GET"])
def draw_select_scopes():
    """shows the page for selecting scopes"""
    if "scopes" in request.args:
        scopes_preselected = Scopes.create_from_string(request.args["scopes"])
    else:
        scopes_preselected = Scopes()
    #scopes_preselected.add("commands")
    session["scopes_preselected"] = scopes_preselected.get_string()

    scopes_all = Scopes.create_from_file("scopes")        
    scopes_remain = scopes_all.diff(scopes_preselected)
    return render_template(
        'select.html.j2', 
        scopes_preselected=scopes_preselected.get_sorted(),
        scopes_remain=scopes_remain.get_sorted()
    )

@app.route("/process", methods=["POST"])
def draw_confirm_scopes():    
    scopes_added = Scopes(request.form.getlist("scope"))
    scopes_preselected = Scopes.create_from_string(session["scopes_preselected"])
    scopes_all = scopes_added + scopes_preselected
    state = secrets.token_urlsafe(20)
    session["state"] = state
    oauth_url = (f'https://slack.com/oauth/authorize?scope={ scopes_all.get_string() }' 
        + f'&client_id={ SLACK_CLIENT_ID }'
        + f'&state={ state }'
        )
        
    return render_template(
        'confirm.html.j2',         
        oauth_url=oauth_url,
        scopes=scopes_all.get_sorted()
    )

@app.route("/finish_auth", methods=["GET", "POST"])
def draw_finished_auth():
    """Exchange to oauth code with a token and store it"""
    
    error = None
    # verify the state            
    if "error" in request.args:
        error = request.args["error"]
    elif (request.args["state"] != session["state"]):
        error = "Invalid state"
    elif "code" not in request.args:
        error = "no code returned"
    
    if error is None:
        try:                    
            # Retrieve the auth code from the request params        
            auth_code = request.args['code']

            # An empty string is a valid token for this request
            client = slack.WebClient(token="")

            # Request the auth tokens from Slack
            api_response = client.oauth_access(
                client_id=SLACK_CLIENT_ID,
                client_secret=SLACK_CLIENT_SECRET,
                code=auth_code
            )    
            print(api_response)
            team_id = api_response["team_id"]
            user_id = api_response["user_id"]
            team_name = api_response["team_name"]            
            scopes_str = api_response["scope"]
            access_token = api_response["access_token"]
            
            # store the received token to our DB for later use                
            with psycopg2.connect(DATABASE_URL) as connection:                
                my_token = Authorization(
                    team_id,
                    user_id,
                    team_name,                
                    scopes_str,
                    access_token
                )
                my_token.store(connection)
            
            return render_template(
                'finished.html.j2',         
                team_name=team_name,                
                token=my_token.token,
                scopes_str=scopes_str
            )
        except (Exception, psycopg2.Error) as error :
            error = error
            raise error
            """
            return render_template(
                'error.html.j2',         
                error=error,                
            )
            """
    else:
        return render_template(
            'error.html.j2',         
            error=error,                
        )
    

def is_slack_request_valid(ts, body, signature, signing_secret) -> bool:
    """verifies a request with signed secret approach
    
    Args:
        ts = timestamp of request from X-Slack-Request-Timestamp header
        body = string of request body
        signature = signature of request from X-Slack-Signature header
        signing_secret = signing secret of this app
    
    Returns:
        true if signatures match
        false otherwise
    """
    version = "v0"        
    base_string = ":".join([version, ts, body])    
    h = hmac.new(
        signing_secret.encode("utf-8"), 
        base_string.encode("utf-8"), 
        hashlib.sha256 
    )
    my_signature = version + "=" + h.hexdigest()
    return my_signature == signature    


@app.route('/slash', methods=['POST'])
def slash_request():                
    """endpoint for receiving all slash command requests from Slack"""
    try:                
        if not is_slack_request_valid(
                ts=request.headers["X-Slack-Request-Timestamp"],
                body=request.get_data().decode("utf-8"),            
                signature=request.headers["X-Slack-Signature"],
                signing_secret=SLACK_SIGNING_SECRET):
            print("Invalid Slack request")
            abort(400)
        
        # get token for current workspace
        team_id = request.form.get("team_id")
        user_id = request.form.get("user_id")
        with psycopg2.connect(DATABASE_URL) as connection:
            my_token = Authorization.fetchFromDb(
                connection, 
                team_id,
                user_id
            )
        if my_token is None:                        
            url = request.url_root            
            blocks = Blocks([
                Section("You have not yet created a token."),
                ActionsBlock([
                    Button(
                        "Create Token", 
                        AID_BUTTON_NEW, 
                        url=url
                    )
                ])
            ])

        else :              
            scopes = Scopes.create_from_string(my_token.scopes)
            # create response                                
            url = request.url_root + "?scopes=" + scopes.get_string()
            blocks = Blocks([
                Section(
                    f"Your token is:\n>`{my_token.token}`\n"
                    + f"with these scopes:\n>`{scopes.get_string()}`"
                ),
                ActionsBlock([
                    Button(
                        "Add Scopes", 
                        AID_BUTTON_NEW, 
                        url=url
                    ),              
                    Button(
                        "Delete Token", 
                        AID_BUTTON_REMOVE, 
                        style=Button.STYLE_DANGER, 
                        confirm=ConfirmationDialog(
                            "Are you sure?",
                            "Do you really want to delete your token?",
                            "Delete Token",
                            "Cancel"
                        )
                    ),
                    Button(
                        "Dummy", 
                        AID_BUTTON_DUMMY
                    )
                ])
            ])
        
        response_msg = ResponseMessage(
            blocks = blocks
        )
        
        return Response(response_msg.get_json(), mimetype='application/json')
            
            
    except Exception as error:
        print("ERROR: ", error)        
        response_json = {
            "text": "An internal error has occurred"
        }
        raise error
        # return Response(response_json, mimetype='application/json')


@app.route('/interactive', methods=['POST'])
def interactive_request():                
    """endpoint for receiving all slash command requests from Slack"""    
    if not is_slack_request_valid(
            ts=request.headers["X-Slack-Request-Timestamp"],
            body=request.get_data().decode("utf-8"),            
            signature=request.headers["X-Slack-Signature"],
            signing_secret=SLACK_SIGNING_SECRET):
        print("Invalid Slack request")
        abort(400)

    if "payload" in request.form:            
        
        payload = json.loads(request.form["payload"])
        # print(payload)        
        
        # get token for current user
        team_id = payload["team"]["id"]
        user_id = payload["user"]["id"]

        
        action_id = payload["actions"][0]["action_id"]
        
        if action_id == AID_BUTTON_REMOVE:
            # lets delete the old token
            try:
                with psycopg2.connect(DATABASE_URL) as connection:
                    token = Authorization.fetchFromDb(
                        connection, 
                        team_id,
                        user_id
                    )                
                    token.delete(connection)
                    response_msg = ResponseMessage(
                        text = "Your token has been deleted.",
                        replace_original=True,
                        delete_original=True
                    )
                    response_msg.send(payload["response_url"])
                    
                    client = slack.WebClient(token=token.token)
                    res = client.auth_revoke()
                    assert res["ok"]
                       
            except Exception as error:
                print("ERROR: ", error)
                abort(500)
        
        elif action_id == AID_BUTTON_DUMMY:
            response_msg = ResponseMessage(
                text = "This is a dummy response"
            )
            response_msg.send(payload["response_url"])

                
    return ""


# to run this flask app locally
if __name__ == '__main__':
    app.run(debug=True, port=8000) 
