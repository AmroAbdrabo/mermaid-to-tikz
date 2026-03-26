#!/usr/bin/env bash

set -euo pipefail

find . -type f \( \
  -name "*.log" -o \
  -name "*.fls" -o \
  -name "*.aux" -o \
  -name "*.fdb_latexmk" -o \
  -name "*.synctex.gz" \
\) -delete
