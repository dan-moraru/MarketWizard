#!/bin/bash

# Configuration
HOST="3.98.52.120:8433" # Change to localhost:8080 if running locally
NAME="market_wizards"
PASSWORD="L1_Cach3_L0cality#1"
SECURE="--secure" # Remove this if using localhost

# List of scenarios to harvest
SCENARIOS=("normal_market" "stressed_market" "flash_crash" "hft_dominated" "mini_flash_crash")

echo "=========================================="
echo "Starting Data Harvest"
echo "=========================================="

for SCENARIO in "${SCENARIOS[@]}"
do
   echo "Currently collecting: $SCENARIO"
   
   # Run the python script in the background, but we want to kill it after some time
   # or let it run until it finishes naturally if the sim has an end.
   
   # OPTION A: Run until simulation ends (Best if sim has a fixed length)
   python data_collector.py --name "$NAME" --password "$PASSWORD" --host "$HOST" --scenario "$SCENARIO" $SECURE
   
   echo "Finished $SCENARIO. Sleeping 5s..."
   sleep 5
done

echo "All scenarios collected!"
