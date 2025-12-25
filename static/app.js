const state = {
  articles: [],
  activeTag: "ALL",
  selectedId: null,
  dateLabel: null,
};

const listEl = document.getElementById("article-list");
const detailEl = document.getElementById("detail");
const tagRowEl = document.getElementById("tag-row");
const resultCountEl = document.getElementById("result-count");
const dateChipEl = document.getElementById("today-date");
const refreshBtn = document.getElementById("refresh-btn");

const escapeHtml = (text) =>
  (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

const formatDirection = (direction) => {
  if (direction === "up") return "上升";
  if (direction === "down") return "下降";
  return "無明顯差異";
};

const impactLabel = (level) => {
  if (level === "yes") return "可能影響";
  if (level === "possibly") return "可能但需保留";
  return "不太影響";
};

const buildTagButton = (tag) => {
  const button = document.createElement("button");
  button.className = `tag ${state.activeTag === tag.value ? "active" : ""}`;
  button.textContent = tag.label;
  button.addEventListener("click", () => {
    state.activeTag = tag.value;
    render();
  });
  return button;
};

const renderTags = () => {
  tagRowEl.innerHTML = "";
  const tagSet = new Set();
  state.articles.forEach((article) => {
    article.tags.forEach((tag) => tagSet.add(tag));
  });
  const tags = [
    { label: "全部", value: "ALL" },
    { label: "已收藏", value: "FAVORITES" },
  ];
  Array.from(tagSet).forEach((tag) => tags.push({ label: tag, value: tag }));
  tags.forEach((tag) => tagRowEl.appendChild(buildTagButton(tag)));
};

const renderList = () => {
  listEl.innerHTML = "";
  let articles = state.articles;
  if (state.activeTag === "FAVORITES") {
    articles = articles.filter((article) => article.favorite);
  } else if (state.activeTag !== "ALL") {
    articles = articles.filter((article) => article.tags.includes(state.activeTag));
  }
  resultCountEl.textContent = `${articles.length} 篇`;
  if (articles.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "沒有資料。請切換主題或先執行匯入。";
    listEl.appendChild(empty);
    return;
  }

  articles.forEach((article, index) => {
    const card = document.createElement("div");
    card.className = "article-card";
    card.style.setProperty("--i", index);
    card.innerHTML = `
      <div class="article-title">${escapeHtml(article.title)}</div>
      <div class="article-meta">
        <span>${escapeHtml(article.journal)}</span>
        <span>${escapeHtml(article.publish_date)}</span>
        <span>${escapeHtml(article.study_type)}</span>
      </div>
      <div class="article-meta">
        ${article.tags.map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("")}
        ${article.favorite ? `<span class="tag-pill">已收藏</span>` : ""}
      </div>
      <div class="muted">${escapeHtml(article.key_takeaway)}</div>
    `;
    card.addEventListener("click", () => {
      state.selectedId = article.id;
      renderDetail();
    });
    listEl.appendChild(card);
  });
};

const renderDetail = () => {
  const article = state.articles.find((item) => item.id === state.selectedId);
  if (!article) {
    detailEl.innerHTML = `
      <div class="empty-state">
        選擇文章以查看重點摘要、PICO 與臨床影響。
      </div>
    `;
    return;
  }

  detailEl.innerHTML = `
    <div class="detail-header">
      <div>
        <div class="detail-title">${escapeHtml(article.title)}</div>
        <div class="article-meta">
          <span>${escapeHtml(article.journal)}</span>
          <span>${escapeHtml(article.publish_date)}</span>
          <span>${escapeHtml(article.study_type)}</span>
        </div>
      </div>
      <button class="favorite-btn ${article.favorite ? "saved" : ""}" id="favorite-btn">
        ${article.favorite ? "已收藏" : "收藏"}
      </button>
    </div>
    <div class="section">
      <h3>一句話重點</h3>
      <p>${escapeHtml(article.key_takeaway)}</p>
    </div>
    <div class="section">
      <h3>臨床框架（PICO）</h3>
      <p><strong>P:</strong> ${escapeHtml(article.pico.P)}</p>
      <p><strong>I:</strong> ${escapeHtml(article.pico.I)}</p>
      <p><strong>C:</strong> ${escapeHtml(article.pico.C)}</p>
      <p><strong>O:</strong> ${escapeHtml(article.pico.O)}</p>
    </div>
    <div class="section">
      <h3>主要結果</h3>
      <p>${escapeHtml(article.primary_outcome)}</p>
      <p><strong>方向：</strong> ${formatDirection(article.outcome_direction)}</p>
    </div>
    <div class="section">
      <h3>實務影響</h3>
      <div class="impact">
        <span class="impact-badge ${escapeHtml(article.impact.level)}">${escapeHtml(
    impactLabel(article.impact.level)
  )}</span>
        <span>${escapeHtml(article.impact.reason)}</span>
      </div>
      <p class="muted">非臨床建議。</p>
    </div>
    <div class="section">
      <a class="detail-link" href="${escapeHtml(article.url)}" target="_blank" rel="noreferrer">
        在 PubMed 查看
      </a>
    </div>
  `;

  const favoriteBtn = document.getElementById("favorite-btn");
  favoriteBtn.addEventListener("click", async (event) => {
    event.stopPropagation();
    const response = await fetch(`/api/favorites/${article.id}`, { method: "POST" });
    const data = await response.json();
    article.favorite = data.favorite;
    render();
  });
};

const render = () => {
  renderTags();
  renderList();
  renderDetail();
};

const loadArticles = async () => {
  const today = new Date().toISOString().slice(0, 10);
  let response = await fetch(`/api/articles?date=${today}`);
  let data = await response.json();
  if (!data.articles.length) {
    response = await fetch("/api/articles");
    data = await response.json();
  }
  state.articles = data.articles;
  state.dateLabel = data.date || today;
  state.selectedId = state.articles[0] ? state.articles[0].id : null;
  dateChipEl.textContent = state.dateLabel;
  render();
};

refreshBtn.addEventListener("click", loadArticles);

loadArticles();
