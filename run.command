#!/bin/bash
# API Runner ishga tushirgich.
#  - loyiha ichidagi .venv ishlatiladi (yo'q bo'lsa yaratiladi);
#  - pip xatolari yashirilmaydi: xato bo'lsa tushunarli xabar chiqadi va oyna Enter bosilguncha yopilmaydi;
#  - port band bo'lsa: bizning eski jarayonimiz bo'lsa to'xtatiladi, boshqa dastur bo'lsa O'LDIRILMAYDI (ogohlantiriladi).
#
# Sozlamalar (ixtiyoriy): APIRUNNER_PORT (sukut 5050), APIRUNNER_VENV_ARGS, APIRUNNER_NO_BROWSER=1

cd "$(dirname "$0")" || exit 1
PORT="${APIRUNNER_PORT:-5050}"

pause_and_exit() {
  echo
  printf "Oynani yopish uchun Enter bosing..."
  read -r _ || true
  exit "${1:-1}"
}
fail() {
  echo
  echo "XATO: $1"
  [ -n "$2" ] && echo "$2"
  pause_and_exit 1
}

# 1) Python
command -v python3 >/dev/null 2>&1 || fail "python3 topilmadi." "Python 3.10+ o'rnating: https://www.python.org/downloads/ (yoki: brew install python)"

# 2) Virtual muhit (.venv)
if [ ! -x .venv/bin/python ]; then
  echo "Virtual muhit yaratilmoqda (.venv)..."
  # shellcheck disable=SC2086
  python3 -m venv ${APIRUNNER_VENV_ARGS} .venv || fail ".venv yaratib bo'lmadi." "Qo'lda urinib ko'ring: python3 -m venv .venv"
fi

# 3) Kutubxonalar (requirements.txt o'zgarmagan bo'lsa qayta o'rnatilmaydi — oflayn ham ishlaydi)
STAMP=".venv/.requirements.sha"
CURRENT_SHA="$(shasum requirements.txt 2>/dev/null | cut -d' ' -f1)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP" 2>/dev/null)" != "$CURRENT_SHA" ]; then
  echo "Kutubxonalar o'rnatilmoqda..."
  if ! .venv/bin/python -m pip install -r requirements.txt; then
    fail "Kutubxonalarni o'rnatib bo'lmadi (yuqoridagi pip xabariga qarang)." "Internet ulanishini tekshiring, so'ng qayta ishga tushiring. Qo'lda: .venv/bin/python -m pip install -r requirements.txt"
  fi
  echo "$CURRENT_SHA" > "$STAMP"
fi

# 4) Port: bizning eski jarayon bo'lsa to'xtatamiz, boshqa dastur bo'lsa tegmaymiz
PIDS="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null)"
OTHER=""
for pid in $PIDS; do
  cmd="$(ps -p "$pid" -o command= 2>/dev/null)"
  if echo "$cmd" | grep -Eq 'api_runner\.py|-m apirunner|apirunner/app\.py'; then
    echo "Port $PORT da eski API Runner jarayoni (PID $pid) topildi — to'xtatilmoqda..."
    kill "$pid" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$pid" 2>/dev/null && { echo "  to'xtamadi, majburan to'xtatilmoqda"; kill -9 "$pid" 2>/dev/null; sleep 0.5; }
  else
    OTHER="$OTHER\n  PID $pid: $cmd"
  fi
done
if [ -n "$OTHER" ]; then
  echo
  echo "OGOHLANTIRISH: $PORT port boshqa dastur tomonidan band (men uni o'ldirmadim):"
  printf "%b\n" "$OTHER"
  echo
  echo "Uni o'zingiz to'xtating yoki boshqa port bilan ishga tushiring: APIRUNNER_PORT=5051 ./run.command"
  pause_and_exit 1
fi

# 5) Ishga tushirish
VERSION="$(.venv/bin/python -c 'import apirunner; print(apirunner.__version__)' 2>/dev/null)"
echo "API RUNNER v${VERSION:-?}"
.venv/bin/python api_runner.py
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  fail "API Runner xato bilan to'xtadi (kod $STATUS)." "Yuqoridagi xabarga qarang."
fi
