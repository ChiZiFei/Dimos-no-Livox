#!/bin/bash
# Go2 + Mid-360 双网卡启动脚本
# 网线连接拓展坞 + WiFi 连接 Go2 热点

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Go2 + Mid-360 启动脚本"
echo "=========================================="
echo ""

# 检查是否需要 sudo
if ! sudo -n true 2>/dev/null; then
    echo "[*] 需要 sudo 权限配置网络"
    echo "    请输入 sudo 密码（或使用 Ctrl+C 取消）:"
    sudo -v
fi

# 自动检测网卡
echo "[*] 检测网卡..."

# 检测网线网卡（排除 lo、docker、wl 开头的）
ETH_IFACE=$(ip link show | grep -E "^[0-9]+: en" | grep -v "wl\|docker" | head -1 | awk -F: '{print $2}' | tr -d ' ')

# 检测 WiFi 网卡（wl 开头）
WIFI_IFACE=$(ip link show | grep -E "^[0-9]+: wl" | head -1 | awk -F: '{print $2}' | tr -d ' ')

# 如果没有自动检测到，使用你系统的默认值
ETH_IFACE=${ETH_IFACE:-"enx6c1ff7bd072d"}
WIFI_IFACE=${WIFI_IFACE:-"wlp130s0f0"}

echo "  网线网卡: $ETH_IFACE"
echo "  WiFi网卡: $WIFI_IFACE"
echo ""

# 配置网线（连接拓展坞）
echo "[*] 配置网线连接（拓展坞）..."
sudo ip addr flush dev "$ETH_IFACE" 2>/dev/null || true
sudo ip addr add 192.168.123.100/24 dev "$ETH_IFACE"
sudo ip link set "$ETH_IFACE" up
echo -e "${GREEN}  ✓ 网线配置完成: 192.168.123.100/24${NC}"
echo ""

# 等待网络就绪
sleep 2

# 检查 WiFi 连接
echo "[*] 检查 WiFi 连接（Go2热点）..."
if ip addr show "$WIFI_IFACE" 2>/dev/null | grep -q "192.168.12"; then
    WIFI_IP=$(ip addr show "$WIFI_IFACE" | grep "192.168.12" | awk '{print $2}' | cut -d/ -f1)
    echo -e "${GREEN}  ✓ WiFi 已连接: $WIFI_IP${NC}"
else
    echo -e "${YELLOW}  ⚠ WiFi 未连接到 Go2 热点${NC}"
    echo "    请手动连接 Go2 WiFi 热点后再运行"
    echo "    或者按回车继续（仅测试 SLAM，无法控制机器人）..."
    read -r
fi
echo ""

# 验证连通性
echo "[*] 验证设备连通性..."

# 测试 Mid-360
if ping -c 2 -W 3 192.168.123.20 &>/dev/null; then
    echo -e "${GREEN}  ✓ Mid-360 (192.168.123.20) 可访问${NC}"
else
    echo -e "${RED}  ✗ 无法连接 Mid-360${NC}"
    echo "    请检查:"
    echo "      1. 网线是否插紧到拓展坞 M8 接口"
    echo "      2. Mid-360 是否上电（查看指示灯）"
    echo "      3. 拓展坞 PC 是否启动完成（等待30秒）"
    exit 1
fi

# 测试拓展坞 PC
if ping -c 2 -W 3 192.168.123.18 &>/dev/null; then
    echo -e "${GREEN}  ✓ 拓展坞 PC (192.168.123.18) 可访问${NC}"
else
    echo -e "${YELLOW}  ⚠ 无法连接拓展坞 PC（可能不影响使用）${NC}"
fi

# 测试 Go2
if ping -c 2 -W 3 192.168.12.1 &>/dev/null; then
    echo -e "${GREEN}  ✓ Go2 (192.168.12.1) 可访问${NC}"
else
    echo -e "${YELLOW}  ⚠ 无法连接 Go2（WiFi 未连接）${NC}"
fi
echo ""

# 检查 venv
echo "[*] 检查 Python 环境..."
if [ ! -d "/home/lenovo/dimos_src/.venv" ]; then
    echo -e "${RED}  ✗ 未找到虚拟环境 .venv${NC}"
    echo "    请先运行: uv venv --python 3.12 && uv pip install -e .[base,unitree]"
    exit 1
fi
echo -e "${GREEN}  ✓ 虚拟环境存在${NC}"
echo ""

# 设置环境变量
echo "[*] 配置环境变量..."
export ROBOT_IP=192.168.12.1
export LIDAR_IP=192.168.123.20
export HOST_IP=192.168.123.100

echo "  ROBOT_IP: $ROBOT_IP (Go2 WiFi)"
echo "  LIDAR_IP: $LIDAR_IP (Mid-360)"
echo "  HOST_IP: $HOST_IP (本机网线)"
echo ""

# 激活环境并启动
echo "[*] 启动 DimOS..."
echo "=========================================="
cd /home/lenovo/dimos_src
source .venv/bin/activate

# 尝试导入测试
if python -c "from dimos.robot.unitree.go2.blueprints.smart.unitree_go2_mid360 import unitree_go2_mid360" 2>/dev/null; then
    echo -e "${GREEN}  ✓ 模块导入成功${NC}"
else
    echo -e "${RED}  ✗ 模块导入失败，请检查安装${NC}"
    exit 1
fi
echo ""

# 启动
echo "正在启动: dimos run unitree-go2-mid360"
echo "按 Ctrl+C 停止"
echo "=========================================="
dimos run unitree-go2-mid360
