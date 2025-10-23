from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
import random
import os

def main():
    # 配置项
    TARGET_RANGE = (1000, 2000)  # 第1001-2000个（对应索引1000-1999，左闭右开）
    TIMEOUT = 20000  # 元素等待超时时间（毫秒）
    RANDOM_DELAY_RANGE = (0.8, 1.5)  # 输入间隔（秒）

    # 打印文件保存路径
    current_dir = os.getcwd()
    save_file_path = os.path.join(current_dir, 'metabolite_with_pathway.csv')
    print(f"实时保存路径：{save_file_path}")

    # 读取CSV数据并筛选第1001-2000个代谢物
    try:
        metabolite_df = pd.read_csv('metabolite.csv')
        metabolite_col = next((col for col in metabolite_df.columns if col.lower() == 'metabolite'), None)
        if metabolite_col is None:
            print("未找到'metabolite'列，退出")
            return
        
        # 初始化has_pathway列（若不存在）
        if 'has_pathway' not in metabolite_df.columns:
            metabolite_df['has_pathway'] = ''
        
        # 筛选目标区间代谢物（避免越界）
        metabolites_all = metabolite_df[metabolite_col].dropna().tolist()
        if len(metabolites_all) < TARGET_RANGE[1]:
            print(f"代谢物总数不足{TARGET_RANGE[1]}个（当前共{len(metabolites_all)}个），无法筛选第{TARGET_RANGE[0]+1}-{TARGET_RANGE[1]}个")
            return
        metabolites = metabolites_all[TARGET_RANGE[0]:TARGET_RANGE[1]]
        print(f"共筛选出 {len(metabolites)} 个代谢物（第{TARGET_RANGE[0]+1}-{TARGET_RANGE[1]}个）待处理")

    except Exception as e:
        print(f"CSV读取错误: {e}")
        return

    # 启动Playwright（Chrome浏览器）
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # True为无头模式（不显示浏览器），False为显示浏览器
            args=["--start-maximized"]  # 最大化窗口
        )
        page = browser.new_page()
        # 设置用户代理（模拟真实浏览器）
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        })

        try:
            # 打开目标网站
            page.goto("https://plantcyc.org", timeout=TIMEOUT)
            time.sleep(2)  # 初始加载等待

            # 遍历筛选后的代谢物
            for idx, metabolite in enumerate(metabolites, 1):
                # 计算原始行索引（确保结果写入正确位置）
                original_row_idx = TARGET_RANGE[0] + (idx - 1)
                try:
                    print(f"\n处理第{TARGET_RANGE[0]+1}-{TARGET_RANGE[1]}批的第 {idx}/{len(metabolites)} 个（原始第{original_row_idx+1}个）: {metabolite}")

                    # 1. 定位输入框和提交按钮（Playwright自动等待元素可交互）
                    input_element = page.locator('input[type="text"]')
                    input_element.wait_for(state="visible", timeout=TIMEOUT)
                    
                    button_element = page.locator('input[type="submit"]')
                    button_element.wait_for(state="visible", timeout=TIMEOUT)

                    # 2. 清空输入框并输入代谢物（避免残留文本）
                    input_element.fill("")  # Playwright的fill方法自动清空并输入
                    time.sleep(0.5)
                    input_element.fill(metabolite)
                    time.sleep(random.uniform(*RANDOM_DELAY_RANGE))

                    # 3. 处理可能的警示框（Playwright自动捕获alert）
                    try:
                        with page.expect_alert(timeout=5000):
                            page.click('input[type="submit"]')  # 触发alert时点击
                        alert = page.alert()
                        alert.accept()  # 接受警示框
                        time.sleep(1)
                    except PlaywrightTimeoutError:
                        # 无警示框，直接点击提交
                        button_element.click()

                    # 4. 等待新标签页打开并切换（Playwright自动跟踪标签页）
                    with page.expect_popup(timeout=TIMEOUT) as popup_info:
                        # 若之前未触发点击，这里补充点击（防止警示框处理后未提交）
                        if not popup_info.value:
                            button_element.click()
                    new_page = popup_info.value  # 获取新标签页对象

                    # 5. 等待新页面加载完成（等待h1标签出现）
                    new_page.locator('h1').wait_for(state="visible", timeout=TIMEOUT)
                    time.sleep(1)

                    # 6. 检查Pathway是否存在（使用提供的XPath）
                    pathway_link = new_page.locator('//*[@id="mainContent"]/a[1]')
                    has_pathway = "yes" if (pathway_link.is_visible() and "pathways" in pathway_link.text_content().lower()) else "no"
                    print(f"结果: {'存在Pathways' if has_pathway == 'yes' else '不存在Pathways'}")

                    # 7. 实时保存结果到CSV
                    metabolite_df.at[original_row_idx, 'has_pathway'] = has_pathway
                    metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
                    print(f"已实时保存到：{save_file_path}")

                    # 8. 关闭新标签页
                    new_page.close()

                except PlaywrightTimeoutError:
                    # 处理超时异常
                    metabolite_df.at[original_row_idx, 'has_pathway'] = "timeout"
                    metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
                    print(f"结果: 页面加载超时（已实时保存）")
                    # 关闭可能残留的新标签页
                    for tab in browser.contexts[0].pages:
                        if tab != page:
                            tab.close()
                except Exception as e:
                    # 处理其他异常
                    metabolite_df.at[original_row_idx, 'has_pathway'] = "error"
                    metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
                    print(f"结果: 错误 - {e}（已实时保存）")
                    # 关闭可能残留的新标签页
                    for tab in browser.contexts[0].pages:
                        if tab != page:
                            tab.close()

        finally:
            # 最终保存并关闭浏览器
            metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
            browser.close()
            print(f"\n第{TARGET_RANGE[0]+1}-{TARGET_RANGE[1]}个代谢物处理完成，最终结果保存至：{save_file_path}")

if __name__ == "__main__":
    main()