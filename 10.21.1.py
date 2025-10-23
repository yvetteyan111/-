# -*- coding: utf-8 -*-
# 稳健版：主页多入口 + 超时兜底 + pageLoadStrategy=eager + 仅在 h1 下检查 <a href="#PATHWAY">Pathways</a>

import os, csv, time, shutil
from collections import OrderedDict
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FFOptions
from selenium.webdriver.firefox.service import Service as FFService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ======= 修改为你的实际路径/列名 =======
INPUT_CSV     = r"/absolute/path/to/metabolites.csv"      # 输入 CSV
NAME_COLUMN   = "name"                                     # 代谢物名称所在列
OUTPUT_CSV    = r"/absolute/path/to/pmn_has_pathway.csv"   # 输出 CSV
HEADLESS      = True                                       # 无头模式
DELAY_BETWEEN = 0.9                                        # 两次查询间隔（秒）
FIREFOX_BIN   = None  # 例如 "/home/ziyan/anaconda3/envs/ingredient/bin/firefox"
# ======================================

# 主页备选入口（旧浏览器可能对 www 有兼容问题）
HOME_CANDIDATES = [
    "https://plantcyc.org/",
    "https://pmn.plantcyc.org/",
    "https://www.plantcyc.org/",
]
INPUT_ID = "pmn-search-query"
WAIT_H1_TIMEOUT = 18   # 等待结果页 h1
PAGELOAD_TIMEOUT = 45  # 整体 page load 超时

def read_names_from_csv(path, col):
    """尝试多编码读取指定列，去重保序"""
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
            tried.append(enc)
            continue
    raise SystemExit(f"无法按这些编码读取：{tried}。请把文件另存为 UTF-8 再试。")

def dismiss_popups(driver):
    for txt in ("Accept", "I agree", "同意", "接受", "OK", "Got it"):
        try:
            for e in driver.find_elements(By.XPATH, f"//button[contains(., '{txt}')]"):
                if e.is_displayed():
                    e.click(); time.sleep(0.2)
        except Exception:
            pass

def goto_home(driver, wait):
    """尝试多个入口，遇到 Timeout 则 window.stop 再换下一个"""
    last_err = None
    for url in HOME_CANDIDATES:
        try:
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            dismiss_popups(driver)
            # 输入框就绪才算成功
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, INPUT_ID)))
            return True, url
        except TimeoutException as e:
            # 停止加载，换下一个入口
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    return False, str(last_err) if last_err else "unknown-error"

def has_pathway_link_under_h1(driver) -> bool:
    """仅在第一个 <h1> 下找 <a href="#PATHWAY">Pathways</a>（大小写不敏感，不点击任何元素）"""
    try:
        h1s = driver.find_elements(By.TAG_NAME, "h1")
        if not h1s:
            return False
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
    """不进入详情；返回 (YES/NO, url, note)"""
    ok, info = goto_home(driver, wait)
    if not ok:
        return "NO", driver.current_url if hasattr(driver, "current_url") else "", f"home-fail:{info}"

    # 输入并提交
    box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, INPUT_ID)))
    box.click()
    try: box.clear()
    except: pass
    box.send_keys(Keys.CONTROL, "a"); box.send_keys(Keys.DELETE)
    box.send_keys(query); box.send_keys(Keys.ENTER)

    # 等待 h1 或 URL 变化；如果 page load 卡住则 stop()
    first_url = driver.current_url
    try:
        WebDriverWait(driver, WAIT_H1_TIMEOUT).until(
            lambda d: d.current_url != first_url or len(d.find_elements(By.TAG_NAME, "h1")) > 0
        )
    except TimeoutException:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass

    time.sleep(0.6)  # 给动态内容一点缓冲
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

    # 旧 Firefox 对 HTTP/2/3 可能有兼容问题，可强制退回 HTTP/1.1（需要时打开）
    # opts.set_preference("network.http.http3.enabled", False)
    # opts.set_preference("network.http.spdy.enabled.http2", False)

    # 使用较新的 Firefox 二进制（建议用 conda 安装），避免系统里的 60.*
    if FIREFOX_BIN:
        opts.binary_location = FIREFOX_BIN

    # 提前设置 Page Load Strategy 为 'eager'，DOM 就绪即返回
    opts.set_capability("pageLoadStrategy", "eager")

    driver = webdriver.Firefox(service=FFService(), options=opts)
    driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
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
        with open(OUTPUT_CSV, "w", encoding="utf-8", newline=True) as f:
            w = csv.DictWriter(f, fieldnames=["query", "has_pathway", "hit_url", "note"])
            w.writeheader(); w.writerows(rows)
        print(f"✓ Done. Wrote {len(rows)} rows to {OUTPUT_CSV}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
