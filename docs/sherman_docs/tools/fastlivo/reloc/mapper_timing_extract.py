"""T3.5e B: per-frame algorithm timing the mapper prints itself ('LIO Mapping Time' / 'VIO Time' tables, 'Current Total Time', seconds).
Per stage and for the LIO+VIO sum of each frame (when the two counts match): n, mean, p50, p95, p99, max in ms, and frames over 50 and 100 ms.
usage: mapper_timing_extract.py LABEL=LOG [LABEL=LOG ...]"""
import re, sys
import numpy as np
ansi = re.compile(r'\x1b\[[0-9;]*m')


def row(label, k, a):
    a = np.asarray(a) * 1e3
    return '%-18s %-7s n=%5d  mean %6.2f  p50 %6.2f  p95 %6.2f  p99 %6.2f  max %7.2f ms | >50 ms: %d  >100 ms: %d' % (
        label, k, len(a), a.mean(), *np.percentile(a, [50, 95, 99]), a.max(), (a > 50).sum(), (a > 100).sum())


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
        if v: print(row(label, k, v))
    if cur['LIO'] and len(cur['LIO']) == len(cur['VIO']):
        print(row(label, 'LIO+VIO', np.array(cur['LIO']) + np.array(cur['VIO'])))
