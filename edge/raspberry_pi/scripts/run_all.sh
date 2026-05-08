#!/bin/bash

cd ~/crps_pi_client

source venv/bin/activate

python client.py &
python dashboard_server.py