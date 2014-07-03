#!/bin/sh

hash=$1

echo "`date` block $hash" >> /app/logs/new.log
if [ ! -f /app/conf/killswitch ]; then
    /usr/local/bin/python /app/bin/sync_server.py -b $hash &>> /app/logs/sync_server.log 
    BLOCKS=$(curl -s http://localhost/api/blocks/count)
    curl -s -o /dev/null http://localhost/api/series/inflation_rate/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/pow_block_reward/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/pow_difficulty/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/pos_difficulty/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/transactions/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/money_supply/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/mined_coins/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/minted_coins/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/destroyed_fees/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/pow_blocks/$BLOCKS 
    curl -s -o /dev/null http://localhost/api/series/pos_blocks/$BLOCKS 
fi


