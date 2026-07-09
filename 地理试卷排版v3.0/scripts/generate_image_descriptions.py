# -*- coding: utf-8 -*-
import json

image_descriptions = {
    "image_count": 10,
    "analysis_timestamp": "2026-07-09T18:30:00+08:00",
    "images": [
        {
            "image_id": "img_001",
            "file_name": "img_001.png",
            "type": "其他",
            "summary": "试卷标题处的小图片，可能是学科标识符号",
            "keywords": ["符号", "标题"],
            "ocr_text": [],
            "discipline_features": [],
            "clues": [],
            "uncertain": True
        },
        {
            "image_id": "img_002",
            "file_name": "img_002.jpeg",
            "type": "示意图",
            "summary": "冷链物流产业链示意图，显示从产地预冷到消费者的完整流程",
            "keywords": ["冷链", "物流", "产业链", "生鲜", "冷藏运输"],
            "ocr_text": ["产地预冷", "采购", "验收", "包装", "批零", "生鲜农产品供应地", "工厂生产", "预冷", "速冻", "冷藏", "加工", "物流中心冷库", "配货", "冷冻", "分销商冷库", "分拣", "配货", "冷藏", "冷冻", "分拣", "装卸", "配送", "销售", "消费者"],
            "discipline_features": ["产业区位", "区域经济发展", "价值链分工"],
            "clues": ["冷藏运输是关键环节", "包含产地、工厂、物流中心、分销商、消费者五个节点"],
            "uncertain": False
        },
        {
            "image_id": "img_003",
            "file_name": "img_003.jpeg",
            "type": "统计图表",
            "summary": "甘青宁区域城市货运发展水平差异柱状图（2010-2020年）",
            "keywords": ["货运", "差异", "甘青宁", "柱状图", "2010", "2015", "2020"],
            "ocr_text": ["货运水平差异值", "0", "0.1", "0.2", "0.3", "0.4", "年份", "2010年", "2015年", "2020年", "总差异", "地区间差异值", "地区内差异值"],
            "discipline_features": ["区域经济发展", "空间差异", "交通地理"],
            "clues": ["总差异呈上升趋势", "地区间差异大于地区内差异"],
            "uncertain": False
        },
        {
            "image_id": "img_004",
            "file_name": "img_004.png",
            "type": "示意图",
            "summary": "北半球波动性气旋中锢囚锋形成演化过程示意图（形成前/形成后）",
            "keywords": ["锢囚锋", "气旋", "等压线", "锋面", "形成过程"],
            "ocr_text": ["800", "900", "1000", "1100", "1200", "1300", "等压线hPa", "锋面", "形成前", "形成后"],
            "discipline_features": ["天气系统", "锋面气旋", "大气运动"],
            "clues": ["形成前有两个低压中心", "形成后合并为一个低压中心", "锋面发生锢囚"],
            "uncertain": False
        },
        {
            "image_id": "img_005",
            "file_name": "img_005.jpeg",
            "type": "示意图",
            "summary": "岱海水量收支示意图，显示地表径流、地下径流、降水、蒸发、生态补水和人类利用",
            "keywords": ["岱海", "水量平衡", "收支", "生态补水", "蒸发", "降水"],
            "ocr_text": ["地表径流", "2.27×10<sup>6</sup>m<sup>3</sup>", "地下径流", "14.26×10<sup>6</sup>m<sup>3</sup>", "蒸发", "54.72×10<sup>6</sup>m<sup>3</sup>", "降水", "22.03×10<sup>6</sup>m<sup>3</sup>", "生态补水", "3.5×10<sup>6</sup>m<sup>3</sup>", "人类利用", "9.46×10<sup>6</sup>m<sup>3</sup>", "岱海"],
            "discipline_features": ["水量平衡", "湿地生态", "水资源"],
            "clues": ["蒸发量最大", "生态补水为人工补水", "人类利用量较大"],
            "uncertain": False
        },
        {
            "image_id": "img_006",
            "file_name": "img_006.png",
            "type": "等高线图",
            "summary": "镇雄县凉水村滑坡体周边等高线地形图（左图）和滑坡发生前后天气状况图（右图）",
            "keywords": ["等高线", "滑坡", "镇雄县", "凉水村", "气温", "降水量"],
            "ocr_text": ["N", "1800", "1900", "2000", "2100", "等高线(m)", "房屋", "滑坡源", "滑坡区域", "道路", "气温(C)", "降水量(mm)", "滑坡发生", "最低气温(C)", "三小时内降水量(mm)"],
            "discipline_features": ["等值线判读", "地质灾害", "地形分析"],
            "clues": ["等高线密集区为陡坡", "滑坡源位于陡坡上部", "滑坡发生时伴随降水"],
            "uncertain": False
        },
        {
            "image_id": "img_007",
            "file_name": "img_007.jpeg",
            "type": "示意图",
            "summary": "滑坡发生过程示意图，包含①②③④四个阶段",
            "keywords": ["滑坡", "过程", "砂岩", "页岩", "灰岩"],
            "ocr_text": ["砂页岩互层", "灰岩", "①", "②", "③", "④"],
            "discipline_features": ["地质灾害", "地貌演化", "岩石类型"],
            "clues": ["展示滑坡从初始到最终的四个阶段", "涉及砂页岩和灰岩地层"],
            "uncertain": False
        },
        {
            "image_id": "img_008",
            "file_name": "img_008.png",
            "type": "地图",
            "summary": "枣庄市位置及区域示意图",
            "keywords": ["枣庄", "位置", "地图"],
            "ocr_text": [],
            "discipline_features": ["区域定位"],
            "clues": [],
            "uncertain": False
        },
        {
            "image_id": "img_009",
            "file_name": "img_009.png",
            "type": "示意图",
            "summary": "苏里南罗斯贝尔金矿光伏储能项目示意图",
            "keywords": ["苏里南", "光伏", "储能", "金矿"],
            "ocr_text": [],
            "discipline_features": ["能源", "可再生能源"],
            "clues": [],
            "uncertain": False
        },
        {
            "image_id": "img_010",
            "file_name": "img_010.png",
            "type": "地图",
            "summary": "西西里岛地理位置及附近地区地形示意图，显示等高线和埃特纳火山",
            "keywords": ["西西里岛", "地形", "埃特纳火山", "墨西拿海峡", "等高线"],
            "ocr_text": ["N", "15°E", "38°N", "37°N", "墨西拿海峡", "埃特纳火山", "3326米", "阿格里真托", "500", "1000"],
            "discipline_features": ["区域定位", "地形分析", "火山地貌"],
            "clues": ["埃特纳火山位于东北部", "墨西拿海峡位于东北部", "等高线显示中部高四周低"],
            "uncertain": False
        }
    ]
}

with open('中间数据/image_descriptions.json', 'w', encoding='utf-8') as f:
    json.dump(image_descriptions, f, ensure_ascii=False, indent=2)

print("image_descriptions.json 已生成")