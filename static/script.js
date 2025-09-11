document.addEventListener('DOMContentLoaded', function() {
    console.log("--- 页面加载完毕，JS脚本开始执行 ---");

    // 获取所有需要操作的HTML元素
    const startButton = document.getElementById('start-task');
    const progressContainer = document.getElementById('progress-container');
    const progressText = document.getElementById('progress-text');
    const progressBar = document.querySelector('.progress-bar-foreground');
    const resultContainer = document.getElementById('result-container');
    const formContainer = document.querySelector('.form-container');
    const viewReportButton = document.getElementById('view-report-button');

    // 检查按钮是否存在
    if (startButton) {
        console.log("--- “开始任务”按钮已成功找到 ---");
    } else {
        console.error("!!! 严重错误：找不到id为 'start-task' 的按钮 !!!");
        return; // 如果找不到按钮，后续代码不执行
    }

    let pollingInterval; 
    let aiBoxShown = false; // <--- 新增这行，这是一个开关，确保信息框只显示一次
    // 当用户点击“开始任务”按钮时
    startButton.addEventListener('click', function() {
        console.log("--- “开始任务”按钮被点击 ---");
        aiBoxShown = false;
        // 1. 从输入框获取用户选项
        const keyword = document.getElementById('keyword').value;
        console.log("--- 获取到关键词:", keyword);
        
        const timeframe = document.getElementById('timeframe').value;
        console.log("--- 获取到时间范围:", timeframe);

        const sortOrder = document.getElementById('sort_order').value;
        console.log("--- 获取到排序方式:", sortOrder);

        const subreddits = document.getElementById('subreddits').value;
        console.log("--- 获取到版块选项:", subreddits);

        const limit = document.getElementById('limit').value;
        console.log("--- 获取到帖子数量:", limit);

        // 简单的前端验证
        console.log("--- 准备进行关键词验证 ---");
        if (!keyword) {
            console.log("--- 验证失败：关键词为空 ---");
            alert('请输入关键词！');
            return;
        }
        console.log("--- 关键词验证通过 ---");

        // 2. 准备发送给后端的数据
        const taskData = {
            keyword: keyword,
            timeframe: timeframe,
            sort_order: sortOrder,
            subreddits: subreddits,
            limit: limit
        };
        console.log("--- 已准备好要发送的数据:", taskData);

        // 3. 切换界面显示：隐藏表单，显示进度条
        console.log("--- 准备隐藏表单，显示进度条 ---");
        formContainer.classList.add('hidden');
        progressContainer.classList.remove('hidden');
        resultContainer.classList.add('hidden');
        console.log("--- 界面已切换 ---");
        
        // 4. 发送“开始任务”请求给后端
        console.log("--- 准备发送 fetch 请求到 /start-task ---");
        fetch('/start-task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData),
        })
        .then(response => {
            console.log("--- 收到 /start-task 的响应 ---");
            if (!response.ok) {
                throw new Error('网络响应不正常');
            }
            return response.json();
        })
        .then(data => {
            console.log("--- 任务已在后端成功启动，准备开始轮询 ---", data.message);
            pollingInterval = setInterval(checkStatus, 1500);
        })
        .catch(error => {
            console.error("!!! 启动任务时发生fetch错误:", error);
            progressText.innerText = '启动任务失败，请检查后端服务或网络。';
        });
    });

    // 查询状态的函数 (这部分保持不变)
    function checkStatus() {
    fetch('/task-status')
        .then(response => response.json())
        .then(data => {
            // --- 你已有的代码 (保持不变) ---
            progressText.innerText = data.status;
            progressBar.style.width = data.progress + '%';

            // --- 从这里开始，是我们新增的代码 ---
            // 检查后端是否发来了 ai_subreddits 数据，并且我们的信息框还没显示过
            if (data.ai_subreddits && !aiBoxShown) {
                console.log("--- 检测到AI推荐的版块，准备显示信息框 ---", data.ai_subreddits);
                const aiBox = document.getElementById('ai-recommendation-box');
                const aiList = document.getElementById('ai-subreddits-list');
                
                // 确保我们找到了对应的HTML元素
                if (aiBox && aiList) {
                    aiList.innerHTML = ''; // 清空上一次可能留下的内容
                    
                    // 遍历后端发来的数据，创建列表项
                    data.ai_subreddits.forEach(sub => {
                        const listItem = document.createElement('li');
                        listItem.textContent = `r/${sub.name} (${sub.translation})`;
                        aiList.appendChild(listItem);
                    });
                    
                    // 让信息框显示出来
                    aiBox.classList.remove('hidden');
                    // 用一个极短的延时来触发CSS动画效果
                    setTimeout(() => {
                        aiBox.classList.add('visible');
                    }, 50);

                    // 把“开关”关上，确保这个信息框只被创建和显示一次
                    aiBoxShown = true; 
                }
            }
            // --- 新增代码到此结束 ---


            // --- 你已有的代码 (保持不变) ---
            if (data.progress >= 100) {
                clearInterval(pollingInterval);
                if (data.report_url) {
                    viewReportButton.href = data.report_url;
                    viewReportButton.target = "_blank";
                } else {
                    viewReportButton.innerText = "生成报告失败";
                    viewReportButton.style.backgroundColor = "#888";
                    viewReportButton.style.cursor = "not-allowed";
                }
                setTimeout(() => {
                    progressContainer.classList.add('hidden');
                    // 当任务完成时，也顺便把AI信息框隐藏掉
                    const aiBox = document.getElementById('ai-recommendation-box');
                    if(aiBox) {
                        aiBox.classList.add('hidden');
                        aiBox.classList.remove('visible'); // 重置样式
                    }
                    resultContainer.classList.remove('hidden');
                }, 500);
            }
        })
        .catch(error => {
            console.error('查询状态时出错:', error);
            clearInterval(pollingInterval);
            progressText.innerText = '查询进度失败，连接可能已断开。';
        });
    }})