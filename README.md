# PPT转视频
## 目前紧急需求
1. 视频中的文字需要大模型提炼（minimax已购买会员）
2. 需要实现多个ppt转视频的任务轮流或并发执行
3. 实现生成视频的记录管理，便于多个任务执行后下载
4. 视频字幕生成（内容与音频内容一致）

## 后续需求
1. 视频中每一页PPT的音频文字提供编辑页面（参考下面图片）
- 每一页PPT中的逐字稿提供展示拦
- 内容可进行编辑
- 内容编辑后可以实时保存
- 合成按钮：修改完全部后可以重新合成视频

![image.png](https://raw.gitcode.com/user-images/assets/9590044/a1351810-4895-4fc6-ae77-54976095dfd5/image.png 'image.png')






# 文本转语音
```bash
curl --request POST \
                  --url https://api.minimaxi.com/v1/t2a_v2 \
                  --header 'Authorization: Bearer sk-cp-xxx' \
                  --header 'Content-Type: application/json' \
                  --data '
            {
              "model": "speech-2.8-hd",
              "text": "今天是不是很开心呀(laughs)，当然了！",
              "stream": false,
              "voice_setting": {
                "voice_id": "male-qn-qingse",
                "speed": 1,
                "vol": 1,
                "pitch": 0,
                "emotion": "happy"
              },
              "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1
              },
              "pronunciation_dict": {
                "tone": [
                  "处理/(chu3)(li3)",
                  "危险/dangerous"
                ]
              },
              "subtitle_enable": false
            }
```
## 将内容保存为mp3
```bash
jq '.data.audio' config.json|xxd -r -p > output.mp3
```