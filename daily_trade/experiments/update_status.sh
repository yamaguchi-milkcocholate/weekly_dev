#!/bin/bash
# experiments/update_status.sh
# 実験完了後にステータスを自動更新するスクリプト

EXPERIMENT_ID=$1
STATUS=$2
CONFIG_FILE=$3
OUTPUT_FILE=$4

if [ -z "$EXPERIMENT_ID" ] || [ -z "$STATUS" ]; then
    echo "Usage: ./update_status.sh <experiment_id> <status> [config_file] [output_file]"
    echo "Example: ./update_status.sh exp_002 completed config/exp_002_early_stopping_fix.yaml models/exp_002_model_report.json"
    exit 1
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S")
STATUS_FILE="experiments/STATUS.yaml"

echo "Updating experiment status:"
echo "  ID: $EXPERIMENT_ID"
echo "  Status: $STATUS"
echo "  Time: $TIMESTAMP"

# ここで実際のYAML更新ロジックを実装
# 今回は手動更新の案内のみ提供

echo ""
echo "Please manually update $STATUS_FILE with:"
echo "  - experiment: $EXPERIMENT_ID"
echo "  - status: $STATUS"
echo "  - timestamp: $TIMESTAMP"
if [ ! -z "$CONFIG_FILE" ]; then
    echo "  - config: $CONFIG_FILE"
fi
if [ ! -z "$OUTPUT_FILE" ]; then
    echo "  - output: $OUTPUT_FILE"
fi