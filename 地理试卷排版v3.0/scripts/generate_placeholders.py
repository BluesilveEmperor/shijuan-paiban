# -*- coding: utf-8 -*-
import json

with open('中间数据/structure.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Question 1-3: 冷链物流产业链
data['document']['sections'][0]['questions'][0]['stem'] = "下图为该中心渔港冷链物流产业链示意图{{image:ph_001}}。天津滨海新区中心渔港拥有京津冀最大冷链产业集群的主导优势是（）"
data['document']['sections'][0]['questions'][0]['placeholders'] = [
    {
        "placeholder_id": "ph_001",
        "token": "{{image:ph_001}}",
        "location_type": "question_stem",
        "owner_id": "question_001",
        "context_before": "下图为该中心渔港冷链物流产业链示意图",
        "context_after": "天津滨海新区中心渔港拥有京津冀最大冷链产业集群",
        "reason": "题干明确提到'下图'，需要插入冷链物流产业链示意图",
        "uncertain": False
    }
]

# Question 7-8: 甘青宁货运
data['document']['sections'][0]['questions'][6]['stem'] = "甘青宁区域城市货运发展水平空间差异化显著，下图示意2010～2020年甘青宁区域城市货运发展水平{{image:ph_002}}。甘青宁区域城市货运发展水平呈现出（）"
data['document']['sections'][0]['questions'][6]['placeholders'] = [
    {
        "placeholder_id": "ph_002",
        "token": "{{image:ph_002}}",
        "location_type": "question_stem",
        "owner_id": "question_007",
        "context_before": "甘青宁区域城市货运发展水平空间差异化显著",
        "context_after": "甘青宁区域城市货运发展水平呈现出",
        "reason": "题干明确提到'下图'，需要插入甘青宁货运发展水平图",
        "uncertain": False
    }
]

# Question 9-10: 锢囚锋
data['document']['sections'][0]['questions'][8]['stem'] = "下图为北半球波动性气旋中锢囚锋形成演化过程示意图{{image:ph_003}}。图示锢囚锋形成原因是（）"
data['document']['sections'][0]['questions'][8]['placeholders'] = [
    {
        "placeholder_id": "ph_003",
        "token": "{{image:ph_003}}",
        "location_type": "question_stem",
        "owner_id": "question_009",
        "context_before": "下图为北半球波动性气旋中锢囚锋形成演化过程示意图",
        "context_after": "图示锢囚锋形成原因是",
        "reason": "题干明确提到'下图'，需要插入锢囚锋示意图",
        "uncertain": False
    }
]

# Question 11-12: 岱海水量
data['document']['sections'][0]['questions'][10]['stem'] = "下图为某年岱海水量收支示意图{{image:ph_004}}。图示年份，岱海湖泊面积变化及主要影响因素是（）"
data['document']['sections'][0]['questions'][10]['placeholders'] = [
    {
        "placeholder_id": "ph_004",
        "token": "{{image:ph_004}}",
        "location_type": "question_stem",
        "owner_id": "question_011",
        "context_before": "下图为某年岱海水量收支示意图",
        "context_after": "图示年份，岱海湖泊面积变化及主要影响因素是",
        "reason": "题干明确提到'下图'，需要插入岱海水量收支示意图",
        "uncertain": False
    }
]

# Question 13-15: 滑坡
data['document']['sections'][0]['questions'][12]['stem'] = "下面左图为滑坡体周边等高线地形图{{image:ph_005}}，右图为滑坡发生前后镇雄县天气状况示意图{{image:ph_006}}。与夏季相比，冬季凉水村发生滑坡的直接诱因是（）"
data['document']['sections'][0]['questions'][12]['placeholders'] = [
    {
        "placeholder_id": "ph_005",
        "token": "{{image:ph_005}}",
        "location_type": "question_stem",
        "owner_id": "question_013",
        "context_before": "下面左图为滑坡体周边等高线地形图",
        "context_after": "右图为滑坡发生前后镇雄县天气状况",
        "reason": "题干明确提到'左图'，需要插入等高线地形图",
        "uncertain": False
    },
    {
        "placeholder_id": "ph_006",
        "token": "{{image:ph_006}}",
        "location_type": "question_stem",
        "owner_id": "question_013",
        "context_before": "右图为滑坡发生前后镇雄县天气状况示意图",
        "context_after": "与夏季相比，冬季凉水村发生滑坡",
        "reason": "题干明确提到'右图'，需要插入天气状况示意图",
        "uncertain": False
    }
]

# Question 16: 枣庄
data['document']['sections'][1]['questions'][0]['materials'][0]['content'] = "枣庄（位置如下图{{image:ph_007}}）因煤而兴，被誉为'百年煤城'"
data['document']['sections'][1]['questions'][0]['placeholders'] = [
    {
        "placeholder_id": "ph_007",
        "token": "{{image:ph_007}}",
        "location_type": "material",
        "owner_id": "material_001",
        "context_before": "枣庄（位置如下图",
        "context_after": "）因煤而兴",
        "reason": "材料提到'位置如下图'，需要插入枣庄位置图",
        "uncertain": False
    }
]

# Question 17: 实验数据表
data['document']['sections'][1]['questions'][1]['materials'][0]['content'] = "下表示意该实验相关信息{{image:ph_008}}"
data['document']['sections'][1]['questions'][1]['placeholders'] = [
    {
        "placeholder_id": "ph_008",
        "token": "{{image:ph_008}}",
        "location_type": "material",
        "owner_id": "material_002",
        "context_before": "下表示意该实验相关信息",
        "context_after": "",
        "reason": "材料提到'下表'，需要插入实验数据表",
        "uncertain": False
    }
]

# Question 18: 苏里南光伏
data['document']['sections'][1]['questions'][2]['materials'][0]['content'] = "我国承建的罗斯贝尔金矿光伏储能项目顺利实现首次并网发电（如下图{{image:ph_009}}），为苏里南矿产资源密集区提供了可复制的方案"
data['document']['sections'][1]['questions'][2]['placeholders'] = [
    {
        "placeholder_id": "ph_009",
        "token": "{{image:ph_009}}",
        "location_type": "material",
        "owner_id": "material_003",
        "context_before": "我国承建的罗斯贝尔金矿光伏储能项目顺利实现首次并网发电",
        "context_after": "为苏里南矿产资源密集区提供了可复制的方案",
        "reason": "材料提到'如下图'，需要插入苏里南光伏项目图",
        "uncertain": False
    }
]

# Question 19: 西西里岛
data['document']['sections'][1]['questions'][3]['materials'][0]['content'] = "下图为西西里岛地理位置及附近地区地形示意图{{image:ph_010}}。有人认为'墨西拿海峡正在变宽'"
data['document']['sections'][1]['questions'][3]['placeholders'] = [
    {
        "placeholder_id": "ph_010",
        "token": "{{image:ph_010}}",
        "location_type": "material",
        "owner_id": "material_004",
        "context_before": "下图为西西里岛地理位置及附近地区地形示意图",
        "context_after": "有人认为'墨西拿海峡正在变宽'",
        "reason": "材料提到'下图'，需要插入西西里岛位置图",
        "uncertain": False
    }
]

with open('中间数据/with_placeholders.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("with_placeholders.json 已生成")