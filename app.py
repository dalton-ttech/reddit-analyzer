print("--- 脚本开始 ---")

import sys
import os
print(f"--- 正在使用 Python 版本: {sys.version} ---")
print(f"--- 当前工作目录: {os.getcwd()} ---")

try:
    from flask import Flask, render_template, request, jsonify
    print("--- 成功导入 Flask ---")
    import praw
    print("--- 成功导入 PRAW (Reddit库) ---")
    import google.generativeai as genai
    print("--- 成功导入 Google Generative AI ---")
    import threading
    print("--- 成功导入 Threading ---")
    import datetime
    print("--- 成功导入 Datetime ---")
    import json
    print("--- 成功导入 JSON ---")
    import re
    print("--- 成功导入 re ---")
    from waitress import serve
    print("--- 成功导入 Waitress ---")
    from dotenv import load_dotenv
    print("--- 成功导入 Dotenv ---")
except ImportError as e:
    print(f"!!! 在导入库时发生严重错误: {e} !!!")
    print("!!! 错误很可能意味着某个库没有被正确安装。!!!")
    print("!!! 请在终端里尝试运行: pip install Flask praw google-generativeai waitress python-dotenv --upgrade !!!")
    exit(1) # 导入失败，直接退出


print("\n--- 所有库导入成功，准备初始化App ---")

load_dotenv() # 在程序开始时加载 .env 文件里的变量

app = Flask(__name__)
print("--- Flask App 初始化成功 ---")


# --- API 密钥现在从环境变量中读取 ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# ------------------------------------


# ==================== 配置变量 ====================
SUBREDDITS_TO_SEARCH = "homeimprovement+interiordesign+Apartmentliving+malelivingspace+femalelivingspace+homeautomation"
BLOCKED_KEYWORDS = ["shower", "politics", "trump", "war", "navy", "smoke", "military", "game"]
# =======================================================
print("--- API密钥和配置变量已加载 ---")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("--- Gemini API 配置成功 ---")
except Exception as e:
    print(f"!!! Gemini API 配置失败: {e} !!!")
    exit(1)


# --- 全局任务状态字典 ---
tasks = {"current_task": {"status": "等待中", "progress": 0, "report_url": "", "ai_subreddits": None}}


# --- 智能检索版块函数 ---
def get_ai_subreddits(keyword, task_info):
    """
    使用 Gemini API 动态获取并翻译相关的 Reddit 版块列表。
    """
    print(f"--- [智能检索] 任务启动，关键词: '{keyword}' ---")
    try:
        task_info["status"] = "正在请求 AI 推荐相关版块..."
        task_info["progress"] = 10
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt_for_subreddits = f"""你是一个对 Reddit 了如指掌的专家。针对关键词 "{keyword}"，请推荐最多10个最相关的 Reddit 子版块。返回的格式必须是一个由加号 `+` 连接的单一字符串，例如 "subreddit1+subreddit2+subreddit3" 或 "r/subreddit1+r/subreddit2"。除了这个字符串，不要返回任何其他文字。"""
        
        print("--- [智能检索] 正在向 Gemini 发送请求 [获取版块]... ---")
        response = model.generate_content(prompt_for_subreddits)
        ai_generated_string = response.text.strip().replace("\n", "")
        
        if not re.match(r'^[a-zA-Z0-9_/]+(\+[a-zA-Z0-9_/]+)*$', ai_generated_string):
            print(f"!!! [智能检索] 错误：获取的版块格式不符合预期: '{ai_generated_string}'。将使用默认版块。 !!!")
            return SUBREDDITS_TO_SEARCH

        print(f"--- [智能检索] 成功获取版块列表: '{ai_generated_string}' ---")
        subreddit_list = [sub.replace('r/', '') for sub in ai_generated_string.split('+') if sub]
        
        task_info["status"] = "获取版块成功，正在请求 AI 翻译..."
        prompt_for_translation = f"""
你是一位专业的翻译。请将下面的 Reddit 子版块名称翻译成简洁、准确的中文名。
你的输出必须是一个完整的 JSON 对象，其中键是原始的英文名，值是中文翻译。
例如，如果输入是 "homeimprovement, interiordesign"，你的输出应该是：
{{
    "homeimprovement": "家居装修",
    "interiordesign": "室内设计"
}}
除了这个 JSON 对象，不要返回任何其他文字。

这是需要翻译的列表：
{", ".join(subreddit_list)}
"""
        
        print("--- [智能检索] 正在向 Gemini 发送请求 [翻译版块]... ---")
        response_translation = model.generate_content(prompt_for_translation)
        json_string = re.search(r'\{.*\}', response_translation.text, re.DOTALL).group(0)
        translations = json.loads(json_string)
        
        results_for_frontend = []
        for sub_name in subreddit_list:
            results_for_frontend.append({
                "name": sub_name,
                "translation": translations.get(sub_name, "翻译失败")
            })
        
        task_info["ai_subreddits"] = results_for_frontend
        print(f"--- [智能检索] 成功生成带翻译的版块列表，并已更新至 task_info ---")
        
        return ai_generated_string

    except Exception as e:
        print(f"!!! [智能检索] 过程中发生错误: {e}。将使用默认版块列表。 !!!")
        return SUBREDDITS_TO_SEARCH


# --- 报告生成函数 ---
def generate_report_html(report_data_json, keyword):
    try:
        data = json.loads(report_data_json)
        title = f"Reddit '{keyword.capitalize()}' 市场深度分析报告"

        # 构建热点词HTML
        hot_words_html = "<ul>"
        for item in data.get("marketHotTopics", []):
            hot_words_html += f"<li>{item['keyword']}: {item['explanation']}</li>"
        hot_words_html += "</ul>"

        # 构建痛点HTML
        pain_points_html = "<ul>"
        for item in data.get("corePainPoints", []):
            pain_points_html += f"<li><strong>{item['title']}:</strong> {item['description']} <span class='count'>{item['count']} 条</span></li>"
        pain_points_html += "</ul>"

        # 构建评论案例HTML
        comments_html = ""
        for item in data.get("commentExamples", []):
            permalink = item.get('permalink', '#')
            comments_html += f"""
            <div class="content-box comment-box">
                <h3>痛点：{item['painPointTitle']}</h3>
                <blockquote>
                    <p>{item['commentTranslation']}</p>
                    <footer>- Reddit 用户 (热度: {item.get('score', 0)} 赞, {item.get('replies', 0)} 回复) | <a href="{permalink}" target="_blank">查看原文</a></footer>
                </blockquote>
            </div>
            """
        
        chart_data_for_script = data.get("painPointChartData", {})

        html_content = f"""
        <!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{title}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
            :root {{ --bg-color: #fdf5e6; --text-color: #5d4037; --primary-color: #d2b48c; --secondary-color: #e9ddc7; --container-bg: #fffaf0; }}
            body {{ font-family: 'Noto Sans SC', sans-serif; margin: 0; background-color: var(--bg-color); color: var(--text-color); }}
            .container {{ max-width: 900px; margin: 40px auto; background-color: var(--container-bg); box-shadow: 0 10px 30px rgba(0,0,0,0.07); border-radius: 12px; }}
            header {{ text-align: center; padding: 40px; border-bottom: 2px solid var(--secondary-color); }}
            main {{ padding: 20px 40px 40px 40px; }}
            h1 {{ font-size: 2.5em; margin: 0; }}
            h2 {{ font-size: 1.8em; color: var(--text-color); margin-top: 40px; padding-bottom: 10px; border-bottom: 2px solid var(--secondary-color); }}
            h3 {{ color: var(--text-color); }}
            .content-box {{ background-color: #fff; border: 1px solid var(--secondary-color); border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
            #hot-words ul li {{ background-color: var(--secondary-color); text-align: left; font-weight: 500; border-left: none; transition: transform 0.2s; padding: 12px 15px; margin-bottom: 10px; border-radius: 5px; }}
            #hot-words ul li:hover {{ transform: scale(1.02); }}
            #pain-points ul li {{ position: relative; padding: 15px; background-color: #fdfcf9; border-left: 4px solid var(--primary-color); margin-bottom: 10px; border-radius: 4px;}}
            .count {{ float: right; background-color: var(--primary-color); color: white; font-size: 0.9em; font-weight: bold; padding: 2px 10px; border-radius: 12px; margin-left: 10px; }}
            .comment-box blockquote {{ border-left: 4px solid var(--primary-color); margin: 0; padding: 10px 20px; background-color: var(--bg-color); font-style: italic; }}
            .comment-box footer {{ text-align: right; margin-top: 10px; font-style: normal; font-size: 0.9em; color: #777; }}
            .chart-container {{ padding: 20px; background-color: #fff; border-radius: 8px; border: 1px solid var(--secondary-color); }}
        </style>
        </head><body>
        <div class="container">
            <header><h1>{title}</h1></header>
            <main>
                <section id="summary"><h2>摘要</h2><div class="content-box"><p>{data.get("executiveSummary", "")}</p></div></section>
                <section id="hot-words"><h2>市场热点词</h2><div class="content-box">{hot_words_html}</div></section>
                <section id="sentiment"><h2>市场情绪</h2><div class="content-box"><p><strong>整体情绪:</strong> {data.get("marketSentiment", {}).get("overall", "")}</p><p><strong>具体分析:</strong> {data.get("marketSentiment", {}).get("analysis", "")}</p></div></section>
                <section id="pain-points"><h2>核心市场痛点</h2><div class="content-box">{pain_points_html}</div></section>
                <section id="chart-section"><h2>痛点频率数据可视化</h2><div class="chart-container"><canvas id="painPointChart"></canvas></div></section>
                <section id="comment-details"><h2>痛点详情评论案例</h2>{comments_html}</section>
            </main>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const chartData = {json.dumps(chart_data_for_script)};
                const config = {{
                    type: 'bar',
                    data: {{ labels: chartData.labels, datasets: [{{ label: '提及次数', data: chartData.data, backgroundColor: chartData.colors, borderWidth: 0 }}] }},
                    options: {{ indexAxis: 'y', responsive: true, plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: '核心市场痛点提及频率对比', font: {{ size: 18, family: "'Noto Sans SC', sans-serif" }} }} }} }}
                }};
                const ctx = document.getElementById('painPointChart').getContext('2d');
                new Chart(ctx, config);
            }});
        </script>
        </body></html>
        """
        return html_content
    except Exception as e:
        return f"<h1>报告生成失败</h1><p>解析AI返回的数据时出错: {e}</p><pre>{report_data_json}</pre>"


# --- 核心任务执行函数 (V7 - 采用公平配额抓取策略) ---
def real_task_runner(keyword, timeframe, sort_order, limit, search_mode):
    task_info = tasks["current_task"]
    TOTAL_CHARS_LIMIT = 20000
    try:
        subreddits_for_this_task = ""
        if search_mode == "smart":
            print(f"--- [主任务] 检测到 '智能检索' 模式 ---")
            subreddits_for_this_task = get_ai_subreddits(keyword, task_info)
        else:
            print(f"--- [主任务] 检测到 '标准检索' 模式 ---")
            subreddits_for_this_task = SUBREDDITS_TO_SEARCH
        
        task_info["status"] = "正在连接 Reddit..."
        task_info["progress"] = 5
        reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET, user_agent=REDDIT_USER_AGENT, username=REDDIT_USERNAME, password=REDDIT_PASSWORD)
        
        task_info["status"] = f"准备在多个版块中公平抓取帖子..."
        task_info["progress"] = 15
        
        individual_subreddits = [s for s in subreddits_for_this_task.split('+') if s]
        if not individual_subreddits: raise ValueError("未能确定任何要搜索的版块。")

        # 1. 计算配额
        target_fetch_count = int(limit) * 2
        quota_per_sub = (target_fetch_count // len(individual_subreddits)) + 1
        print(f"--- [PRAW] 策略：最终分析 {limit} 个帖子, 准备抓取约 {target_fetch_count} 个帖子作为样本池。")
        print(f"--- [PRAW] 共 {len(individual_subreddits)} 个版块, 每个版块配额为 {quota_per_sub} 个帖子。")

        all_search_results = []
        for sub_name in individual_subreddits:
            sub_name = sub_name.replace('r/', '').strip()
            try:
                print(f"--- [PRAW] ==> 正在版块 r/{sub_name} 中抓取 {quota_per_sub} 个帖子...")
                subreddit = reddit.subreddit(sub_name)
                search_params = { 'query': keyword, 'limit': quota_per_sub, 'sort': sort_order }
                if sort_order in ['top', 'relevance']:
                    search_params['time_filter'] = timeframe
                all_search_results.extend(list(subreddit.search(**search_params)))
            except Exception as e:
                print(f"!!! [PRAW] 警告：搜索版块 r/{sub_name} 时出错: {e}。已跳过。!!!")
                continue
        
        print(f"--- [PRAW] 公平抓取完成，共获得 {len(all_search_results)} 个帖子。")

        # 2. 汇总后排序
        task_info["status"] = "帖子抓取完毕，正在排序..."
        task_info["progress"] = 20
        all_search_results.sort(key=lambda x: x.score, reverse=True)
        print(f"--- [主任务] {len(all_search_results)} 个帖子已按热度排序。")

        # 3. 筛选并切片
        final_submissions = []
        print(f"--- [主任务] 开始过滤屏蔽词，并选取前 {limit} 个有效帖子... ---")
        for submission in all_search_results:
            if len(final_submissions) >= int(limit):
                break

            title_lower = submission.title.lower()
            if any(blocked_word in title_lower for blocked_word in BLOCKED_KEYWORDS):
                continue
            
            final_submissions.append(submission)
        
        print(f"--- [主任务] 筛选完成，最终选定 {len(final_submissions)} 个帖子进行分析。")
        
        # 4. 抓取最终选定帖子的评论
        comments_for_analysis = []
        task_info["status"] = "正在抓取最终帖子的评论..."
        task_info["progress"] = 25
        for submission in final_submissions:
            print(f"--- [主任务] 正在处理帖子: '{submission.title}' (Score: {submission.score}) ---")
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list():
                comments_for_analysis.append({
                    "body": comment.body,
                    "score": comment.score,
                    "replies": len(comment.replies),
                    "permalink": f"https://www.reddit.com{comment.permalink}"
                })
        
        if not comments_for_analysis: raise ValueError("未能找到任何相关的评论。")
        
        comments_text = "\n".join([json.dumps(c, ensure_ascii=False) for c in comments_for_analysis])

        task_info["status"] = "数据抓取完毕，正在请求 Gemini AI 分析..."
        task_info["progress"] = 65
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
你是一位顶级的市场研究和数据分析专家。你的任务是根据下面提供的关于 "{keyword}" 的 Reddit 评论（数据为JSON Lines格式，每行一条评论，包含body, score, replies, permalink），生成一份结构化的、内容丰富的市场分析报告。

你的分析要求：
1.  **深度与广度**：请从评论中总结出至少 **5-8个** 核心的市场痛点或用户需求点。
2.  **案例支撑**：对于每一个识别出的核心痛点，请挑选 **2-3条** 最具代表性的评论作为案例进行支撑。
3.  **严格的JSON格式**：你的输出必须是一个完整的、可以被Python直接解析的JSON对象。请严格遵循下面的结构，不要添加任何额外的解释或文字。

{{
    "executiveSummary": "在这里用3-4句话概述最重要的发现，包括最主要的市场痛点和情绪。",
    "marketHotTopics": [
        {{"keyword": "热点词1", "explanation": "解释..."}},
        {{"keyword": "热点词2", "explanation": "解释..."}},
        {{"keyword": "热点词3", "explanation": "解释..."}}
    ],
    "marketSentiment": {{
        "overall": "正面 XX%, 负面 XX%, 中性 XX%",
        "analysis": "具体分析市场情绪背后的原因，比如用户为什么感到满意或不满。"
    }},
    "corePainPoints": [
        {{"title": "痛点一标题", "description": "详细描述这个痛点的具体表现、背景和用户感受。", "count": 0}},
        {{"title": "痛点二标题", "description": "详细描述...", "count": 0}}
    ],
    "painPointChartData": {{
        "labels": ["痛点一", "痛点二", "..."],
        "data": [0, 0, 0],
        "colors": ["#D2B48C", "#E9DDc7", "#856404", "#a17a48", "#b99a6b"]
    }},
    "commentExamples": [
        {{
            "painPointTitle": "所属的痛点标题",
            "commentTranslation": "将最有代表性的那条评论翻译成中文。",
            "score": 0,
            "replies": 0,
            "permalink": "这里应该填入原始评论的完整URL链接"
        }}
    ]
}}

请根据下面的原始数据填充以上JSON结构。其中'count'代表属于该痛点的评论大致数量，'painPointChartData'里的数据需要根据你总结的痛点来生成。务必从原始数据中提取 'permalink' 并填入 'commentExamples'。
--- 原始评论数据 ---
{comments_text[:TOTAL_CHARS_LIMIT]}
"""
        
        response = model.generate_content(prompt)
        
        task_info["status"] = "AI分析完成，正在生成报告..."
        task_info["progress"] = 90
        
        json_string = re.search(r'\{.*\}', response.text, re.DOTALL).group(0)
        report_data_json = json.loads(json_string)
        
        report_html = generate_report_html(json.dumps(report_data_json), keyword)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{keyword}_{timestamp}.html"
        report_filepath = os.path.join('static', report_filename)
        
        with open(report_filepath, 'w', encoding='utf-8') as f: f.write(report_html)
            
        task_info["status"] = "已完成"
        task_info["progress"] = 100
        task_info["report_url"] = f"/static/{report_filename}"

    except Exception as e:
        task_info["status"] = f"任务出错: {str(e)}"
        task_info["progress"] = 100
        print(f"任务出错: {e}")


# --- Flask 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.route('/start-task', methods=['POST'])
def start_task():
    data = request.json
    search_mode = data.get('subreddits')

    tasks["current_task"] = { "status": "任务初始化...", "progress": 0, "report_url": "", "ai_subreddits": None }
    
    thread = threading.Thread(target=real_task_runner, args=(data.get('keyword'), data.get('timeframe'), data.get('sort_order'), data.get('limit'), search_mode))
    thread.start()
    return jsonify({"message": "任务已成功启动"})

@app.route('/task-status')
def task_status():
    return jsonify(tasks["current_task"])


# --- 服务器启动 ---
print("\n--- 准备启动服务器 ---")
if __name__ == '__main__':
    print("--- 使用 Waitress 服务器启动 ---")
    serve(app, host='0.0.0.0', port=5000)