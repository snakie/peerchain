#!/bin/bash

SERVER=/app/bin/sync_server.py
LOG=/app/logs/new.log

# LAST_BLOCKS=$(grep block $LOG | tail | awk {'print $8'} | xargs)
# for block in $LAST_BLOCKS; do
#     $SERVER -b $block -n
# done

LAST_TX=$(grep tx $LOG | tail | awk {'print $8'} | xargs)
for tx in $LAST_TX; do
    $SERVER -t $tx -n
done

