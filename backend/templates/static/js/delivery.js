let currentMenuGrupoId = null; 
let currentAdicGrupoId = null;

// ==========================================
// FUNÇÕES UTILITÁRIAS E MODAIS
// ==========================================
function safeVal(val) { return (val === null || val === undefined || String(val).toLowerCase() === 'null' || val === '') ? '-' : val; }
function safeEdit(val) { return (val === null || val === undefined || String(val).toLowerCase() === 'null') ? '' : val; }

function openModalDel(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'flex';
}

function closeModalDel(formId) {
    const modal = document.getElementById(formId + '_modal');
    if (modal) modal.style.display = 'none';
}

window.novoCadastroDelivery = function(formId) {
    limparFormulario(formId);
    
    // Assegura que o ID do Pai está selecionado antes de abrir modal do Filho
    if(formId === 'form_menu_itens') {
        if(!currentMenuGrupoId) {
            showMsgDel("Selecione uma Categoria de Cardápio antes de adicionar um produto!");
            return;
        }
        document.getElementById('mi_grupo_id').value = currentMenuGrupoId;
    }
    if(formId === 'form_adic_itens') {
        if(!currentAdicGrupoId) {
            showMsgDel("Selecione um Grupo de Adicional antes de adicionar uma opção!");
            return;
        }
        document.getElementById('adi_grupo_id').value = currentAdicGrupoId;
    }
    
    openModalDel(formId);
};

function showMsgDel(text) {
    const painel = document.createElement('div');
    painel.style.cssText = "position:fixed; top:20px; right:20px; background:#111; border: 2px solid #00ffcc; padding: 15px 20px; border-radius: 8px; z-index:9999; color: #fff; text-align: left; box-shadow: 0 0 20px rgba(0, 255, 204, 0.4); font-size: 14px;";
    painel.innerHTML = `<strong>Aviso do Sistema:</strong><br><br>${text} <br><br><button onclick="this.parentElement.remove()" class="btn-neon btn-neon-danger bg-transparent p-5" style="width:100%">Fechar</button>`;
    document.body.appendChild(painel);
    setTimeout(() => { if (painel.parentElement) painel.remove(); }, 5000);
}

function limparFormulario(formId) {
    const form = document.getElementById(formId);
    if(form) {
        form.reset();
        const idField = form.querySelector('input[type="hidden"]');
        if(idField) idField.value = '';
    }
}

function serializeForm(formId, prefix) {
    const inputs = document.querySelectorAll(`#${formId} input, #${formId} select, #${formId} textarea`);
    const payload = {};
    inputs.forEach(input => {
        let key = input.id.replace(prefix, '');
        if(key) payload[key] = input.value;
    });
    return payload;
}

window.dispatchEdit = function(formId, prefix, encoded, isPai) {
    const itemObj = JSON.parse(decodeURIComponent(encoded));
    limparFormulario(formId);
    for (const [key, value] of Object.entries(itemObj)) {
        const el = document.getElementById(prefix + key);
        if (el) el.value = safeEdit(value);
    }
    
    if(isPai) {
        if(prefix === 'mg_') selecionarMenuGrupo(itemObj.id, itemObj.nome_grupo);
        if(prefix === 'adg_') selecionarAdicGrupo(itemObj.id, itemObj.nome_grupo);
    }
    
    openModalDel(formId);
};

// ==========================================
// CONTROLO DE VISTAS (F5 PERSISTENCE)
// ==========================================
function switchDeliveryView(viewId, btnElement) {
    document.querySelectorAll('.erp-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.menu-item').forEach(btn => btn.classList.remove('active'));
    
    const target = document.getElementById(viewId);
    if(target) {
        target.classList.add('active'); 
        btnElement.classList.add('active');
    }
    
    localStorage.setItem('lastDeliveryView', viewId);
    
    if(viewId === 'view_menu') loadMenuGrupos();
    if(viewId === 'view_adicionais') loadAdicGrupos();
}

document.addEventListener("DOMContentLoaded", async () => { 
    await loadDropdownsDelivery();
    
    // Restaura a aba através da persistência do F5
    let lastView = localStorage.getItem('lastDeliveryView') || 'view_menu';
    let btn = document.querySelector(`button[onclick*="${lastView}"]`);
    if(btn) {
        switchDeliveryView(lastView, btn);
    } else {
        let firstBtn = document.querySelector('.menu-item');
        if(firstBtn) switchDeliveryView('view_menu', firstBtn);
    }
});

// ==========================================
// PREENCHIMENTO AUTOMÁTICO DE DROPDOWNS
// ==========================================
async function loadDropdownsDelivery() {
    try {
        const resProd = await fetch('/api/delivery/produtos_erp');
        const dataProd = await resProd.json();
        
        let htmlProd = '<option value="">-- Selecione o Produto --</option>';
        dataProd.forEach(p => {
            htmlProd += `<option value="${p.id}" data-nome="${safeEdit(p.nome)}" data-preco="${safeEdit(p.preco_venda)}">${p.nome}</option>`;
        });
        
        window.optProdutos = htmlProd;
        document.querySelectorAll('.ddl-produtos-erp').forEach(el => {
            const currentVal = el.value; el.innerHTML = htmlProd; el.value = currentVal;
        });

        const resCat = await fetch('/api/cadastros/categorias');
        const dataCat = await resCat.json();
        
        let htmlCat = '<option value="">-- Selecione a Categoria --</option>';
        if(dataCat && dataCat.length > 0) {
            dataCat.forEach(c => { htmlCat += `<option value="${safeEdit(c.descricao)}">${safeEdit(c.descricao)}</option>`; });
        } else {
            htmlCat += '<option value="Pizzas">Pizzas</option><option value="Bebidas">Bebidas</option>';
        }
        
        document.querySelectorAll('.ddl-categorias-erp').forEach(el => {
            const currentVal = el.value; el.innerHTML = htmlCat; el.value = currentVal;
        });

        const resGrup = await fetch('/api/cadastros/grupos_produtos');
        const dataGrup = await resGrup.json();
        
        let htmlGrup = '<option value="">-- Selecione o Grupo --</option>';
        if(dataGrup && dataGrup.length > 0) {
            dataGrup.forEach(g => { htmlGrup += `<option value="${safeEdit(g.nome_grupo)}">${safeEdit(g.nome_grupo)}</option>`; });
        } else {
            htmlGrup += '<option value="Bordas">Bordas</option><option value="Extras">Extras</option>';
        }
        
        document.querySelectorAll('.ddl-grupos-erp').forEach(el => {
            const currentVal = el.value; el.innerHTML = htmlGrup; el.value = currentVal;
        });

    } catch(e) { console.warn("Erro ao carregar dropdowns:", e); }
}

window.updateMenuNamePrice = function(sel) {
    const opt = sel.options[sel.selectedIndex];
    if(opt && opt.value) {
        document.getElementById('mi_nome_personalizado').value = opt.getAttribute('data-nome') || '';
        document.getElementById('mi_produto_nome').value = opt.getAttribute('data-nome') || '';
        document.getElementById('mi_preco_venda').value = opt.getAttribute('data-preco') || '0';
    }
};

window.updateAdicNamePrice = function(sel) {
    const opt = sel.options[sel.selectedIndex];
    if(opt && opt.value) {
        document.getElementById('adi_nome').value = opt.getAttribute('data-nome') || '';
        document.getElementById('adi_preco_adicional').value = opt.getAttribute('data-preco') || '0';
    }
};

// ==========================================
// FUNÇÕES DE CRUD (API)
// ==========================================
async function postRecordDelivery(tabela, payload, formId) {
    try {
        const res = await fetch(`/api/delivery/${tabela}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json();
        
        if(res.ok && data.sucesso !== false) { 
            limparFormulario(formId); 
            return true; 
        }
        showMsgDel('Erro ao salvar os dados: ' + (data.erro || 'Erro desconhecido BD')); 
        return false;
    } catch(e) { 
        showMsgDel('Falha de rede.'); 
        return false; 
    }
}

async function deleteRecordDelivery(tabela, id, callback) {
    if(!confirm("Tem certeza que deseja excluir permanentemente?")) return;
    try {
        const res = await fetch(`/api/delivery/${tabela}/${id}`, { method: 'DELETE' });
        if(res.ok) callback();
    } catch(e) {}
}


// ==========================================
// CARDÁPIO: GRUPOS E ITENS
// ==========================================
async function loadMenuGrupos() {
    try {
        const res = await fetch('/api/delivery/menu_grupos'); const data = await res.json();
        const tb = document.getElementById('tb_menu_grupos'); tb.innerHTML = '';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            tb.innerHTML += `<tr>
                <td class="text-muted text-center">${i.ordem || 0}</td>
                <td class="text-primary font-bold cursor-pointer" onclick="selecionarMenuGrupo(${i.id}, '${safeEdit(i.nome_grupo).replace(/'/g,"\\'")}')">${safeVal(i.icone)} ${safeVal(i.nome_grupo)}</td>
                <td class="text-center">
                    <button type="button" class="btn-neon btn-neon-primary" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('form_menu_grupos', 'mg_', '${enc}', true)">✏️</button> 
                    <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordDelivery('menu_grupos', ${i.id}, loadMenuGrupos)">🗑️</button>
                </td>
            </tr>`; 
        });
        if(!currentMenuGrupoId) refreshMenuBadge();
    } catch(e) {}
}

window.salvarMenuGrupo = async function(e) {
    e.preventDefault();
    if(await postRecordDelivery('menu_grupos', serializeForm('form_menu_grupos', 'mg_'), 'form_menu_grupos')) {
        closeModalDel('form_menu_grupos');
        currentMenuGrupoId = null; refreshMenuBadge(); loadMenuGrupos();
    }
};

window.selecionarMenuGrupo = function(id, nome) {
    currentMenuGrupoId = id; 
    document.getElementById('mi_grupo_id').value = id;
    
    const badge = document.getElementById('menu_badge');
    badge.innerText = `Cat: ${nome}`;
    
    refreshMenuBadge();
    loadMenuItems(id);
};

window.refreshMenuBadge = function() {
    const badge = document.getElementById('menu_badge');
    const btnNovo = document.getElementById('btn_novo_item_menu');
    if(currentMenuGrupoId) {
        badge.style.display = 'inline-block';
        btnNovo.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
        btnNovo.style.display = 'none';
        document.getElementById('tb_menu_itens').innerHTML = '<tr><td colspan="5" class="text-center text-muted">Selecione uma Categoria primeiro.</td></tr>';
    }
}

async function loadMenuItems(grupo_id) {
    try {
        const res = await fetch(`/api/delivery/menu_itens/${grupo_id}`); const data = await res.json();
        const tb = document.getElementById('tb_menu_itens'); tb.innerHTML = '';
        if(data.length === 0) tb.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nenhum produto cadastrado.</td></tr>';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            const isAtivo = (i.ativo == 1 || i.disponivel == 1) ? '<span class="text-success">Sim</span>' : '<span class="text-danger">Não</span>';
            tb.innerHTML += `<tr>
                <td class="text-info">${safeVal(i.nome_personalizado)}</td>
                <td>${safeVal(i.codigo_pdv)}</td>
                <td class="text-success font-bold">R$ ${safeVal(i.preco_venda)}</td>
                <td class="text-center">${isAtivo}</td>
                <td class="text-center">
                    <button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('form_menu_itens', 'mi_', '${enc}', false)">✏️</button>
                    <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordDelivery('menu_itens', ${i.id}, () => loadMenuItems(${grupo_id}))">🗑️</button>
                </td>
            </tr>`;
        });
    } catch(e) {}
}

window.salvarMenuItem = async function(e) {
    e.preventDefault();
    if(!currentMenuGrupoId) return;
    const payload = serializeForm('form_menu_itens', 'mi_');
    if(await postRecordDelivery('menu_itens', payload, 'form_menu_itens')) {
        closeModalDel('form_menu_itens');
        document.getElementById('mi_grupo_id').value = currentMenuGrupoId; 
        loadMenuItems(currentMenuGrupoId);
    }
};

// ==========================================
// ADICIONAIS: GRUPOS E ITENS
// ==========================================
async function loadAdicGrupos() {
    try {
        const res = await fetch('/api/delivery/adicionais_grupos'); const data = await res.json();
        const tb = document.getElementById('tb_adic_grupos'); tb.innerHTML = '';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            tb.innerHTML += `<tr>
                <td class="text-warning font-bold cursor-pointer" onclick="selecionarAdicGrupo(${i.id}, '${safeEdit(i.nome_grupo).replace(/'/g,"\\'")}')">${safeVal(i.nome_grupo)}<br><small class="text-muted" style="font-weight:normal;">${safeVal(i.descricao)}</small></td>
                <td class="text-center text-xs">Min:${i.minimo||0} / Max:${i.maximo||1}</td>
                <td class="text-center">
                    <button type="button" class="btn-neon btn-neon-primary" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('form_adic_grupos', 'adg_', '${enc}', true)">✏️</button> 
                    <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordDelivery('adicionais_grupos', ${i.id}, loadAdicGrupos)">🗑️</button>
                </td>
            </tr>`; 
        });
        if(!currentAdicGrupoId) refreshAdicBadge();
    } catch(e) {}
}

window.salvarAdicGrupo = async function(e) {
    e.preventDefault();
    if(await postRecordDelivery('adicionais_grupos', serializeForm('form_adic_grupos', 'adg_'), 'form_adic_grupos')) {
        closeModalDel('form_adic_grupos');
        currentAdicGrupoId = null; refreshAdicBadge(); loadAdicGrupos();
    }
};

window.selecionarAdicGrupo = function(id, nome) {
    currentAdicGrupoId = id; 
    document.getElementById('adi_grupo_id').value = id;
    
    const badge = document.getElementById('adic_badge');
    badge.innerText = `Opções: ${nome}`;
    
    refreshAdicBadge();
    loadAdicItens(id);
};

window.refreshAdicBadge = function() {
    const badge = document.getElementById('adic_badge');
    const btnNovo = document.getElementById('btn_novo_item_adic');
    if(currentAdicGrupoId) {
        badge.style.display = 'inline-block';
        btnNovo.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
        btnNovo.style.display = 'none';
        document.getElementById('tb_adic_itens').innerHTML = '<tr><td colspan="3" class="text-center text-muted">Selecione um Grupo de Adicional primeiro.</td></tr>';
    }
}

async function loadAdicItens(grupo_id) {
    try {
        const res = await fetch(`/api/delivery/adicionais_itens/${grupo_id}`); const data = await res.json();
        const tb = document.getElementById('tb_adic_itens'); tb.innerHTML = '';
        if(data.length === 0) tb.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhuma opção cadastrada.</td></tr>';
        data.forEach(i => {
            const enc = encodeURIComponent(JSON.stringify(i));
            tb.innerHTML += `<tr>
                <td class="text-info">${safeVal(i.nome)}</td>
                <td class="text-warning font-bold">+ R$ ${safeVal(i.preco_adicional)}</td>
                <td class="text-center">
                    <button type="button" class="btn-neon btn-neon-warning" style="padding:2px 6px; font-size:0.7rem;" onclick="dispatchEdit('form_adic_itens', 'adi_', '${enc}', false)">✏️</button>
                    <button type="button" class="btn-neon btn-neon-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="deleteRecordDelivery('adicionais_itens', ${i.id}, () => loadAdicItens(${grupo_id}))">🗑️</button>
                </td>
            </tr>`;
        });
    } catch(e) {}
}

window.salvarAdicItem = async function(e) {
    e.preventDefault();
    if(!currentAdicGrupoId) return;
    const payload = serializeForm('form_adic_itens', 'adi_');
    if(await postRecordDelivery('adicionais_itens', payload, 'form_adic_itens')) {
        closeModalDel('form_adic_itens');
        document.getElementById('adi_grupo_id').value = currentAdicGrupoId; 
        loadAdicItens(currentAdicGrupoId);
    }
};

// ==========================================
// EXPORTAÇÃO E IMPRESSÃO (EXCEL, PDF, PRINT)
// ==========================================
function getCleanTableData(tableId) {
    const table = document.getElementById(tableId);
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

window.exportarExcel = function(tableId, fileName) {
    if (typeof XLSX === 'undefined') { alert('A biblioteca Excel não carregou.'); return; }
    const data = getCleanTableData(tableId);
    const ws = XLSX.utils.aoa_to_sheet([data.headers, ...data.rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Relatório");
    XLSX.writeFile(wb, fileName + ".xlsx");
};

window.exportarPDF = function(tableId, title) {
    if (typeof window.jspdf === 'undefined') { alert('A biblioteca PDF não carregou.'); return; }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const data = getCleanTableData(tableId);
    doc.text(title, 14, 15);
    doc.autoTable({ head: [data.headers], body: data.rows, startY: 20, theme: 'grid' });
    doc.save(title.replace(/\s+/g, '_') + ".pdf");
};