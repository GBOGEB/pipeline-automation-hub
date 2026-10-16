#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${1:-.}"
output_file="${2:-}"
python_bin="${PYTHON_BIN:-python3}"
if [[ -n "$output_file" ]]; then
  "$python_bin" "$script_dir/worker_devkit.py" --config "$script_dir/runner.toml" --plan "$script_dir/worker_plan.json" --repo "$repo_root" --out "$output_file"
else
  "$python_bin" "$script_dir/worker_devkit.py" --config "$script_dir/runner.toml" --plan "$script_dir/worker_plan.json" --repo "$repo_root"
fi
