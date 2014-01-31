#!/bin/sh

hash=$1

echo "`date` block $hash" >> /app/logs/new.log
if [ ! -f /app/conf/killswitch ]; then
    /usr/local/bin/python /app/bin/sync_server.py -b $hash >> /app/logs/sync_server.log
fi


