#!/usr/bin/env python3
"""動画頭切れ修正の手動ドライラン（配信せず・本番メソッドを実機検証）。

start_streaming() のメディア制御部分を、本番と同じ OBSClient のメソッド
(_freeze_media_at_zero / _ensure_media_paused_at_zero) で再現し、warmup 中に
動画が位置0で静止し続けるか、PLAY 後に位置0から再生されるかを実測する。
start_stream()/YouTube は呼ばないため配信には送出されない（安全）。

使い方:
    cd ~/projects/radio-calisthenics-together
    ./.venv/bin/python scripts/_check_media_head.py
"""
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.obs_client import OBSClient, MEDIA_BUFFER_WAIT_SEC, MEDIA_CURSOR_TOLERANCE_MS
from rct.settings import settings

PLAY = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"


def _cursor(obs, source):
    try:
        st = obs.client.get_media_input_status(source)
        return getattr(st, "media_cursor", None), getattr(st, "media_state", None)
    except Exception as e:
        return None, f"ERR:{e}"


def main():
    scene = settings.OBS_SCENE_NAME
    source = settings.OBS_MEDIA_SOURCE_NAME
    if not source:
        print("OBS_MEDIA_SOURCE_NAME が未設定です。")
        sys.exit(1)

    obs = OBSClient()
    if not obs.connect():
        print("OBS に接続できません。OBS と WebSocket が起動しているか確認してください。")
        sys.exit(1)

    print(f"=== ドライラン（本番メソッド）: scene='{scene}', source='{source}' ===")
    print("（配信は行いません。OBSプレビューのみ）\n")

    # start_streaming() のメディア制御部と同じ流れ（start_stream/YouTube は除く）
    obs.client.set_current_program_scene(scene)
    obs.set_scene_item_enabled(scene, source, False)
    time.sleep(0.5)
    obs.set_scene_item_enabled(scene, source, True)
    time.sleep(0.3)
    obs._freeze_media_at_zero(source)  # ← 本番と同じ凍結

    print(f"[warmup] {MEDIA_BUFFER_WAIT_SEC}s 静止確認（許容 <= {MEDIA_CURSOR_TOLERANCE_MS}ms）:")
    warm = []
    for i in range(int(MEDIA_BUFFER_WAIT_SEC / 0.5)):
        time.sleep(0.5)
        c, s = _cursor(obs, source)
        warm.append(c if c is not None else -1)
        print(f"  t={(i + 1) * 0.5:.1f}s  cursor={c}ms  state={s}")

    print("\n[guard] _ensure_media_paused_at_zero 実行:")
    obs._ensure_media_paused_at_zero(source)

    print("\n[play] PLAY 送出後:")
    obs.client.trigger_media_input_action(source, PLAY)
    play = []
    for i in range(6):
        time.sleep(0.5)
        c, s = _cursor(obs, source)
        play.append(c if c is not None else -1)
        print(f"  t={(i + 1) * 0.5:.1f}s  cursor={c}ms  state={s}")

    wv = [c for c in warm if c >= 0]
    pv = [c for c in play if c >= 0]
    max_warm = max(wv) if wv else -1
    p0, p1 = (pv[0], pv[-1]) if pv else (-1, -1)
    warm_ok = 0 <= max_warm <= MEDIA_CURSOR_TOLERANCE_MS
    play_ok = 0 <= p0 <= 800 and p1 > p0

    print("\n=== 判定 ===")
    print(f"  warmup 最大cursor={max_warm}ms -> {'OK（位置0で静止）' if warm_ok else 'NG（再生が進む＝頭切れ）'}")
    print(f"  PLAY {p0}->{p1}ms -> {'OK（位置0付近から再生）' if play_ok else 'NG'}")
    print(f"\n  総合: {'PASS' if warm_ok and play_ok else 'FAIL'}")

    # 後始末: 位置0で一時停止に戻す
    obs._freeze_media_at_zero(source)


if __name__ == "__main__":
    main()
