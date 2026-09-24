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
# pages.dev / vercel.app 子域名全球唯一，名字被别的账号占用时，实际链接会和项目名不同。
# 所以发布后会抓取正式链接，比对 <title> 与本地页面：
#     一致 → 退出码 0；
#     标题不同（链接是别人的站）→ 退出码 3，改用上方输出里的链接；
#     访问不到（多为运行环境的网络限制）→ 提示手动打开确认，退出码 0。VERIFY=0 跳过校验。
#
# 依赖: Node.js（npx 会按需下载 wrangler / vercel CLI）、curl、python3
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

dry() { [ "${DRY_RUN:-}" = 1 ]; }

run() {
  if dry; then echo "+ $*"; else "$@"; fi
}

need() {
  dry && return 0
  [ -n "${!1:-}" ] || { echo "缺少环境变量 $1" >&2; exit 1; }
}

title_of() {
  sed -n '/<title>/{s:.*<title>\(.*\)</title>.*:\1:p;q;}'
}

verify() {
  local url=$1 want got="" page reached=0 i
  if dry; then echo "+ 抓取 $url 比对页面标题"; return 0; fi
  [ "${VERIFY:-1}" = 0 ] && return 0
  want=$(title_of < "$html")
  for i in 1 2 3 4 5; do
    if page=$(curl -fsSL --max-time 20 "$url" 2>/dev/null); then
      reached=1
      got=$(title_of <<<"$page")
      if [ "$got" = "$want" ]; then echo "已验证：$url 的页面标题与本地一致"; return 0; fi
    fi
    [ "$i" = 5 ] || sleep 3
  done
  if [ "$reached" = 1 ]; then
    echo "✗ $url 的标题是「$got」，不是本次发布的「$want」：这个链接不是本次页面，请以上方输出里的链接为准" >&2
    exit 3
  fi
  echo "⚠ 访问不到 $url（可能是运行环境的网络限制），请在手机上打开确认后再交付" >&2
}

# Cloudflare API 查项目：输出 HTTP 状态码，响应写到 $work/cf.json
cf_lookup() {
  curl -sS --max-time 20 -o "$work/cf.json" -w '%{http_code}' \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/pages/projects/$project" 2>/dev/null
}

# 从查询结果取项目真实的 pages.dev 子域名
cf_subdomain() {
  python3 -c 'import json, sys; print(json.load(sys.stdin)["result"]["subdomain"])' < "$work/cf.json" 2>/dev/null
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
    sub=""
    if dry; then
      run npx --yes wrangler@4 pages project create "$project" --production-branch main
    else
      code=$(cf_lookup) || true
      # 只有 API 明确回答“项目不存在”（404 / 8000007）才创建；创建失败（令牌权限、网络等）直接退出
      if [ "$code" = 404 ] || grep -q 8000007 "$work/cf.json" 2>/dev/null; then
        npx --yes wrangler@4 pages project create "$project" --production-branch main
        code=$(cf_lookup) || true
      fi
      if [ "$code" = 200 ]; then sub=$(cf_subdomain) || sub=""; fi
    fi
    run npx --yes wrangler@4 pages deploy "$site" --project-name "$project" --branch main --commit-dirty=true
    # 子域名全球唯一，被别的账号占用时实际子域名和项目名不同；查不到时退回项目名，由标题校验兜底
    case "$sub" in "") sub="$project.pages.dev" ;; *.pages.dev) ;; *) sub="$sub.pages.dev" ;; esac
    url="https://$sub"
    echo "正式链接: $url"
    verify "$url"
    ;;
  vercel)
    need VERCEL_TOKEN
    scope=()
    [ -n "${VERCEL_SCOPE:-}" ] && scope=(--scope "$VERCEL_SCOPE")
    # 目录名即项目名；--yes 首次发布自动创建并关联项目
    # ${scope[@]+...} 写法兼容 macOS 自带的 bash 3.2（set -u 下直接展开空数组会报 unbound variable）
    run npx --yes vercel@59 deploy "$site" --prod --yes --token "${VERCEL_TOKEN:-DRY_RUN}" ${scope[@]+"${scope[@]}"}
    url="https://$project.vercel.app"
    echo "正式链接通常为: $url（项目名被占用时以上方输出的 Production 链接为准）"
    verify "$url"
    ;;
  *)
    usage
    ;;
esac
