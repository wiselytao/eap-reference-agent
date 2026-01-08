#!/usr/bin/env bash

find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type d -name ".*" -prune -exec rm -rf {} +
rm -fr PRD
rm -fr Reference
