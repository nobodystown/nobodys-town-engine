#!/bin/bash
# Runs the official town in the background in 20-minute chunks, 16 at once, until day END.
# Usage: ./qloop.sh END LABEL [SPEND_CAP] [EPISODE]   e.g. ./qloop.sh 455 q1_51 45 2   (EPISODE = the year: 1 = 1950, 2 = 1951; default 1)
# Near the end it switches to tiny chunks so it stops within a day of END. Stops on the spend cap, on ANY failed chunk,
# and on any STOPPED status from golive (outside-mind fallback, OpenRouter credit low, API error, day watchdog). Aaron, Nov 20.
cd /home/claude
END=$1; L=$2; CAP=${3:-30}; EP=${4:-1}; TOTAL=0; FAILS=0
day() { python3 -c "import pickle;print(pickle.load(open('nobodys_town/OFFICIAL/state.pkl','rb')).w.day)"; }
while true; do
  D=$(day)
  if [ "$D" -ge "$END" ]; then echo "$(date +%H:%M) $L DONE at day $D total \$$TOTAL" >> $L.progress; break; fi
  MIN=20; [ $((END - D)) -le 12 ] && MIN=0.1
  timeout 1500 python3 -m nt.golive season $EP --budget 10 --minutes $MIN --workers 16 > $L.chunk 2>&1
  cat $L.chunk >> $L.full
  LAST=$(grep '^{' $L.chunk | tail -1)
  if [ -z "$LAST" ]; then
    echo "$(date +%H:%M) ALERT: chunk ended without summary, stopping" >> $L.progress; tail -15 $L.chunk >> $L.progress; break
  fi
  FAILS=0
  case "$LAST" in *STOPPED*) echo "$(date +%H:%M) ALERT: $LAST" >> $L.progress; break;; esac
  SP=$(echo "$LAST" | python3 -c "import sys,json;print(json.load(sys.stdin)['spent_this_session'])")
  TOTAL=$(python3 -c "print(round($TOTAL+$SP,3))")
  echo "$(date +%H:%M) day $(day) total \$$TOTAL :: $(echo "$LAST" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])")" >> $L.progress
  python3 -c "import sys;sys.exit(0 if $TOTAL>$CAP else 1)" && { echo "SPEND CAP \$$CAP hit" >> $L.progress; break; }
done
