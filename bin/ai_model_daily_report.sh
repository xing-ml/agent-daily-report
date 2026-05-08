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
  "(\"new AI model\" OR \"new LLM\" OR \"released model\" OR \"launched model\")"
  "(\"AI model benchmark\" OR \"model comparison\" OR \"model evaluation\" OR performance OR breakthrough)"
  "(\"open source model\" OR \"open weight model\" OR \"released model\") (GitHub OR Hugging Face OR community)"
  "(LLM OR \"large language model\" OR \"AI model\") (capability OR improvement OR reasoning OR coding OR math OR science)"
  "(\"AI model\" OR \"language model\" OR LLM) (cost OR pricing OR \"per token\" OR API OR inference)"
  "(multimodal OR \"vision model\" OR \"image generation\" OR audio OR video) (new OR released OR update OR benchmark)"
  "(\"AI模型\" OR 大模型 OR 多模态模型) (发布 OR 开源 OR 更新 OR 基准测试 OR 推理 OR 价格)"
  "(\"AI模型\" OR 大模型 OR 语言模型) (能力 OR 推理 OR 编码 OR 企业 OR 微调 OR 训练)"
  "(\"ИИ модель\" OR LLM OR \"мультимодальная модель\") (релиз OR benchmark OR open source OR цена OR capability)"
  "((\"AIモデル\" OR 大規模言語モデル OR マルチモーダルモデル) (リリース OR ベンチマーク OR 価格 OR 能力)) OR ((\"AI 모델\" OR LLM OR 멀티모달 모델) (출시 OR 벤치마크 OR 가격 OR 성능))"
  "((\"AI मॉडल\" OR LLM OR \"मल्टीमॉडल मॉडल\") (रिलीज़ OR बेंचमार्क OR कीमत OR क्षमता)) OR ((\"AI மாதிரி\" OR LLM OR \"பல்மாதிரி மாடல்\") (வெளியீடு OR தரச்சோதனை OR விலை OR திறன்))"
  "((\"modelo de IA\" OR LLM OR \"modelo multimodal\") (lanzamiento OR benchmark OR precio OR capacidad)) OR ((\"modelo de IA\" OR LLM OR \"modelo multimodal\") (lançamento OR benchmark OR preço OR capacidade))"
  "((\"modèle IA\" OR LLM OR \"modèle multimodal\") (lancement OR benchmark OR prix OR capacité)) OR ((\"KI-Modell\" OR LLM OR \"multimodales Modell\") (Release OR Benchmark OR Preis OR Fähigkeit))"
  "((\"نموذج ذكاء اصطناعي\" OR LLM OR \"نموذج متعدد الوسائط\") (إطلاق OR معيار OR سعر OR قدرة)) OR ((\"مدل هوش مصنوعی\" OR LLM OR \"مدل چندوجهی\") (انتشار OR بنچمارک OR قیمت OR توانمندی)) OR ((\"yapay zeka modeli\" OR LLM OR \"çok modlu model\") (lansman OR benchmark OR fiyat OR yetenek))"
)

ARGS=(
  --task-name ai_model
  --top-k 10
  --final-event-cap 20
  --output-dir "$TEMP_DIR"
  --max-content-chars 4000
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
