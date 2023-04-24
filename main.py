"""Badge Tracker Cloud Run Service."""
import json
import os
import requests

from bs4 import BeautifulSoup

from flask import Flask
from flask import redirect
from flask import render_template
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

arch_badges = [
    "Preparing for your Professional Cloud Architect Journey",
    "Google Cloud Fundamentals: Core Infrastructure",
    "Essential Google Cloud Infrastructure: Foundation",
    "Essential Google Cloud Infrastructure: Core Services",
    "Elastic Google Cloud Infrastructure: Scaling and Automation",
    "Reliable Google Cloud Infrastructure: Design and Process",
    "Getting Started with Google Kubernetes Engine",
    "Logging, Monitoring and Observability in Google Cloud",
    "Create and Manage Cloud Resources",
    "Perform Foundational Infrastructure Tasks in Google Cloud",
    "Set Up and Configure a Cloud Environment in Google Cloud",
    "Automating Infrastructure on Google Cloud with Terraform",
    "Deploy and Manage Cloud Environments with Google Cloud",
    "Optimize Costs for Google Kubernetes Engine",
    "Cloud Architecture: Design, Implement, and Manage",
]

dev_badges = [
    "Google Cloud Fundamentals: Core Infrastructure",
    "Getting Started With Application Development",
    "Securing and Integrating Components of your Application",
    "App Deployment, Debugging, and Performance",
    "Application Development with Cloud Run",
    "Getting Started with Google Kubernetes Engine",
    "Hybrid Cloud Modernizing Applications with Anthos",
    "Serverless Cloud Run Development",
    "Serverless Firebase Development",
    "Deploy to Kubernetes in Google Cloud",
]

ml_badges = [
    # "A Tour of Google Cloud Hands-on Labs",
    "Google Cloud Big Data and Machine Learning Fundamentals",
    "How Google Does Machine Learning",
    "Launching into Machine Learning",
    "TensorFlow on Google Cloud",
    "Feature Engineering",
    "Machine Learning in the Enterprise",
    "Production Machine Learning Systems",
    "Computer Vision Fundamentals with Google Cloud",
    "Natural Language Processing on Google Cloud",
    "Recommendation Systems on Google Cloud",
    "Machine Learning Operations (MLOps): Getting Started",
    "ML Pipelines on Google Cloud",
    "Perform Foundational Data, ML, and AI Tasks in Google Cloud",
    "Build and Deploy Machine Learning Solutions on Vertex AI",
]


class User(UserMixin):
    """User class."""
    def __init__(self, user_info):
        """Initialize."""
        self.id = user_info.get("sub")
        self.name = user_info.get("name")
        self.email = user_info.get("email")
        self.picture = user_info.get("picture")
        self.profile_url = user_info.get("profile_url")

    def create(user_info):
        """Save a user to firestore."""
        sub = user_info.get("sub")
        name = user_info.get("name")
        email = user_info.get("email")
        picture = user_info.get("picture")
        print(f"Creating user: {name} <{email}> [{sub}]")

        data = {
            "sub": sub,
            "email": email,
            "name": name,
            "picture": picture,
        }
        client = firestore.Client()
        client.collection("users").document(sub).set(data)
        return User(user_info)

    def get(user_id):
        """Returna user from Firestore."""
        print(f"Getting user: {user_id}")
        client = firestore.Client()
        doc = client.collection("users").document(user_id).get()
        if doc.exists:
            return User(doc.to_dict())
        print(f"User not found: {user_id}")
        return None

    def update(self, **kwargs):
        """Update a user in Firestore."""
        print(f"Updating user: {self.name} <{self.email}> [{self.id}]")
        print(json.dumps(kwargs, indent=2, sort_keys=True))
        client = firestore.Client()
        client.collection("users").document(self.id).update(kwargs)


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
    return User.get(user_id)


@app.route("/")
def index():
    """Display the main index page."""
    if current_user.is_authenticated:
        return render_template("index.html", current_user=current_user)
    else:
        return render_template("login.html")


@app.route("/badges")
@login_required
def badges():
    """Retrieve badges for the logged in user."""
    profile_url = current_user.profile_url
    if not profile_url:
        return redirect(url_for("index"))
    response = requests.get(profile_url)
    soup = BeautifulSoup(response.content, "html.parser")
    results = soup.findAll("span", class_="ql-subhead-1")

    # get completed badges
    completed = []
    for result in results:
        completed.append(result.text.strip())

    print(f"Completed Badges: {len(completed)}")
    print("\n".join(sorted(completed)))
    return render_template(
        "badges.html",
        current_user=current_user,
        completed=completed,
        arch_badges=arch_badges,
        dev_badges=dev_badges,
        ml_badges=ml_badges,
    )


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
    unique_id = user_info.get("sub")
    print(f"Unique ID: {unique_id}")

    # Doesn't exist? Add it to the database.
    user = User.get(unique_id)
    if not user:
        user = User.create(user_info)

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


@app.route("/update")
@login_required
def update():
    """Update the user's profile url."""
    profile_url = request.args.get("profile_url")
    current_user.update(profile_url=profile_url)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
