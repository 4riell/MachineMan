// =========================================================
// LÓGICA EXCLUSIVA DA TELA DE NOTIFICAÇÕES (notificacoes.js)
// =========================================================

document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auto') === 'true') {
        ativarAlarme();
    }
});

function ativarAlarme() {
    const telaAlerta = document.getElementById('tela-cheia-alerta');
    const audioLocal = document.getElementById('audio-sirene');
    
    if (telaAlerta) {
        telaAlerta.style.display = 'flex';
        document.body.classList.add('modo-alarme');
    }

    // Tenta tocar o áudio local de fallback caso a aba principal tenha sido fechada
    if (audioLocal && localStorage.getItem('pref_som') !== 'false') {
        audioLocal.play().catch(e => {
            console.log("Aguardando clique na tela vermelha para liberar o som de backup...");
        });
    }
}

function garantirSom() {
    const audioLocal = document.getElementById('audio-sirene');
    if (audioLocal && audioLocal.paused && localStorage.getItem('pref_som') !== 'false') {
        audioLocal.play();
    }
}

function pararAlarme(event) {
    if(event) event.stopPropagation(); 
    
    // 1. Para o som de backup local do Pop-up
    const audioLocal = document.getElementById('audio-sirene');
    if (audioLocal) {
        audioLocal.pause();
        audioLocal.currentTime = 0;
    }

    // 2. MANDA A JANELA PRINCIPAL PARAR O ALARME DELA TAMBÉM!
    if (window.opener && window.opener.pararAlarmeGlobal) {
        window.opener.pararAlarmeGlobal();
    }
    
    // Esconde a tela vermelha
    const telaAlerta = document.getElementById('tela-cheia-alerta');
    if (telaAlerta) {
        telaAlerta.style.display = 'none';
        document.body.classList.remove('modo-alarme');
    }
    
    window.history.replaceState({}, document.title, "/notificacoes");
}

async function marcarLida(id) {
    await fetch(`/api/notificacoes/${id}/lida`, { method: 'POST' });
    window.location.reload();
}

async function excluirNotificacao(id) {
    await fetch(`/api/notificacoes/${id}`, { method: 'DELETE' });
    window.location.reload();
}

async function limparTudo() {
    if(confirm("Tem certeza que deseja apagar permanentemente todas as notificações?")) {
        await fetch(`/api/notificacoes/limpar_tudo`, { method: 'DELETE' });
        window.location.reload();
    }
}

function salvarPreferencias() {
    const toggleSom = document.getElementById('toggleSom').checked;
    const toggleVisual = document.getElementById('toggleVisual').checked;
    
    localStorage.setItem('pref_som', toggleSom);
    localStorage.setItem('pref_visual', toggleVisual);
}

function atualizarFiltros() {
    const inativos = document.getElementById('toggleInativos').checked;
    const restritos = document.getElementById('toggleRestritos').checked;
    
    fetch('/api/notificacoes/preferencias', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inativos, restritos })
    }).then(() => window.location.reload());
}

window.addEventListener('load', () => {
    const toggleSom = document.getElementById('toggleSom');
    const toggleVisual = document.getElementById('toggleVisual');
    
    if (toggleSom) toggleSom.checked = localStorage.getItem('pref_som') !== 'false';
    if (toggleVisual) toggleVisual.checked = localStorage.getItem('pref_visual') !== 'false';
});