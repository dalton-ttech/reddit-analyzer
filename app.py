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
except ImportError as e:
    print(f"!!! 在导入库时发生严重错误: {e} !!!")
    print("!!! 错误很可能意味着某个库没有被正确安装。!!!")
    print("!!! 请在终端里尝试运行: pip install Flask praw google-generativeai waitress --upgrade !!!")
    exit(1) # 导入失败，直接退出


print("\n--- 所有库导入成功，准备初始化App ---")

app = Flask(__name__)
print("--- Flask App 初始化成功 ---")

@app.route('/favicon.ico')
def favicon():
    return ('', 204)


# ---!!! 请在这里填入你所有的API密钥 !!!---
from flask import Flask, render_template, request, jsonify
import praw
import google.generativeai as genai
import threading
import os
import datetime
import json
import re
from dotenv import load_dotenv # <-- 新增导入

load_dotenv() # <-- 新增：在程序开始时加载 .env 文件里的变量

app = Flask(__name__)

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


tasks = {"current_task": {"status": "等待中", "progress": 0, "report_url": ""}}

# ... (generate_report_html 和 real_task_runner 函数保持不变) ...
# 注意：这部分代码来自我们之前的最终版本，确保所有功能都包含在内
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
            comments_html += f"""
            <div class="content-box comment-box">
                <h3>痛点：{item['painPointTitle']}</h3>
                <blockquote>
                    <p>{item['commentTranslation']}</p>
                    <footer>- Reddit 用户 (热度: {item['score']} 赞, {item['replies']} 回复)</footer>
                </blockquote>
            </div>
            """
        
        # 准备图表数据
        chart_data_for_script = data.get("painPointChartData", {})

        # 最终HTML模板
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

def real_task_runner(keyword, timeframe, sort_order, limit):
    task_info = tasks["current_task"]
    TOTAL_CHARS_LIMIT = 20000
    try:
        task_info["status"] = "正在连接 Reddit..."
        task_info["progress"] = 5
        reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET, user_agent=REDDIT_USER_AGENT, username=REDDIT_USERNAME, password=REDDIT_PASSWORD)
        
        task_info["status"] = f"正在指定的版块中搜索 '{keyword}'..."
        task_info["progress"] = 15
        subreddit = reddit.subreddit(SUBREDDITS_TO_SEARCH)
        search_results = list(subreddit.search(keyword, sort=sort_order, time_filter=timeframe, limit=int(limit) * 3))
        
        comments_for_analysis = []
        task_info["status"] = "正在抓取评论并过滤..."
        task_info["progress"] = 25
        collected_posts_count = 0

        for submission in search_results:
            if collected_posts_count >= int(limit): break
            title_lower = submission.title.lower()
            if any(blocked_word in title_lower for blocked_word in BLOCKED_KEYWORDS): continue
            
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list():
                comments_for_analysis.append({
                    "body": comment.body,
                    "score": comment.score,
                    "replies": len(comment.replies)
                })
            collected_posts_count += 1
        
        if not comments_for_analysis: raise ValueError("未能找到任何相关的评论。")
        
        comments_text = "\n".join([f"Comment (Score: {c['score']}, Replies: {c['replies']}): {c['body']}" for c in comments_for_analysis])

        task_info["status"] = "数据抓取完毕，正在请求 Gemini AI 分析..."
        task_info["progress"] = 65
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        prompt = f"""
        你是一位顶级的市场研究和数据分析专家。你的任务是根据下面提供的关于 "{keyword}" 的 Reddit 评论（每条评论都附带了热度分和回复数），生成一份结构化的市场分析报告。
        你的输出必须是一个完整的、可以被Python直接解析的JSON对象。请严格遵循下面的结构，不要添加任何额外的解释或文字。

        {{
            "executiveSummary": "在这里用2-3句话概述核心发现。",
            "marketHotTopics": [
                {{"keyword": "热点词1", "explanation": "解释..."}},
                {{"keyword": "热点词2", "explanation": "解释..."}}
            ],
            "marketSentiment": {{
                "overall": "正面 XX%, 负面 XX%, 中性 XX%",
                "analysis": "具体分析..."
            }},
            "corePainPoints": [
                {{"title": "痛点一标题", "description": "详细描述...", "count": 0}},
                {{"title": "痛点二标题", "description": "详细描述...", "count": 0}}
            ],
            "painPointChartData": {{
                "labels": ["痛点一", "痛点二", "..."],
                "data": [0, 0, 0],
                "colors": ["#D2B48C", "#E9DDc7", "#856404"]
            }},
            "commentExamples": [
                {{
                    "painPointTitle": "所属的痛点标题",
                    "commentTranslation": "将最有代表性的那条评论翻译成中文。",
                    "score": 0,
                    "replies": 0
                }}
            ]
        }}

        请根据下面的原始数据填充以上JSON结构。其中'count'代表属于该痛点的评论大致数量，'painPointChartData'里的数据需要根据你总结的痛点来生成。'commentExamples'请为每个主要痛点挑选一条最典型（比如赞同数最高）的评论作为案例。
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start-task', methods=['POST'])
def start_task():
    data = request.json
    tasks["current_task"] = { "status": "任务初始化...", "progress": 0, "report_url": "" }
    thread = threading.Thread(target=real_task_runner, args=(data.get('keyword'), data.get('timeframe'), data.get('sort_order'), data.get('limit')))
    thread.start()
    return jsonify({"message": "任务已成功启动"})

@app.route('/task-status')
def task_status():
    return jsonify(tasks["current_task"])

print("\n--- 准备启动服务器 ---")
if __name__ == '__main__':
    from waitress import serve
    print("--- 使用 Waitress 服务器启动 ---")
    serve(app, host='0.0.0.0', port=5000)