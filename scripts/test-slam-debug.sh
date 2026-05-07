#!/bin/bash
# Test script for SLAM debugging - no voxel mapper, with debug output

set -e

echo "=========================================="
echo "  Go2 Mid-360 SLAM Debug Test"
echo "=========================================="
echo ""
echo "Features:"
echo "  - Debug odometry logging"
echo "  - NO voxel mapper (pure SLAM test)"
echo "  - Cost mapper only"
echo ""

# Check sudo
if ! sudo -n true 2>/dev/null; then
    echo "[*] 需要 sudo 密码配置网络:"
    sudo -v
fi

# Detect interfaces
ETH_IFACE=$(ip link show | grep -E "^[0-9]+: en" | grep -v "wl\|docker" | head -1 | awk -F: '{print $2}' | tr -d ' ')
WIFI_IFACE=$(ip link show | grep -E "^[0-9]+: wl" | head -1 | awk -F: '{print $2}' | tr -d ' ')
ETH_IFACE=${ETH_IFACE:-"enx6c1ff7bd072d"}
WIFI_IFACE=${WIFI_IFACE:-"wlp130s0f0"}

echo "网卡: $ETH_IFACE (网线), $WIFI_IFACE (WiFi)"
echo ""

# Configure network
echo "[*] 配置网络..."
sudo ip addr flush dev "$ETH_IFACE" 2>/dev/null || true
sudo ip addr add 192.168.123.100/24 dev "$ETH_IFACE"
sudo ip link set "$ETH_IFACE" up
echo "✓ 网线: 192.168.123.100/24"
echo ""

sleep 2

# Check connectivity
echo "[*] 检查连通性..."
if ping -c 1 192.168.123.20 &>/dev/null; then
    echo "✓ Mid-360 (192.168.123.20)"
else
    echo "✗ Mid-360 不可达"
fi

if ping -c 1 192.168.12.1 &>/dev/null; then
    echo "✓ Go2 (192.168.12.1)"
else
    echo "⚠ Go2 不可达 (检查 WiFi)"
fi
echo ""

# Check venv
if [ ! -d "/home/lenovo/dimos_src/.venv" ]; then
    echo "✗ 未找到虚拟环境"
    exit 1
fi

# Run test
echo "[*] 启动调试版本 (unitree-go2-mid360-test)..."
echo "=========================================="
echo "查看日志中的 [SLAM ODOM] 消息"
echo "浏览器打开: http://localhost:9090"
echo "按 Ctrl+C 停止"
echo "=========================================="
echo ""

cd /home/lenovo/dimos_src
source .venv/bin/activate

export ROBOT_IP=192.168.12.1
export LIDAR_IP=192.168.123.20
export HOST_IP=192.168.123.100
export DIMOS_LOG_LEVEL=DEBUG

dimos run unitree-go2-mid360-test 2>&1 | grep -E "(Starting|SLAM ODOM|Error|error|WARN)"
