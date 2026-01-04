import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from .logger import setup_logger
from datetime import datetime, timedelta

logger = setup_logger()

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

class YouTubeClient:
    def __init__(self, credentials_path='config/youtube/client_secrets.json', token_path='config/youtube/token.pickle'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.youtube = self._get_service()

    def _get_service(self):
        creds = None
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    logger.error(f"Credentials file not found at {self.credentials_path}")
                    raise FileNotFoundError(f"Please place your client_secrets.json in {self.credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                # Note: This will require browser interaction on first run
                # For Docker, we'll need to run this on host once to get the token.pickle
                creds = flow.run_local_server(port=0)

            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        return build('youtube', 'v3', credentials=creds)

    def create_broadcast(self, title, description, start_time=None, privacy_status='public'):
        if not start_time:
            # Default to now + 2 minutes
            start_time = (datetime.utcnow() + timedelta(minutes=2)).isoformat() + 'Z'

        logger.info(f"Creating YouTube Live Broadcast: {title} at {start_time} (Privacy: {privacy_status})")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'scheduledStartTime': start_time,
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False,
            }
        }

        request = self.youtube.liveBroadcasts().insert(part='snippet,status', body=body)
        broadcast = request.execute()
        return broadcast

    def create_stream(self, title):
        logger.info(f"Creating YouTube Live Stream: {title}")
        body = {
            'snippet': {
                'title': title,
            },
            'cdn': {
                'frameRate': '30fps',
                'ingestionType': 'rtmp',
                'resolution': '1080p',
            }
        }
        request = self.youtube.liveStreams().insert(part='snippet,cdn', body=body)
        stream = request.execute()
        return stream

    def bind_broadcast(self, broadcast_id, stream_id):
        logger.info(f"Binding broadcast {broadcast_id} to stream {stream_id}")
        request = self.youtube.liveBroadcasts().bind(
            id=broadcast_id,
            part='id,contentDetails',
            streamId=stream_id
        )
        return request.execute()
