// ==========================================
// FUNÇÕES UTILITÁRIAS E MODAIS
// ==========================================
function openModalOp(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'flex';
}

function closeModalOp(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'none';
}

window.novoCadastroOp = function(formId) {
    limparFormularioOp(formId);
    
    if (formId === 'form_pdv_movimentos') {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        document.getElementById('pdv_data_hora').value = `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    if (formId === 'form_vales' || formId === 'form_mdfe') {
        const inputData = formId === 'form_vales' ? 'val_data_emissao' : 'mdf_data_emissao';
        document.getElementById(inputData).value = new Date().toISOString().split('T')[0];
        
        if (formId === 'form_vales') {
            document.getElementById('val_codigo').value = "VAL-" + Math.floor(Math.random() * 100000).toString().padStart(5, '0');
        }
    }
    
    openModalOp(formId);
};

function limparFormularioOp(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
    }
}

function serializeForm(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input:not(.ignore-serialize), #${formId} select:not(.ignore-serialize), #${formId} textarea:not(.ignore-serialize)`);
    const payload = {};
    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if(key) payload[key] = input.value;
    });
    return payload;
}

window.dispatchEdit = function(formId, prefix, encoded) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    limparFormularioOp(formId);
    
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById(prefix + key);
        if (el) el.value = (value !== null && value !== undefined) ? value : '';
    }

    openModalOp(formId);
};

function showMsgOp(text) {
    const painel = document.createElement('div');
    painel.style.cssText = "position:fixed; top:20px; right:20px; background:#111; border: 2px solid #00ffcc; padding: 15px 20px; border-radius: 8px; z-index:9999; color: #fff; text-align: left; box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); font-size: 14px;";
    painel.innerHTML = `<strong>Aviso do Sistema:</strong><br><br>${text} <br><br><button onclick="this.parentElement.remove()" class="btn-neon btn-neon-danger bg-transparent p-5" style="width:100%">Fechar</button>`;
    document.body.appendChild(painel);
    setTimeout(() => { if (painel.parentElement) painel.remove(); }, 5000);
}

// ==========================================
// CONTROLO DE VISTAS (F5 PERSISTENCE)
// ==========================================
function switchOpView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    const target = document.getElementById(viewId);
    if(target) {
        target.classList.add('active');
        btnElement.classList.add('active');
    }
    
    localStorage.setItem('lastOpView', viewId);

    const loadMapOp = {
        'view_pdv_movimentos': loadPdvMovimentos,
        'view_vales': loadVales,
        'view_mdfe': loadMdfe,
        'view_balanca': loadRelBalanca
    };
    if (loadMapOp[viewId]) loadMapOp[viewId]();
}

async function loadDropdownsOperacional() {
    try {
        const res = await fetch('/api/operacional/opcoes_formularios?_t=' + new Date().getTime());
        const data = await res.json();
        
        let htmlCaixas = '<option value="">-- Selecione o Caixa --</option>';
        if (data.caixas) data.caixas.forEach(x => htmlCaixas += `<option value="${x}">${x}</option>`);
        document.querySelectorAll('.ddl-caixas').forEach(el => el.innerHTML = htmlCaixas);

        let htmlOpers = '<option value="">-- Selecione o Operador --</option>';
        if (data.operadores) data.operadores.forEach(x => htmlOpers += `<option value="${x}">${x}</option>`);
        document.querySelectorAll('.ddl-operadores').forEach(el => el.innerHTML = htmlOpers);

        let htmlCli = '<option value="">-- Selecione o Cliente --</option>';
        if (data.clientes) data.clientes.forEach(x => htmlCli += `<option value="${x}">${x}</option>`);
        document.querySelectorAll('.ddl-clientes').forEach(el => el.innerHTML = htmlCli);

        let htmlMoto = '<option value="">-- Selecione o Motorista --</option>';
        if (data.motoristas) data.motoristas.forEach(x => htmlMoto += `<option value="${x}">${x}</option>`);
        document.querySelectorAll('.ddl-motoristas').forEach(el => el.innerHTML = htmlMoto);

        let htmlVeic = '<option value="">-- Selecione o Veículo (Placa) --</option>';
        if (data.veiculos) data.veiculos.forEach(x => htmlVeic += `<option value="${x}">${x}</option>`);
        document.querySelectorAll('.ddl-veiculos').forEach(el => el.innerHTML = htmlVeic);

        let htmlCliList = '<option value="">-- Selecione o Cliente --</option>';
        if (data.clientes_list) data.clientes_list.forEach(x => htmlCliList += `<option value="${x.id}" data-nome="${x.nome}">${x.nome}</option>`);
        document.querySelectorAll('.ddl-clientes-id').forEach(el => el.innerHTML = htmlCliList);

        let htmlFuncList = '<option value="">-- Selecione o Funcionário --</option>';
        if (data.funcionarios_list) data.funcionarios_list.forEach(x => htmlFuncList += `<option value="${x.id}">${x.nome}</option>`);
        document.querySelectorAll('.ddl-funcionarios-id').forEach(el => el.innerHTML = htmlFuncList);

    } catch(e) { console.warn("Falha ao carregar opções de dropdown operacionais.", e); }
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadDropdownsOperacional();
    
    // Restaura a aba através da persistência do F5
    let lastView = localStorage.getItem('lastOpView') || 'view_pdv_movimentos';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    if(btn) {
        switchOpView(lastView, btn);
    } else {
        let firstBtn = document.querySelector('.menu-item');
        if(firstBtn) switchOpView('view_pdv_movimentos', firstBtn);
    }
});


// ==========================================
// FUNÇÕES DA API (CRUD)
// ==========================================
async function postRecordOp(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/operacional/${tabela}`, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload) 
        });
        
        const resultado = await res.json(); 

        if(res.ok && resultado.sucesso) { 
            limparFormularioOp(formId); 
            showMsgOp('Registo guardado com sucesso!');
            return true; 
        } else {
            showMsgOp('Erro no Banco de Dados: ' + (resultado.erro || 'Erro desconhecido'));
            return false;
        }
    } catch(e) { 
        showMsgOp('Falha de rede ou servidor offline.'); 
        return false; 
    }
}

async function deleteRecordOp(tabela, id, callbackFunc) {
    if(!confirm("Deseja realmente excluir este registo permanentemente?")) return;
    try {
        const res = await fetch(`/api/operacional/${tabela}/${id}`, { method: 'DELETE' });
        if(res.ok) window[callbackFunc]();
    } catch(e) {}
}

window.salvarOperacional = async function(e, tabela) {
    e.preventDefault();
    const map = { 'pdv_movimentos': 'pdv_', 'vales': 'val_', 'mdfe': 'mdf_' };
    const loadMap = { 'pdv_movimentos': loadPdvMovimentos, 'vales': loadVales, 'mdfe': loadMdfe };
    
    const formId = `form_${tabela}`;
    const payload = serializeForm(formId, map[tabela]);

    if (await postRecordOp(tabela, payload, formId)) {
        closeModalOp(formId);
        if(loadMap[tabela]) loadMap[tabela]();
    }
};

function acBtns(frm, prefix, item, tbName, loadFunc) {
    let enc = encodeURIComponent(JSON.stringify(item));
    return `<button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('${frm}', '${prefix}', '${enc}')">✏️</button> <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordOp('${tbName}', ${item.id}, '${loadFunc}')">🗑️</button>`;
}

// ==========================================
// LOADERS (CARREGAR TABELAS)
// ==========================================
async function loadPdvMovimentos() {
    try {
        const res = await fetch('/api/operacional/pdv_movimentos'); 
        const data = await res.json();
        const tb = document.getElementById('tb_pdv_movimentos'); 
        if(!tb) return;
        tb.innerHTML = '';
        data.forEach(i => {
            let corVal = i.tipo === 'Suprimento' ? 'text-success' : 'text-danger';
            tb.innerHTML += `<tr>
                <td>${(i.data_hora || '').replace('T', ' ')}</td>
                <td class="text-info">${i.caixa_nome || '-'}</td>
                <td>${i.operador || '-'}</td>
                <td class="font-bold ${corVal}">${i.tipo || '-'}</td>
                <td class="font-bold ${corVal}">R$ ${Number(i.valor || 0).toFixed(2)}</td>
                <td class="text-center">${acBtns('form_pdv_movimentos', 'pdv_', i, 'pdv_movimentos', 'loadPdvMovimentos')}</td>
            </tr>`; 
        });
    } catch(e) { console.error("Erro ao carregar PDV:", e); }
}

async function loadVales() {
    try {
        const res = await fetch('/api/operacional/vales'); 
        const data = await res.json();
        const tb = document.getElementById('tb_vales'); 
        if(!tb) return;
        tb.innerHTML = '';
        data.forEach(i => {
            tb.innerHTML += `<tr>
                <td class="font-bold text-warning">${i.codigo || '-'}</td>
                <td>${i.data || i.data_emissao || '-'}</td>
                <td>${i.cliente_nome || '-'}</td>
                <td class="text-success font-bold">R$ ${Number(i.valor || 0).toFixed(2)}</td>
                <td>${i.validade || '-'}</td>
                <td class="font-bold">${i.status || '-'}</td>
                <td class="text-center">${acBtns('form_vales', 'val_', i, 'vales', 'loadVales')}</td>
            </tr>`; 
        });
    } catch(e) { console.error("Erro ao carregar Vales:", e); }
}

async function loadMdfe() {
    try {
        const res = await fetch('/api/operacional/mdfe'); 
        const data = await res.json();
        const tb = document.getElementById('tb_mdfe'); 
        if(!tb) return;
        tb.innerHTML = '';
        data.forEach(i => {
            tb.innerHTML += `<tr>
                <td class="font-bold text-warning">${i.numero || '-'} / ${i.serie || '-'}</td>
                <td>${i.data_emissao || '-'}</td>
                <td class="text-info">${i.motorista_nome || '-'}</td>
                <td>${i.placa_veiculo || '-'}</td>
                <td class="font-bold text-success">${i.status || '-'}</td>
                <td class="text-center">${acBtns('form_mdfe', 'mdf_', i, 'mdfe', 'loadMdfe')}</td>
            </tr>`; 
        });
    } catch(e) { console.error("Erro ao carregar MDF-e:", e); }
}

async function loadRelBalanca() {
    try {
        const res = await fetch('/api/operacional/relatorios/balanca'); 
        const data = await res.json();
        const tb = document.getElementById('tb_rel_balanca'); 
        if(!tb) return;
        tb.innerHTML = '';
        data.forEach(i => {
            let color = i.status.includes('Crítica') ? 'text-danger' : 'text-success';
            tb.innerHTML += `<tr>
                <td>${i.data || '-'}</td>
                <td class="font-bold">${i.item || '-'}</td>
                <td>${Number(i.peso_sistema || 0).toFixed(3)}</td>
                <td>${Number(i.peso_balanca || 0).toFixed(3)}</td>
                <td class="font-bold ${color}">${i.status || '-'}</td>
            </tr>`;
        });
    } catch(e) { console.error("Erro ao carregar Balança:", e); }
}

window.loadPdvMovimentos = loadPdvMovimentos;
window.loadVales = loadVales;
window.loadMdfe = loadMdfe;
window.loadRelBalanca = loadRelBalanca;

// ==========================================
// EXPORTAÇÃO E IMPRESSÃO (EXCEL E PDF)
// ==========================================
function getCleanTableDataOp(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return { headers: [], rows: [] };
    const headers = [];
    const rows = [];
    const headerCells = table.querySelectorAll('thead th');
    let skipCols = [];

    headerCells.forEach((th, index) => {
        const thText = th.innerText.toLowerCase().trim();
        if (thText !== 'ação' && thText !== 'ações') {
            headers.push(th.innerText);
        } else {
            skipCols.push(index);
        }
    });

    const tbodyRows = table.querySelectorAll('tbody tr');
    tbodyRows.forEach(tr => {
        const rowData = [];
        const cells = tr.querySelectorAll('td');
        if(cells.length === 1 && cells[0].colSpan > 1) return;

        cells.forEach((td, index) => {
            if (!skipCols.includes(index)) {
                rowData.push(td.innerText);
            }
        });
        if (rowData.length > 0) rows.push(rowData);
    });

    return { headers, rows };
}

window.exportarExcelOp = function(tableId, fileName) {
    if (typeof XLSX === 'undefined') { alert('A biblioteca Excel não carregou.'); return; }
    const data = getCleanTableDataOp(tableId);
    if(data.rows.length === 0) { showMsgOp("Não há dados para exportar."); return; }
    const ws = XLSX.utils.aoa_to_sheet([data.headers, ...data.rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Relatório");
    XLSX.writeFile(wb, fileName + ".xlsx");
};

window.exportarPDFOp = function(tableId, title) {
    if (typeof window.jspdf === 'undefined') { alert('A biblioteca PDF não carregou.'); return; }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const data = getCleanTableDataOp(tableId);
    if(data.rows.length === 0) { showMsgOp("Não há dados para exportar."); return; }
    doc.text(title, 14, 15);
    doc.autoTable({ head: [data.headers], body: data.rows, startY: 20, theme: 'grid' });
    doc.save(title.replace(/\s+/g, '_') + ".pdf");
};