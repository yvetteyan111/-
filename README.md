# 在PMN数据库(plantcyc)上批量检查代谢物是否存在对应的通路

## 功能说明
该脚本用于批量检查植物代谢物在 [PlantCyc 数据库](https://plantcyc.org) 中是否存在相关通路信息。通过 Selenium 自动化浏览器操作，对输入的代谢物列表进行逐一查询，并记录每个代谢物是否存在对应的通路信息。

## 依赖环境
- Python 3.x
- 所需 Python 库：
  - selenium
  - pandas
  - webdriver-manager
  - time
  - random
  - os

## 安装依赖
使用 pip 安装所需依赖：
```bash
pip install selenium pandas webdriver-manager
```

## 使用方法
1. 准备输入文件：
   - 在脚本同目录下创建名为 `metabolite.csv` 的文件
   - 文件中需包含名为 `metabolite` 的列（不区分大小写），该列包含需要查询的代谢物名称

2. 运行脚本：
   ```bash
   python [脚本文件名].py
   ```

3. 查看结果：
   - 结果将实时保存到脚本运行目录下的 `metabolite_with_pathway12.csv` 文件
   - 脚本运行过程中会打印保存路径，可直接复制路径在文件管理器中打开

## 脚本特点
1. 自动化操作：通过无头浏览器模式（headless）自动完成查询过程，无需人工干预
2. 实时保存：每处理一个代谢物就会保存一次结果，避免程序意外终止导致数据丢失
3. 异常处理：包含多种异常处理机制，如超时、弹窗等情况，保证程序稳定性
4. 精准定位：通过索引精准匹配代谢物与结果，避免因顺序问题导致的错误

## 结果说明
输出文件 `metabolite_with_pathway12.csv` 在输入文件基础上增加了 `has_pathway` 列，可能的值包括：
- "yes"：存在相关通路
- "no"：不存在相关通路
- "timeout"：页面加载超时
- "alert_error"：警示框处理异常
- "error"：其他错误

## 注意事项
1. 请确保网络连接稳定，避免因网络问题导致查询失败
2. 脚本运行过程中会有随机延迟，模拟人工操作，避免对目标网站造成过大压力
3. 若需要处理全部代谢物，可修改代码中 `metabolites = metabolites_all[7676:]` 部分，改为 `metabolites = metabolites_all`
4. 运行过程中请勿关闭控制台窗口，否则会中断程序执行

## 自定义设置
- 可修改浏览器 User-Agent 信息以模拟不同的浏览器
- 可调整代码中的等待时间（`time.sleep()` 和 `WebDriverWait` 的超时参数）以适应不同的网络环境
