#!/usr/bin/env bash

exec claude --include-partial-messages --setting-sources user --settings '{"attribution":{"commit":"","pr":""}}' "$@"