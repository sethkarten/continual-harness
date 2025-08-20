#!/usr/bin/env python3
import requests
import time

print('Testing if server player moves at all...')

server_url = 'http://127.0.0.1:8040'

try:
    # Check initial position
    response = requests.get(f'{server_url}/state', timeout=5)
    state1 = response.json()
    pos1 = state1['player']['position']
    loc1 = state1['player']['location']
    print(f'Initial: {loc1} at ({pos1["x"]}, {pos1["y"]})')

    # Send ONE down action
    print('Sending single DOWN action...')
    response = requests.post(f'{server_url}/action', json={'buttons': ['down']}, timeout=5)
    time.sleep(1.0)

    response = requests.get(f'{server_url}/state', timeout=5)
    state2 = response.json()
    pos2 = state2['player']['position']
    loc2 = state2['player']['location']
    print(f'After 1 DOWN: {loc2} at ({pos2["x"]}, {pos2["y"]})')

    if pos1['x'] != pos2['x'] or pos1['y'] != pos2['y']:
        print('✅ Player IS moving')
    else:
        print('❌ Player NOT moving')

except Exception as e:
    print(f'Error: {e}')