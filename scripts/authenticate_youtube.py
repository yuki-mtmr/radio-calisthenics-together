import os
import pickle
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.logger import setup_logger

logger = setup_logger()

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def main():
    creds_path = 'config/youtube/client_secrets.json'
    token_path = 'config/youtube/token.pickle'

    if not os.path.exists(creds_path):
        print(f"Error: {creds_path} not found.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)

    # This will open a browser window for authentication
    print("Opening browser for Google authentication...")
    print("If the browser doesn't open, follow the instructions in the console.")

    creds = flow.run_local_server(port=0)

    # Save the credentials for the next run
    with open(token_path, 'wb') as token:
        pickle.dump(creds, token)

    print(f"Successfully authenticated! Token saved to {token_path}")

if __name__ == "__main__":
    main()
