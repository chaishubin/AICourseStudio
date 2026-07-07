AI Course Studio - optional custom fonts
========================================

This directory is scanned during Docker builds and copied to:

  /usr/local/share/fonts/custom/

Put only fonts that you are allowed to redistribute or use in generated
commercial course videos. The project does not bundle proprietary system fonts.

Recommended Simplified Chinese open-source fonts
------------------------------------------------

The Docker image already installs these Debian/Ubuntu font packages:

  - fonts-noto-cjk
    Families: Noto Sans CJK SC, Noto Serif CJK SC
    License: SIL Open Font License 1.1

  - fonts-droid-fallback
    Family: Droid Sans Fallback
    License: Apache 2.0

  - fonts-wqy-zenhei
    Family: WenQuanYi Zen Hei
    License: GPL-2 with font embedding exception

  - fonts-wqy-microhei
    Family: WenQuanYi Micro Hei
    License: Apache 2.0 or GPL-3+ with font exception

Additional open-source families that are suitable if you install them yourself:

  - Source Han Sans SC / CN
  - Source Han Serif SC / CN
  - LXGW WenKai
  - LXGW WenKai Screen
  - AR PL UMing CN
  - AR PL UKai CN
  - AR PL SungtiL GB
  - AR PL KaitiM GB

Usage
-----

1. Copy licensed .ttf, .ttc, or .otf files into this directory.
2. Rebuild the image:

     docker compose --env-file .env -f docker/docker-compose.yml build

3. Restart the service:

     docker compose --env-file .env -f docker/docker-compose.yml up -d

Proprietary font warning
------------------------

Do not copy macOS or Windows system fonts such as PingFang SC, Microsoft YaHei,
SimSun, SimHei, Songti, or Heiti into this directory unless you have confirmed
that your license permits server-side use, redistribution in Docker images, and
embedding/burning the font into generated videos.
