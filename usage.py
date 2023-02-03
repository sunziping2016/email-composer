#!/usr/bin/env python3
import json
import sys
import pandas as pd


def format_bytes(size):
    power = 2 ** 10
    n = 0
    power_labels = {0: '', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return f'{size:.2f}{power_labels[n]}B'


def main():
    users = {}
    for item in json.load(sys.stdin)['stat']:
        _, email, _, entry = item['name'].split('>>>')
        users.setdefault(email, {})[entry] = int(item['value'])
    data = pd.DataFrame([(k, v['uplink'], v['downlink']) for k, v in users.items()],
                        columns=['email', 'up_traffic', 'down_traffic'])
    data['total_traffic'] = data.up_traffic + data.down_traffic
    data.to_csv(sys.stdout, index=False)


if __name__ == '__main__':
    main()
