#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMP_DIR="$PROJECT_DIR/temp"
PYTHON_BIN="${DAILY_REPORT_PYTHON:-$HOME/miniconda3/envs/daily_report_env/bin/python3.11}"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${DAILY_REPORT_PYTHON_FALLBACK:-python3.11}"
fi

mkdir -p "$TEMP_DIR"

QUERIES=(
  "(self media OR \"social media\" OR \"content creator\") (trending OR viral OR trend)"
  "(YouTube OR TikTok OR Instagram OR X OR Twitter) (algorithm OR update OR change)"
  "(influencer OR \"content creator\") (monetization OR revenue OR earnings OR sponsorship OR \"brand deal\")"
  "(AI OR \"artificial intelligence\") (\"content creation\" OR video OR image) (tool OR update)"
  "(podcast OR audio OR \"live streaming\" OR \"live stream\") (new OR launch OR trending OR feature OR update)"
  "((\"social media marketing\" OR \"content marketing\") (tool OR platform OR strategy)) OR ((UGC OR \"user generated content\" OR \"short form video\" OR \"short video\" OR Reels OR TikTok) (trending OR viral OR format OR feature))"
  "(自媒体 OR \"社交媒体\" OR 内容创作者 OR 博主) (趋势 OR 爆款 OR 算法 OR 变现 OR AI工具)"
  "(哔哩哔哩 OR Bilibili OR \"b站\" OR bilibili) (创作者 OR UP主 OR content creator) (平台更新 OR 算法 OR 创作激励 OR 变现 OR 直播 OR platform update OR algorithm OR monetization OR creator incentive)"
  "(小红书 OR Xiaohongshu OR XHS) (算法 OR 变现 OR 算法调整 OR 流量 OR 笔记 OR 创作者 OR algorithm OR algorithm change OR traffic OR creator)"
  "(西瓜视频 OR Xigua Video OR 西瓜) (创作者 OR 变现 OR 流量 OR 算法 OR 内容 OR creator OR monetization OR traffic OR algorithm)"
  "(微信视频号 OR 微信视频 OR Wechat Video OR \"WeChat Video Account\" OR 视频号) (创作者 OR content creator) (变现 OR 直播 OR 流量 OR 算法 OR monetization OR livestream OR traffic OR algorithm)"
  "(\"контент-креатор\" OR блогер OR \"creator economy\") (платформа OR тренд OR монетизация OR AI OR алгоритм)"
  "((クリエイター OR インフルエンサー OR SNS) (トレンド OR 収益化 OR アルゴリズム OR AIツール OR ショート動画)) OR ((크리에이터 OR 인플루언서 OR 소셜미디어) (트렌드 OR 수익화 OR 알고리즘 OR AI 도구 OR 쇼츠))"
  "((\"content creator\" OR influencer) (India OR Hindi OR viral OR monetization OR algorithm)) OR ((\"உள்ளடக்க உருவாக்குபவர்\" OR influencer) (Tamil OR trend OR monetization OR algorithm))"
  "((\"creador de contenido\" OR influencer) (viral OR monetización OR algoritmo OR tendencia)) OR ((\"criador de conteúdo\" OR influencer) (viral OR monetização OR algoritmo OR tendência))"
  "((\"créateur de contenu\" OR influenceur) (viral OR monétisation OR algorithme OR tendance)) OR ((\"Content Creator\" OR Influencer) (Deutschland OR Algorithmus OR Monetarisierung OR Trend))"
  "((\"صانع محتوى\" OR مؤثر) (ترند OR تحقيق الدخل OR خوارزمية OR أداة ذكاء اصطناعي)) OR ((\"تولیدکننده محتوا\" OR اینفلوئنسر) (ترند OR درآمدزایی OR الگوریتم OR ابزار هوش مصنوعی)) OR ((\"içerik üreticisi\" OR influencer) (trend OR para kazanma OR algoritma OR yapay zeka aracı))"
)

ARGS=(
  --task-name selfmedia
  --top-k 10
  --final-event-cap 20
  --output-dir "$TEMP_DIR"
  --max-content-chars 4000
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
