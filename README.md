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