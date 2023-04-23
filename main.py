"""Badge Reader Cloud Run Service"""
import os

from flask import Flask
from google.cloud import secretmanager_v1

app = Flask(__name__)


def get_secret(secret, version="latest"):
    """Get the secret value from the environment."""
    client = secretmanager_v1.SecretManagerServiceClient()
    project = "gdg-cloud-boston"
    secret_version_name = f'projects/{project}/secrets/{secret}/versions/{version}'
    request = {"name": secret_version_name}
    return client.access_secret_version(request=request).payload.data.decode("UTF-8")


@app.route("/")
def index():
    """Display the main index page."""
    name = os.environ.get("NAME", "World")
    secret = get_secret("badgetracker-oauth-client-secret")
    print(secret)
    return "Hello {}!".format(name)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
