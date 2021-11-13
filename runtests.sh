#!/bin/bash
export PYTHONPATH=.
echo "-----------------------------------------"
echo "STARTING FAST MODE TESTS"
python lockdown/test.py -v -fopT
echo "FINISHED FAST MODE TESTS"
echo "-----------------------------------------"
echo "STARTING STRICT MODE TESTS"
python lockdown/test.py -v -spr
echo "FINISHED STRICT MODE TESTS"
