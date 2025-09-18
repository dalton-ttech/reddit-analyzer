document.addEventListener('DOMContentLoaded', function() {
    console.log("--- 页面加载完毕，JS脚本开始执行 ---");

    // --- 默认屏蔽词列表 ---
    let currentBlockedKeywords = ["shower", "politics", "trump", "war", "navy", "smoke", "military", "game"];

    // --- 获取所有需要操作的HTML元素 ---
    const startButton = document.getElementById('start-task');
    const progressContainer = document.getElementById('progress-container');
    const progressText = document.getElementById('progress-text');
    const progressBar = document.querySelector('.progress-bar-foreground');
    const resultContainer = document.getElementById('result-container');
    const formContainer = document.querySelector('.form-container');
    const viewReportButton = document.getElementById('view-report-button');
    const blocklistContainer = document.getElementById('blocklist-container');
    const newBlockwordInput = document.getElementById('new-blockword-input');
    const addBlockwordBtn = document.getElementById('add-blockword-btn');
    const sortOrderSelect = document.getElementById('sort_order');
    const timeframeSelect = document.getElementById('timeframe');
    
    let pollingInterval;
    let aiBoxShown = false;

    // --- 动态屏蔽词功能 ---
    function renderBlocklistTags() {
        blocklistContainer.innerHTML = '';
        currentBlockedKeywords.forEach(word => {
            const tag = document.createElement('div');
            tag.className = 'blocklist-tag';
            tag.innerHTML = `<span>${word}</span><button class="remove-tag-btn" data-word="${word}">&times;</button>`;
            blocklistContainer.appendChild(tag);
        });
    }

    function addBlockword() {
        const newWord = newBlockwordInput.value.trim().toLowerCase();
        if (newWord && !currentBlockedKeywords.includes(newWord)) {
            currentBlockedKeywords.push(newWord);
            renderBlocklistTags();
        }
        newBlockwordInput.value = '';
    }

    addBlockwordBtn.addEventListener('click', addBlockword);
    newBlockwordInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            addBlockword();
        }
    });
    blocklistContainer.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-tag-btn')) {
            const wordToRemove = event.target.dataset.word;
            currentBlockedKeywords = currentBlockedKeywords.filter(word => word !== wordToRemove);
            renderBlocklistTags();
        }
    });

    // --- 动态UI联动功能 ---
    function updateTimeframeState() {
        const selectedSort = sortOrderSelect.value;
        if (selectedSort === 'hot' || selectedSort === 'new') {
            timeframeSelect.disabled = true;
            timeframeSelect.classList.add('disabled-look');
        } else {
            timeframeSelect.disabled = false;
            timeframeSelect.classList.remove('disabled-look');
        }
    }

    sortOrderSelect.addEventListener('change', updateTimeframeState);

    // --- 核心：任务启动与轮询 ---
    startButton.addEventListener('click', function() {
        console.log("--- “开始任务”按钮被点击 ---");
        aiBoxShown = false;

        const taskData = {
            keyword: document.getElementById('keyword').value,
            timeframe: document.getElementById('timeframe').value,
            sort_order: document.getElementById('sort_order').value,
            subreddits: document.getElementById('subreddits').value,
            limit: document.getElementById('limit').value,
            analysis_mode: document.getElementById('analysis_mode').value,
            blocked_keywords: currentBlockedKeywords
        };

        if (!taskData.keyword.trim()) {
            alert('请输入关键词！');
            return;
        }

        console.log("--- 已准备好要发送的数据:", taskData);
        
        formContainer.classList.add('hidden');
        progressContainer.classList.remove('hidden');
        resultContainer.classList.add('hidden');
        const aiBox = document.getElementById('ai-recommendation-box');
        if(aiBox) {
            aiBox.classList.add('hidden');
            aiBox.classList.remove('visible');
        }

        fetch('/start-task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData),
        })
        .then(response => {
            if (!response.ok) throw new Error('网络响应不正常');
            return response.json();
        })
        .then(data => {
            console.log("--- 任务已在后端成功启动，准备开始轮询 ---", data.message);
            // 清除可能存在的上一次的定时器
            if(pollingInterval) clearInterval(pollingInterval);
            // 启动新的定时器
            pollingInterval = setInterval(checkStatus, 1500);
        })
        .catch(error => {
            console.error("!!! 启动任务时发生fetch错误:", error);
            progressText.innerText = '启动任务失败，请检查后端服务或网络。';
        });
    });

    /**
     * 关键函数：检查后台任务状态并更新UI
     */
    function checkStatus() {
        fetch('/task-status')
            .then(response => {
                if (!response.ok) throw new Error('查询状态失败');
                return response.json();
            })
            .then(data => {
                progressText.innerText = data.status;
                progressBar.style.width = data.progress + '%';

                if (data.ai_subreddits && !aiBoxShown) {
                    const aiList = document.getElementById('ai-subreddits-list');
                    if (aiList) {
                        aiList.innerHTML = '';
                        data.ai_subreddits.forEach(sub => {
                            const listItem = document.createElement('li');
                            listItem.textContent = `r/${sub.name} (${sub.translation})`;
                            aiList.appendChild(listItem);
                        });
                        const aiBox = document.getElementById('ai-recommendation-box');
                        aiBox.classList.remove('hidden');
                        setTimeout(() => aiBox.classList.add('visible'), 50);
                        aiBoxShown = true;
                    }
                }

                if (data.progress >= 100) {
                    clearInterval(pollingInterval);
                    if (data.report_url) {
                        viewReportButton.href = data.report_url;
                        viewReportButton.target = "_blank";
                        viewReportButton.textContent = "点击查看洞察报告";
                        viewReportButton.style.backgroundColor = "";
                        viewReportButton.style.cursor = "";

                    } else {
                        viewReportButton.href = "#";
                        viewReportButton.textContent = "生成报告失败";
                        viewReportButton.style.backgroundColor = "#888";
                        viewReportButton.style.cursor = "not-allowed";
                    }
                    setTimeout(() => {
                        progressContainer.classList.add('hidden');
                        const aiBox = document.getElementById('ai-recommendation-box');
                        if(aiBox) aiBox.classList.add('hidden');
                        resultContainer.classList.remove('hidden');
                    }, 500);
                }
            })
            .catch(error => {
                console.error('查询状态时出错:', error);
                clearInterval(pollingInterval);
                progressText.innerText = '查询进度失败，连接可能已断开。';
            });
    }
    
    // --- 页面加载时初始化 ---
    renderBlocklistTags();
    updateTimeframeState();
});
