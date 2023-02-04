#!/bin/bash
first_arg="$1"
shift
echo First argument: "$first_arg"
echo Remaining arguments: "$@"
mserver5 --dbpath=/tmp/mydbfarm/SF-10/$5 --set monet_vault_key=/tmp/mydbfarm/SF-10/$5/.vaultkey &
echo mserver5 --dbpath=/tmp/mydbfarm/SF-10/$5 --set monet_vault_key=/tmp/mydbfarm/SF-10/$5/.vaultkey 
pid1=$!
echo $pid1 > /sys/fs/cgroup/memory/my_cgroup/cgroup.procs
echo $(($first_arg * 1024 * 1024 * 1024)) > /sys/fs/cgroup/memory/my_cgroup/memory.limit_in_bytes
#../run_with_memory_monitor.sh',str(args.memory), "mclient", '-tperformance', '-fraw', '-d', db, queryfile
sleep 2
"$@" &
pid=$!
echo $pid > /sys/fs/cgroup/memory/my_cgroup/cgroup.procs
echo $(($first_arg * 1024 * 1024 * 1024)) > /sys/fs/cgroup/memory/my_cgroup/memory.limit_in_bytes
while true; do
    line=$(ps auxh -q $pid1)
    if [ "$line" == "" ]; then
        break;
    fi
    echo $line >> log.out
    for child in $(pgrep -P $pid1);
    do
      line=$(ps auxh -q $child)
      if [ "$line" == "" ]; then
          continue;
      fi
      echo $line >> log.out
    done
    sleep 0.005
if ! ps -p $pid > /dev/null
then
   kill -9 $pid1
fi
done
awk 'BEGIN { maxvsz=0; maxrss=0; count=0; sum=0} \
    { if ($5>maxvsz) {maxvsz=$5}; if ($6>maxrss) {maxrss=$6};  sum=sum+maxrss; count=count+1; }\
    END { print "vsz=" maxvsz " rss=" maxrss " avgrss=" sum/count;}' log.out
rm log.out

