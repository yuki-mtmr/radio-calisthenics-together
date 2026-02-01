# Radio Calisthenics Together - プロジェクト固有ルール

## launchd操作ルール

### 必須確認事項

launchdのplistを操作する際は、以下を必ず守ること：

1. **unload後は必ず全plistをロード**
   - `launchctl unload`でワイルドカードを使った場合、アンロードされた全てのplistを個別に`load`すること
   - 一部だけロードして他を忘れることは絶対に禁止

2. **操作後の確認コマンド**
   ```bash
   launchctl list | grep radio-calisthenics
   ```
   4つのタスクが全て表示されることを確認：
   - jp.radio-calisthenics-together.prepare
   - jp.radio-calisthenics-together.start
   - jp.radio-calisthenics-together.stop
   - jp.radio-calisthenics-together.monitor

3. **plistファイルの場所**
   ```
   ~/Library/LaunchAgents/jp.radio-calisthenics-together.*.plist
   ```

### 正しい再読み込み手順

```bash
# 全てアンロード
launchctl unload ~/Library/LaunchAgents/jp.radio-calisthenics-together.*.plist

# 全てロード（個別に指定）
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.prepare.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.start.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.stop.plist
launchctl load ~/Library/LaunchAgents/jp.radio-calisthenics-together.monitor.plist

# 確認
launchctl list | grep radio-calisthenics
```

### 自動修復機能

health_monitor.pyが未ロードのタスクを検出した場合、自動的にロードを試みる。
ただし、これは最後の砦であり、手動操作時に正しく全てをロードすることが前提。

## スケジュール

- 06:45 - monitor（健全性チェック）
- 06:50 - prepare（Docker/OBS起動）
- 06:59 - start（配信開始）
- 07:15 - stop（配信終了）
