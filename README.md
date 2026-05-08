# 书法 8 选 1 人工测评平台

## 生成题库

```bash
python3 generate_quizzes.py
```

脚本从 `../tie_sample_90.json` 和 `../bei_sample_90.json` 读取处理后的帖、碑数据，从 `/mnt/g/YGSF_new_color` 复制目标图和候选参考图到 `images/帖/`、`images/碑/`，并生成 `data/quizzes.json`。默认每类生成 10 套题库，每套 100 题，每题 8 个候选。

## 启动平台

电脑端：

```bash
python3 server_desktop.py
```

浏览器打开 `http://127.0.0.1:9000`。

手机端：

```bash
python3 server_mobile.py
```

手机和电脑连同一局域网后，在手机浏览器打开 `http://<电脑局域网 IP>:9001`。例如电脑 IP 是 `192.168.1.23` 时，打开 `http://192.168.1.23:9001`。

提交后的记录会追加写入 `records/attempts.jsonl`。浏览器本机也会保存一份历史记录，并支持导出 CSV。
