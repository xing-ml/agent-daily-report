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
  "(\"AI agent\" OR \"AI agents\" OR agentic) (\"use case\" OR application OR implementation OR \"real world\" OR \"in the wild\")"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (customer service OR support OR healthcare OR medical OR finance OR banking OR insurance) (implementation OR \"case study\" OR example)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (education OR learning OR school OR marketing OR sales OR e-commerce) (implementation OR \"case study\" OR example)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (coding OR software OR development OR research OR analysis OR data) (implementation OR \"case study\" OR example)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (automation OR workflow OR productivity OR ops OR internal tool) (implementation OR \"case study\" OR example)"
  "(\"AI agent\" OR \"AI agents\" OR agentic) (startup OR company OR enterprise) (funding OR acquisition OR launch OR deployment)"
  "(\"AI Agent\" OR \"AI智能体\" OR 智能体 OR 多智能体) (案例 OR 应用 OR 落地 OR \"真实使用\" OR 工作流)"
  "(智能体 OR AI智能体) (客服 OR 医疗 OR 金融 OR 教育 OR 营销 OR 编程 OR 自动化) (案例 OR 落地 OR 实践)"
  "(\"ИИ-агент\" OR \"ИИ-агенты\" OR \"агентный ИИ\") (кейс OR применение OR \"в реальном мире\" OR автоматизация OR workflow)"
  "((\"AIエージェント\" OR \"自律エージェント\") (活用事例 OR 導入 OR 実運用 OR ワークフロー OR 自動化)) OR ((\"AI 에이전트\" OR \"자율형 에이전트\") (활용 사례 OR 도입 OR 실사용 OR 워크플로우 OR 자동화))"
  "((\"AI एजेंट\" OR \"एजेंटिक AI\") (उपयोग मामला OR कार्यप्रवाह OR स्वचालन OR कार्यान्वयन)) OR ((\"AI ஏஜென்ட்\" OR \"தன்னாட்சி முகவர்\") (பயன்பாட்டு உதாரணம் OR பணிச்சரம் OR தானியக்கம் OR நடைமுறை))"
  "((\"agente de IA\" OR \"agentes de IA\") (caso de uso OR implementación OR automatización OR flujo de trabajo)) OR ((\"agente de IA\" OR \"agentes de IA\") (caso de uso OR implementação OR automação OR fluxo de trabalho))"
  "((\"agent IA\" OR \"agents IA\") (cas d'usage OR déploiement OR automatisation OR workflow)) OR ((\"KI-Agent\" OR \"KI-Agenten\") (Anwendungsfall OR Implementierung OR Automatisierung OR Workflow))"
  "((\"وكيل ذكاء اصطناعي\" OR \"وكلاء الذكاء الاصطناعي\") (حالة استخدام OR تطبيق OR أتمتة OR سير العمل)) OR ((\"هوش مصنوعی عامل\" OR \"ایجنت هوش مصنوعی\") (مورد استفاده OR پیاده‌سازی OR خودکارسازی OR گردش کار)) OR ((\"yapay zeka ajanı\" OR \"AI ajan\") (kullanım durumu OR uygulama OR otomasyon OR iş akışı))"
)

ARGS=(
  --task-name ai_agent_usecase
  --top-k 10
  --final-event-cap 12
  --output-dir "$TEMP_DIR"
  --max-content-chars 4000
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
