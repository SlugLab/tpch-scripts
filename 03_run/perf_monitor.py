#!/usr/bin/env python3

import argparse
import glob
import os
import random
import re
import sys
import subprocess
import time

output_avgrss=[]
output_rss=[]

class Issue(Exception):
    def __init__(self, msg):
        self.msg = msg

def writer(outfilename, also_stdout):
    outfile = open(outfilename, 'a')

    def write(fmt, *args):
        line = fmt % args
        if also_stdout:
            print(line)
        print(line, file=outfile)
        outfile.flush()

    return write

def qq(s):
    if '"' in s or '\\' in s:
        raise("Oops")
    return '"' + s + '"'

def run(db, queryfile):
    # We assume $PATH is already set for all MonetDB binary files
    # /usr/bin/env searches the PATH for us
    cmd = ['../run_with_memory_monitor.sh',str(args.memory), "mclient", '-tperformance', '-fraw', '-d', db, queryfile]
    print(" ".join(cmd))
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (res, err) = p.communicate()
    except subprocess.CalledProcessError as e:
        print("Query \"%s\" triggered an exception:" % queryfile, file=sys.stderr)
        raise e
    #print(res,err)
    pt_vsz = re.compile(rb"vsz=\d+ ")
    vsz = int(pt_vsz.search(res).group(0)[4:-1])
    pt_rss = re.compile(rb"rss=\d+ ")
    rss = int(pt_rss.search(res).group(0)[4:-1])
    pt_avgrss = re.compile(rb"avgrss=\d+")
    avgrss = int(pt_avgrss.search(res).group(0)[7:])
    # print(vsz,rss,avgrss)
    #if (output_iter//args.init_no+1)*2 != len(output):
    #    output.append(rss)
    #    output.append(avgrss)
    #else:
    #    if output[(output_iter//args.init_no)*2]<rss:
    #        output[(output_iter//args.init_no)*2]=rss
    #    if output[(output_iter//args.init_no)*2+1]<avgrss:
    #        output[(output_iter//args.init_no)*2+1]=avgrss
    # Look for something like this: clk: 1297.253 ms
    output_rss.append(rss)
    output_avgrss.append(avgrss)
    pattern = re.compile(rb'^clk:\s*(\d+\.\d+)\s*ms\s*$', re.M)
    m = pattern.search(err)
    if not m:
        max = 100
        snippet = err if len(err) <= max else "..." + err[-max:]
        raise Issue("Query \"%s\" failed: %r" % (queryfile, snippet))
    return float(m.group(1))

def main(args):
    global output_rss
    global output_avgrss
    config = args.name or args.db

    outfilename = config + ".csv"
    if args.output:
        if os.path.isdir(args.output):
            outfilename = os.path.join(args.output, outfilename)
        else:
            outfilename = args.output
    if os.path.exists(outfilename):
        write = writer(outfilename, not args.silent)
    else:
        write = writer(outfilename, not args.silent)
        write("dbname,seqno,query,exec_time,perf_dev,dev_pcnt,perf_stts,rss,avgrss,memory")

    queries = sorted(glob.glob('??.sql'))
    queries=['21.sql','22.sql']
    if not queries:
        raise Issue("No queries found")

    # First get the performance baseline: execute each query 5 times
    #   consecutively, remove the slowest execution and compute the average of
    #   the remaining executions as its baseline performance.
    seq = 0
    base_performance = {}
    niters = args.init_no or 10
    for q in queries:
        qtimes = []
        for i in range(niters):
            qtimes.append(run(args.db, q))
        qtimes.remove(max(qtimes))
        base_performance[q] = sum(qtimes)/len(qtimes)
        # also write this normal time to the output file
        name = "q"+os.path.splitext(os.path.basename(q))[0]
        print(qq(config), seq, qq(name), base_performance[q], 0,0,0,max(output_rss),max(output_avgrss),args.memory)
        write("%s,%d,%s,%.2f,%.2f,%.2f%%,%d,%d,%d,%d", qq(config), seq, qq(name), base_performance[q], 0,0,0,max(output_rss),max(output_avgrss),args.memory)
        output_rss=[]
        output_avgrss=[]

    # Now repeatedly run the queries randomly to monitor their performances
    rnd = random.Random(0)
    done = False
    deadline = time.time() + (args.duration or float("inf"))
    patience = args.patience or 0
    threshold = args.threshold or 0.25
    memory = args.memory
    wait = patience
    alert = 0
    while not done:
        seq += 1
        rnd.shuffle(queries)   # randomise query exec.
        for q in queries:
            qtime = run(args.db, q)
            name = "q"+os.path.splitext(os.path.basename(q))[0]
            dev = qtime-base_performance[q]
            devpercnt = dev/base_performance[q]
            if devpercnt > threshold and alert == 0:
                wait -= 1
                if wait == 0:
                    alert = 1
            else:
                if devpercnt < threshold and alert == 1:
                    wait += 1
                    if wait == patience:
                        alert = 0
            write("%s,%d,%s,%.2f,%.2f,%.2f%%,%d,%d,%d,%d", qq(config), seq, qq(name), qtime, dev, devpercnt*100, alert,max(output_rss),max(output_avgrss),args.memory)
            output_rss=[]
            output_avgrss=[]
        # we always finish executing a full query set
        if time.time() >= deadline:
            done = True
            break

    print("DONE! Output written to ", outfilename)
    return 0

parser = argparse.ArgumentParser(description='Repeatedly run benchmark queries and monitor the query performance')
parser.add_argument('db',
                    help='Database name')
parser.add_argument('--name', '-n',
                    help='Config name, used to label the results, defaults to database name')
parser.add_argument('--duration', '-d', type=int,
                    help='After this many seconds no new query set is started, 0 or omitted: to continue indefinitely.')
parser.add_argument('--init_no', '-i', type=int,
                    help='The number of iterations to run to initialise the query base performance, default: 10.')
parser.add_argument('--output', '-o',
                    help='File or directory to write output to, defaults to ./<CONFIG>.csv')
parser.add_argument('--silent', action='store_true',
                    help='Do not write the results to stdout')
parser.add_argument('--patience', '-p', type=int,
                    help='Wait for how many degraded queries before changing the performance status, 0: immediately.')
parser.add_argument('--threshold', '-t', type=float,
                    help='How much slower (in percentage) compared to its baseline performance should we regard a query\'s performance to have degradated, default: 0.25.')
parser.add_argument('--memory', '-m', type=int,default=100,
		help='memory size limit implemented by cgroup')
if __name__ == "__main__":
    try:
        args = parser.parse_args()
        status = main(args)
        sys.exit(status or 0)
    except Issue as e:
        print("An error occurred:", e.msg, file=sys.stderr)
        sys.exit(1)
