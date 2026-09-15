
# ==================== 更新 / 拉取 ====================

sync: ## 拉取远端最新并硬对齐 origin/master（兼容强制推送，自动暂存未提交改动）
	git fetch origin
	git stash push --include-untracked -m "make sync 自动暂存" || true
	git reset --hard origin/master
	git stash pop || true
	@echo "✅ 已同步 origin/master 最新代码"

# ==================== 推送 ====================

push: ## 推送到所有远程仓库
	git push origin HEAD
	@echo "推送完成！"

push-force: ## 强制推送到所有远程仓库（忽略冲突）
	git push --force origin HEAD
	@echo "强制推送完成！"

# ==================== 代码格式化 ====================

# Python 格式化（ruff 独立二进制，无需 venv/pip；已用官方脚本装到 ~/.local/bin）
format-py:
	"$$HOME/.local/bin/ruff" format .

# JSON / Markdown / YAML 格式化（prettier，npx 自动拉取）
format-web:
	npx --yes prettier --write "**/*.{json,md,yaml,yml}"

# TOML 格式化（taplo，npx 自动拉取）
format-toml:
	npx --yes @taplo/cli format "**/*.toml"

# 纯文本：去除行尾空白、确保文件以换行结尾
format-txt:
	@find . -type f -name '*.txt' -not -path './.git/*' -not -path './.venv/*' -not -path './node_modules/*' -exec sh -c 'for f; do sed -i "" -e "s/[[:space:]]*$$//" "$$f"; last=$$(tail -c1 "$$f" | od -An -tx1 | tr -d " "); [ "$$last" = "0a" ] || printf "\n" >> "$$f"; done' _ {} +

# 一键格式化全部
format: format-py format-web format-toml format-txt
	@echo "✅ 格式化完成"
