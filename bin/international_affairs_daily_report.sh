#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMP_DIR="$PROJECT_DIR/temp"
PYTHON_BIN="${DAILY_REPORT_PYTHON:-$HOME/miniconda3/envs/daily-report-env/bin/python3.11}"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${DAILY_REPORT_PYTHON_FALLBACK:-python3.11}"
fi

mkdir -p "$TEMP_DIR"

QUERIES=(
  "(\"US Israel Iran\" OR \"United States Israel Iran\") (war OR conflict OR strike OR attack) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((UK OR Britain OR Canada OR Australia) (Israel Iran) (war OR conflict OR \"Middle East\") (statement OR position OR stance)) OR ((France OR Macron OR Germany OR Scholz) (Israel Iran) (war OR conflict OR position)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(EU OR \"European Union\" OR Europe) (Israel Iran) (war OR conflict OR sanctions OR statement OR diplomacy) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((India OR Modi) (Israel Iran) (war OR conflict)) OR ((Türkiye OR Saudi OR UAE) (Israel Iran) (war OR conflict OR statement)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(\"美以伊\" OR 美国 OR 以色列 OR 伊朗) (冲突 OR 战争 OR 空袭 OR 制裁 OR 表态) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(中东 OR 伊朗 OR 以色列) (中国 OR 外交部 OR 立场 OR 冲突 OR 谈判) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(США OR Израиль OR Иран) (война OR конфликт OR удар OR санкции OR заявление) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((Россия OR Путин OR \"Израиль Иран\") (война OR конфликт) (позиция OR заявление)) OR ((Европа OR ЕС) (Израиль Иран) (санкции OR позиция)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(इज़राइल OR ईरान OR अमेरिका) (युद्ध OR संघर्ष OR हमला OR बयान OR प्रतिबंध) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(இஸ்ரேல் OR ஈரான் OR அமெரிக்கா) (போர் OR மோதல் OR தாக்குதல் OR நிலைப்பாடு OR தடைகள்) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((Israel OR Irán OR Estados Unidos) (guerra OR conflicto OR ataque OR sanciones OR postura)) OR ((Israel OR Irã OR Estados Unidos) (guerra OR conflito OR ataque OR sanções OR posição)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((Israël OR Iran OR États-Unis) (guerre OR conflit OR frappe OR sanctions OR position)) OR ((Israel OR Iran OR USA) (Krieg OR Konflikt OR Angriff OR Sanktionen OR Haltung)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((إسرائيل OR إيران OR أمريكا) (حرب OR صراع OR هجوم OR عقوبات OR موقف)) OR ((Türkiye OR Suudi Arabistan OR BAE) (İsrail OR İran) (سavaş OR çatışma OR yaptırım OR tutum)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(ישראל OR איראן OR ארה\"ב) (מלחמה OR עימות OR תקיפה OR הצהרה OR סנקציות) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "(ایران OR اسرائیل OR آمریکا) (جنگ OR درگیری OR حمله OR موضع OR تحریم) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
  "((日本 OR 日本政府) (イスラエル OR イラン) (紛争 OR 攻撃 OR 制裁 OR 立場)) OR ((한국 OR 한국정부) (이스라엘 OR 이란) (전쟁 OR 공습 OR 제재 OR 입장)) -site:wikipedia.org -site:youtube.com -site:*.wikipedia.org -site:youtu.be"
)

ARGS=(
  --task-name international_affairs
  --top-k 10
  --final-event-cap 20
  --output-dir "$TEMP_DIR"
  --max-content-chars 4500
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
