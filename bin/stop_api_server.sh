#!/bin/bash

PID=$(ps auwx | grep '/app/bin/api_server.py' | grep -v grep | awk '{ print $2 }')
sudo kill $PID
