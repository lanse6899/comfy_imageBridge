# 🔵BB桥接预览 (ImageBridgeX)

一个基于 Impact Pack 的 PreviewBridge 节点复刻的临时能够使用图像桥接预览节点。Impact Pack 如果可以使用后请使用它的。

## 功能特性

- ✅ **图像预览桥接** - 支持在 MaskEditor 中预览和编辑图像
- ✅ **遮罩编辑传递** - 支持编辑和传递图像上的遮罩（Mask）
- ✅ **Clipspace 文件集成** - 自动支持 ComfyUI 的 clipspace 文件系统
- ✅ **遮罩缓存管理** - 智能缓存和恢复遮罩数据
- ✅ **自动清理机制** - 加载新图像时自动清理旧缓存和字段
- ✅ **多模型支持** - 兼容各种图像处理流程

## 节点参数

### 输入参数

#### 必需参数
- **images** (`IMAGE`) - 输入的图像张量
- **image** (`STRING`) - 图像字符串标识符，用于桥接系统（通常由系统自动管理）

#### 可选参数
- **block** (`BOOLEAN`) - 是否在空遮罩时阻止执行
  - `if_empty_mask`: 当遮罩为空时停止执行
  - `never`: 不阻止执行，即使遮罩为空也继续
- **restore_mask** (`SELECT`) - 遮罩恢复策略
  - `never`: 不恢复遮罩，每次从空遮罩开始
  - `always`: 总是恢复上次保存的遮罩
  - `if_same_size`: 仅在图像尺寸相同时恢复遮罩

### 输出

- **IMAGE** - 处理后的图像
- **MASK** - 编辑后的遮罩

## 使用说明

### 基本使用

1. **添加节点**
   - 在 ComfyUI 节点菜单中找到 "🔵BB桥接预览"
   - 将节点添加到工作流中

2. **连接图像**
   - 将图像输出连接到节点的 `images` 输入端口
   - 节点会自动处理图像预览和遮罩编辑

3. **编辑遮罩**
   - 在节点预览区域点击图像
   - 使用 MaskEditor 功能编辑遮罩
   - 编辑后的遮罩会自动保存和传递

### 重要提示

**第一张图像运行时画遮罩可以正常使用，如果想要第二次图像加载绘制遮罩请先清理 `image` 中的选项内容，绘制遮罩即可运行或再次即可！**

### 高级功能

#### 遮罩恢复策略

- **never**: 适合每次都需要重新编辑遮罩的场景
- **always**: 适合需要保留上次编辑结果的场景
- **if_same_size**: 适合图像尺寸固定但内容变化的场景

#### 空遮罩处理

- 设置 `block` 为 `if_empty_mask` 可以在遮罩为空时停止执行
- 这对于需要确保有遮罩才能继续的流程很有用

## 技术细节

### 缓存系统

节点使用独立的缓存系统，包括：
- `image_bridge_x_image_id_map` - 图像 ID 映射
- `image_bridge_x_name_map` - 名称映射
- `image_bridge_x_cache` - 图像缓存
- `image_bridge_x_last_mask_cache` - 遮罩缓存

### 文件存储

- 预览图像保存在 `ComfyUI/temp/ImageBridgeX/` 目录
- 文件命名格式：`IBX-{timestamp}.png`

### 自动清理机制

当加载新图像时，节点会自动：
1. 清理旧的图像缓存
2. 清理旧的遮罩缓存
3. 清空 `image` 字段（通过 `widgets_values`）
4. 生成新的图像标识符

### 与原始节点的区别

- 使用独立的缓存系统，不会与 PreviewBridge 节点冲突
- 文件保存在独立的目录（ImageBridgeX）
- 支持自动清理机制

## 工作流程示例

```
加载图像 → 🔵BB桥接预览 → 编辑遮罩 → 输出图像和遮罩
```

1. 图像输入到节点
2. 节点显示预览图像
3. 用户编辑遮罩
4. 节点输出处理后的图像和遮罩
5. 可以连接到后续处理节点

## 注意事项

⚠️ **重要提示**

- 节点需要 ComfyUI 支持 `ExecutionBlocker` 功能才能使用 `block` 功能
- `restore_mask` 的优先级高于 `block` 设置
- 当图像改变时，旧的缓存会自动清理
- `image` 字段通常由系统自动管理，不建议手动修改

## 故障排除

### 遮罩没有保存
- 检查 `restore_mask` 设置
- 确认遮罩编辑后已保存

### 图像没有更新
- 重启 ComfyUI
- 检查缓存目录权限

### 节点无法执行
- 检查 ComfyUI 版本是否支持
- 查看控制台错误信息

## 更新日志

### v1.0.0
- 初始版本
- 基于 PreviewBridge 复刻
- 添加自动清理机制
- 支持遮罩缓存和恢复

## 许可证

与 ComfyUI-Impact-Pack 相同

## 相关链接

- [ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
