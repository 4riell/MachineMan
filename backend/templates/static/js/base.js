// Cria o áudio de alarme global na página principal
window.audioAlarmeGlobal = new Audio('https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg');
window.audioAlarmeGlobal.loop = true; // Sirene contínua!

// Função para parar o som que poderá ser chamada pelo pop-up
window.pararAlarmeGlobal = function() {
    if (window.audioAlarmeGlobal) {
        window.audioAlarmeGlobal.pause();
        window.audioAlarmeGlobal.currentTime = 0;
    }
};

// "Hack" para liberar o áudio no navegador: No primeiro clique do usuário em qualquer lugar da tela, o som é liberado.
document.body.addEventListener('click', function unlockAudio() {
    window.audioAlarmeGlobal.play().then(() => {
        window.audioAlarmeGlobal.pause();
        window.audioAlarmeGlobal.currentTime = 0;
    }).catch(() => {});
    document.body.removeEventListener('click', unlockAudio);
}, { once: true });


let lastUnreadCount = 0; 

setInterval(async () => {
    // Se a janela atual já for o Pop-up, não fazemos nada para evitar loop
    if (window.name === 'JanelaAlerta') return;

    try {
        const showRestritos = localStorage.getItem('pref_inc_restritos') === 'true';
        const showInativos = localStorage.getItem('pref_inc_inativos') === 'true';
        
        const showPopup = localStorage.getItem('pref_visual') !== 'false'; 
        const playSom = localStorage.getItem('pref_som') !== 'false'; 

        const params = new URLSearchParams({ inc_restritos: showRestritos, inc_inativos: showInativos });
        const resp = await fetch(`/api/notificacoes/check?${params.toString()}`);
        const data = await resp.json();
        
        const countTotal = data.total_badge;
        const countFiltrado = data.unread_count; 

        const badge = document.getElementById('notif_badge');
        if (badge) {
            badge.innerText = countTotal > 99 ? '99+' : countTotal;
            badge.style.display = countTotal > 0 ? 'flex' : 'none';
        }

        // SE HOUVER MENSAGENS NOVAS...
        if (countFiltrado > 0 && countFiltrado > lastUnreadCount) {
            if (showPopup) {
                abrirAlertaPopUp();
            }
            
            if (playSom) {
                // Toca a sirene contínua diretamente na tela principal!
                window.audioAlarmeGlobal.play().catch(e => console.log('Áudio principal bloqueado', e));
            }
        }
        
        lastUnreadCount = countFiltrado;

    } catch (error) {}
}, 3000); 

let janelaPopUp = null;

function abrirAlertaPopUp() {
    if (janelaPopUp && !janelaPopUp.closed) {
        janelaPopUp.focus();
    } else {
        const w = 800; const h = 600;
        const left = (screen.width/2)-(w/2); const top = (screen.height/2)-(h/2);
        janelaPopUp = window.open('/notificacoes?auto=true', 'JanelaAlerta', `width=${w},height=${h},top=${top},left=${left},toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes`);
    }
}

// ==========================================
// PREENCHIMENTO UNIVERSAL DE SELECTS DO ERP
// ==========================================
async function loadGlobalDropdowns() {
    try {
        let resForn = await fetch('/api/suprimentos/fornecedores');
        if(resForn.ok) {
            let dataForn = await resForn.json();
            let htmlForn = '<option value="">-- Selecione o Fornecedor --</option>';
            dataForn.forEach(d => {
                let nome = d.nome_razao || d.razao_social || d.nome;
                if(nome) htmlForn += `<option value="${nome}">${nome}</option>`;
            });
            document.querySelectorAll('select[id*="fornecedor"]:not(#for_tipo_fornecedor)').forEach(el => el.innerHTML = htmlForn);
        }
    } catch(e) {}

    try {
        let resFp = await fetch('/api/financeiro/formas');
        if(resFp.ok) {
            let dataFp = await resFp.json();
            let htmlFp = '<option value="">-- Forma de Pgto --</option>';
            dataFp.forEach(d => {
                let nome = d.descricao || d.nome;
                if(nome) htmlFp += `<option value="${nome}">${nome}</option>`;
            });
            document.querySelectorAll('select[id*="forma_pgto"], select[id*="forma_pagamento"]').forEach(el => {
                let currentVal = el.value;
                el.innerHTML = htmlFp;
                if(currentVal) el.value = currentVal;
            });
        }
    } catch(e) {}

    try {
        let resCb = await fetch('/api/financeiro/contas_bancarias');
        if(resCb.ok) {
            let dataCb = await resCb.json();
            let htmlCb = '<option value="">-- Selecione a Conta --</option>';
            dataCb.forEach(d => {
                let label = d.nome;
                if (d.banco && String(d.banco).trim() !== '' && String(d.banco).toLowerCase() !== 'null' && String(d.banco).toLowerCase() !== 'none') {
                    label += ` (${String(d.banco).trim()})`;
                }
                htmlCb += `<option value="${d.nome}">${label}</option>`;
            });
            document.querySelectorAll('select[id*="conta_banco"], select[id*="banco_destino"]').forEach(el => {
                let currentVal = el.value;
                el.innerHTML = htmlCb;
                if(currentVal) el.value = currentVal;
            });
        }
    } catch(e) {}

    try {
        let resCc = await fetch('/api/financeiro/centro_custo');
        if(resCc.ok) {
            let dataCc = await resCc.json();
            let htmlCc = '<option value="">-- Centro de Custo --</option>';
            dataCc.forEach(d => htmlCc += `<option value="${d.nome}">${d.nome}</option>`);
            document.querySelectorAll('select[id*="centro_custo"]').forEach(el => {
                let currentVal = el.value;
                el.innerHTML = htmlCc;
                if(currentVal) el.value = currentVal;
            });
        }
    } catch(e) {}
}

window.toggleMenu = function(e) {
    if (e) e.preventDefault();
    const btn = document.querySelector('.hamburger-btn');
    if (btn) btn.classList.toggle('active');

    const topNav = document.getElementById('top-nav') || document.querySelector('nav');
    if (topNav) {
        topNav.classList.toggle('active');
        topNav.classList.toggle('open');
        topNav.classList.toggle('show');
        topNav.classList.toggle('menu-open'); 
    }

    const sidebar = document.querySelector('.erp-sidebar') || document.querySelector('.sidebar') || document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('active');
        sidebar.classList.toggle('open');
        sidebar.classList.toggle('show');
        sidebar.classList.toggle('menu-open');
    }
};

document.addEventListener("DOMContentLoaded", () => {
    if (!window.location.pathname.includes('/financeiro')) {
        loadGlobalDropdowns();
    }
    const menuBtn = document.querySelector('.hamburger-btn');
    if (menuBtn) {
        menuBtn.removeAttribute('onclick'); 
        menuBtn.addEventListener('click', window.toggleMenu); 
    }
});