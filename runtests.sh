#!/bin/bash
export PYTHONPATH=.
echo "-----------------------------------------"
echo "STARTING FAST MODE TESTS: -fopTs"
python lockdown/test.py -v -fopTs
echo "FINISHED FAST MODE TESTS: -fopTs"
echo "-----------------------------------------"
echo "STARTING STRICT MODE TESTS: -p"
python lockdown/test.py -v -p
echo "FINISHED STRICT MODE TESTS: -p"
