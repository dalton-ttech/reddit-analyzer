print("--- 脚本开始 ---")

import sys
import os
import threading
import datetime
import json
import re
from flask import Flask, render_template, request, jsonify
from waitress import serve
from dotenv import load_dotenv
import praw
import google.generativeai as genai

print(f"--- 正在使用 Python 版本: {sys.version} ---")
print(f"--- 当前工作目录: {os.getcwd()} ---")

# --- 初始化与配置 ---
load_dotenv()
app = Flask(__name__)

# --- API 密钥 ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- 全局配置 ---
SUBREDDITS_TO_SEARCH = "homeimprovement+interiordesign+Apartmentliving+malelivingspace+femalelivingspace+homeautomation"
STATUS_FILE = "task_status.json"
TOTAL_CHARS_LIMIT = 30000
# 默认屏蔽词列表现在在这里定义
DEFAULT_BLOCKED_KEYWORDS = ["shower", "politics", "trump", "war", "navy", "smoke", "military", "game"]


# --- 线程锁，确保文件访问安全 ---
file_lock = threading.Lock()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("--- Gemini API 配置成功 ---")
except Exception as e:
    print(f"!!! Gemini API 配置失败: {e} !!!")
    exit(1)

# --- 状态更新帮助函数 (带锁) ---
def update_status_file(status_text, progress_percent, report_url=None, ai_subreddits=None):
    with file_lock:
        current_state = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                    current_state = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                current_state = {}

        current_state["status"] = status_text
        current_state["progress"] = progress_percent
        if report_url is not None:
            current_state["report_url"] = report_url
        if ai_subreddits is not None:
            current_state["ai_subreddits"] = ai_subreddits
            
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_state, f, ensure_ascii=False, indent=4)
    print(f"--- [状态更新] {status_text} ({progress_percent}%) ---")

# --- 智能检索版块函数 ---
def get_ai_subreddits(keyword):
    try:
        update_status_file("正在请求 AI 推荐相关版块...", 10)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt_for_subreddits = f'针对关键词 "{keyword}"，请推荐最多15个最相关的 Reddit 子版块。返回格式必须是单一字符串，由+连接。'
        response = model.generate_content(prompt_for_subreddits)
        ai_generated_string = response.text.strip().replace("\n", "")
        
        if not re.match(r'^[a-zA-Z0-9_/]+(\+[a-zA-Z0-9_/]+)*$', ai_generated_string):
            raise ValueError(f"获取的版块格式不符合预期: '{ai_generated_string}'")

        subreddit_list = [sub.replace('r/', '') for sub in ai_generated_string.split('+') if sub]
        
        update_status_file("获取版块成功，正在请求 AI 翻译...", 12)
        prompt_for_translation = f'请将以下Reddit版块名翻译成中文，并返回一个完整的JSON对象，键是英文名，值是中文名：{", ".join(subreddit_list)}'
        response_translation = model.generate_content(prompt_for_translation)
        match = re.search(r'\{.*\}', response_translation.text, re.DOTALL)
        if not match: raise ValueError("翻译API未能返回有效的JSON格式。")
        
        translations = json.loads(match.group(0))
        results_for_frontend = [{"name": sub, "translation": translations.get(sub, "翻译失败")} for sub in subreddit_list]
        
        update_status_file("AI推荐版块已生成", 15, ai_subreddits=results_for_frontend)
        return ai_generated_string
    except Exception as e:
        print(f"!!! [智能检索] 过程中发生错误: {e}。将使用默认版块列表。 !!!")
        update_status_file(f"智能检索失败: {e}", 15)
        return SUBREDDITS_TO_SEARCH

# --- 报告生成函数 (V1.9 - 视觉增强版) ---
def generate_report_html(report_data_json, keyword, used_subreddits, analysis_mode):
    try:
        data = json.loads(report_data_json)
        
        if analysis_mode == 'pain_points':
            title = f"Reddit '{keyword.capitalize()}' 用户痛点深度分析报告"
            main_title = "核心用户痛点"
            main_data_key = "identifiedPainPoints"
            chart_title = "痛点频率数据可视化"
            comment_title_prefix = "痛点："
            comment_data_key = "painPointTitle"
        else: # hot_topics
            title = f"Reddit '{keyword.capitalize()}' 市场热点分析报告"
            main_title = "核心讨论议题"
            main_data_key = "keyDiscussionTopics"
            chart_title = "议题热度数据可视化"
            comment_title_prefix = "议题："
            comment_data_key = "associatedTopic"

        summary_data = data.get("executiveSummary", {})
        summary_html = ""
        if isinstance(summary_data, dict):
            overall_sentiment = summary_data.get("overallSentiment", "")
            key_findings = summary_data.get("keyFindings", [])
            summary_html += f"<div class='summary-main-point'>{overall_sentiment}</div>"
            if key_findings:
                summary_html += "<div class='summary-cards-container'>"
                for finding in key_findings:
                    summary_html += f"<div class='summary-card'>{finding}</div>"
                summary_html += "</div>"
        else:
            summary_html = f"<p>{summary_data}</p>"
        
        subreddits_html = "<ul class='subreddit-list'>" + "".join(f"<li>r/{sub}</li>" for sub in used_subreddits) + "</ul>"
        main_content_html = "<ul>" + "".join(f"<li><strong>{item['title']}</strong><br>{item.get('description', '')} <span class='count'>{item.get('count', 0)} 条</span></li>" for item in data.get(main_data_key, [])) + "</ul>"
        comments_html = "".join(f"""<div class="content-box comment-box"><h3>{comment_title_prefix}{item.get(comment_data_key, 'N/A')}</h3><blockquote><p>{item['commentTranslation']}</p><footer>- Reddit 用户 (热度: {item.get('score', 0)} 赞, {item.get('replies', 0)} 回复) | <a href="{item.get('permalink', '#')}" target="_blank">查看原文</a></footer></blockquote></div>""" for item in data.get("commentExamples", []))
        chart_data_for_script = data.get("chartData", {})
        
        html_content = f"""
        <!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{title}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
            :root{{--bg-color:#fdf5e6;--text-color:#5d4037;--primary-color:#d2b48c;--secondary-color:#e9ddc7;--container-bg:#fffaf0;}}
            body{{font-family:'Noto Sans SC',sans-serif;margin:0;background-color:var(--bg-color);color:var(--text-color);}}
            .container{{max-width:900px;margin:40px auto;background-color:var(--container-bg);box-shadow:0 10px 30px rgba(0,0,0,0.07);border-radius:12px;}}
            header{{text-align:center;padding:40px;border-bottom:2px solid var(--secondary-color);}}
            main{{padding:20px 40px 40px 40px;}}
            h1{{font-size:2.5em;margin:0;}}
            h2{{font-size:1.8em;color:var(--text-color);margin-top:40px;padding-bottom:10px;border-bottom:2px solid var(--secondary-color);}}
            h3{{color:var(--text-color);}}
            .content-box{{background-color:#fff;border:1px solid var(--secondary-color);border-radius:8px;padding:20px;margin-bottom:20px;}}
            ul{{padding-left:20px;list-style-position:inside;}}
            #main-content ul li{{position:relative;padding:15px;background-color:#fdfcf9;border-left:4px solid var(--primary-color);margin-bottom:10px;border-radius:4px;}}
            .count{{float:right;background-color:var(--primary-color);color:white;font-size:0.9em;font-weight:bold;padding:2px 10px;border-radius:12px;margin-left:10px;}}
            .comment-box blockquote{{border-left:4px solid var(--primary-color);margin:0;padding:10px 20px;background-color:var(--bg-color);font-style:italic;}}
            .comment-box footer{{text-align:right;margin-top:10px;font-style:normal;font-size:0.9em;color:#777;}}
            .chart-container{{padding:20px;background-color:#fff;border-radius:8px;border:1px solid var(--secondary-color);}}
            .subreddit-list{{list-style-type:none;padding:0;display:flex;flex-wrap:wrap;gap:10px;}}
            .subreddit-list li{{background-color:var(--secondary-color);color:var(--text-color);font-size:0.9em;padding:5px 12px;border-radius:15px;}}
            .summary-main-point{{font-size:1.1em;font-weight:500;margin-bottom:20px;padding-bottom:15px;border-bottom:2px solid var(--secondary-color);text-align:center;}}
            .summary-cards-container{{display:flex;justify-content:space-around;gap:15px;flex-wrap:wrap;}}
            .summary-card{{background-color:var(--secondary-color);padding:15px;border-radius:8px;flex:1;min-width:200px;text-align:center;font-weight:500;box-shadow:0 2px 4px rgba(0,0,0,0.05);}}
        </style>
        </head><body>
        <div class="container">
            <header><h1>{title}</h1></header>
            <main>
                <section id="summary"><h2>摘要</h2><div class="content-box">{summary_html}</div></section>
                <section id="scope"><h2>分析范围</h2><div class="content-box">{subreddits_html}</div></section>
                <section id="chart-section"><h2>{chart_title}</h2><div class="chart-container"><canvas id="analysisChart"></canvas></div></section>
                <section id="main-content"><h2>{main_title}</h2><div class="content-box">{main_content_html}</div></section>
                <section id="comment-details"><h2>相关评论案例</h2>{comments_html}</section>
            </main>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded',function(){{
                const chartData = {json.dumps(chart_data_for_script)};
                if (chartData && chartData.labels && chartData.labels.length > 0) {{
                    const config = {{
                        type: 'bar',
                        data: {{
                            labels: chartData.labels,
                            datasets: [{{
                                label: '提及次数',
                                data: chartData.data,
                                backgroundColor: chartData.colors,
                                borderWidth: 0
                            }}]
                        }},
                        options: {{
                            indexAxis: 'y',
                            responsive: true,
                            plugins: {{
                                legend: {{ display: false }},
                                title: {{ display: true, text: '{main_title}提及频率对比', font: {{ size: 18, family: "'Noto Sans SC', sans-serif" }} }}
                            }}
                        }}
                    }};
                    const ctx = document.getElementById('analysisChart').getContext('2d');
                    new Chart(ctx, config);
                }}
            }});
        </script>
        </body></html>"""
        return html_content
    except Exception as e:
        empty_json = json.dumps({})
        return f"<h1>报告生成失败</h1><p>解析AI返回的数据时出错: {e}</p><pre>{str(empty_json)}</pre>"

# --- 核心任务执行函数 (双引擎 + 幽灵数据修复版) ---
def real_task_runner(keyword, timeframe, sort_order, limit, search_mode, blocked_keywords, analysis_mode):
    print(f"--- [演员上台] Keyword: {keyword}, Mode: {analysis_mode} ---")
    try:
        subreddits_for_this_task = ""
        if search_mode == "smart":
            subreddits_for_this_task = get_ai_subreddits(keyword)
        elif search_mode == "standard":
            subreddits_for_this_task = SUBREDDITS_TO_SEARCH
        
        update_status_file("正在连接 Reddit...", 20)
        reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET, user_agent=REDDIT_USER_AGENT, username=REDDIT_USERNAME, password=REDDIT_PASSWORD)
        
        individual_subreddits = ['all'] if search_mode == 'all_reddit' else [s.replace('r/', '') for s in subreddits_for_this_task.split('+') if s]
        if not individual_subreddits: raise ValueError("未能确定任何要搜索的版块。")

        update_status_file(f"在 {len(individual_subreddits)} 个版块中搜索...", 25)
        
        target_fetch_count = int(limit) * 3
        quota_per_sub = (target_fetch_count // len(individual_subreddits)) if len(individual_subreddits) > 0 else target_fetch_count
        all_search_results = []
        
        for sub_name in individual_subreddits:
            try:
                search_query = ""
                final_sort_order = sort_order
                
                if analysis_mode == 'pain_points':
                    print(f"--- [PRAW] ==> 正在版块 r/{sub_name} 中以“痛点挖掘”模式搜索...")
                    pain_point_keywords = [f'{keyword} {p}' for p in ['problem', 'issue', 'recommendation', 'help', 'question', 'advice', 'frustrated', 'annoying', 'wish', 'sucks', 'broken', 'how to', 'alternative', 'fix', 'solution', 'nightmare', 'disappointed']]
                    search_query = f'({" OR ".join(pain_point_keywords)})'
                    final_sort_order = 'relevance'
                else:
                    print(f"--- [PRAW] ==> 正在版块 r/{sub_name} 中以“热点分析”模式搜索...")
                    search_query = f'"{keyword}"'
                
                subreddit = reddit.subreddit(sub_name)
                search_params = {'query': search_query, 'limit': quota_per_sub, 'sort': final_sort_order}
                if final_sort_order in ['top', 'relevance']:
                    search_params['time_filter'] = timeframe
                all_search_results.extend(list(subreddit.search(**search_params)))
            except Exception as e:
                print(f"!!! [PRAW] 警告：搜索 r/{sub_name} 时出错: {e}。已跳过。!!!")

        print(f"--- [PRAW] 抓取完成，共获得 {len(all_search_results)} 个帖子。")
        if not all_search_results: raise ValueError(f"未能找到关于 '{keyword}' 的任何帖子。请尝试“市场热点分析”模式或更换关键词。")

        update_status_file("帖子抓取完毕，正在排序和过滤...", 40)
        all_search_results.sort(key=lambda x: x.score, reverse=True)
        
        final_submissions = []
        for s in all_search_results:
            if len(final_submissions) >= int(limit): break
            if not any(bw in s.title.lower() for bw in blocked_keywords):
                final_submissions.append(s)

        print(f"--- [主任务] 筛选完成，最终选定 {len(final_submissions)} 个帖子进行分析。")
        if not final_submissions: raise ValueError(f"过滤屏蔽词后，未能找到有效的帖子。")

        update_status_file(f"正在从 {len(final_submissions)} 个帖子中抓取评论...", 50)
        comments_for_analysis = []
        for submission in final_submissions:
            submission.comments.replace_more(limit=0)
            comments_for_analysis.extend([{"body": c.body, "score": c.score, "replies": len(c.replies), "permalink": f"https://www.reddit.com{c.permalink}"} for c in submission.comments.list()])
        if not comments_for_analysis: raise ValueError("未能找到任何相关的评论。")
        
        comments_text = "\n".join([json.dumps(c, ensure_ascii=False) for c in comments_for_analysis])

        update_status_file("数据整理完毕，正在请求 Gemini AI 分析...", 65)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = ""
        if analysis_mode == 'pain_points':
            prompt = f"""你是一位顶级的、专注于用户体验的产品经理。你的核心任务是从以下关于 "{keyword}" 的 Reddit 评论中，深度挖掘用户在**具体使用场景**中遇到的**真实痛点**。
            你的任务要求：1. **聚焦负面体验**。2. **忽略无关内容**。3. **总结3-5个核心痛点**。4. **严格的JSON格式**，特别是 executiveSummary 必须是一个包含 overallSentiment 和 keyFindings 数组的JSON对象。
            {{
                "executiveSummary": {{ "overallSentiment": "在这里用一句话概述最重要的发现。", "keyFindings": ["发现一", "发现二", "发现三"] }},
                "identifiedPainPoints": [{{"title": "痛点标题", "usageScenario": "痛点发生的使用场景", "description": "详细描述痛点", "count": 0}}],
                "chartData": {{"labels": ["痛点一"], "data": [0], "colors": ["#D2B48C", "#E9DDc7", "#856404"]}},
                "commentExamples": [{{"painPointTitle": "所属痛点标题", "commentTranslation": "将代表性评论翻译成中文", "score": 0, "replies": 0, "permalink": "评论URL"}}]
            }} --- 原始评论数据 --- {comments_text[:TOTAL_CHARS_LIMIT]}"""
        else: # hot_topics
            prompt = f"""你是一位敏锐的市场研究专家。你的任务是从以下关于 "{keyword}" 的 Reddit 评论中，总结出热门的讨论主题和用户的主流观点。
            你的任务要求：1. **识别5-8个核心议题**。2. **总结主流观点**。3. **严格的JSON格式**，特别是 executiveSummary 必须是一个包含 overallSentiment 和 keyFindings 数组的JSON对象。
            {{
                "executiveSummary": {{ "overallSentiment": "在这里用一句话概述最重要的发现。", "keyFindings": ["发现一", "发现二", "发现三"] }},
                "keyDiscussionTopics": [{{"title": "议题标题", "description": "概括主流观点", "count": 0}}],
                "chartData": {{"labels": ["议题一"], "data": [0], "colors": ["#D2B48C", "#E9DDc7", "#856404"]}},
                "commentExamples": [{{"associatedTopic": "所属议题标题", "commentTranslation": "将代表性评论翻译成中文", "score": 0, "replies": 0, "permalink": "评论URL"}}]
            }} --- 原始评论数据 --- {comments_text[:TOTAL_CHARS_LIMIT]}"""
            
        response = model.generate_content(prompt)
        
        update_status_file("AI响应已收到，准备解析JSON...", 85)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if not match:
            print("--- AI原始返回内容 ---\n" + response.text + "\n--------------------")
            raise ValueError("AI响应格式不正确，任务中断。")
            
        report_data_json = json.loads(match.group(0))

        update_status_file("AI 分析完成，正在生成HTML报告...", 90)
        report_html = generate_report_html(json.dumps(report_data_json), keyword, individual_subreddits, analysis_mode)
        
        update_status_file("报告生成完毕，正在保存文件...", 95)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"report_{keyword.replace(' ','_')}_{timestamp}.html"
        report_filepath = os.path.join('static', report_filename)
        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(report_html)
            
        update_status_file("已完成", 100, report_url=f"/static/{report_filename}")

    except Exception as e:
        print(f"!!! [主任务] 任务执行过程中发生严重错误: {e} !!!")
        update_status_file(f"任务出错: {str(e)}", 100)

# --- Flask 路由 (带锁) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.route('/start-task', methods=['POST'])
def start_task():
    try:
        with file_lock:
            initial_state = { "status": "任务初始化...", "progress": 0, "report_url": "", "ai_subreddits": None }
            with open(STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(initial_state, f, ensure_ascii=False)

        data = request.json
        print(f"--- [导演接收剧本] Keyword: {data.get('keyword')}, Mode: {data.get('analysis_mode')}")
        
        # 关键修复：使用安全的默认值获取方式
        blocked_keywords_from_frontend = data.get('blocked_keywords')
        final_blocked_keywords = blocked_keywords_from_frontend if blocked_keywords_from_frontend is not None else DEFAULT_BLOCKED_KEYWORDS.copy()

        thread = threading.Thread(target=real_task_runner, args=(
            data.get('keyword'), 
            data.get('timeframe', 'year'), 
            data.get('sort_order', 'relevance'), 
            data.get('limit', 10), 
            data.get('subreddits', 'smart'), 
            final_blocked_keywords, 
            data.get('analysis_mode', 'pain_points')
        ))
        thread.start()
        return jsonify({"message": "任务已成功启动"})
    except Exception as e:
        print(f"!!! 任务启动失败: {e} !!!")
        update_status_file(f"任务启动失败: {str(e)}", 100)
        return jsonify({"message": "任务启动失败"}), 500

@app.route('/task-status')
def task_status():
    try:
        with file_lock:
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
        return jsonify(status_data)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"status": "等待任务启动...", "progress": 0, "report_url": ""})

# --- 服务器启动 ---
print("\n--- 准备启动服务器 ---")
if __name__ == '__main__':
    print("--- 使用 Waitress 服务器启动 ---")
    serve(app, host='0.0.0.0', port=5000, threads=8)
