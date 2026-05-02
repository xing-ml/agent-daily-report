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
  "(construction technology OR proptech OR \"construction tech\") (new OR launch OR update OR breakthrough)"
  "(AI OR \"artificial intelligence\") (construction OR building OR architecture) OR ((robotics OR autonomous OR automation) (construction OR \"building site\" OR \"construction site\"))"
  "((\"3D printing\" OR \"additive manufacturing\") (construction OR building OR infrastructure)) OR ((BIM OR \"building information modeling\") (new OR update OR software))"
  "((sustainable construction OR \"green building\" OR \"net zero\") (technology OR innovation)) OR ((modular construction OR prefabricated OR prefab) (technology OR innovation))"
  "((construction software OR platform OR SaaS) (funding OR acquisition OR launch)) OR ((smart building OR IoT OR \"internet of things\") (construction OR \"building management\"))"
  "(\"digital twin\" OR \"digital twins\") (construction OR building OR infrastructure)"
  "(\"建筑科技\" OR proptech OR contech OR \"建造科技\") (发布 OR 更新 OR 突破 OR AI OR 机器人 OR BIM OR 数字孪生)"
  "(\"建筑科技\" OR \"智能建造\" OR \"绿色建筑\") (平台 OR 项目 OR 落地 OR 模块化 OR 3D打印)"
  "(\"строительные технологии\" OR contech OR proptech) (ИИ OR робототехника OR BIM OR \"цифровой двойник\" OR запуск)"
  "((建設テック OR コンテック OR スマートビル) (AI OR ロボット OR BIM OR デジタルツイン OR 3Dプリント OR 発表)) OR ((건설 기술 OR 콘테크 OR 스마트빌딩) (AI OR 로봇 OR BIM OR 디지털 트윈 OR 3D프린팅 OR 출시))"
  "((\"निर्माण प्रौद्योगिकी\" OR proptech OR contech) (AI OR रोबोटिक्स OR BIM OR डिजिटल ट्विन OR लॉन्च)) OR ((\"கட்டுமான தொழில்நுட்பம்\" OR contech) (AI OR ரோபோடிக்ஸ் OR BIM OR டிஜிட்டல் ட்வின் OR வெளியீடு))"
  "((\"tecnología de la construcción\" OR contech OR proptech) (IA OR robótica OR BIM OR \"gemelo digital\" OR lanzamiento)) OR ((\"tecnologia da construção\" OR contech OR proptech) (IA OR robótica OR BIM OR \"gêmeo digital\" OR lançamento))"
  "((\"technologie de la construction\" OR contech OR proptech) (IA OR robotique OR BIM OR \"jumeau numérique\" OR lancement)) OR ((\"Bautechnologie\" OR contech OR proptech) (KI OR Robotik OR BIM OR \"digitaler Zwilling\" OR Start))"
  "((\"تقنيات البناء\" OR contech OR proptech) (ذكاء اصطناعي OR روبوتات OR BIM OR \"توأم رقمي\" OR إطلاق)) OR ((\"فناوری ساخت\" OR contech OR proptech) (هوش مصنوعی OR رباتیک OR BIM OR \"دوقلوی دیجیتال\" OR انتشار)) OR ((\"inşaat teknolojisi\" OR contech OR proptech) (yapay zeka OR robotik OR BIM OR \"dijital ikiz\" OR lansman))"
)

ARGS=(
  --task-name con_tech
  --top-k 10
  --final-event-cap 12
  --output-dir "$TEMP_DIR"
  --max-content-chars 4000
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
