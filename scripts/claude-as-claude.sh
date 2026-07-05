#!/bin/bash
exec env ANTHROPIC_API_KEY="$ANTHROPIC_API_TOKEN" claude --setting-sources user --settings '{"attribution":{"commit":"","pr":""}}' "$@"
