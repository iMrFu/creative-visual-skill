# 视觉钩子策略库 — Hook Library

> 每种钩子策略定义了“怎么让人想点”的一种视觉原理。
> 钩子策略的选择依据是文章的情绪张力类型。

---

## Hook Strategy

```json
{
  "hook_type": "contrast",
  "hook_type_cn": "对比矛盾",
  "principle": "画面同时出现两个对立元素，制造认知冲突，迫使观者停留思考",
  "trigger_conditions": "文章有明确的 conflict_point（矛盾/撕裂）",
  "example_visual": "一只温暖的手 and 一只冰冷的手同时伸向同一个孩子",
  "compatible_composition_strategies": ["dominance", "asymmetric_tension"],
  "tags": ["对比", "矛盾", "冲突", "双面"]
}
```

## Hook Strategy

```json
{
  "hook_type": "scale",
  "hook_type_cn": "尺度悬殊",
  "principle": "极端的大小对比制造压迫感或渺小感，唤起保护欲或紧迫感",
  "trigger_conditions": "文章讲述渺小个体面对巨大挑战",
  "example_visual": "一个孩子站在堆到天花板的书桌前，身影渺小",
  "compatible_composition_strategies": ["negative_space", "dominance"],
  "tags": ["悬殊", "渺小", "压迫", "大小对比"]
}
```

## Hook Strategy

```json
{
  "hook_type": "isolation",
  "hook_type_cn": "孤独聚焦",
  "principle": "一个元素孤立于广阔空间，唤起共情和好奇心——“为什么只有它？”",
  "trigger_conditions": "文章强调孤独、被忽视、少数派的处境",
  "example_visual": "一个人站在空旷的白色广场中央，周围什么都没有",
  "compatible_composition_strategies": ["negative_space", "asymmetric_tension"],
  "tags": ["孤独", "聚焦", "空旷", "单点"]
}
```

## Hook Strategy

```json
{
  "hook_type": "narrative_gap",
  "hook_type_cn": "叙事留白",
  "principle": "画面暗示一个故事但不给结局，观者必须脑补，从而产生探究欲",
  "trigger_conditions": "文章有 curiosity_gap（信息缺口）或未解答的疑问",
  "example_visual": "只看到母亲的背影，看不到她的表情；门半开着但看不到里面",
  "compatible_composition_strategies": ["asymmetric_tension", "close_up"],
  "tags": ["留白", "悬念", "未完成", "半遮"]
}
```

## Hook Strategy

```json
{
  "hook_type": "color_disrupt",
  "hook_type_cn": "色彩打断",
  "principle": "一个元素打破整体色彩和谐，制造视觉刺点，引导注意力",
  "trigger_conditions": "文章有强烈的情绪转折或突兀的对比",
  "example_visual": "温暖画面中一个灰暗的角落；全黑画面中唯一一盏暖灯",
  "compatible_composition_strategies": ["dominance", "asymmetric_tension"],
  "tags": ["色彩", "打断", "刺点", "反差"]
}
```

## Hook Strategy

```json
{
  "hook_type": "emotional_mirror",
  "hook_type_cn": "情绪镜像",
  "principle": "画面直接映射读者此刻的内心状态，产生“这画的就是我”的强烈认同",
  "trigger_conditions": "文章有 empathy_anchor（共鸣锚点）或第二人称召唤",
  "example_visual": "疲惫的家长看到同样疲惫的画中人；深夜伏案的身影",
  "compatible_composition_strategies": ["close_up", "dominance"],
  "tags": ["镜像", "共鸣", "共情", "投射"]
}
```

## Hook Strategy

```json
{
  "hook_type": "fragment",
  "hook_type_cn": "局部特写",
  "principle": "只展示局部细节，留下巨大的想象空间，好奇心驱动点击",
  "trigger_conditions": "文章有敏感或私密的内容，或“不可说”的情绪",
  "example_visual": "只看到握紧的拳头；只看到发红的眼眶；只看到一双小手",
  "compatible_composition_strategies": ["close_up", "negative_space"],
  "tags": ["特写", "局部", "细节", "想象"]
}
```

---

## Composition Strategy

```json
{
  "composition_strategy": "dominance",
  "composition_strategy_cn": "主导构图",
  "principle": "一个超大元素占据画面 60%+，其他元素作为陪衬或压迫源",
  "visual_effect": "强势、不可忽视、压迫感或保护感",
  "layout_keywords": "dominant element occupying 60%+ of frame, other elements subordinate, strong visual hierarchy, massive scale, overwhelming presence"
}
```

## Composition Strategy

```json
{
  "composition_strategy": "asymmetric_tension",
  "composition_strategy_cn": "非对称张力",
  "principle": "主体偏移中心，制造不安定感，视线被牵引而非安放",
  "visual_effect": "紧张、不稳定、有故事感",
  "layout_keywords": "subject placed off-center, asymmetric balance creating visual tension, diagonal leading lines, unstable dynamic composition, visual weight shifted to one side"
}
```

## Composition Strategy

```json
{
  "composition_strategy": "negative_space",
  "composition_strategy_cn": "留白构图",
  "principle": "大面积空白 + 微小主体，空白本身成为叙事元素",
  "visual_effect": "孤独感、强调渺小、呼吸感、禅意",
  "layout_keywords": "extreme negative space surrounding a small subject, vast emptiness emphasizing smallness, generous white space, minimalist isolation, breathing room"
}
```

## Composition Strategy

```json
{
  "composition_strategy": "close_up",
  "composition_strategy_cn": "特写构图",
  "principle": "极端裁切，只留关键细节，拒绝全貌",
  "visual_effect": "亲密、压迫、不可回避、强迫关注",
  "layout_keywords": "extreme close-up cropping, only essential details visible, tight frame cutting off context, forced focus on single element, intimate and unavoidable"
}
```
