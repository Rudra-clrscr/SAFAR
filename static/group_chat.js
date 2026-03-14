/* Group Chat — SAFAR */
document.addEventListener('DOMContentLoaded', () => {
  const socket = io();
  const form   = document.querySelector('#chat-form') || document.querySelector('.chat-input-bar');
  const input  = document.getElementById('msg-input');
  const sendBtn= document.getElementById('send-btn');
  const msgs   = document.getElementById('messages');
  const groupId = document.body.dataset.groupId;
  const me      = document.body.dataset.username;

  if (groupId) socket.emit('join', { group_id: groupId });

  function appendMsg(sender, text, time, isSent) {
    const row = document.createElement('div');
    row.className = 'msg-row ' + (isSent ? 'sent' : 'received');
    const t = time ? new Date(time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : '';
    row.innerHTML = `
      <div class="msg-avatar">${sender[0].toUpperCase()}</div>
      <div>
        ${!isSent ? `<div class="msg-name">${sender}</div>` : ''}
        <div class="msg-bubble">${text}</div>
        <div class="msg-time">${t}</div>
      </div>`;
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function send() {
    const text = input.value.trim();
    if (!text || !groupId) return;
    fetch(`/api/tt/groups/${groupId}/messages`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ message: text })
    }).then(r => r.json()).then(d => {
      if (d.id) input.value = '';
    }).catch(console.error);
  }

  if (sendBtn) sendBtn.addEventListener('click', send);
  if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

  socket.on('new_message', data => {
    appendMsg(data.sender, data.message, data.timestamp, data.sender === me);
  });

  if (msgs) msgs.scrollTop = msgs.scrollHeight;
});
