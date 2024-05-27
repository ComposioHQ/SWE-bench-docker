#!/bin/bash

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <directory> <swe_bench_tasks>"
    exit 1
fi

directory=$1
swe_bench_tasks=$2

python generate_report.py \
 --predictions_path $(pwd)/${directory}/all_preds.jsonl \
 --log_dir $(pwd)/${directory}/logs \
 --output_dir $(pwd)/${directory} \
 --swe_bench_tasks ${swe_bench_tasks}
