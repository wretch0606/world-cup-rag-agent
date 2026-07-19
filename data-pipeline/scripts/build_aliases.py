"""
从 Kaggle 数据集自动生成完整的球队别名映射表（含中文名 + FIFA 代码）。
"""
import csv, json
from pathlib import Path

DATASET_PATH = "raw_data/FIFA World Cup 1930-2022 All Match Dataset.csv"
OUTPUT_PATH = "data/team_aliases.json"

# ── 地域分配 ──────────────────────────────────────
UEFA = ["England", "France", "Germany", "Italy", "Spain", "Netherlands", "Portugal",
        "Belgium", "Croatia", "Serbia", "Sweden", "Denmark", "Poland", "Switzerland",
        "Austria", "Hungary", "Czech", "Slovakia", "Romania", "Bulgaria", "Scotland",
        "Wales", "Northern Ireland", "Republic of Ireland", "Norway", "Iceland",
        "Slovenia", "Bosnia", "Greece", "Turkey", "Russia", "Ukraine",
        "Soviet Union", "East Germany", "West Germany", "Yugoslavia",
        "Czechoslovakia", "Serbia and Montenegro"]

CONMEBOL = ["Brazil", "Argentina", "Uruguay", "Chile", "Colombia", "Peru",
            "Paraguay", "Ecuador", "Bolivia"]

AFC = ["Japan", "South Korea", "North Korea", "China", "Australia", "Iran",
       "Saudi Arabia", "Kuwait", "United Arab Emirates", "Iraq", "Qatar"]

CAF = ["Cameroon", "Senegal", "Ghana", "Nigeria", "Ivory Coast", "Morocco", "Egypt",
       "Tunisia", "Algeria", "South Africa", "Togo", "Angola", "Zaire"]

CONCACAF = ["United States", "Mexico", "Costa Rica", "Canada", "Honduras",
            "Jamaica", "El Salvador", "Trinidad and Tobago", "Panama", "Haiti", "Cuba"]

OFC = ["New Zealand"]

# ── 英文 → 中文队名 ──────────────────────────────
EN_TO_CN = {
    "Algeria": "阿尔及利亚", "Angola": "安哥拉", "Argentina": "阿根廷",
    "Australia": "澳大利亚", "Austria": "奥地利", "Belgium": "比利时",
    "Bolivia": "玻利维亚", "Bosnia and Herzegovina": "波黑",
    "Brazil": "巴西", "Bulgaria": "保加利亚", "Cameroon": "喀麦隆",
    "Canada": "加拿大", "Chile": "智利", "China": "中国",
    "Colombia": "哥伦比亚", "Costa Rica": "哥斯达黎加", "Croatia": "克罗地亚",
    "Cuba": "古巴", "Czech Republic": "捷克", "Czechoslovakia": "捷克斯洛伐克",
    "Denmark": "丹麦", "Dutch East Indies": "荷属东印度", "East Germany": "东德",
    "Ecuador": "厄瓜多尔", "Egypt": "埃及", "El Salvador": "萨尔瓦多",
    "England": "英格兰", "France": "法国", "Germany": "德国",
    "Ghana": "加纳", "Greece": "希腊", "Haiti": "海地", "Honduras": "洪都拉斯",
    "Hungary": "匈牙利", "Iceland": "冰岛", "Iran": "伊朗", "Iraq": "伊拉克",
    "Israel": "以色列", "Italy": "意大利", "Ivory Coast": "科特迪瓦",
    "Jamaica": "牙买加", "Japan": "日本", "Kuwait": "科威特",
    "Mexico": "墨西哥", "Morocco": "摩洛哥", "Netherlands": "荷兰",
    "New Zealand": "新西兰", "Nigeria": "尼日利亚", "North Korea": "朝鲜",
    "Northern Ireland": "北爱尔兰", "Norway": "挪威", "Panama": "巴拿马",
    "Paraguay": "巴拉圭", "Peru": "秘鲁", "Poland": "波兰",
    "Portugal": "葡萄牙", "Qatar": "卡塔尔", "Republic of Ireland": "爱尔兰",
    "Romania": "罗马尼亚", "Russia": "俄罗斯", "Saudi Arabia": "沙特阿拉伯",
    "Scotland": "苏格兰", "Senegal": "塞内加尔", "Serbia": "塞尔维亚",
    "Serbia and Montenegro": "塞尔维亚和黑山", "Slovakia": "斯洛伐克",
    "Slovenia": "斯洛文尼亚", "South Africa": "南非", "South Korea": "韩国",
    "Soviet Union": "苏联", "Spain": "西班牙", "Sweden": "瑞典",
    "Switzerland": "瑞士", "Togo": "多哥",
    "Trinidad and Tobago": "特立尼达和多巴哥",
    "Tunisia": "突尼斯", "Turkey": "土耳其", "Ukraine": "乌克兰",
    "United Arab Emirates": "阿联酋", "United States": "美国",
    "Uruguay": "乌拉圭", "Wales": "威尔士", "West Germany": "西德",
    "Yugoslavia": "南斯拉夫", "Zaire": "扎伊尔",
}

# ── 英文 → FIFA 三字母码 ─────────────────────────
FIFA_ID_MAP = {
    "Algeria": "ALG", "Angola": "ANG", "Argentina": "ARG",
    "Australia": "AUS", "Austria": "AUT", "Belgium": "BEL",
    "Bolivia": "BOL", "Bosnia and Herzegovina": "BIH", "Brazil": "BRA",
    "Bulgaria": "BUL", "Cameroon": "CMR", "Canada": "CAN",
    "Chile": "CHI", "China": "CHN", "Colombia": "COL",
    "Costa Rica": "CRC", "Croatia": "CRO", "Cuba": "CUB",
    "Czech Republic": "CZE", "Czechoslovakia": "TCH", "Denmark": "DEN",
    "Dutch East Indies": "DEI", "East Germany": "GDR", "Ecuador": "ECU",
    "Egypt": "EGY", "El Salvador": "SLV", "England": "ENG",
    "France": "FRA", "Germany": "GER", "Ghana": "GHA",
    "Greece": "GRE", "Haiti": "HAI", "Honduras": "HON",
    "Hungary": "HUN", "Iceland": "ISL", "Iran": "IRN",
    "Iraq": "IRQ", "Israel": "ISR", "Italy": "ITA",
    "Ivory Coast": "CIV", "Jamaica": "JAM", "Japan": "JPN",
    "Kuwait": "KUW", "Mexico": "MEX", "Morocco": "MAR",
    "Netherlands": "NED", "New Zealand": "NZL", "Nigeria": "NGA",
    "North Korea": "PRK", "Northern Ireland": "NIR", "Norway": "NOR",
    "Panama": "PAN", "Paraguay": "PAR", "Peru": "PER",
    "Poland": "POL", "Portugal": "POR", "Qatar": "QAT",
    "Republic of Ireland": "IRL", "Romania": "ROU", "Russia": "RUS",
    "Saudi Arabia": "KSA", "Scotland": "SCO", "Senegal": "SEN",
    "Serbia": "SRB", "Serbia and Montenegro": "SCG", "Slovakia": "SVK",
    "Slovenia": "SVN", "South Africa": "RSA", "South Korea": "KOR",
    "Soviet Union": "URS", "Spain": "ESP", "Sweden": "SWE",
    "Switzerland": "SUI", "Togo": "TOG", "Trinidad and Tobago": "TRI",
    "Tunisia": "TUN", "Turkey": "TUR", "Ukraine": "UKR",
    "United Arab Emirates": "UAE", "United States": "USA",
    "Uruguay": "URU", "Wales": "WAL", "West Germany": "FRG",
    "Yugoslavia": "YUG", "Zaire": "ZAI",
}


def guess_confederation(name: str) -> str:
    for t in UEFA:
        if t in name: return "UEFA"
    for t in CONMEBOL:
        if t in name: return "CONMEBOL"
    for t in AFC:
        if t in name: return "AFC"
    for t in CAF:
        if t in name: return "CAF"
    for t in CONCACAF:
        if t in name: return "CONCACAF"
    for t in OFC:
        if t in name: return "OFC"
    return ""


def main():
    # 提取所有球队名
    all_teams = set()
    for enc in ["utf-8-sig", "utf-8", "gbk", "latin-1"]:
        try:
            with open(DATASET_PATH, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    h = row.get("Home Team Name", "").strip()
                    a = row.get("Away Team Name", "").strip()
                    if h: all_teams.add(h)
                    if a: all_teams.add(a)
            break
        except UnicodeError:
            continue

    # 生成映射
    aliases = {}
    teams = {}
    used_ids = set()

    for name in sorted(all_teams):
        # 使用 FIFA 三字母码
        tid = f"team_{FIFA_ID_MAP.get(name, 'UNK')}"
        if tid in used_ids:
            i = 2
            while f"{tid}{i}" in used_ids:
                i += 1
            tid = f"{tid}{i}"
        used_ids.add(tid)

        cn_name = EN_TO_CN.get(name, name)

        # 别名链：英文原样 + 小写 + 中文
        aliases[name] = tid
        aliases[name.lower()] = tid
        aliases[cn_name] = tid
        if cn_name != name:
            aliases[cn_name.lower()] = tid

        conf = guess_confederation(name)
        fifa = FIFA_ID_MAP.get(name, "UNK")
        teams[tid] = {
            "canonical_name": cn_name,
            "confederation": conf,
            "fifa_code": fifa,
        }

    data = {"aliases": aliases, "teams": teams}
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已生成 {len(teams)} 支球队到 {OUTPUT_PATH}")
    for tid, info in sorted(teams.items()):
        print(f"  {tid}: {info['canonical_name']} ({info['confederation']})")


if __name__ == "__main__":
    main()
