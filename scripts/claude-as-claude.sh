#!/usr/bin/env bash

exec claude --setting-sources user --settings '{"attribution":{"commit":"","pr":""},"permissions":{"defaultMode":"bypassPermissions","allow":["Read(*)","Write(*)","Edit(*)"]}}' "$@"