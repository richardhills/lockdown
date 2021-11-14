#!/bin/bash
export PYTHONPATH=.
echo "-----------------------------------------"
echo "STARTING FAST MODE TESTS: -fopT"
python lockdown/test.py -v -fopT
echo "FINISHED FAST MODE TESTS: -fopT"
echo "-----------------------------------------"
echo "STARTING STRICT MODE TESTS: -spr"
python lockdown/test.py -v -spr
echo "FINISHED STRICT MODE TESTS: -spr"
