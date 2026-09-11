#!/usr/bin/env bash
# The whole bench, in the order you want it: can this machine run the stack at
# all, then is the code internally sound, then did the refactor move a contract.
#
#   ./bench/run.sh              everything
#   ./bench/run.sh preflight    hardware / environment only
#   ./bench/run.sh report       contract inventory + orphan analysis
#
# Read-only throughout. Never commands the arm -- see bench/preflight.py SAFETY.
set -uo pipefail
cd "$(dirname "$0")/.."

case "${1:-all}" in
  report)    exec python3 bench/contracts.py report ;;
  preflight) exec python3 bench/preflight.py ;;
esac

pf=0; st=0; ct=0

echo "######################## 1/3  PREFLIGHT ########################"
python3 bench/preflight.py || pf=1

echo; echo "######################## 2/3  STATIC ###########################"
python3 bench/static.py || st=1

echo; echo "######################## 3/3  CONTRACTS ########################"
python3 bench/contracts.py check || ct=1

echo
echo "================================================================"
printf "  preflight  %s\n" "$([ $pf -eq 0 ] && echo 'ok (see its skip list)' || echo 'FAIL')"
printf "  static     %s\n" "$([ $st -eq 0 ] && echo 'ok' || echo 'FAIL')"
printf "  contracts  %s\n" "$([ $ct -eq 0 ] && echo 'ok' || echo 'FAIL')"
echo "================================================================"
echo "Reminder: a green bench means no contract moved and the environment is"
echo "sane. It does NOT mean the robot works. Everything from 'arm moves'"
echo "onward is untested by design and needs a human with the e-stop."

[ $((pf + st + ct)) -eq 0 ]
