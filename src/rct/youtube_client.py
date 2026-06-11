import os
import pickle
import time
from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from .logger import setup_logger
from .notify import send_alert_email

logger = setup_logger()

TOKEN_REFRESH_MAX_RETRIES = 5
TOKEN_REFRESH_RETRY_DELAY = 30  # seconds

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

class YouTubeClient:
    def __init__(self, credentials_path='config/youtube/client_secrets.json', token_path='config/youtube/token.pickle'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.youtube = self._get_service()

    def _load_cached_creds(self):
        """保存済みトークンを読み込む。ファイルがなければ None。"""
        if not os.path.exists(self.token_path):
            return None
        with open(self.token_path, 'rb') as f:
            return pickle.load(f)

    def _refresh_creds_with_retry(self, creds):
        """期限切れトークンをリトライ付きでリフレッシュする。全滅時はアラートを送り None を返す。"""
        last_error = None
        for attempt in range(1, TOKEN_REFRESH_MAX_RETRIES + 1):
            try:
                creds.refresh(Request())
                last_error = None
                break
            except Exception as e:
                last_error = e
                logger.warning(f"Token refresh attempt {attempt}/{TOKEN_REFRESH_MAX_RETRIES} failed: {e}")
                if attempt < TOKEN_REFRESH_MAX_RETRIES:
                    logger.info(f"Retrying in {TOKEN_REFRESH_RETRY_DELAY}s...")
                    time.sleep(TOKEN_REFRESH_RETRY_DELAY)

        if last_error:
            logger.error(f"Token refresh failed after {TOKEN_REFRESH_MAX_RETRIES} attempts")
            repo_root = Path(__file__).resolve().parents[2]
            send_alert_email(
                "Token Refresh Failed",
                f"YouTubeトークンの自動更新に{TOKEN_REFRESH_MAX_RETRIES}回リトライしましたが失敗しました。\n\n"
                f"最後のエラー: {last_error}\n\n"
                "以下のコマンドで再認証してください:\n"
                f"cd {repo_root}\n"
                ".venv/bin/python scripts/authenticate_youtube.py"
            )
            return None

        return creds

    def _run_new_auth_flow(self):
        """新規認証フローを実行して creds を返す。"""
        if not os.path.exists(self.credentials_path):
            logger.error(f"Credentials file not found at {self.credentials_path}")
            raise FileNotFoundError(f"Please place your client_secrets.json in {self.credentials_path}")
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
        # Note: This will require browser interaction on first run
        # For Docker, we'll need to run this on host once to get the token.pickle
        return flow.run_local_server(port=0)

    def _save_creds(self, creds):
        """トークンをファイルに保存する。"""
        with open(self.token_path, 'wb') as f:
            pickle.dump(creds, f)

    def _get_service(self):
        creds = self._load_cached_creds()

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds = self._refresh_creds_with_retry(creds)
            if not creds or not creds.valid:
                creds = self._run_new_auth_flow()
            self._save_creds(creds)

        return build('youtube', 'v3', credentials=creds)

    def create_broadcast(self, title, description, start_time_iso, privacy_status='public'):
        """
        YouTube Live 枠を作成します。
        start_time_iso: UTC (ISO 8601) format string.
        """
        logger.info(f"Creating YouTube Live Broadcast: {title} at {start_time_iso} (Privacy: {privacy_status})")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'scheduledStartTime': start_time_iso,
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False,
            },
            'contentDetails': {
                'enableAutoStart': True,
                'enableAutoStop': True,
                'monitorStream': {
                    'enableMonitorStream': False
                }
            }
        }

        request = self.youtube.liveBroadcasts().insert(part='snippet,status,contentDetails', body=body)
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

    def list_upcoming_broadcasts(self):
        request = self.youtube.liveBroadcasts().list(
            part='snippet,status',
            broadcastStatus='upcoming',
            maxResults=20
        )
        response = request.execute()
        return response.get('items', [])

    def list_active_broadcasts(self):
        """現在配信中の broadcast を取得する。verify_stream の自動検証で利用。"""
        request = self.youtube.liveBroadcasts().list(
            part='snippet,status',
            broadcastStatus='active',
            maxResults=20
        )
        response = request.execute()
        return response.get('items', [])

    def delete_broadcast(self, broadcast_id):
        logger.info(f"Deleting broadcast: {broadcast_id}")
        self.youtube.liveBroadcasts().delete(id=broadcast_id).execute()

    def verify_token(self):
        """トークンが有効か軽量API call で確認する。

        Returns:
            tuple[bool, str | None]: (成功, エラーメッセージ)
        """
        try:
            self.youtube.channels().list(part='id', mine=True).execute()
            return True, None
        except Exception as e:
            return False, str(e)

    def find_broadcast_by_date(self, date_str):
        """タイトルに指定した日付が含まれる待機中の枠を探します"""
        upcoming = self.list_upcoming_broadcasts()
        for item in upcoming:
            if date_str in item['snippet']['title']:
                return item
        return None
