/* Unified Script — SAFAR */
document.addEventListener('DOMContentLoaded', () => {
  // Navbar scroll + mobile toggle
  const nav = document.getElementById('main-nav');
  const menuToggle = document.getElementById('menu-toggle');
  const navLinks = document.getElementById('nav-links');
  if (nav) window.addEventListener('scroll', () => nav.classList.toggle('scrolled', window.scrollY > 60));
  if (menuToggle && navLinks) {
    menuToggle.addEventListener('click', () => navLinks.classList.toggle('open'));
    navLinks.querySelectorAll('a').forEach(a => a.addEventListener('click', () => navLinks.classList.remove('open')));
  }

  // Chatbot
  const fab     = document.getElementById('chatbot-fab');
  const panel   = document.getElementById('chatbot-panel');
  const closeBtn = document.getElementById('chatbot-close');
  const clearBtn = document.getElementById('chatbot-clear');
  const input    = document.getElementById('chatbot-input');
  const sendBtn  = document.getElementById('chatbot-send');
  const msgBox   = document.getElementById('chatbot-msgs');

  if (!panel) return;

  if (fab) fab.addEventListener('click', () => panel.classList.toggle('open'));
  if (closeBtn) closeBtn.addEventListener('click', () => panel.classList.remove('open'));
  if (clearBtn) clearBtn.addEventListener('click', () => {
    if (msgBox) msgBox.innerHTML = '<div class="chat-msg bot"><p>Chat cleared! How can I help you? 👋</p></div>';
  });

  function sendMessage() {
    const text = (input.value || '').trim();
    if (!text) return;
    appendMsg(text, 'user');
    input.value = '';
    getBotResponse(text);
  }

  if (sendBtn) sendBtn.addEventListener('click', sendMessage);
  if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

  function appendMsg(text, who) {
    if (!msgBox) return;
    const d = document.createElement('div');
    d.className = 'chat-msg ' + who;
    const time = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
    d.innerHTML = '<p>' + text.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</p><small>' + time + '</small>';
    msgBox.appendChild(d);
    msgBox.scrollTop = msgBox.scrollHeight;
  }

  function showTyping() {
    const t = document.createElement('div');
    t.className = 'typing-dots'; t.id = 'typing-indicator';
    t.innerHTML = '<span></span><span></span><span></span>';
    msgBox.appendChild(t); msgBox.scrollTop = msgBox.scrollHeight;
  }
  function hideTyping() { const t = document.getElementById('typing-indicator'); if (t) t.remove(); }

  const local = {
    'how it works': 'SAFAR lets you create/join travel groups and chat with members. Our AI-powered safety system adds real-time GPS tracking! 🌍',
    'join group': 'Go to Groups, browse available groups, and click "Join". Public groups are instant — private groups need approval. 👥',
    'safety': 'SAFAR tracks your GPS in real-time, checks safety zones, detects anomalies, and lets you send a one-tap panic alert. 🛡️',
    'create group': 'On the Groups page, fill in group name, type, destination, and description — then hit Create! ✈️',
    'panic': 'The PANIC button instantly alerts authorities with your GPS location and sets your safety score to 0. 🆘',
    'hello': 'Hi there! 👋 I can help with travel groups, destinations, safety features, or anything else. What do you need?',
    'help': 'I can help with: groups 👥, safety 🛡️, destinations 🗺️, and platform features. Just ask!',
  };

  async function getBotResponse(msg) {
    showTyping();
    const lower = msg.toLowerCase();
    for (const [k, v] of Object.entries(local)) {
      if (lower.includes(k)) { setTimeout(() => { hideTyping(); appendMsg(v, 'bot'); }, 700); return; }
    }
    try {
      const res = await fetch('/api/chatbot', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:msg}) });
      hideTyping();
      if (res.ok) { const d = await res.json(); appendMsg(d.response, 'bot'); }
      else appendMsg("Sorry, couldn't process that. Try again! 😊", 'bot');
    } catch { hideTyping(); appendMsg("Trouble connecting — check your internet and retry! 🔌", 'bot'); }
  }

  // --- UI ANIMATIONS OVERHAUL ---

  // 0. Auto-inject Loader & Cursor HTML if missing
  if (!document.getElementById('global-loader')) {
    const l = document.createElement('div');
    l.id = 'global-loader';
    l.className = 'page-loader';
    l.innerHTML = '<div class="loader-logo">SAFAR</div>';
    document.body.prepend(l);
  }
  
  if (!document.getElementById('custom-cursor')) {
    const c = document.createElement('div');
    c.id = 'custom-cursor';
    c.className = 'custom-cursor';
    document.body.appendChild(c);
  }

  // 1. Smooth Page Loader
  const loader = document.getElementById('global-loader');
  if (loader) {
    // Force minimum 500ms display for smooth entrance, then fade out
    setTimeout(() => {
      loader.classList.add('hidden');
      setTimeout(() => loader.style.display = 'none', 800);
    }, 500);
  }

  // 2. Custom Cursor
  const cursor = document.getElementById('custom-cursor');
  if (cursor) {
    document.addEventListener('mousemove', (e) => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
    });
    
    // Add hover effect for interactive elements
    const interactives = document.querySelectorAll('a, button, .card, .card-3d, .dest-card, .feature-card, input, select');
    interactives.forEach(el => {
      el.addEventListener('mouseenter', () => cursor.classList.add('hovering'));
      el.addEventListener('mouseleave', () => cursor.classList.remove('hovering'));
    });
  }

  // 3. Entrance Reveals (Intersection Observer)
  const reveals = document.querySelectorAll('.reveal');
  if (reveals.length > 0) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
          // Optional: stop observing once revealed
          // revealObserver.unobserve(entry.target); 
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' });
    
    reveals.forEach(r => revealObserver.observe(r));
  }

  // 4. 3D Tilt Motion for Hero Mascots & Cards
  const tiltElements = document.querySelectorAll('[data-tilt]');
  tiltElements.forEach(el => {
    el.addEventListener('mousemove', (e) => {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      // Calculate rotation (max 15 degrees)
      const rotateX = ((y - centerY) / centerY) * -15; 
      const rotateY = ((x - centerX) / centerX) * 15;
      
      // Select the inner 3D object (assuming it's the mascot image)
      const target = el.querySelector('img') || el;
      target.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.05, 1.05, 1.05) translateZ(50px)`;
      target.style.transition = 'transform 0.1s ease-out';
    });
    
    el.addEventListener('mouseleave', () => {
      const target = el.querySelector('img') || el;
      target.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1) translateZ(0px)';
      // Slower transition back to rest
      target.style.transition = 'transform 0.5s ease-in-out';
    });
  });

});
