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
  "(\"AI agent\" OR \"AI agents\") (launch OR release OR update OR new)"
  "(\"AI agent framework\" OR \"agent platform\" OR \"agent tool\") (new OR released OR launched)"
  "(\"multi-agent\" OR \"multi agent\") (system OR platform OR framework)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (API OR SDK OR tool OR integration OR \"open source\" OR GitHub)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (security OR safety OR alignment OR control OR research OR paper OR arXiv)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (enterprise OR business OR production OR cost OR pricing OR monetization OR benchmark OR evaluation OR test)"
  "(\"AI智能体\" OR \"智能体\" OR \"AI Agent\" OR \"多智能体\") (发布 OR 上线 OR 更新 OR 推出 OR 平台 OR 框架 OR 开源)"
  "(\"AI智能体\" OR \"智能体\" OR \"多智能体\") (API OR SDK OR 工具 OR 集成 OR 企业 OR 生产 OR 安全 OR 对齐 OR 研究 OR 论文)"
  "(\"ИИ-агент\" OR \"ИИ-агенты\" OR \"агентный ИИ\" OR \"мультиагентный\") (релиз OR запуск OR обновление OR платформа OR \"open source\" OR GitHub OR API OR SDK OR безопасность OR исследование OR enterprise)"
  "((\"AIエージェント\" OR \"マルチエージェント\" OR \"自律エージェント\") (リリース OR 発表 OR 公開 OR 更新 OR プラットフォーム OR フレームワーク OR API OR SDK OR GitHub OR 研究)) OR ((\"AI 에이전트\" OR \"멀티 에이전트\" OR \"자율형 에이전트\") (출시 OR 발표 OR 공개 OR 업데이트 OR 플랫폼 OR 프레임워크 OR API OR SDK OR GitHub OR 연구))"
  "((\"AI एजेंट\" OR \"एजेंटिक AI\") (लॉन्च OR अपडेट OR प्लेटफ़ॉर्म OR API OR SDK OR शोध)) OR ((\"AI ஏஜென்ட்\" OR \"தன்னாட்சி முகவர்\") (வெளியீடு OR புதுப்பிப்பு OR தளம் OR API OR ஆய்வு))"
  "((\"agente de IA\" OR \"agentes de IA\") (lanzamiento OR actualización OR plataforma OR API OR GitHub OR investigación)) OR ((\"agente de IA\" OR \"agentes de IA\") (lançamento OR atualização OR plataforma OR API OR GitHub OR pesquisa))"
  "((\"agent IA\" OR \"agents IA\") (lancement OR mise à jour OR plateforme OR API OR GitHub OR recherche)) OR ((\"KI-Agent\" OR \"KI-Agenten\") (Start OR Update OR Plattform OR API OR GitHub OR Forschung))"
  "((\"وكيل ذكاء اصطناعي\" OR \"وكلاء الذكاء الاصطناعي\") (إطلاق OR تحديث OR منصة OR API OR GitHub OR بحث)) OR ((\"هوش مصنوعی عامل\" OR \"ایجنت هوش مصنوعی\") (انتشار OR به‌روزرسانی OR پلتفرم OR API OR GitHub OR پژوهش)) OR ((\"yapay zeka ajanı\" OR \"AI ajan\") (lansman OR güncelleme OR platform OR API OR GitHub OR araştırma))"
)

ARGS=(
  --task-name ai_agent
  --top-k 10
  --final-event-cap 20
  --output-dir "$TEMP_DIR"
  --max-content-chars 4000
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
