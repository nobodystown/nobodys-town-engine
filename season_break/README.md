# Season-break rule fixes (staged, NOT applied)
Approved by Aaron Nov 20 (9:56pm): apply at the end of 1950, between episode 1 and 2, BEFORE day 365 runs.
`stage/base` = the locked rule code (chain head fix 3). `stage/f4` ... `stage/f11` = each fix stacked on the one before.
Apply in order, each as its own logged entry, from /home/claude:
  for n in 4..11: cp stage/f$n/*.py nt/ ; python3 -m nt.golive fix "<reason>" --base stage/f$((n-1))   (fix 4 uses --base stage/base)
Fixes: 4 world never writes a resident's choice/confession/culprit (prompt + second ask) | 5 trip action + world sees who is away |
6 fact sheet "nothing after today" | 7 passers-by leave | 8 newcomer surnames not near-duplicates | 9 outside minds give up after 30s |
10 world never repeats an event (second ask) | 11 residents see the posted election notice.
Tested Nov 20: mock year OK; trip test OK; live 2-day TEST copy $1.47, 0 fallbacks. Dice streams untouched (second asks roll no dice).
