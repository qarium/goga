.PHONY: install-hooks

install-hooks:
	@git config core.hooksPath .githooks
	@chmod +x .githooks/* 2>/dev/null || true
	@echo "OK: git hooks path set to .githooks"
	@echo "Active hooks:"
	@ls -1 .githooks/ 2>/dev/null | sed 's/^/  - /'
