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
  # === English (6) ===
  "(construction technology OR proptech OR \"property technology\" OR \"construction tech\" OR \"construction software\") (new OR launch OR update OR breakthrough OR AI OR automation OR \"artificial intelligence\")"
  "((construction OR building) (funding OR investment OR acquisition OR IPO OR valuation OR partnership OR collaboration OR \"strategic alliance\"))"
  "((construction OR building) (market OR expansion OR global OR international))"
  "((construction OR building) (carbon OR sustainability OR ESG OR \"circular economy\" OR \"net zero\"))"
  "((construction OR building) (workforce OR labor OR training OR skills OR education))"
  "((SaaS OR platform OR software OR solution OR service) (construction OR building OR architecture) OR \"digital twin\" OR \"3D printing\" OR BIM OR robotics OR \"smart building\" OR \"building information modeling\")"
  # === Chinese (3) ===
  "(\"建筑科技\" OR proptech OR contech OR \"建造科技\" OR \"建筑软件\") (发布 OR 更新 OR 突破 OR AI OR 自动化 OR 机器人)"
  "((建筑 OR 建造) (融资 OR 投资 OR 收购 OR IPO OR 估值 OR 合作 OR 战略))"
  "(\"建筑科技\" OR \"智能建造\" OR \"绿色建筑\") (平台 OR 项目 OR 落地 OR 模块化 OR 3D打印 OR BIM OR 数字孪生)"
  # === Spanish (3) ===
  "(tecnología de la construcción OR contech OR proptech OR \"software de construcción\") (IA OR robótica OR automatización OR lanzamiento OR innovación)"
  "((construcción OR edificación) (financiación OR inversión OR adquisición OR alianza OR asociación))"
  "((construcción OR edificación) (mercado OR expansión OR global OR internacional))"
  # === Arabic (3) ===
  "(تقنيات البناء OR contech OR proptech OR \"برمجيات البناء\") (ذكاء اصطناعي OR روبوتات OR أتمتة OR إطلاق OR ابتكار)"
  "((بناء OR تشييد) (تمويل OR استثمار OR استحواذ OR شراكة OR تحالف))"
  "((بناء OR تشييد) (سوق OR توسع OR عالمي OR دولي))"
  # === Hindi (3) ===
  "(निर्माण प्रौद्योगिकी OR contech OR proptech OR \"निर्माण सॉफ़्टवेयर\") (AI OR रोबोटिक्स OR स्वचालन OR लॉन्च OR नवीनता)"
  "((निर्माण OR इमारत) (धन जुटाना OR निवेश OR अधिग्रहण OR साझेदारी OR रणनीति))"
  "((निर्माण OR इमारत) (बाज़ार OR विस्तार OR वैश्विक OR अंतर्राष्ट्रीय))"
  # === Japanese (2) ===
  "(建設テック OR コンテック OR プロパテック OR \"建築ソフト\") (AI OR ロボット OR 自動化 OR 新製品 OR 発表)"
  "((建設 OR 建築) (資金調達 OR 投資 OR 買収 OR 提携 OR 戦略的))"
  # === Korean (2) ===
  "(건설 기술 OR 콘테크 OR 프로퍼티 테크 OR \"건축 소프트웨어\") (AI OR 로봇 OR 자동화 OR 신제품 OR 출시)"
  "((건설 OR 건축) (자금조달 OR 투자 OR 인수 OR 제휴 OR 전략적))"
  # === German (1) ===
  "(Bautechnologie OR contech OR proptech OR \"Bau-Software\") (KI OR Robotik OR Automatisierung OR Innovation)"
  # === French (1) ===
  "(technologie de la construction OR contech OR proptech OR \"logiciel de construction\") (IA OR robotique OR automatisation OR innovation)"
  # === Russian (1) ===
  "(строительные технологии OR contech OR proptech OR \"строительное ПО\") (ИИ OR робототехника OR автоматизация OR инновация)"
  # === Portuguese (1) ===
  "(tecnologia da construção OR contech OR proptech OR \"software de construção\") (IA OR robótica OR automação OR inovação)"
  # === Turkish (1) ===
  "(inşaat teknolojisi OR contech OR proptech OR \"inşaat yazılımı\") (yapay zeka OR robotik OR otomasyon OR yenilik)"
)

ARGS=(
  --task-name con_tech
  --top-k 10
  --final-event-cap 20
  --output-dir "$TEMP_DIR"
  --max-content-chars 4000
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
