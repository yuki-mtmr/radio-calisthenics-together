import tkinter as tk
import customtkinter as ctk
import subprocess
import os
import sys
import re
from threading import Thread
import time

# srcディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from rct.settings import settings

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ラジオ体操自動配信 - 管理パネル")
        self.geometry("650x850")

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
        self.buffer_entry.insert(0, os.getenv("YOUTUBE_RESERVATION_BUFFER_MINUTES", "60"))
        self.buffer_entry.grid(row=2, column=1, padx=20, pady=(10, 0), sticky="w")
        ctk.CTkLabel(self.settings_frame, text="※OBS接続を安定させるための内部的な待機時間です", font=ctk.CTkFont(size=10), text_color="gray").grid(row=3, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="w")

        # メディアソース名
        ctk.CTkLabel(self.settings_frame, text="OBSメディアソース名:", font=self.font_normal).grid(row=4, column=0, padx=20, pady=10, sticky="w")
        self.media_entry = ctk.CTkEntry(self.settings_frame, width=250)
        self.media_entry.insert(0, os.getenv("OBS_MEDIA_SOURCE_NAME", "radio-calisthenics_stickman.mp4"))
        self.media_entry.grid(row=4, column=1, padx=20, pady=10, sticky="w")

        # プライバシー設定
        ctk.CTkLabel(self.settings_frame, text="YouTube公開設定:", font=self.font_normal).grid(row=5, column=0, padx=20, pady=10, sticky="w")
        self.privacy_var = ctk.StringVar(value=os.getenv("YOUTUBE_PRIVACY_STATUS", "public"))
        self.privacy_menu = ctk.CTkOptionMenu(self.settings_frame, values=["public", "unlisted", "private"], variable=self.privacy_var)
        self.privacy_menu.grid(row=5, column=1, padx=20, pady=10, sticky="w")

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

        # ステータス更新スレッド開始
        self.update_status()

    def load_initial_times(self):
        # .env から設定を読み込む補助関数
        def get_env_val(key, default=""):
            if os.path.exists(".env"):
                with open(".env", "r") as f:
                    for line in f:
                        if line.startswith(f"{key}="):
                            return line.split("=", 1)[1].strip()
            return default

        try:
            # 時刻設定 (plist)
            if os.path.exists("config/launchd/jp.radio-calisthenics-together.start.plist"):
                with open("config/launchd/jp.radio-calisthenics-together.start.plist", "r") as f:
                    content = f.read()
                    h = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", content)
                    m = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", content)
                    self.start_h.insert(0, h.group(1) if h else "07")
                    self.start_m.insert(0, m.group(1) if m else "00")

            if os.path.exists("config/launchd/jp.radio-calisthenics-together.stop.plist"):
                with open("config/launchd/jp.radio-calisthenics-together.stop.plist", "r") as f:
                    content = f.read()
                    h = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", content)
                    m = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", content)
                    self.stop_h.insert(0, h.group(1) if h else "07")
                    self.stop_m.insert(0, m.group(1) if m else "30")

            # .env 設定
            self.media_entry.delete(0, "end")
            self.media_entry.insert(0, get_env_val("OBS_MEDIA_SOURCE_NAME", "radio-calisthenics_stickman.mp4"))

            self.buffer_entry.delete(0, "end")
            self.buffer_entry.insert(0, get_env_val("YOUTUBE_RESERVATION_BUFFER_MINUTES", "2"))

            self.privacy_var.set(get_env_val("YOUTUBE_PRIVACY_STATUS", "public"))

            # start/stop_h/m が空の場合は .env から補完
            if not self.start_h.get():
                st = get_env_val("STREAM_START_TIME", "07:00").split(":")
                self.start_h.insert(0, st[0])
                self.start_m.insert(0, st[1])
            if not self.stop_h.get():
                et = get_env_val("STREAM_STOP_TIME", "07:05").split(":")
                self.stop_h.insert(0, et[0])
                self.stop_m.insert(0, et[1])

        except Exception as e:
            print(f"Error loading initial values: {e}")

    def update_status(self):
        def check():
            while True:
                try:
                    result = subprocess.check_output(
                        ["docker", "compose", "run", "--rm", "rct", "python", "scripts/check_status.py"],
                        stderr=subprocess.STDOUT
                    ).decode()
                    self.status_label.configure(text=result.strip(), text_color="white")
                except Exception:
                    self.status_label.configure(text=f"OBS/Dockerに接続できません", text_color="red")
                time.sleep(10)
        Thread(target=check, daemon=True).start()

    def log(self, text):
        self.console.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.console.see("end")

    def update_plist(self, file_path, hour, minute):
        with open(file_path, "r") as f:
            content = f.read()

        content = re.sub(r"(<key>Hour</key>\s*<integer>)\d+(</integer>)", rf"\g<1>{int(hour)}\g<2>", content)
        content = re.sub(r"(<key>Minute</key>\s*<integer>)\d+(</integer>)", rf"\g<1>{int(minute)}\g<2>", content)

        with open(file_path, "w") as f:
            f.write(content)

    def save_settings(self):
        try:
            # .env の更新
            privacy = self.privacy_var.get()
            media = self.media_entry.get()
            buffer = self.buffer_entry.get()
            start_time = f"{self.start_h.get().zfill(2)}:{self.start_m.get().zfill(2)}"
            stop_time = f"{self.stop_h.get().zfill(2)}:{self.stop_m.get().zfill(2)}"

            with open(".env", "r") as f:
                lines = f.readlines()

            new_lines = []
            keys_to_update = {
                "YOUTUBE_PRIVACY_STATUS": privacy,
                "OBS_MEDIA_SOURCE_NAME": media,
                "YOUTUBE_RESERVATION_BUFFER_MINUTES": buffer,
                "STREAM_START_TIME": start_time,
                "STREAM_STOP_TIME": stop_time
            }
            found_keys = set()

            for line in lines:
                key = line.split("=")[0]
                if key in keys_to_update:
                    new_lines.append(f"{key}={keys_to_update[key]}\n")
                    found_keys.add(key)
                else:
                    new_lines.append(line)
            for k, v in keys_to_update.items():
                if k not in found_keys: new_lines.append(f"{k}={v}\n")

            with open(".env", "w") as f:
                f.writelines(new_lines)

            # plist の更新 (Macの起動時刻は、配信開始の1分前に自動設定)
            try:
                h = int(self.start_h.get())
                m = int(self.start_m.get())

                # 1. 配信開始の1分前（既存）
                start_mins = h * 60 + m
                launch_mins = (start_mins - 1) % 1440
                launch_h = launch_mins // 60
                launch_m = launch_mins % 60

                # 2. 準備開始の10分前（新規）
                prepare_mins = (start_mins - 10) % 1440
                prepare_h = prepare_mins // 60
                prepare_m = prepare_mins % 60

            except:
                launch_h, launch_m = 6, 59
                prepare_h, prepare_m = 6, 50

            self.update_plist("config/launchd/jp.radio-calisthenics-together.start.plist", launch_h, launch_m)
            self.update_plist("config/launchd/jp.radio-calisthenics-together.stop.plist", self.stop_h.get(), self.stop_m.get())

            if os.path.exists("config/launchd/jp.radio-calisthenics-together.prepare.plist"):
                self.update_plist("config/launchd/jp.radio-calisthenics-together.prepare.plist", prepare_h, prepare_m)

            # install_launchd.sh の実行
            subprocess.run(["./scripts/install_launchd.sh"], check=True)

            self.log(f"保存完了: YouTube予約 {start_time}")
            self.log(f"スケジュール更新: 準備開始 {prepare_h:02d}:{prepare_m:02d}, 配信処理開始 {launch_h:02d}:{launch_m:02d}")
        except Exception as e:
            self.log(f"保存エラー: {e}")

    def manual_start(self):
        self.log("手動配信を開始します...")
        def run():
            try:
                subprocess.run(["docker", "compose", "run", "--rm", "rct", "python", "scripts/start_stream.py"], check=True)
                self.log("配信開始に成功しました。")
            except Exception as e:
                self.log(f"配信開始失敗: {e}")
        Thread(target=run).start()

    def manual_stop(self):
        self.log("配信を停止します...")
        def run():
            try:
                subprocess.run(["docker", "compose", "run", "--rm", "rct", "python", "scripts/stop_stream.py"], check=True)
                self.log("配信停止に成功しました。")
            except Exception as e:
                self.log(f"配信停止失敗: {e}")
        Thread(target=run).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
