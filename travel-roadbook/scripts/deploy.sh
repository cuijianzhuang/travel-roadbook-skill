#!/usr/bin/env bash
# deploy.sh — 把路书 HTML 发布到 Cloudflare Pages 或 Vercel，得到公开 https 链接
#
# 用法:
#     bash deploy.sh cloudflare <路书.html> <项目名>
#     bash deploy.sh vercel     <路书.html> <项目名>
#
# 项目名: 小写字母、数字、连字符，如 trip-2026-chuanxi。同一项目名重复发布会覆盖为最新版，链接不变。
#
# 需要的环境变量（令牌只从环境读取，不要写进路书或仓库）:
#     cloudflare: CLOUDFLARE_API_TOKEN（权限 Cloudflare Pages: Edit）、CLOUDFLARE_ACCOUNT_ID
#     vercel:     VERCEL_TOKEN；团队账号另设 VERCEL_SCOPE（团队 slug）
#
# 依赖: Node.js（npx 会按需下载 wrangler / vercel CLI）
# DRY_RUN=1 时只打印将执行的命令，不联网。
set -euo pipefail

usage() {
  echo "usage: deploy.sh <cloudflare|vercel> <roadbook.html> <project-name>" >&2
  exit 2
}

[ $# -eq 3 ] || usage
provider=$1 html=$2 project=$3

[ -f "$html" ] || { echo "找不到文件: $html" >&2; exit 2; }
[[ "$project" =~ ^[a-z0-9]([a-z0-9-]{0,56}[a-z0-9])?$ ]] || {
  echo "项目名只能用小写字母、数字、连字符，且不以连字符开头或结尾: $project" >&2; exit 2; }

run() {
  if [ "${DRY_RUN:-}" = 1 ]; then echo "+ $*"; else "$@"; fi
}

need() {
  [ "${DRY_RUN:-}" = 1 ] && return 0
  [ -n "${!1:-}" ] || { echo "缺少环境变量 $1" >&2; exit 1; }
}

# 发布目录只放 index.html，避免把 JSON 等源文件一起公开
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
site="$work/$project"
mkdir -p "$site"
cp "$html" "$site/index.html"

case "$provider" in
  cloudflare)
    need CLOUDFLARE_API_TOKEN
    need CLOUDFLARE_ACCOUNT_ID
    # 首次发布先建项目；项目已存在时这一步会报错，忽略即可
    run npx --yes wrangler@4 pages project create "$project" --production-branch main || echo "（项目已存在，继续发布）"
    run npx --yes wrangler@4 pages deploy "$site" --project-name "$project" --branch main --commit-dirty=true
    echo "正式链接: https://$project.pages.dev"
    ;;
  vercel)
    need VERCEL_TOKEN
    scope=()
    [ -n "${VERCEL_SCOPE:-}" ] && scope=(--scope "$VERCEL_SCOPE")
    # 目录名即项目名；--yes 首次发布自动创建并关联项目
    run npx --yes vercel@latest deploy "$site" --prod --yes --token "${VERCEL_TOKEN:-DRY_RUN}" "${scope[@]}"
    echo "正式链接通常为: https://$project.vercel.app（项目名被占用时以上方输出的 Production 链接为准）"
    ;;
  *)
    usage
    ;;
esac
