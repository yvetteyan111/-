# -*- coding: utf-8 -*-
# pmn_check_pathway_under_h1.py
# 逻辑：在 PlantCyc 搜索框输入名称并回车 → 等待结果页 h1 → 检查 h1 下是否存在 <a href="#PATHWAY">Pathways</a>
# 不进入详情页；只在结果页判断。输入/输出路径硬编码在下方常量里。

import os, csv, time, shutil
from collections import OrderedDict
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FFOptions
from selenium.webdriver.firefox.service import Service as FFService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ======= 修改为你的实际路径/列名 =======
INPUT_CSV    = r"/absolute/path/to/metabolites.csv"     # 输入 CSV
NAME_COLUMN  = "name"                                    # 代谢物名称所在列
OUTPUT_CSV   = r"/absolute/path/to/pmn_has_pathway.csv"  # 输出 CSV
HEADLESS     = True                                       # 无头模式
DELAY_BETWEEN = 0.9                                       # 每个查询间隔（秒）
FIREFOX_BIN  = None  # 例如："/home/ziyan/anaconda3/envs/ingredient/bin/firefox"；若不需要请留 None
# =====================================

HOME = "https://www.plantcyc.org/"
INPUT_ID = "pmn-search-query"
PER_QUERY_TIMEOUT = 18  # 等待结果页 h1 的最大秒数

def read_names_from_csv(path, col):
    """尝试多种编码读取 CSV 指定列，去重保序"""
    tried = []
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936", "big5", "latin1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                r = csv.DictReader(f)
                if col not in r.fieldnames:
                    raise SystemExit(f"CSV 中找不到列 {col}；现有列：{r.fieldnames}")
                names = [(row.get(col) or "").strip() for row in r if (row.get(col) or "").strip()]
            seen, out = set(), []
            for x in names:
                if x not in seen:
                    seen.add(x); out.append(x)
            return out
        except UnicodeDecodeError:
            tried.append(enc); continue
    raise SystemExit(f"无法按这些编码读取：{tried}。请把文件另存为 UTF-8 再试。")

def dismiss_popups(driver):
    for txt in ("Accept", "I agree", "同意", "接受", "OK", "Got it"):
        try:
            for e in driver.find_elements(By.XPATH, f"//button[contains(., '{txt}')]"):
                if e.is_displayed():
                    e.click(); time.sleep(0.2)
        except Exception:
            pass

def has_pathway_link_under_h1(driver) -> bool:
    """
    仅在“首个 h1 下面”查找 <a href="#PATHWAY">Pathways</a>（大小写不敏感）
    不点击任何元素。
    """
    try:
        # 等待 h1 出现（如果上层已等过，这里很快）
        h1 = driver.find_elements(By.TAG_NAME, "h1")
        if not h1:
            return False
        # 在第一个 h1 之后寻找锚链接（文本 Pathways，href="#PATHWAY"）
        # 使用 translate 实现大小写不敏感匹配
        els = driver.find_elements(
            By.XPATH,
            "(//h1)[1]/following::a[translate(@href,'#pathway','#PATHWAY')='#PATHWAY' "
            " and normalize-space(translate(string(.),"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))='pathways']"
        )
        return len(els) > 0
    except Exception:
        return False

def search_one(driver, wait, query):
    """不点击详情；返回 (YES/NO, url, note)"""
    driver.get(HOME)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    dismiss_popups(driver)

    # 输入并提交
    box = wait.until(EC.presence_of_element_located((By.ID, INPUT_ID)))
    box.click()
    try: box.clear()
    except: pass
    box.send_keys(Keys.CONTROL, "a"); box.send_keys(Keys.DELETE)
    box.send_keys(query); box.send_keys(Keys.ENTER)

    # 等待结果页 h1 出现或 URL 变化
    first_url = driver.current_url
    try:
        WebDriverWait(driver, PER_QUERY_TIMEOUT).until(
            lambda d: d.current_url != first_url or len(d.find_elements(By.TAG_NAME, "h1")) > 0
        )
    except Exception:
        pass  # 即使没等到也继续走下面的判断

    # 再给一点时间让页面稳定
    time.sleep(0.6)

    has = has_pathway_link_under_h1(driver)
    return ("YES" if has else "NO", driver.current_url, "ok" if has else "no-pathway-link-under-h1")

def main():
    if not os.path.isfile(INPUT_CSV):
        raise SystemExit(f"找不到输入CSV：{INPUT_CSV}")
    if not shutil.which("geckodriver"):
        raise SystemExit("找不到 geckodriver；请先安装：conda install -c conda-forge geckodriver")

    opts = FFOptions()
    if HEADLESS:
        opts.add_argument("-headless")
    if FIREFOX_BIN:
        opts.binary_location = FIREFOX_BIN  # 如你需要用 conda 的 Firefox，请在顶部常量里设置路径

    driver = webdriver.Firefox(service=FFService(), options=opts)
    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 20)

    try:
        queries = read_names_from_csv(INPUT_CSV, NAME_COLUMN)
        rows = []
        for i, q in enumerate(queries, 1):
            has, url, note = search_one(driver, wait, q)
            rows.append(OrderedDict(query=q, has_pathway=has, hit_url=url, note=note))
            print(f"[{i}/{len(queries)}] {q} -> {has}  ({url})")
            time.sleep(DELAY_BETWEEN)

        os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_CSV)), exist_ok=True)
        with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["query", "has_pathway", "hit_url", "note"])
            w.writeheader(); w.writerows(rows)
        print(f"✓ Done. Wrote {len(rows)} rows to {OUTPUT_CSV}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
