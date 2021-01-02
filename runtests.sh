#!/bin/bash
export PYTHONPATH=.
#echo "STARTING NO RTTI TEST - FASTEST"
#python lockdown/test.py -t
#echo "FINISHED NO RTTI TEST - FASTEST"
echo "-----------------------------------------"
echo "STARTING NORMAL MODE TESTS"
python lockdown/test.py
echo "FINISHED NORMAL MODE TESTS"
echo "-----------------------------------------"
#echo "STARTING DEBUG MODE, NO RTTI TESTS"
#python lockdown/test.py -dt
#echo "FINISHED DEBUG MODE, NO RTTI TESTS"
echo "-----------------------------------------"
echo "STARTING DEBUG MODE TESTS"
python lockdown/test.py -d
echo "FINISHED DEBUG MODE TESTS"
