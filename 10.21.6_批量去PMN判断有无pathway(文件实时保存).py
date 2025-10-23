from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, UnexpectedAlertPresentException, NoAlertPresentException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import random
import os  # 新增：用于处理文件路径

# 初始化浏览器
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

# 新增：打印文件保存路径，方便查找
current_dir = os.getcwd()
save_file_path = os.path.join(current_dir, 'metabolite_with_pathway.csv')
print(f"实时保存路径：{save_file_path}")  # 运行后复制此路径到文件管理器打开

# 打开网站
driver.get('https://plantcyc.org')
time.sleep(2)  # 初始加载等待
# 记录初始标签页句柄（用于后续关闭新标签页）
original_window = driver.current_window_handle

# 获取输入框和提交按钮
try:
    input_element = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="text"]'))
    )
    button_element = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="submit"]'))
    )
except TimeoutException:
    print("无法找到输入框或提交按钮，退出")
    driver.quit()
    exit()

# 读取CSV数据
try:
    metabolite_df = pd.read_csv('metabolite.csv')
    metabolite_col = next((col for col in metabolite_df.columns if col.lower() == 'metabolite'), None)
    if metabolite_col is None:
        print("未找到'metabolite'列")
        driver.quit()
        exit()
    # 新增：初始化has_pathway列（避免后续赋值时列不存在）
    if 'has_pathway' not in metabolite_df.columns:
        metabolite_df['has_pathway'] = ''  # 先设为空字符串
    metabolites_all = metabolite_df[metabolite_col].dropna().unique().tolist()
    metabolites = metabolites_all[1000:2000]
    print(f"共 {len(metabolites)} 个代谢物待处理")
except Exception as e:
    print(f"CSV读取错误: {e}")
    driver.quit()
    exit()

# 检查Pathway是否存在
def check_pathway_exists(driver):
    try:
        link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="mainContent"]/a[1]'))
        )
        return "pathways" in link.text.lower()
    except:
        return False

# 遍历代谢物（去掉单独的has_pathway列表，直接在DataFrame中赋值）
for idx, metabolite in enumerate(metabolites, 1):
    # 找到当前代谢物在DataFrame中的行索引（避免顺序错乱）
    row_idx = metabolite_df[metabolite_df[metabolite_col] == metabolite].index[0]
    try:
        print(f"\n处理第 {idx}/{len(metabolites)}: {metabolite}")
        
        # 确保在初始标签页操作（防止之前的标签页未关闭）
        driver.switch_to.window(original_window)
        
        # 清空输入框并输入
        input_element.clear()
        time.sleep(0.5)
        input_element.send_keys(metabolite)
        time.sleep(random.uniform(0.8, 1.5))
        
        # 点击提交前先处理可能残留的警示框
        try:
            driver.switch_to.alert.accept()  # 接受警示框
            time.sleep(1)
        except NoAlertPresentException:
            pass  # 无警示框则继续
        
        # 点击提交
        button_element.click()
        time.sleep(1)  # 等待新标签页打开
        
        # 处理可能的警示框（提交后弹出）
        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert.accept()  # 接受警示框
            time.sleep(1)
        except (TimeoutException, NoAlertPresentException):
            pass  # 无警示框则继续
        
        # 切换到新打开的标签页
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))  # 等待新标签页打开
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)  # 切换到新标签页
                break
        
        # 等待新页面加载完成
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, 'h1'))
        )
        time.sleep(1)  # 额外等待内容加载
        
        # 检查Pathway并赋值结果
        if check_pathway_exists(driver):
            metabolite_df.at[row_idx, 'has_pathway'] = "yes"  # 精准赋值到对应行
            print("结果: 存在Pathways")
        else:
            metabolite_df.at[row_idx, 'has_pathway'] = "no"
            print("结果: 不存在Pathways")
        
        # 新增：实时保存CSV（每处理1个就保存1次）
        metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
        print(f"已实时保存到：{save_file_path}")
        
        # 关闭当前新标签页，回到初始页面
        driver.close()
        driver.switch_to.window(original_window)
        time.sleep(1)  # 等待初始页面恢复
        
    except TimeoutException:
        metabolite_df.at[row_idx, 'has_pathway'] = "timeout"
        print("结果: 页面加载超时")
        # 实时保存异常结果
        metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
        print(f"已实时保存超时结果到：{save_file_path}")
        # 异常时确保关闭新标签页并切回初始页
        if len(driver.window_handles) > 1:
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    driver.close()
            driver.switch_to.window(original_window)
    except UnexpectedAlertPresentException:
        # 处理未捕获的警示框
        try:
            driver.switch_to.alert.accept()
        except:
            pass
        metabolite_df.at[row_idx, 'has_pathway'] = "alert_error"
        print("结果: 警示框处理异常")
        # 实时保存异常结果
        metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
        print(f"已实时保存异常结果到：{save_file_path}")
    except Exception as e:
        metabolite_df.at[row_idx, 'has_pathway'] = "error"
        print(f"结果: 错误 - {e}")
        # 实时保存异常结果
        metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
        print(f"已实时保存错误结果到：{save_file_path}")
        # 异常时清理标签页
        if len(driver.window_handles) > 1:
            for window_handle in driver.window_handles:
                if window_handle != original_window:
                    driver.switch_to.window(window_handle)
                    driver.close()
            driver.switch_to.window(original_window)

# 最终保存（冗余保障，即使实时保存失效也能兜底）
metabolite_df.to_csv(save_file_path, index=False, encoding='utf-8')
print(f"\n所有处理完成，最终结果保存至：{save_file_path}")

# 关闭浏览器
driver.quit()