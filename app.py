# main module with the Slack app

import os
import slack
from flask import Flask, json, request, render_template, session, Response, abort, redirect
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

# session constants
SESSION_INSTALL_TYPE = "install_type"
SESSION_STATE = "state"
SESSION_TEAM_ID = "team_id"
SESSION_USER_ID = "user_id"

INSTALL_TYPE_ADD = "add_scopes"
INSTALL_TYPE_NEW = "new_install"

# Slack action IDs
AID_BUTTON_NEW = "button_new"
AID_BUTTON_REMOVE = "button_remove"
AID_BUTTON_REFRESH = "button_refresh"

##########################################
# Utility functions
#

def is_slack_request_valid(
        ts: str, 
        body: str, 
        signature: str, 
        signing_secret:str ) -> bool:
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


##########################################
# Classes
#

class Scopes:
    
    DELIMITER = ","
    SCOPE_COMMANDS = "commands"
    SCOPE_IDENTIFY = "identify"

    def __init__(self, scopes: set=None):
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

    def __add__(self, s2: "Scopes") -> "Scopes":
        s_sum = self._scopes.union(s2.scopes)
        return Scopes(s_sum)

    def __contains__(self, key: str) -> bool:
        return key in self._scopes

    def __eq__(self, other):
        """change comparison for this object type to by value"""
        # Objects of a different class are never equal
        if type(other) != type(self):
            return False
        return self.scopes == other.scopes

    def __ne__(self, other):
        """change comparison for this object type to by value"""
        return not self.__eq__(other)

    def __str__(self) -> str:
        return self.get_string()

    def get_count(self) -> int:
        """returns the count of scopes"""
        return len(self.scopes)

    def get_string(self) -> str:
        scopes_list = list(self._scopes)
        scopes_list.sort()
        return self.DELIMITER.join(scopes_list)

    def add(self, scope: str) -> None: 
        if not isinstance(scope, str):
            raise TypeError("scope must be of type string")
        if self.DELIMITER in scope:
            raise ValueError(f"scope can not contain {self.DELIMITER}")

        self._scopes.add(scope)
   
    def diff(self, scopes_second: "Scopes") -> "Scopes":
        if not isinstance(scopes_second, Scopes):
            raise TypeError("scopes_second must be of type Scopes")
        scopes_diff = self._scopes.difference(scopes_second.scopes)
        return Scopes(scopes_diff)

    def get_sorted(self) -> str:
        scopes_list = list(self._scopes)
        scopes_list.sort()
        return scopes_list
    
    @classmethod
    def create_from_string(cls, scopes_str: str) -> "Scopes":
        scopes = set(scopes_str.split(cls.DELIMITER))
        if "" in scopes:
            scopes.remove("")
        return cls(scopes)

    @classmethod
    def create_from_file(cls, filename: str) -> "Scopes":
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
            user_name: str, 
            scopes: Scopes, 
            token: str,            
            last_update: datetime = None
        ):
        # validation
        if not isinstance(scopes, Scopes):
            raise TypeError("scopes must be of type Scopes")        
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
        self._user_name = str(user_name)[:255]
        self._scopes = scopes
        self._token = str(token)[:255]        
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
    def user_name(self) -> str:
        return self._user_name
    
    @property
    def scopes(self) -> str:
        return self._scopes

    @property
    def token(self) -> str:
        return self._token
    
    @property
    def last_update(self) -> datetime:
        return self._last_update

    def __eq__(self, other):
        """change comparison for this object type to by value"""
        # Objects of a different class are never equal
        if type(other) != type(self):
            return False
        return ( self.team_id == other.team_id and
            self.user_id == other.user_id and
            self.scopes == other.scopes and
            self.team_name == other.team_name and    
            self.user_name == other.user_name and    
            self.token == other.token and            
            self.last_update == other.last_update            
        )

    def __ne__(self, other):
        """change comparison for this object type to by value"""
        return not self.__eq__(other)

    def is_owner(self):
        """auth is belonging to app owner if it containts commands scopes"""
        return Scopes.SCOPE_COMMANDS in self.scopes

    def json_dumps(self) -> str:        
        """returns the JSON representation of this object as string"""
        arr = {
            "team_id": self.team_id,
            "user_id": self.user_id,
            "team_name": self.team_name,
            "user_name": self.user_name,
            "scopes": self.scopes.get_string(),
            "token": self.token,
            "last_update": self.last_update.isoformat()
        }
        return json.dumps(arr)

    @classmethod
    def json_loads(cls, json_str: str) -> "Authorization":
        """returns a new object from the provided JSON representation"""
        arr = json.loads(json_str)
        tz_utc = pytz.timezone("UTC")
        return Authorization(
            arr["team_id"],
            arr["user_id"],
            arr["team_name"],
            arr["user_name"],
            Scopes.create_from_string(arr["scopes"]),
            arr["token"],
            datetime.fromisoformat(arr["last_update"])
        )

    #############
    # DB related methods        
    def store(self, connection: object):
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
                        user_name,
                        scopes, 
                        token,                         
                        last_update
                    ) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s) 
                    ON CONFLICT (team_id, user_id)
                    DO UPDATE SET 
                        team_name=%s,
                        user_name=%s, 
                        scopes=%s, 
                        token=%s,                         
                        last_update=%s
                """
                record = (
                    self.team_id, 
                    self.user_id, 
                    self.team_name,
                    self.user_name,
                    self.scopes.get_string(), 
                    self.token,                     
                    self.last_update,
                    self.team_name,
                    self.user_name,                 
                    self.scopes.get_string(), 
                    self.token,                    
                    self.last_update
                )
                cursor.execute(sql_query, record)
                connection.commit()
        except (Exception, psycopg2.Error) as error:            
            print("WARN: Failed to insert record into table", error)
            raise error
                
            
    def delete(self, connection: object):
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
    def fetchFromDb(
            cls, 
            connection: object, 
            team_id: str, 
            user_id: str) -> any:
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
                        user_name,
                        scopes, 
                        token,                        
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
                    obj = Authorization(
                        record[0], 
                        record[1], 
                        record[2], 
                        record[3],
                        Scopes.create_from_string(record[4]), 
                        record[5], 
                        record[6]
                    )
            
        except (Exception, psycopg2.Error) as error :
            print("Error while fetching data from PostgreSQL", error)
            raise

        return obj

    @classmethod
    def get_count_for_team(
            cls, 
            connection: object, 
            team_id: str) -> int:
        """return the number of stored authorizations for a team
         
         Args:            
            connection: current postgres connection
            team_id: team ID of object to be fetched

        Returns:
            count of authorizations for that team
        
        Exceptions:
            on any error
        """
        try:            
            with connection.cursor() as cursor:
                sql_query = """SELECT COUNT(*)
                    FROM mytoken_auths 
                    WHERE team_id = %s
                    """                
                cursor.execute(sql_query, (team_id,))
                record = cursor.fetchone()
                if (record == None):
                    raise RuntimeError(
                        f"Could not get auths count for team {team_id} "                            
                    )                    
                else:                
                    count = record[0]                    
            
        except (Exception, psycopg2.Error) as error :
            print("Error while fetching data from PostgreSQL", error)
            raise

        return count


app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


##########################################
# Web App
#

@app.route("/", methods=["GET"])
def web_select_scopes():
    """shows the page for selecting scopes
    If called with no query params, will assume first install 
    and preselect the commands scope to enable slash commands for the app
    If called with team_id and user_id will add scopes to existing ones    
    """
    
    if "team_id" in request.args and "user_id" in request.args:
        team_id = request.args["team_id"]
        user_id = request.args["user_id"]
        with psycopg2.connect(DATABASE_URL) as connection:
            my_auth = Authorization.fetchFromDb(
                connection, 
                team_id,
                user_id
            )
        if my_auth is None:
            scopes_preselected = Scopes([Scopes.SCOPE_IDENTIFY])
            team_name = None
            user_name = None
        else:
            scopes_preselected = my_auth.scopes
            team_name = my_auth.team_name
            user_name = my_auth.user_name
            session["team_id"] = team_id
            session["user_id"] = user_id
    else:
        scopes_preselected = Scopes(
            [Scopes.SCOPE_IDENTIFY, Scopes.SCOPE_COMMANDS]
        )
        team_name = None
        user_name = None

    state = secrets.token_urlsafe(20)
    session[SESSION_STATE] = state

    session["scopes_preselected"] = scopes_preselected.get_string()
    scopes_all = Scopes.create_from_file("scopes")        
    scopes_remain = scopes_all.diff(scopes_preselected)
    if team_name is not None:
        session[SESSION_INSTALL_TYPE] = INSTALL_TYPE_ADD
        return render_template(
            'select.html.j2', 
            scopes_preselected=scopes_preselected.get_sorted(),
            scopes_remain=scopes_remain.get_sorted(),
            team_name=team_name,
            user_name=user_name
        )
    else:
        session[SESSION_INSTALL_TYPE] = INSTALL_TYPE_NEW
        oauth_url = (f'https://slack.com/oauth/authorize?scope={ scopes_preselected.get_string() }' 
            + f'&client_id={ SLACK_CLIENT_ID }'
            + f'&state={ state }'
            )
        return render_template(
            'install_start.html.j2',
            oauth_url=oauth_url
        )


@app.route("/confirm", methods=["POST"])
def web_confirm_scopes():    
    if "scopes_preselected" not in session:
        print("session incomplete")
        abort(500)
    
    if "team_id" in session and "user_id" in session:
        # load current auth to display name on web page
        team_id = session["team_id"]
        user_id = session["user_id"]        
        with psycopg2.connect(DATABASE_URL) as connection:
            my_auth = Authorization.fetchFromDb(
                connection, 
                team_id,
                user_id
            )
    else:
        my_auth = None
    
    if my_auth is not None:
        team_name = my_auth.team_name
        user_name = my_auth.user_name
    else:
        team_name = None
        user_name = None
    
    scopes_preselected = Scopes.create_from_string(session["scopes_preselected"])
    scopes_added = Scopes(request.form.getlist("scope"))    
    scopes_all = scopes_added + scopes_preselected
       
    state = session[SESSION_STATE]

    oauth_url = (f'https://slack.com/oauth/authorize?scope={ scopes_all.get_string() }' 
        + f'&client_id={ SLACK_CLIENT_ID }'
        + f'&state={ state }'
        )
    if my_auth is not None:
        oauth_url += f"&team={ my_auth.team_id }"
    
    restart_url = f"/?team_id={ team_id }&user_id={ user_id }"
    return render_template(
        'confirm.html.j2',         
        oauth_url=oauth_url,
        restart_url=restart_url,
        scopes=scopes_all.get_sorted(),
        team_name=team_name,
        user_name=user_name        
    )


@app.route("/finish_auth", methods=["GET", "POST"])
def web_finished_auth():
    """Exchange to oauth code with a token and store it"""
    
    error = None
    # verify the state            
    if "error" in request.args:
        error = request.args["error"]
    elif (request.args["state"] != session[SESSION_STATE]):
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
            assert api_response["ok"]
            team_id = api_response["team_id"]
            user_id = api_response["user_id"]
            team_name = api_response["team_name"]            
            scopes = Scopes.create_from_string(api_response["scope"])
            access_token = api_response["access_token"]
            
            client = slack.WebClient(token=access_token)
            api_response = client.auth_test()
            assert api_response["ok"]
            user_name = api_response["user"]
            
            # store the received auth to our DB for later use
            # will be marked as owner if it has the commands scope
            with psycopg2.connect(DATABASE_URL) as connection:
                my_auth = Authorization(
                    team_id,
                    user_id,
                    team_name,
                    user_name,
                    scopes,
                    access_token
                )
                my_auth.store(connection)

            session[SESSION_TEAM_ID] = team_id
            session[SESSION_USER_ID] = user_id
            
            ## redirect to next page
            return redirect("/complete", code=302)
            
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
    

@app.route("/complete", methods=["GET"])
def web_install_complete():
    """Show user installation result"""

    if "team_id" not in session or "user_id" not in session:
        raise RuntimeError("Session corrupt")

    team_id = session[SESSION_TEAM_ID]
    user_id = session[SESSION_USER_ID]

    with psycopg2.connect(DATABASE_URL) as connection:
        my_auth = Authorization.fetchFromDb(
            connection, 
            team_id,
            user_id
        )
    
    if my_auth is None:
        raise RuntimeError(
            "Can not find auth for current user"
        )

    restart_url = f"/?team_id={ team_id }&user_id={ user_id }"            
    return render_template(
        'finished.html.j2',                         
        team_name=my_auth.team_name,
        token=my_auth.token,
        scopes_str=my_auth.scopes.get_string(),
        restart_url=restart_url,
        isNewInstall=(session[SESSION_INSTALL_TYPE] == INSTALL_TYPE_NEW)
    )


##########################################
# Slack app
#

@app.route('/slash', methods=['POST'])
def slack_slash_request():                
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

        if team_id is not None and user_id is not None:            
            return Response(
                slack_create_main_menu(team_id, user_id).get_json(), 
                mimetype='application/json'
            )
            
    except Exception as error:
        print("ERROR: ", error)        
        response_json = {
            "text": "An internal error has occurred"
        }
        raise error
        # return Response(response_json, mimetype='application/json')

    return ""


def slack_create_main_menu(team_id: str, user_id: str) -> ResponseMessage:
    """creates main menu"""
    with psycopg2.connect(DATABASE_URL) as connection:
        my_auth = Authorization.fetchFromDb(
            connection, 
            team_id,
            user_id
        )
    url = f"{request.url_root }?team_id={team_id}&user_id={user_id}" 
    if my_auth is None:                                    
        blocks = Blocks([
            Section("You have not yet created a token."),
            ActionsBlock([
                Button(
                    "Create Token", 
                    AID_BUTTON_NEW, 
                    url=url
                ),
                Button(
                    "Refresh", 
                    AID_BUTTON_REFRESH
                )
            ])
        ])

    else :                          
        # create response                                            
        text = (f"Your token is:\n>`{my_auth.token}`\n"
            + f"with these scopes:\n>`{my_auth.scopes.get_string()}`\n")            
        actions = ActionsBlock([
            Button(
                "Add Scopes", 
                AID_BUTTON_NEW, 
                url=url
            )
        ])
        # only non owners can delete their token
        if not my_auth.is_owner():
            actions.add(
                Button(
                    "Delete Token", 
                    AID_BUTTON_REMOVE, 
                    style=Button.STYLE_DANGER, 
                    confirm=ConfirmationDialog(
                        "Are you sure?",
                        "Do you really want to delete your token?",
                        "Delete Token",
                        "Cancel"
            )))
        actions.add(
            Button(
                "Refresh", 
                AID_BUTTON_REFRESH
        ))
        blocks = Blocks([
            Section(
                text
            ),
            actions
        ])
    
    return ResponseMessage(
        blocks = blocks
    )

@app.route('/interactive', methods=['POST'])
def slack_interactive_request():                
    """endpoint for receiving all slash command requests from Slack"""    
    if not is_slack_request_valid(
            ts=request.headers["X-Slack-Request-Timestamp"],
            body=request.get_data().decode("utf-8"),            
            signature=request.headers["X-Slack-Signature"],
            signing_secret=SLACK_SIGNING_SECRET):
        print("Invalid Slack request")
        abort(400)

    if "payload" in request.form:                            
        # get context from current request
        payload = json.loads(request.form["payload"])
        # print(payload)                
        team_id = payload["team"]["id"]
        user_id = payload["user"]["id"]        
        action_id = payload["actions"][0]["action_id"]
        
        try:            
            with psycopg2.connect(DATABASE_URL) as connection:
                # get token for current user
                my_auth = Authorization.fetchFromDb(
                    connection, 
                    team_id,
                    user_id
                )                
                if action_id == AID_BUTTON_REMOVE:
                    # lets delete the old token
                    if my_auth is None:
                        raise RuntimeError("could not find auth to delete")
                    
                    # revoke token
                    client = slack.WebClient(token=my_auth.token)
                    res = client.auth_revoke()
                    assert res["ok"]
                    
                    # remove auth from storage
                    my_auth.delete(connection)
                    
                    # inform user
                    response_msg = ResponseMessage(
                        text = "Your token has been deleted.",
                        replace_original=True,
                        delete_original=True
                    )
                    response_msg.send(payload["response_url"])
                    
                    # redraw menu
                    # response_msg = create_main_menu(team_id, user_id)
                    # response_msg.send(payload["response_url"])
                    
            
                elif action_id == AID_BUTTON_REFRESH:                    
                    response_msg = slack_create_main_menu(team_id, user_id)
                    response_msg.replace_original = True
                    response_msg.delete_original = True
                    response_msg.send(payload["response_url"])

        except Exception as error:
            print("ERROR: ", error)
            abort(500)
                
    return ""


##########################################
# Main - for running this app locally
#

if __name__ == '__main__':
    app.run(debug=True, port=8000) 
