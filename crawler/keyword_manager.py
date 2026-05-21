# -*- coding: utf-8 -*-
from typing import List, Dict


CAR_MODEL_ALIASES: Dict[str, List[str]] = {
    "比亚迪秦PLUS": ["秦PLUS", "秦PLUS DM-i", "秦PLUS EV", "比亚迪秦"],
    "特斯拉Model 3": ["Model 3", "特斯拉3", "Tesla Model 3"],
    "比亚迪汉": ["汉EV", "汉DM-i", "比亚迪汉"],
    "特斯拉Model Y": ["Model Y", "特斯拉Y", "Tesla Model Y"],
    "蔚来ES6": ["ES6", "蔚来ES6"],
    "小鹏P7": ["P7", "小鹏P7"],
    "理想L7": ["L7", "理想L7"],
    "问界M7": ["M7", "问界M7", "AITO M7"],
    "宝马3系": ["3系", "宝马3系", "BMW 3系"],
    "奔驰C级": ["C级", "奔驰C", "Mercedes C"],
}

SEARCH_SUFFIXES = [
    "舆情", "投诉", "评价", "召回", "质量",
    "口碑", "问题", "缺点", "优点", "销量",
]


def get_keywords_for_model(car_model: str) -> List[str]:
    keywords = [car_model]
    aliases = CAR_MODEL_ALIASES.get(car_model, [])
    keywords.extend(aliases)
    search_queries = []
    for kw in keywords[:3]:
        for suffix in SEARCH_SUFFIXES[:3]:
            search_queries.append(f"{kw} {suffix}")
    return search_queries


def get_car_model_aliases(car_model: str) -> List[str]:
    aliases = CAR_MODEL_ALIASES.get(car_model, [])
    return [car_model] + aliases
