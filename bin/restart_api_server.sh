#!/bin/bash

/app/bin/stop_api_server.sh && /app/bin/start_api_server.sh && sudo find /var/cache/nginx/ -type f -delete
