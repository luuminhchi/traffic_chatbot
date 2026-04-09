let chatHistory = [],
  currentChat = [],
  isLoading = false,
  isSending = false,
  currentChatIndex = -1;

const messagesContainer = document.getElementById("messages");
const inputField = document.getElementById("inputField");
const sendBtn = document.getElementById("sendBtn");
const historySidebar = document.getElementById("historySidebar");

inputField.addEventListener("input", () => {
  inputField.style.height = "auto";
  inputField.style.height = Math.min(inputField.scrollHeight, 100) + "px";
});

function updateSidebar() {
  historySidebar.innerHTML = "";
  chatHistory.forEach((item, index) => {
    // Safety check: verify item has data
    if (!item || (Array.isArray(item) && item.length === 0)) {
      return; // Skip empty conversations
    }

    const chatItem = document.createElement("div");
    chatItem.className =
      "chat-item" + (currentChatIndex === index ? " active" : "");

    // Get first question - handle both array and object formats
    let firstQuestion = "";
    if (Array.isArray(item) && item[0] && item[0].question) {
      firstQuestion = item[0].question;
    } else if (item.question) {
      firstQuestion = item.question;
    } else {
      firstQuestion = "Chat không có tiêu đề";
    }

    chatItem.textContent =
      firstQuestion.substring(0, 80) + (firstQuestion.length > 80 ? "..." : "");
    chatItem.onclick = () => loadChatByIndex(index);
    historySidebar.appendChild(chatItem);
  });
}

async function loadChatHistory() {
  try {
    const res = await fetch("/api/history/");
    const data = await res.json();
    // Nếu đang gửi tin nhắn thì không ghi đè giao diện
    if (isSending) return;
    if (
      data.success &&
      data.history &&
      Array.isArray(data.history) &&
      data.history.length > 0
    ) {
      // History từ server là array của conversations (mỗi conversation là array của messages)
      chatHistory = data.history.filter(
        (conv) => conv && (Array.isArray(conv) ? conv.length > 0 : true),
      );
      if (chatHistory.length > 0) {
        showWelcome();
        updateSidebar();
      } else {
        showWelcome();
      }
    } else {
      showWelcome();
    }
  } catch (err) {
    console.log("First chat or error loading history", err);
    if (!isSending) showWelcome();
  }
}

function showWelcome() {
  currentChat = [];
  currentChatIndex = -1;
  messagesContainer.classList.remove("has-messages");
  messagesContainer.innerHTML = `<div style="flex:1; display:flex; align-items:center; justify-content:center; width:100%;">
    <div class="welcome-section">
      <div class="welcome-icon">⚖️</div>
      <div class="welcome-title">Trợ lý Luật Giao Thông Việt Nam</div>
      <p class="welcome-subtitle">Hỏi bất kỳ câu hỏi nào về luật giao thông, mức phạt, quy định và các vấn đề liên quan</p>
      <div class="examples">
        <button class="example-btn" onclick="sendQuestion('Lỗi không đội mũ bảo hiểm xe máy bị phạt bao nhiêu?')">🚲 Mũ bảo hiểm</button>
        <button class="example-btn" onclick="sendQuestion('Tốc độ tối đa cho xe máy?')">🏁 Tốc độ</button>
        <button class="example-btn" onclick="sendQuestion('Phạt bao nhiêu nếu vượt đèn đỏ?')">🚦 Đèn đỏ</button>
        <button class="example-btn" onclick="sendQuestion('Tài liệu phải mang theo khi lái xe?')">📋 Tài liệu</button>
      </div>
    </div>
  </div>`;
  updateSidebar();
}

function displayChatMessages(chatMessages) {
  if (!chatMessages || chatMessages.length === 0) {
    messagesContainer.innerHTML = "";
    return;
  }

  messagesContainer.innerHTML = "";
  messagesContainer.classList.add("has-messages");
  chatMessages.forEach((item) => {
    if (!item) return;
    if (item.question) addMessageToUI(item.question, "user");
    if (item.answer) addMessageToUI(item.answer, "bot", item.sources);
  });
  scrollToBottom();
}

function loadChatByIndex(index) {
  if (currentChatIndex === index) return;
  currentChatIndex = index;

  // Handle both array and object formats
  const selectedConversation = chatHistory[index];
  if (Array.isArray(selectedConversation)) {
    currentChat = selectedConversation;
  } else {
    currentChat = Array.isArray(selectedConversation)
      ? selectedConversation
      : [selectedConversation];
  }

  messagesContainer.classList.add("has-messages");
  displayChatMessages(currentChat);
  updateSidebar();
}

async function sendMessage() {
  const question = inputField.value.trim();
  if (!question || isSending) return;

  isSending = true;
  inputField.value = "";
  inputField.style.height = "44px";

  if (currentChat.length === 0) {
    messagesContainer.innerHTML = "";
    messagesContainer.classList.add("has-messages");
  }

  addMessageToUI(question, "user");
  setLoading(true);

  try {
    const res = await fetch("/api/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: currentChat }),
    });

    const data = await res.json();

    if (data.success) {
      setLoading(false);
      addMessageToUI(data.answer, "bot", data.sources);

      currentChat.push({
        question,
        answer: data.answer,
        sources: data.sources || [],
      });

      if (currentChatIndex === -1) {
        chatHistory.push([...currentChat]);
        currentChatIndex = chatHistory.length - 1;
      } else {
        chatHistory[currentChatIndex] = [...currentChat];
      }

      updateSidebar();

      // Lưu history lên server kèm index để UPDATE thay vì APPEND
      await fetch("/api/history/save/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: currentChat,
          conversation_index: currentChatIndex,
        }),
      });
    } else {
      addMessageToUI("Có lỗi: " + data.error, "bot");
    }
  } catch (err) {
    addMessageToUI("Lỗi kết nối: " + err.message, "bot");
  } finally {
    setLoading(false);
    isSending = false;
  }
}

function addMessageToUI(text, sender, sources = null) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${sender}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.innerHTML = sender === "user" ? "👤" : "⚖️";

  const content = document.createElement("div");
  content.className = "message-content";
  content.textContent = text;

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(content);
  messagesContainer.appendChild(msgDiv);

  if (sender === "bot" && sources && sources.length > 0) {
    const sourceDiv = document.createElement("div");
    sourceDiv.className = "sources-box";
    sourceDiv.innerHTML = "<strong>Nguồn:</strong> " + sources.join(", ");
    messagesContainer.appendChild(sourceDiv);
  }

  scrollToBottom();
}

function scrollToBottom() {
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function setLoading(state) {
  isLoading = state;
  if (state) {
    const spinner = document.createElement("div");
    spinner.className = "loading-spinner";
    spinner.id = "loadingSpinner";
    spinner.innerHTML = `
      <div class="message-avatar" style="background: var(--bg-dark); color: var(--primary);">⚖️</div>
      <div class="loading-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
    `;
    messagesContainer.appendChild(spinner);
    scrollToBottom();
  } else {
    const spinner = document.getElementById("loadingSpinner");
    if (spinner) spinner.remove();
  }
  sendBtn.disabled = state;
}

function handleKeyPress(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function sendQuestion(q) {
  inputField.value = q;
  sendMessage();
}

function startNewChat() {
  showWelcome();
  updateSidebar();
}

window.addEventListener("DOMContentLoaded", loadChatHistory);
