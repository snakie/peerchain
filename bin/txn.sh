#!/bin/sh

hash=$1

echo "`date` tx $hash" >> /app/logs/new.log
if [ ! -f /app/conf/killswitch ]; then
    /usr/local/bin/python /app/bin/sync_server.py -t $hash
fi


