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
  "(\"AI engineer\" OR \"AI researcher\" OR \"LLM engineer\" OR \"machine learning engineer\") (job OR hiring OR \"now hiring\" OR \"urgent hire\")"
  "(\"AI agent\" OR \"AI agent developer\" OR \"agent framework\" OR \"AI infrastructure\") (job OR hiring OR \"now hiring\")"
  "(\"LLM\" OR \"large language model\" OR \"AI safety\" OR \"AI governance\") (engineer OR developer OR researcher OR specialist) (job OR hiring)"
  "(科技招聘 OR AI招聘 OR 大模型招聘 OR 猎头) (热门岗位 OR 急招 OR 新兴职位 OR 薪资 OR 招聘趋势)"
  "(AI工程师 OR 算法工程师 OR 智能体 OR AI产品经理) (招聘 OR 岗位 OR 急招 OR 薪资)"
  "(\"ИИ инженер\" OR \"ML инженер\" OR \"исследователь ИИ\") (вакансия OR найм OR зарплата OR срочно)"
  "((AIエンジニア OR LLMエンジニア OR 機械学習 OR AIプロダクトマネージャー) (採用 OR 求人 OR 年収 OR 急募))"
  "((AI 엔지니어 OR LLM 엔지니어 OR 머신러닝 OR AI PM) (채용 OR 연봉 OR 공고 OR 급구))"
  "((\"AI engineer\" OR \"ML engineer\" OR \"LLM engineer\") (India OR Bangalore OR Hyderabad OR Mumbai OR Delhi OR Noida) (hiring OR job OR salary OR opening))"
  "((\"ingeniero de IA\" OR \"ingeniero de machine learning\") (España OR México OR Colombia OR Argentina OR Chile OR Perú) (empleo OR trabajo OR contratacion OR salario OR urgente))"
  "((\"engenheiro de IA\" OR \"engenheiro de machine learning\") (Brasil OR São Paulo OR Rio de Janeiro OR Curitiba) (vaga OR emprego OR contratacao OR salario OR urgente))"
  "((\"ingénieur IA\" OR \"chercheur IA\") (emploi OR recrutement OR salaire OR urgent)) OR ((\"KI-Ingenieur\" OR \"ML-Ingenieur\") (Job OR Einstellung OR Gehalt OR dringend))"
  "((\"مهندس ذكاء اصطناعي\" OR \"باحث ذكاء اصطناعي\") (السعودية OR الإمارات OR قطر OR البحرين OR وظيفة OR توظيف OR راتب))"
  "((\"مهندس هوش مصنوعی\" OR \"پژوهشگر هوش مصنوعی\") (استخدام OR حقوق OR فوری)) OR ((\"yapay zeka mühendisi\" OR \"makine öğrenmesi mühendisi\") (iş OR işe alım OR maaş OR acil))"
  "((\"ingenier AI\" OR \"insinyur AI\" OR \"teknisi AI\") (Indonesia OR Jakarta OR Surabaya) (pekerjaan OR lowongan OR rekrutmen OR gaji)) OR ((\"วิศวกร AI\" OR \"นักพัฒนา AI\") (Thailand OR Bangkok OR หางาน OR จ้าง))"
  "((\"kỹ sư AI\" OR \"kỹ sư machine learning\") (Vietnam OR Hà Nội OR TP.HCM OR tuyển dụng OR việc làm)) OR ((\"AI engineer\" OR \"machine learning engineer\") (Philippines OR Manila OR Cebu) (job OR hiring OR salary))"
  "(AI OR \"artificial intelligence\") (salary OR compensation OR pay OR benefits OR \"hot jobs\" OR \"in demand\")"
  "(AI OR \"artificial intelligence\") (company OR startup OR \"venture backed\") (funding OR investment OR expansion OR hiring)"
  "(\"MLOps\" OR \"AI infrastructure\" OR \"computer vision\" OR \"NLP engineer\" OR \"AI product manager\") (job OR hiring OR \"urgent hire\")"
)

ARGS=(
  --task-name headhunter
  --top-k 10
  --final-event-cap 30
  --output-dir "$TEMP_DIR"
  --max-content-chars 3500
)

for query in "${QUERIES[@]}"; do
  ARGS+=(--query "$query")
done

"$PYTHON_BIN" "$PROJECT_DIR/collector/daily_report_collector.py" "${ARGS[@]}"
