"""T3.5e B: per-frame algorithm timing the mapper prints itself ('LIO Mapping Time' / 'VIO Time' tables, 'Current Total Time', seconds).
usage: mapper_timing_extract.py LABEL=LOG [LABEL=LOG ...]"""
import re, sys
import numpy as np
ansi = re.compile(r'\x1b\[[0-9;]*m')
for arg in sys.argv[1:]:
    label, path = arg.split('=', 1)
    sec, cur = None, {'LIO': [], 'VIO': []}
    for line in open(path, errors='replace'):
        line = ansi.sub('', line)
        if 'LIO Mapping Time' in line: sec = 'LIO'
        elif 'VIO Time' in line: sec = 'VIO'
        elif 'Current Total Time' in line and sec:
            cur[sec].append(float(line.split('|')[2]))
    for k, v in cur.items():
        if v:
            a = np.array(v) * 1e3
            print('%-16s %s n=%5d  mean %7.2f ms  median %7.2f  p95 %7.2f  max %8.2f  (frames over 100 ms: %d)' % (label, k, len(a), a.mean(), np.median(a), np.percentile(a, 95), a.max(), (a > 100).sum()))
