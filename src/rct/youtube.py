"""YouTubeClient factory。

実体は youtube-autopost ライブラリ (vendor/*.whl, private repo
/Users/yukimatsumori/projects/youtube-autopost からビルド) の YouTubeClient。
rct 側はパスのデフォルトと send_alert_email コールバックの配線のみを担う。

呼び出し箇所は `from rct.youtube import make_youtube_client as YouTubeClient`
としてエイリアス import し、既存の `YouTubeClient()` 呼び出し・
`patch("scripts.xxx.YouTubeClient")` の契約テストを変更なしで維持する。
"""
from youtube_autopost import YouTubeClient

from .notify import send_alert_email

DEFAULT_CREDENTIALS_PATH = "config/youtube/client_secrets.json"
DEFAULT_TOKEN_PATH = "config/youtube/token.json"


def make_youtube_client(
    credentials_path: str = DEFAULT_CREDENTIALS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH,
) -> YouTubeClient:
    """rct の既定パスと send_alert_email を配線した YouTubeClient を返す。"""
    return YouTubeClient(
        credentials_path=credentials_path,
        token_path=token_path,
        on_alert=send_alert_email,
    )
