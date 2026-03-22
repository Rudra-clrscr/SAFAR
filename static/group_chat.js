/* ================================================================
   SAFAR — WhatsApp-Style Group Chat (group_chat.js)
   Real-time messaging, typing indicators, emoji, auto-scroll
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
  const socket   = io();
  const body     = document.body;
  const groupId  = body.dataset.groupId;
  const me       = body.dataset.username;

  // DOM refs
  const msgsEl     = document.getElementById('messages');
  const inputEl    = document.getElementById('msg-input');
  const sendBtn    = document.getElementById('send-btn');
  const emojiBtn   = document.getElementById('emoji-btn');
  const emojiPicker= document.getElementById('emoji-picker');
  const emojiTabs  = document.getElementById('emoji-tabs');
  const emojiGrid  = document.getElementById('emoji-grid');
  const scrollFab  = document.getElementById('scroll-fab');
  const unreadBadge= document.getElementById('unread-badge');
  const typingEl   = document.getElementById('typing-indicator');
  const typingName = document.getElementById('typing-name');
  const searchInput= document.getElementById('msg-search');
  const sidebar    = document.getElementById('chat-sidebar');
  const overlay    = document.getElementById('sidebar-overlay');
  const membersBtn = document.getElementById('members-toggle-btn');
  const searchToggle= document.getElementById('search-toggle-btn');
  const loadMoreBtn= document.getElementById('load-more-btn');
  const loadMoreWrap= document.getElementById('load-more-wrap');
  const emptyState = document.getElementById('empty-state');
  const onlineCountEl  = document.getElementById('online-count');
  const topOnlineEl    = document.getElementById('top-online-count');

  let unreadCount   = 0;
  let typingTimeout = null;
  let isTyping      = false;
  let lastSender    = null;
  let senderColors  = {};
  let colorIndex    = 0;
  let oldestMsgId   = null;
  let hasMoreMsgs   = true;

  // ─── SocketIO Join ────────────────────────
  if (groupId) {
    socket.emit('join', { group_id: groupId, username: me });
  }

  // ─── Sender Color Assignment ──────────────
  function getSenderColor(name) {
    if (!senderColors[name]) {
      senderColors[name] = colorIndex % 8;
      colorIndex++;
    }
    return `sender-color-${senderColors[name]}`;
  }

  // ─── Date Formatting ─────────────────────
  function formatDate(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
    const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());

    if (msgDay.getTime() === today.getTime()) return 'Today';
    if (msgDay.getTime() === yesterday.getTime()) return 'Yesterday';
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function formatTime(dateStr) {
    if (!dateStr) return '';
    // If already formatted as HH:MM, return as is
    if (/^\d{1,2}:\d{2}$/.test(dateStr)) return dateStr;
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // ─── Scroll Helpers ──────────────────────
  function isNearBottom() {
    return msgsEl.scrollHeight - msgsEl.scrollTop - msgsEl.clientHeight < 120;
  }

  function scrollToBottom(smooth) {
    msgsEl.scrollTo({ top: msgsEl.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
    unreadCount = 0;
    unreadBadge.style.display = 'none';
    scrollFab.classList.remove('visible');
  }

  msgsEl.addEventListener('scroll', () => {
    if (isNearBottom()) {
      scrollFab.classList.remove('visible');
      unreadCount = 0;
      unreadBadge.style.display = 'none';
    } else {
      scrollFab.classList.add('visible');
    }
  });

  scrollFab.addEventListener('click', () => scrollToBottom(true));

  // ─── Message Rendering ────────────────────
  function createMsgRow(sender, text, timestamp, isSent, animate) {
    const isContinuation = (lastSender === sender);

    const row = document.createElement('div');
    row.className = `msg-row ${isSent ? 'sent' : 'received'}${isContinuation ? ' continuation' : ''}`;
    row.dataset.sender = sender;
    row.dataset.ts = timestamp;
    if (!animate) row.style.animation = 'none';

    const time = formatTime(timestamp);

    row.innerHTML = `
      <div class="msg-avatar">${sender[0].toUpperCase()}</div>
      <div class="msg-content">
        ${(!isSent && !isContinuation) ? `<div class="msg-name ${getSenderColor(sender)}">${escapeHtml(sender)}</div>` : ''}
        <div class="msg-bubble">${escapeHtml(text)}</div>
        <div class="msg-footer">
          <span class="msg-time">${time}</span>
          ${isSent ? '<span class="msg-ticks">✓✓</span>' : ''}
        </div>
      </div>`;

    lastSender = sender;
    return row;
  }

  function addDateSeparator(dateStr) {
    const label = formatDate(dateStr);
    const sep = document.createElement('div');
    sep.className = 'chat-date-sep';
    sep.innerHTML = `<span>${label}</span>`;
    msgsEl.insertBefore(sep, typingEl);
    return label;
  }

  function addSystemMsg(text) {
    const el = document.createElement('div');
    el.className = 'chat-system-msg';
    el.innerHTML = `<span>${escapeHtml(text)}</span>`;
    msgsEl.insertBefore(el, typingEl);
    lastSender = null;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ─── Initialize existing messages ─────────
  function initExistingMessages() {
    const existing = msgsEl.querySelectorAll('.msg-row');
    let prevDate = null;
    let prevSender = null;

    existing.forEach(row => {
      const sender = row.dataset.sender;
      const ts = row.dataset.ts;

      // Assign sender colors for received messages
      if (sender !== me) {
        const nameEl = row.querySelector('.msg-name');
        if (nameEl) nameEl.classList.add(getSenderColor(sender));
      }

      // Mark continuations
      if (prevSender === sender) {
        row.classList.add('continuation');
      }

      // Track for date separators
      if (ts) {
        try {
          const d = new Date(ts);
          if (!isNaN(d.getTime())) {
            const dateKey = d.toDateString();
            if (dateKey !== prevDate) {
              // Insert date separator before this row
              const sep = document.createElement('div');
              sep.className = 'chat-date-sep';
              sep.innerHTML = `<span>${formatDate(ts)}</span>`;
              row.parentNode.insertBefore(sep, row);
              prevDate = dateKey;
            }
          }
        } catch(e) {}
      }

      prevSender = sender;
      row.style.animation = 'none';
    });

    lastSender = prevSender;
    scrollToBottom(false);
  }

  initExistingMessages();

  // ─── Send Message ─────────────────────────
  function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || !groupId) return;

    // Hide empty state
    if (emptyState) emptyState.style.display = 'none';

    // Optimistic UI
    const now = new Date().toISOString();
    const row = createMsgRow(me, text, now, true, true);
    msgsEl.insertBefore(row, typingEl);
    scrollToBottom(true);
    inputEl.value = '';
    autoResizeInput();

    // Stop typing
    if (isTyping) {
      socket.emit('stop_typing', { group_id: groupId });
      isTyping = false;
    }

    // Send via API
    fetch(`/api/tt/groups/${groupId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    }).then(r => r.json()).then(d => {
      if (!d.id) console.warn('Message not confirmed:', d);
    }).catch(err => {
      console.error('Send failed:', err);
      row.querySelector('.msg-ticks').textContent = '✗';
      row.querySelector('.msg-ticks').style.color = '#ef4444';
    });
  }

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // ─── Auto-resize textarea ─────────────────
  function autoResizeInput() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  }
  inputEl.addEventListener('input', autoResizeInput);

  // ─── Typing Indicator ─────────────────────
  inputEl.addEventListener('input', () => {
    if (!isTyping && inputEl.value.trim()) {
      isTyping = true;
      socket.emit('typing', { group_id: groupId, username: me });
    }
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
      if (isTyping) {
        isTyping = false;
        socket.emit('stop_typing', { group_id: groupId, username: me });
      }
    }, 2000);
  });

  // Remote typing
  const typingUsers = new Set();
  socket.on('user_typing', data => {
    if (data.username === me) return;
    typingUsers.add(data.username);
    updateTypingDisplay();
  });

  socket.on('user_stop_typing', data => {
    typingUsers.delete(data.username);
    updateTypingDisplay();
  });

  function updateTypingDisplay() {
    if (typingUsers.size === 0) {
      typingEl.classList.remove('visible');
      return;
    }
    const names = Array.from(typingUsers);
    let text;
    if (names.length === 1) text = `${names[0]} is typing`;
    else if (names.length === 2) text = `${names[0]} and ${names[1]} are typing`;
    else text = `${names.length} people are typing`;
    typingName.textContent = text;
    typingEl.classList.add('visible');
    if (isNearBottom()) scrollToBottom(true);
  }

  // ─── Incoming Messages ────────────────────
  socket.on('new_message', data => {
    if (data.sender === me) return; // We already added it optimistically

    if (emptyState) emptyState.style.display = 'none';

    // Check if we need a date separator
    const msgDate = new Date(data.timestamp);
    const lastDateSep = msgsEl.querySelectorAll('.chat-date-sep');
    const lastLabel = lastDateSep.length > 0 ? lastDateSep[lastDateSep.length - 1].textContent : '';
    const newLabel = formatDate(data.timestamp);
    if (newLabel !== lastLabel) {
      addDateSeparator(data.timestamp);
    }

    // Remove from typing
    typingUsers.delete(data.sender);
    updateTypingDisplay();

    const row = createMsgRow(data.sender, data.message, data.timestamp, false, true);
    msgsEl.insertBefore(row, typingEl);

    if (isNearBottom()) {
      scrollToBottom(true);
    } else {
      unreadCount++;
      unreadBadge.textContent = unreadCount;
      unreadBadge.style.display = 'flex';
      scrollFab.classList.add('visible');
    }

    // Notification sound
    if (document.hidden) {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        osc.type = 'sine';
        gain.gain.value = 0.08;
        osc.start();
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
        osc.stop(ctx.currentTime + 0.15);
      } catch(e) {}
    }
  });

  // ─── System events ────────────────────────
  socket.on('user_joined', data => {
    if (data.username !== me) {
      addSystemMsg(`${data.username} joined the chat`);
      if (isNearBottom()) scrollToBottom(true);
    }
  });

  socket.on('user_left', data => {
    addSystemMsg(`${data.username} left the chat`);
    if (isNearBottom()) scrollToBottom(true);
  });

  // ─── Online tracking ─────────────────────
  socket.on('online_users', data => {
    const online = data.users || [];
    const count = online.length;
    if (onlineCountEl) onlineCountEl.textContent = count;
    if (topOnlineEl) topOnlineEl.textContent = `${count} online`;

    // Update sidebar dots
    document.querySelectorAll('.member-chip').forEach(chip => {
      const uname = chip.dataset.username;
      const dotEl = document.getElementById(`dot-${uname}`);
      if (dotEl) {
        dotEl.className = online.includes(uname) ? 'online-dot' : 'offline-dot';
      }
    });
  });

  // ─── Emoji Picker ─────────────────────────
  const emojiData = {
    '😀': ['😀','😁','😂','🤣','😃','😄','😅','😆','😉','😊','😋','😎','😍','🥰','😘','😗','😙','😚','🙂','🤗','🤩','🤔','🤨','😐','😑','😶','🙄','😏','😣','😥','😮','🤐','😯','😪','😫','🥱','😴','😌','😛','😜','😝','🤤','😒','😓','😔','😕','🙃','🤑','😲','🙁','😖','😞','😤','😢','😭','😦','😧','😨','😩','🤯','😬','😰','😱','🥵','🥶','😳','🤪','😵','🥴','😠','😡','🤬','😈','👿','💀','☠️','💩','🤡','👹','👺','👻','👽','👾','🤖'],
    '👋': ['👋','🤚','🖐️','✋','🖖','👌','🤌','🤏','✌️','🤞','🫰','🤟','🤘','🤙','👈','👉','👆','🖕','👇','☝️','👍','👎','✊','👊','🤛','🤜','👏','🙌','🫶','👐','🤲','🤝','🙏','✍️','💪','🦵','🦶','👂','🫀'],
    '🌍': ['🌍','🌎','🌏','🌐','🗺️','🏔️','⛰️','🌋','🗻','🏕️','🏖️','🏜️','🏝️','🏞️','🌅','🌄','🌇','🌆','🌃','🌉','🌁','✈️','🛩️','🛫','🛬','🚀','🛸','🚁','🚂','🚃','🚄','🚅','🚆','🚇','🚈','🚉','🚊','🚝','🚞','🚋','🚌','🚍','🚎','🚐','🚑','🚒','🚓','🚕','🚗','🏎️','⛵','🚤','🛥️','🛳️','🚢'],
    '🍔': ['🍔','🍕','🍟','🌭','🌮','🌯','🥙','🧆','🥚','🍳','🥘','🍲','🍜','🍝','🍛','🍣','🍱','🥟','🍤','🍙','🍚','🍘','🍥','🥮','🍢','🍡','🍧','🍨','🍦','🥧','🧁','🍰','🎂','🍮','🍭','🍬','🍫','🍿','🍩','🍪','🌰','🥜','🍯','🥛','☕','🍵','🧃','🥤','🍶','🍺','🥂','🍷','🥃','🍹','🍸','🧊'],
    '⚽': ['⚽','🏀','🏈','⚾','🥎','🎾','🏐','🏉','🥏','🎱','🏓','🏸','🏒','🏑','🥍','🏏','🪃','🥅','⛳','🏹','🎣','🥊','🥋','🎿','⛷️','🏂','🪂','🏋️','🤸','🤽','🧗','🤾','🏄','🚣','🏊','🚴','🚵','🎽','🏅','🎖️','🥇','🥈','🥉','🏆','🎯','🎮','🕹️','🎲','🎭','🎪'],
    '❤️': ['❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','❣️','💕','💞','💓','💗','💖','💘','💝','💟','☮️','✝️','☪️','🕉️','☸️','✡️','🔯','🕎','☯️','☦️','🙏','⭐','🌟','💫','✨','⚡','🔥','💥','☀️','🌈','🎉','🎊','🎵','🎶','🔔','🎁','🏳️','🏴','🚩'],
  };

  const emojiCategories = Object.keys(emojiData);
  let activeCategory = emojiCategories[0];

  function renderEmojiTabs() {
    emojiTabs.innerHTML = emojiCategories.map((cat, i) =>
      `<button class="${i === 0 ? 'active' : ''}" data-cat="${cat}">${cat}</button>`
    ).join('');

    emojiTabs.addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn) return;
      activeCategory = btn.dataset.cat;
      emojiTabs.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
      renderEmojiGrid();
    });
  }

  function renderEmojiGrid() {
    const emojis = emojiData[activeCategory] || [];
    emojiGrid.innerHTML = emojis.map(e => `<button data-emoji="${e}">${e}</button>`).join('');
  }

  renderEmojiTabs();
  renderEmojiGrid();

  emojiGrid.addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn || !btn.dataset.emoji) return;
    const start = inputEl.selectionStart;
    const end = inputEl.selectionEnd;
    const emoji = btn.dataset.emoji;
    inputEl.value = inputEl.value.substring(0, start) + emoji + inputEl.value.substring(end);
    inputEl.selectionStart = inputEl.selectionEnd = start + emoji.length;
    inputEl.focus();
    autoResizeInput();
  });

  emojiBtn.addEventListener('click', e => {
    e.stopPropagation();
    emojiPicker.classList.toggle('open');
    emojiBtn.classList.toggle('active');
  });

  document.addEventListener('click', e => {
    if (!emojiPicker.contains(e.target) && e.target !== emojiBtn) {
      emojiPicker.classList.remove('open');
      emojiBtn.classList.remove('active');
    }
  });

  // ─── Message Search ───────────────────────
  searchInput.addEventListener('input', () => {
    const query = searchInput.value.toLowerCase().trim();
    const rows = msgsEl.querySelectorAll('.msg-row');

    rows.forEach(row => {
      const bubble = row.querySelector('.msg-bubble');
      if (!bubble) return;
      const originalText = bubble.dataset.original || bubble.textContent;
      bubble.dataset.original = originalText;

      if (!query) {
        bubble.innerHTML = escapeHtml(originalText);
        row.style.opacity = '1';
        return;
      }

      const lowerText = originalText.toLowerCase();
      if (lowerText.includes(query)) {
        // Highlight matches
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        bubble.innerHTML = escapeHtml(originalText).replace(regex, '<mark>$1</mark>');
        row.style.opacity = '1';
      } else {
        bubble.innerHTML = escapeHtml(originalText);
        row.style.opacity = '0.3';
      }
    });
  });

  // ─── Sidebar Toggle (Mobile) ──────────────
  membersBtn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('visible');
    membersBtn.classList.toggle('active');
  });

  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('visible');
    membersBtn.classList.remove('active');
  });

  // Search toggle (focus sidebar search on desktop, open sidebar on mobile)
  searchToggle.addEventListener('click', () => {
    if (window.innerWidth <= 768) {
      sidebar.classList.add('open');
      overlay.classList.add('visible');
    }
    searchInput.focus();
    searchToggle.classList.toggle('active');
  });

  // ─── Load Older Messages ──────────────────
  function getFirstMsgId() {
    const firstMsg = msgsEl.querySelector('.msg-row');
    return firstMsg ? firstMsg.dataset.msgId : null;
  }

  loadMoreBtn.addEventListener('click', () => {
    if (!hasMoreMsgs) return;
    loadMoreBtn.textContent = 'Loading...';
    loadMoreBtn.disabled = true;

    let url = `/api/tt/groups/${groupId}/messages?limit=30`;
    if (oldestMsgId) url += `&before=${oldestMsgId}`;

    fetch(url)
      .then(r => r.json())
      .then(msgs => {
        if (!msgs.length || msgs.length < 30) {
          hasMoreMsgs = false;
          loadMoreWrap.style.display = 'none';
        }

        const scrollHeightBefore = msgsEl.scrollHeight;
        const scrollTopBefore = msgsEl.scrollTop;
        const fragment = document.createDocumentFragment();
        let prevSender = null;

        msgs.reverse().forEach(m => {
          const row = createMsgRow(m.sender, m.message, m.timestamp, m.sender === me, false);
          if (prevSender === m.sender) row.classList.add('continuation');
          fragment.appendChild(row);
          prevSender = m.sender;
          if (m.id && (!oldestMsgId || m.id < oldestMsgId)) oldestMsgId = m.id;
        });

        const firstChild = loadMoreWrap.nextSibling;
        msgsEl.insertBefore(fragment, firstChild);

        // Maintain scroll position
        msgsEl.scrollTop = scrollTopBefore + (msgsEl.scrollHeight - scrollHeightBefore);

        loadMoreBtn.textContent = '↑ Load older messages';
        loadMoreBtn.disabled = false;
      })
      .catch(err => {
        console.error('Load more failed:', err);
        loadMoreBtn.textContent = '↑ Load older messages';
        loadMoreBtn.disabled = false;
      });
  });

  // Show load-more if we have messages
  const initialMsgCount = msgsEl.querySelectorAll('.msg-row').length;
  if (initialMsgCount >= 100) {
    loadMoreWrap.style.display = 'flex';
    const firstRow = msgsEl.querySelector('.msg-row');
    if (firstRow && firstRow.dataset.msgId) {
      oldestMsgId = firstRow.dataset.msgId;
    }
  }

  // ─── Window focus handling ────────────────
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && isNearBottom()) {
      scrollToBottom(false);
    }
  });

  // ─── Cleanup on leave ─────────────────────
  window.addEventListener('beforeunload', () => {
    if (groupId) socket.emit('leave', { group_id: groupId, username: me });
  });
});
