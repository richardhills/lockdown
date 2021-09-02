#!/bin/bash
export PYTHONPATH=.
#echo "STARTING NO RTTI TEST - FASTEST"
#python lockdown/test.py -t
#echo "FINISHED NO RTTI TEST - FASTEST"
echo "-----------------------------------------"
echo "STARTING FAST MODE TESTS"
python lockdown/test.py -fopT
echo "FINISHED FAST MODE TESTS"
echo "-----------------------------------------"
#echo "STARTING DEBUG MODE, NO RTTI TESTS"
#python lockdown/test.py -dt
#echo "FINISHED DEBUG MODE, NO RTTI TESTS"
echo "-----------------------------------------"
echo "STARTING STRICT MODE TESTS"
python lockdown/test.py -spr
echo "FINISHED STRICT MODE TESTS"
