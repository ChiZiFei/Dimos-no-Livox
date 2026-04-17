# Dimos-no-Livox

⚠️ **注意：此为无法显示点云的简化版本**，专为 Unitree Go2 + 官方拓展坞 Mid-360 SLAM 设计。

如需完整点云可视化功能，请使用原版 DimOS 并本地编译 FastLio2。

---

## 简介

DimOS 修改版，用于 Unitree Go2 官方拓展坞 Mid-360 SLAM 集成。

**核心特点：**
- ✅ 零编译（无需 FastLio2/Livox SDK）
- ✅ 官方 SLAM 服务（拓展坞 PC 预装）
- ✅ 官方外参（Unitree SDK2 文档）
- ❌ **无本地点云显示**（通过 WebRTC 传输）

---

## 快速开始

### 硬件连接

```
电脑 ──┬── 网线 ───→ 拓展坞 M8 接口 (192.168.123.x)
     │
     └── WiFi ───→ Go2 热点 (192.168.12.x)
```

### 运行

```bash
cd /home/lenovo/dimos_src
./scripts/start-go2-mid360.sh
```

### 访问可视化

浏览器打开：
- Rerun: http://localhost:9090
- 命令中心: http://localhost:7779

---

## 主要修改

| 功能 | 原版 DimOS | 本版本 |
|------|-----------|--------|
| SLAM 方式 | 本地 FastLio2 | 官方服务（拓展坞） |
| 点云显示 | ✅ 本地渲染 | ❌ WebRTC 传输 |
| 编译需求 | 需编译 Livox SDK | 无需编译 |
| 外参来源 | 手动标定 | Unitree 官方文档 |

详见 [MODIFICATIONS.md](./MODIFICATIONS.md)

---

## 网络架构

```
官方 SLAM (拓展坞 PC 192.168.123.18)
    ↓
Go2 机身整合
    ↓
WebRTC (192.168.12.1)
    ↓
DimOS (本机)
```

---

## 关键文件

```
dimos/robot/unitree/go2/
├── connection.py          # enable_internal_lidar 参数
├── static_tf.py           # Mid-360 官方外参
├── go2.urdf              # 官方安装位姿
└── blueprints/smart/
    └── unitree_go2_mid360.py  # 主 blueprint（无 FastLio2）

scripts/
└── start-go2-mid360.sh    # 一键启动
```

---

## 参考

- Unitree SLAM 服务接口文档（2026-01-20）
- Mid-360 外参：平移 [0.1870, 0, 0.0803]，旋转 13° Y轴

---

## 许可

基于 [DimOS](https://github.com/dimensionalOS/dimos) Apache 2.0 许可修改。
