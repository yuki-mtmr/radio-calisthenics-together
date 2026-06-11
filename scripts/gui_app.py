import customtkinter as ctk
import subprocess
import os
import sys
from pathlib import Path
from threading import Thread
import time

# プロジェクトルート基準で動作させる (Finder/デスクトップショートカット起動は CWD が / のため)。
# rct.settings の load_dotenv() が .env を解決できるよう、rct import より前に chdir する。
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'src'))

from rct.env_file import read_env_value, update_env_values  # noqa: E402
from rct.plist_schedule import write_schedule  # noqa: E402
from rct.video_library import list_videos, find_video, is_env_safe_filename  # noqa: E402
from rct.obs_client import OBSClient  # noqa: E402
from rct.docker_ops import docker_bin  # noqa: E402

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
VIDEOS_DIR = os.path.join(PROJECT_ROOT, "videos")
DEFAULT_MEDIA_SOURCE = "radio-calisthenics_stickman.mp4"
STATUS_POLL_INTERVAL_MS = 10_000

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ラジオ体操自動配信 - 管理パネル")
        self.geometry("650x980")

        os.makedirs(VIDEOS_DIR, exist_ok=True)

        # フォント設定
        self.font_bold = ctk.CTkFont(family="Hiragino Sans", size=24, weight="bold")
        self.font_normal = ctk.CTkFont(family="Hiragino Sans", size=14)

        self.grid_columnconfigure(0, weight=1)

        # ヘッダー
        self.label = ctk.CTkLabel(self, text="ラジオ体操自動配信 配信管理", font=self.font_bold)
        self.label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # ステータス表示
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.status_frame.grid_columnconfigure(0, weight=1)

        self.status_title = ctk.CTkLabel(self.status_frame, text="現在のステータス", font=ctk.CTkFont(family="Hiragino Sans", weight="bold"))
        self.status_title.pack(pady=5)

        self.status_label = ctk.CTkLabel(self.status_frame, text="ステータスを確認中...", text_color="gray", font=self.font_normal)
        self.status_label.pack(pady=10)

        # 設定フレーム
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.settings_frame.grid_columnconfigure(1, weight=1)

        # スケジュール時刻設定
        ctk.CTkLabel(self.settings_frame, text="開始時刻 (HH:MM):", font=self.font_normal).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        time_inner_frame1 = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        time_inner_frame1.grid(row=0, column=1, padx=20, pady=10, sticky="w")

        self.start_h = ctk.CTkEntry(time_inner_frame1, width=50)
        self.start_h.pack(side="left")
        ctk.CTkLabel(time_inner_frame1, text=":").pack(side="left", padx=5)
        self.start_m = ctk.CTkEntry(time_inner_frame1, width=50)
        self.start_m.pack(side="left")

        ctk.CTkLabel(self.settings_frame, text="終了時刻 (HH:MM):", font=self.font_normal).grid(row=1, column=0, padx=20, pady=10, sticky="w")
        time_inner_frame2 = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        time_inner_frame2.grid(row=1, column=1, padx=20, pady=10, sticky="w")

        self.stop_h = ctk.CTkEntry(time_inner_frame2, width=50)
        self.stop_h.pack(side="left")
        ctk.CTkLabel(time_inner_frame2, text=":").pack(side="left", padx=5)
        self.stop_m = ctk.CTkEntry(time_inner_frame2, width=50)
        self.stop_m.pack(side="left")

        # システム内部の待機設定
        ctk.CTkLabel(self.settings_frame, text="システムの起動待機 (秒):", font=self.font_normal).grid(row=2, column=0, padx=20, pady=(10, 0), sticky="w")
        self.buffer_entry = ctk.CTkEntry(self.settings_frame, width=100)
        self.buffer_entry.grid(row=2, column=1, padx=20, pady=(10, 0), sticky="w")
        ctk.CTkLabel(self.settings_frame, text="※OBS接続を安定させるための内部的な待機時間です", font=ctk.CTkFont(size=10), text_color="gray").grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="w")

        # メディアソース名
        ctk.CTkLabel(self.settings_frame, text="OBSメディアソース名:", font=self.font_normal).grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.media_entry = ctk.CTkEntry(self.settings_frame, width=250)
        self.media_entry.grid(row=4, column=1, padx=20, pady=10, sticky="w")

        # プライバシー設定
        ctk.CTkLabel(self.settings_frame, text="YouTube公開設定:", font=self.font_normal).grid(row=5, column=0, padx=20, pady=10, sticky="w")
        self.privacy_var = ctk.StringVar(value="public")
        self.privacy_menu = ctk.CTkOptionMenu(self.settings_frame, values=["public", "unlisted", "private"], variable=self.privacy_var)
        self.privacy_menu.grid(row=5, column=1, padx=20, pady=10, sticky="w")

        # 配信動画の選択 (videos/ ストック)
        ctk.CTkLabel(self.settings_frame, text="配信動画 (videos/):", font=self.font_normal).grid(row=6, column=0, padx=20, pady=10, sticky="w")
        video_inner = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        video_inner.grid(row=6, column=1, padx=20, pady=10, sticky="w")
        self.video_var = ctk.StringVar(value="")
        self.video_menu = ctk.CTkOptionMenu(video_inner, values=[""], variable=self.video_var, width=270, font=self.font_normal)
        self.video_menu.pack(side="left")
        self.video_reload_btn = ctk.CTkButton(video_inner, text="再読込", width=64, command=self.reload_video_list, font=self.font_normal)
        self.video_reload_btn.pack(side="left", padx=8)

        self.apply_video_btn = ctk.CTkButton(self.settings_frame, text="この動画に切り替え (次回配信から)", command=self.apply_video_selection, fg_color="#8d5a1f", hover_color="#a86c25", font=self.font_normal)
        self.apply_video_btn.grid(row=7, column=1, padx=20, pady=(0, 10), sticky="w")

        # 保存ボタン
        self.save_btn = ctk.CTkButton(self, text="設定を保存して反映 (Macスケジュール更新)", command=self.save_settings, fg_color="#1f538d", font=self.font_normal)
        self.save_btn.grid(row=3, column=0, padx=20, pady=20)

        # 予約のヒント
        hint_text = "【ヒント】7:00開始に設定すると、Macは自動的に6:59に起動して準備を始めます。"
        ctk.CTkLabel(self, text=hint_text, font=ctk.CTkFont(size=11), text_color="#1f538d").grid(row=4, column=0, padx=20, pady=(0, 10))

        # 手動操作ボタン
        self.actions_frame = ctk.CTkFrame(self)
        self.actions_frame.grid(row=5, column=0, padx=20, pady=10, sticky="nsew")

        self.start_btn = ctk.CTkButton(self.actions_frame, text="今すぐ配信開始", command=self.manual_start, fg_color="green", hover_color="#228B22", font=self.font_normal)
        self.start_btn.pack(side="left", padx=20, pady=20, expand=True)

        self.stop_btn = ctk.CTkButton(self.actions_frame, text="今すぐ配信停止", command=self.manual_stop, fg_color="red", hover_color="#B22222", font=self.font_normal)
        self.stop_btn.pack(side="left", padx=20, pady=20, expand=True)

        # ログコンソール
        self.console = ctk.CTkTextbox(self, height=200, font=ctk.CTkFont(family="Courier", size=12))
        self.console.grid(row=6, column=0, padx=20, pady=20, sticky="nsew")

        # 初期値読み込み
        self.load_initial_times()

        # ステータス更新ループ開始 (Tk after ループ。ブロッキング待機は使わない)
        self._poll_in_flight = False
        self.update_status()

    def load_initial_times(self):
        try:
            # 時刻は .env の STREAM_START/STOP_TIME が正。
            # 旧実装は start.plist (= 配信1分前の Mac 起動時刻) を読んでいたため、
            # 保存のたびに表示が1分ずつ早まるバグがあった。
            st = read_env_value(ENV_PATH, "STREAM_START_TIME", "07:00").split(":")
            self.start_h.insert(0, st[0].zfill(2))
            self.start_m.insert(0, st[1].zfill(2))
            et = read_env_value(ENV_PATH, "STREAM_STOP_TIME", "07:05").split(":")
            self.stop_h.insert(0, et[0].zfill(2))
            self.stop_m.insert(0, et[1].zfill(2))

            self.media_entry.insert(0, read_env_value(ENV_PATH, "OBS_MEDIA_SOURCE_NAME", DEFAULT_MEDIA_SOURCE))
            self.buffer_entry.insert(0, read_env_value(ENV_PATH, "YOUTUBE_RESERVATION_BUFFER_MINUTES", "2"))
            self.privacy_var.set(read_env_value(ENV_PATH, "YOUTUBE_PRIVACY_STATUS", "public"))

            self.reload_video_list()
        except Exception as e:
            print(f"Error loading initial values: {e}")

    # ---------------------------------------------------------- ステータス

    def update_status(self):
        """10秒ごとのステータスポーリング (after ループ、二重起動は in-flight ガード)。"""
        if not self._poll_in_flight:
            self._poll_in_flight = True
            Thread(target=self._poll_status_once, daemon=True).start()
        self.after(STATUS_POLL_INTERVAL_MS, self.update_status)

    def _poll_status_once(self):
        """ワーカースレッド: 短命 OBSClient で状態取得。

        接続を使い回すと日曜 04:00 の OBS 週次再起動で stale 化するため毎回作り直す。
        ReqClient は非スレッドセーフなのでポーリングとボタン操作で共有しない。
        """
        obs = OBSClient()
        try:
            status = obs.get_status()
            current_file = None
            if status["connected"]:
                source = read_env_value(ENV_PATH, "OBS_MEDIA_SOURCE_NAME", DEFAULT_MEDIA_SOURCE)
                current_file = obs.get_current_media_file(source)

            if not status["connected"]:
                text, color = "OBS に接続できません (OBS 未起動の可能性)", "red"
            else:
                live = "🔴 配信中" if status["streaming"] else "⚪️ 待機中"
                lines = [f"{live}  /  シーン: {status['scene']}"]
                if current_file:
                    selected = read_env_value(ENV_PATH, "OBS_MEDIA_FILE_PATH", "")
                    marker = ""
                    if selected:
                        marker = "  ✓" if selected == current_file else "  ⚠ 選択と不一致"
                    lines.append(f"現在の動画: {Path(current_file).name}{marker}")
                else:
                    lines.append("現在の動画: 取得できません")
                text, color = "\n".join(lines), "white"
        except Exception as e:
            text, color = f"ステータス取得エラー: {e}", "red"
        finally:
            obs.disconnect()
            self._poll_in_flight = False

        try:
            self.after(0, lambda: self.status_label.configure(text=text, text_color=color))
        except RuntimeError:
            pass  # ウィンドウ破棄後

    # ------------------------------------------------------------- ログ

    def log(self, text):
        def _append():
            self.console.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
            self.console.see("end")
        # ワーカースレッドから呼ばれても安全なよう Tk イベントループ経由で挿入する
        self.after(0, _append)

    # ------------------------------------------------------- 動画選択

    def reload_video_list(self):
        names = [p.name for p in list_videos(VIDEOS_DIR)]
        if not names:
            names = ["(videos/ に動画がありません)"]
        self.video_menu.configure(values=names)
        selected_path = read_env_value(ENV_PATH, "OBS_MEDIA_FILE_PATH", "")
        selected_name = Path(selected_path).name if selected_path else ""
        if selected_name in names:
            self.video_var.set(selected_name)
        elif self.video_var.get() not in names:
            self.video_var.set(names[0])

    def apply_video_selection(self):
        """選択動画を .env に保存し、可能なら OBS に即時反映する。

        .env (OBS_MEDIA_FILE_PATH) が SoT。毎朝 06:59 の start_streaming が
        ensure_media_file で OBS に再同期するため、ここでの即時反映は任意。
        """
        name = self.video_var.get()
        if not is_env_safe_filename(name):
            self.log(f"このファイル名は使用できません (#・改行・前後空白を含む): {name}")
            return
        path = find_video(VIDEOS_DIR, name)
        if path is None:
            self.log(f"videos/ に見つかりません: {name} (再読込してください)")
            return
        abs_path = str(path.resolve())
        update_env_values(ENV_PATH, {"OBS_MEDIA_FILE_PATH": abs_path})
        self.log(f"選択を保存しました: {name} (次回配信から有効)")

        def apply_now():
            obs = OBSClient()
            try:
                if not obs.connect():
                    self.log("OBS 未起動のため即時反映はスキップ (明朝の配信開始時に自動適用)")
                    return
                if obs.get_status()["streaming"]:
                    self.log("配信中のため即時反映はスキップ (次回配信から有効)")
                    return
                source = read_env_value(ENV_PATH, "OBS_MEDIA_SOURCE_NAME", DEFAULT_MEDIA_SOURCE)
                result = obs.ensure_media_file(source, abs_path)
                if result is True:
                    self.log(f"OBS に即時反映しました: {name}")
                elif result is False:
                    self.log("OBS は既にこの動画に設定済みです")
                else:
                    self.log("OBS への即時反映に失敗 (明朝の配信開始時に自動適用されます)")
            finally:
                obs.disconnect()

        Thread(target=apply_now, daemon=True).start()

    # ------------------------------------------------------- 設定保存

    def save_settings(self):
        try:
            start_time = f"{self.start_h.get().zfill(2)}:{self.start_m.get().zfill(2)}"
            stop_time = f"{self.stop_h.get().zfill(2)}:{self.stop_m.get().zfill(2)}"

            update_env_values(ENV_PATH, {
                "YOUTUBE_PRIVACY_STATUS": self.privacy_var.get(),
                "OBS_MEDIA_SOURCE_NAME": self.media_entry.get(),
                "YOUTUBE_RESERVATION_BUFFER_MINUTES": self.buffer_entry.get(),
                "STREAM_START_TIME": start_time,
                "STREAM_STOP_TIME": stop_time,
            })

            # plist の更新 (Macの起動時刻は配信開始の1分前、準備開始は10分前に自動設定)
            try:
                h = int(self.start_h.get())
                m = int(self.start_m.get())
                start_mins = h * 60 + m
                launch_mins = (start_mins - 1) % 1440
                launch_h, launch_m = launch_mins // 60, launch_mins % 60
                prepare_mins = (start_mins - 10) % 1440
                prepare_h, prepare_m = prepare_mins // 60, prepare_mins % 60
            except Exception:
                launch_h, launch_m = 6, 59
                prepare_h, prepare_m = 6, 50

            write_schedule("config/launchd/jp.radio-calisthenics-together.start.plist", launch_h, launch_m)
            write_schedule("config/launchd/jp.radio-calisthenics-together.stop.plist", int(self.stop_h.get()), int(self.stop_m.get()))
            prepare_plist = "config/launchd/jp.radio-calisthenics-together.prepare.plist"
            if os.path.exists(prepare_plist):
                write_schedule(prepare_plist, prepare_h, prepare_m)

            # install_launchd.sh の実行
            subprocess.run([os.path.join(PROJECT_ROOT, "scripts", "install_launchd.sh")], check=True)

            self.log(f"保存完了: YouTube予約 {start_time}")
            self.log(f"スケジュール更新: 準備開始 {prepare_h:02d}:{prepare_m:02d}, 配信処理開始 {launch_h:02d}:{launch_m:02d}")
        except Exception as e:
            self.log(f"保存エラー: {e}")

    # ------------------------------------------------------- 手動操作

    def manual_start(self):
        self.log("手動配信を開始します...")
        def run():
            try:
                # docker_bin(): Finder 起動 (.app) は PATH が最小で "docker" を解決できない
                subprocess.run([docker_bin(), "compose", "run", "--rm", "rct", "python", "scripts/start_stream.py"], check=True)
                self.log("配信開始に成功しました。")
            except Exception as e:
                self.log(f"配信開始失敗: {e}")
        Thread(target=run, daemon=True).start()

    def manual_stop(self):
        self.log("配信を停止します...")
        def run():
            try:
                subprocess.run([docker_bin(), "compose", "run", "--rm", "rct", "python", "scripts/stop_stream.py"], check=True)
                self.log("配信停止に成功しました。")
            except Exception as e:
                self.log(f"配信停止失敗: {e}")
        Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
