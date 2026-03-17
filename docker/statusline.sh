#!/bin/bash
input=$(cat)
full_model=$(echo "$input" | jq -r '.model.display_name')
model=$(echo "$full_model" | awk '{print $1}')
branch=$(git branch --show-current 2>/dev/null || echo "none")
dirty=$(git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null || echo "*")
ctx=$(echo "$input" | jq -r '(.context_window.used_percentage // 0) | round')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd | . * 100 | round | . / 100')

model_lower=$(echo "$full_model" | tr '[:upper:]' '[:lower:]')
case "$model_lower" in
  *opus*)   model_color='\033[1;32m' ;;
  *sonnet*) model_color='\033[1;33m' ;;
  *haiku*)  model_color='\033[1;31m' ;;
  *)        model_color='\033[1;35m' ;;
esac

if [ "$ctx" -gt 80 ]; then
  ctx_color='\033[1;31m'
elif [ "$ctx" -gt 50 ]; then
  ctx_color='\033[1;33m'
else
  ctx_color='\033[1;35m'
fi

if [ "$branch" = "main" ]; then
  branch_color='\033[1;31m'
else
  branch_color='\033[1;35m'
fi

printf '\033[1;35m[dir=%s]\033[0m' "$(basename "$(pwd)")"
printf "${branch_color}[branch=%s%s]\033[0m" "$branch" "$dirty"
printf "${model_color}[model=%s]\033[0m" "$model"
printf "${ctx_color}[ctx=%s%%]\033[0m" "$ctx"
printf '\033[1;35m[cost=$%s]\033[0m\n' "$cost"
