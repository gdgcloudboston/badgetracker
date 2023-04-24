"""Badge Reader Cloud Run Service."""
import json
import os
import requests

from flask import Flask
from flask import redirect
from flask import request
from flask import url_for
from flask_login import current_user
from flask_login import login_required
from flask_login import login_user
from flask_login import LoginManager
from flask_login import logout_user
from flask_login import UserMixin

from google.cloud import firestore
from google.cloud import secretmanager_v1
from oauthlib.oauth2 import WebApplicationClient

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


class User(UserMixin):
    """User class."""
    def __init__(self, user):
        """Initialize."""
        self.id = user.get("sub")
        self.name = user.get("name")
        self.email = user.get("email")
        self.profile_pic = user.get("picture")


def get_google_provider_cfg():
    """Return the Google Provider Configuration."""
    return requests.get(DISCOVERY_URL).json()


def get_secret(secret, version="latest"):
    """Get the secret value from the environment."""
    client = secretmanager_v1.SecretManagerServiceClient()
    project = "gdg-cloud-boston"
    secret_version_name = f'projects/{project}/secrets/{secret}/versions/{version}'
    req = {"name": secret_version_name}
    return client.access_secret_version(request=req).payload.data.decode("UTF-8")


def get_user(user_id):
    """Returna user from Firestore."""
    client = firestore.Client()
    user = client.collection("users").document(user_id).get()
    if user.exists:
        return User(user.to_dict())
    return None


def save_user(user):
    """Save a user to firestore."""
    email = user.get("email")
    name = user.get("name")
    # picture = user.get("picture")
    sub = user.get("sub")
    print(f"{name} <{email}> [{sub}]")

    client = firestore.Client()
    client.collection("users").document(sub).set(user)

    return


OAUTH_CLIENT_INFO = json.loads(get_secret("badgetracker-oauth-client-secret"))
CLIENT_ID = OAUTH_CLIENT_INFO["web"]["client_id"]
CLIENT_SECRET = OAUTH_CLIENT_INFO["web"]["client_secret"]


# User session management setup
# https://flask-login.readthedocs.io/en/latest
login_manager = LoginManager()
login_manager.init_app(app)

# OAuth 2 client setup
client = WebApplicationClient(CLIENT_ID)


# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    """Load a user."""
    print(f"Loading user: {user_id}")
    return get_user(user_id)


@app.route("/")
def index():
    """Display the main index page."""
    if current_user.is_authenticated:
        return (
            "<p>Hello, {}! You're logged in! Email: {}</p>"
            "<div><p>Google Profile Picture:</p>"
            '<img src="{}" alt="Google profile pic"></img></div>'
            '<a class="button" href="/logout">Logout</a>'.format(
                current_user.name, current_user.email, current_user.profile_pic
            )
        )
    else:
        return '<a class="button" href="/login">Google Login</a>'


@app.route("/callback")
def callback():
    """Handle the callback."""
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url.replace("http://", "https://"),
        redirect_url=request.base_url.replace("http://", "https://"),
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(CLIENT_ID, CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    user_info = requests.get(uri, headers=headers, data=body).json()

    save_user(user_info)

    user = User(user_info)

    # Begin user session by logging the user in
    login_user(user)

    # Send user back to homepage
    return redirect(url_for("index"))


@app.route("/login")
def login():
    """Login with Google."""
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=f"{request.url_root}callback".replace("http://", "https://"),
        scope=["openid", "email", "profile"],
    )
    # print(request_uri)
    return redirect(request_uri)


@app.route("/logout")
@login_required
def logout():
    """Logout the user."""
    logout_user()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
