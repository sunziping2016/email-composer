#!/bin/sh
set -e 

ssh $(cat config.json | jq -r .v2.host) v2ray api stats --json --server="127.0.0.1:1930" | ./usage.py > data/traffic.csv
