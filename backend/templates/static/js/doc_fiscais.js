// ==========================================
// TOASTS E NOTIFICAÇÕES GLOBAIS
// ==========================================
window.showToast = function(msg, type = 'info') {
    const container = document.getElementById('toast_container');
    if(!container) return;
    const toast = document.createElement('div');
    const colors = {
        'success': 'background: rgba(16, 185, 129, 0.9); border-left: 4px solid #059669;',
        'error': 'background: rgba(239, 68, 68, 0.9); border-left: 4px solid #b91c1c;',
        'info': 'background: rgba(59, 130, 246, 0.9); border-left: 4px solid #2563eb;',
        'warning': 'background: rgba(245, 158, 11, 0.9); border-left: 4px solid #d97706;'
    };
    toast.style.cssText = `
        ${colors[type] || colors['info']}
        color: white; padding: 15px 20px; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        font-family: sans-serif; font-size: 0.9rem; font-weight: bold;
        animation: slideIn 0.3s ease forwards; min-width: 250px;
    `;
    toast.innerHTML = msg;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
};

window.customConfirm = function(msg, callback) {
    document.getElementById('custom_confirm_msg').innerText = msg;
    const modal = document.getElementById('custom_confirm_modal');
    modal.classList.add('active');
    
    document.getElementById('btn_confirm_yes').onclick = function() {
        modal.classList.remove('active');
        callback();
    };
};

// ==========================================
// CONTROLES DE INTERFACE
// ==========================================
function switchDocView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(viewId).classList.add('active');
    btnElement.classList.add('active');

    const loaders = { 'view_mde': loadMde, 'view_nfce': loadNotas, 'view_ciap': loadCiap, 'view_inventario': loadInventario };
    if (loaders[viewId]) loaders[viewId]();
}

function openModalFis(formId) { document.getElementById(formId + '_modal')?.classList.add('active'); }
function closeModalFis(formId) { document.getElementById(formId + '_modal')?.classList.remove('active'); }

window.novoCadastroFis = function(formId) {
    limparFormulario(formId);
    openModalFis(formId);
};

window.toggleAllCheckboxes = function(masterCheckbox, tbodyId) {
    const checkboxes = document.querySelectorAll(`#${tbodyId} input[type="checkbox"]`);
    checkboxes.forEach(cb => cb.checked = masterCheckbox.checked);
};

// ==========================================
// FUNÇÕES INTEGRADAS DA SEFAZ (MD-e)
// ==========================================

window.consultarSefaz = async function(btnElement) {
    const originalText = btnElement.innerHTML;
    btnElement.innerHTML = "⏳ Conectando Sefaz...";
    btnElement.disabled = true;

    try {
        const res = await fetch('/api/docs/mde/consultar', { method: 'POST' });
        const data = await res.json();
        
        if (data.sucesso) {
            showToast('Sincronização com a SEFAZ concluída!', 'success');
            loadMde(); // Recarrega a tabela para ver se algo novo caiu
        } else {
            showToast('Erro na consulta: ' + data.erro, 'error');
        }
    } catch(e) {
        showToast('Falha de rede ao conectar com servidor.', 'error');
    } finally {
        btnElement.innerHTML = originalText;
        btnElement.disabled = false;
    }
};

window.enviarManifestacao = async function(tipoEvento, btnElement) {
    const marcados = Array.from(document.querySelectorAll('#tb_mde input[type="checkbox"]:checked'));
    if(marcados.length === 0) {
        showToast("Selecione pelo menos uma Nota Fiscal na tabela.", "warning");
        return;
    }

    const originalText = btnElement.innerHTML;
    btnElement.innerHTML = "⏳ Transmitindo...";
    btnElement.disabled = true;

    const ids = marcados.map(cb => parseInt(cb.value));

    try {
        const res = await fetch('/api/docs/mde/manifestar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids, tipo_evento: tipoEvento })
        });
        const data = await res.json();
        
        if (data.sucesso) {
            showToast(data.mensagem, 'success');
            loadMde(); 
        } else {
            showToast('Erro ao Manifestar: ' + data.erro, 'error');
        }
    } catch(e) {
        showToast('Falha na comunicação ao tentar manifestar.', 'error');
    } finally {
        btnElement.innerHTML = originalText;
        btnElement.disabled = false;
        document.querySelector('#tb_mde_table thead input[type="checkbox"]').checked = false;
    }
};

window.baixarSelecionados = function() {
    const marcados = document.querySelectorAll('#tb_mde input[type="checkbox"]:checked');
    if(marcados.length === 0) {
        showToast("Selecione as notas que deseja efetuar o Download do XML.", "warning");
        return;
    }
    showToast("Preparando ZIP com XMLs selecionados...", "info");
    // Futuramente ligará com uma rota para devolver os Blobs
};

// ==========================================
// LOADERS (API FETCHERS)
// ==========================================
async function loadMde() {
    try {
        const res = await fetch('/api/docs/nfe'); 
        const data = await res.json();
        const tb = document.getElementById('tb_mde'); 
        if(!tb) return;
        tb.innerHTML = '';
        
        if (data.length === 0) {
            tb.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhuma NFe importada ainda. Clique em "Consultar SEFAZ" acima.</td></tr>';
            return;
        }

        data.forEach(i => {
            const numSerie = [i.numero, i.serie].filter(x => x && x !== '-' && x !== 'null').join(' / ') || 'S/N';
            // Destaca a cor baseada no status (Se "Sem Manifestação" é cinza/laranja, etc)
            let statusClass = "bg-alerta";
            if (i.status && i.status.includes("Ciência")) statusClass = "bg-autorizada";
            if (i.status && (i.status.includes("Desconhecimento") || i.status.includes("Não Realizada"))) statusClass = "bg-cancelada";
            
            tb.innerHTML += `<tr>
                <td class="text-center"><input type="checkbox" value="${i.id}"></td>
                <td>${i.data_emissao || '-'}</td>
                <td>
                    <div class="font-bold">${numSerie}</div>
                    <div class="text-xs text-muted" style="font-family: monospace;">${i.chave_acesso || ''}</div>
                </td>
                <td class="text-info">${i.fornecedor_nome || i.cliente_nome || '-'}</td>
                <td><span class="badge-fiscal ${statusClass}">${i.status || 'Sem Manifestação'}</span></td>
                <td class="text-success font-bold">R$ ${(Number(i.vlr_total || i.total_nota)||0).toFixed(2)}</td>
            </tr>`; 
        });
    } catch(e) { console.error("Erro Load MDE", e); }
}

async function loadNotas() {
    try {
        const [resNfe, resNfce] = await Promise.all([fetch('/api/docs/nfe'), fetch('/api/docs/nfce')]);
        const data = [...await resNfe.json(), ...await resNfce.json()].sort((a, b) => b.id - a.id);

        const tb = document.getElementById('tb_notas'); if(!tb) return;
        tb.innerHTML = '';
        data.forEach(i => {
            let statusColor = String(i.status).toLowerCase().includes('cancelada') ? 'bg-cancelada' : 'bg-autorizada';
            const numSerie = [i.numero, i.serie].filter(x => x && x !== '-' && x !== 'null').join(' / ') || '-';
            const tipoNota = i.tipo_nota || (i.nfce_numero || i.valor !== undefined ? 'NFC-e' : 'NF-e');
            
            tb.innerHTML += `<tr>
                <td class="text-center"><input type="checkbox" value="${i.id}"></td>
                <td class="font-bold">${numSerie} <span class="text-xs text-muted">(${tipoNota})</span></td>
                <td>${i.data_emissao || i.data || i.nfce_data || '-'}</td>
                <td class="text-muted text-xs" style="font-family: monospace;">${i.chave_acesso || '-'}</td>
                <td><span class="badge-fiscal ${statusColor}">${i.status || 'Autorizada'}</span></td>
                <td class="text-success font-bold">R$ ${(Number(i.vlr_total || i.valor || i.total_nota || i.nfce_valor)||0).toFixed(2)}</td>
            </tr>`; 
        });
    } catch(e) {}
}

async function loadCiap() { /* ... Lógica mantida idêntica para brevidade ... */ }
async function loadInventario() { /* ... Lógica mantida idêntica para brevidade ... */ }

// ==========================================
// FUNÇÕES UTILITÁRIAS DE INICIALIZAÇÃO
// ==========================================
function limparFormulario(formId) {
    const form = document.getElementById(formId);
    if(form) { form.reset(); const idF = form.querySelector('input[type="hidden"]'); if(idF) idF.value = ''; }
}

window.deleteRecordFis = function(tabela, id, callbackLoad) {
    customConfirm("Excluir este registro permanentemente?", async () => {
        try { 
            const res = await fetch(`/api/docs/${tabela}/${id}`, { method: 'DELETE' }); 
            if(res.ok) {
                showToast("Registro excluído.", "success");
                window[callbackLoad](); 
            }
        } catch(e) { showToast("Erro de rede.", "error"); }
    });
};

document.addEventListener("DOMContentLoaded", () => {
    loadMde(); 
});