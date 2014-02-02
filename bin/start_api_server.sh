#!/bin/sh

sudo -u nginx bash -c 'setsid /app/bin/api_server.py &>> /app/logs/api_server.log &'


