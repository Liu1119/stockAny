#!/bin/bash

echo "================================"
echo "股票定时选股系统"
echo "================================"
echo ""

case "$1" in
    test)
        echo "测试模式：立即执行一次选股任务"
        python3 stock_selector.py
        ;;
    start)
        echo "启动定时任务（每天下午14:30执行）"
        echo "按 Ctrl+C 停止程序"
        echo ""
        python3 scheduler.py
        ;;
    background)
        echo "后台运行定时任务"
        nohup python3 scheduler.py > scheduler.log 2>&1 &
        echo "定时任务已在后台启动"
        echo "日志文件: scheduler.log"
        echo "查看日志: tail -f scheduler.log"
        echo "停止任务: ps aux | grep scheduler.py | grep -v grep | awk '{print $2}' | xargs kill"
        ;;
    status)
        echo "检查定时任务状态"
        if pgrep -f "scheduler.py" > /dev/null; then
            echo "✓ 定时任务正在运行"
            echo "进程ID: $(pgrep -f scheduler.py)"
        else
            echo "✗ 定时任务未运行"
        fi
        ;;
    stop)
        echo "停止定时任务"
        if pgrep -f "scheduler.py" > /dev/null; then
            pkill -f "scheduler.py"
            echo "✓ 定时任务已停止"
        else
            echo "✗ 定时任务未运行"
        fi
        ;;
    *)
        echo "使用方法:"
        echo "  $0 test      - 测试选股功能（立即执行一次）"
        echo "  $0 start     - 启动定时任务（前台运行）"
        echo "  $0 background- 后台运行定时任务"
        echo "  $0 status    - 检查定时任务状态"
        echo "  $0 stop      - 停止定时任务"
        echo ""
        echo "示例:"
        echo "  $0 test      # 测试选股功能"
        echo "  $0 start     # 前台运行"
        echo "  $0 background# 后台运行"
        ;;
esac
