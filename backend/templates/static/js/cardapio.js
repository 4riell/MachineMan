const todosProdutos = JSON.parse(document.getElementById('dados-produtos-json').textContent);
const todasVariacoes = JSON.parse(document.getElementById('dados-variacoes-json').textContent);
let categoriaAtiva = 'all';
let configAtiva = 'all';
let ordemDirecao = {};

function ordenarTabela(tableId, colIndex, type) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const key = `${tableId}-${colIndex}`;
    ordemDirecao[key] = !ordemDirecao[key]; 
    const asc = ordemDirecao[key];
    rows.sort((a, b) => {
        let valA, valB;
        if (type === 'price') {
            valA = parseFloat(a.querySelector('.prod-preco').dataset.preco) || 0;
            valB = parseFloat(b.querySelector('.prod-preco').dataset.preco) || 0;
        } else {
            valA = a.children[colIndex].innerText.toLowerCase();
            valB = b.children[colIndex].innerText.toLowerCase();
        }
        if (valA < valB) return asc ? -1 : 1;
        if (valA > valB) return asc ? 1 : -1;
        return 0;
    });
    rows.forEach(row => tbody.appendChild(row));
}

const tbodyGrupos = document.getElementById('tbody-grupos');
if (tbodyGrupos) {
    tbodyGrupos.addEventListener('dragstart', e => { 
        if (configAtiva === 'all') { e.preventDefault(); return; } // Bloqueia arrastar no filtro "Todas"
        const row = e.target.closest('tr'); 
        if(row) row.classList.add('dragging'); 
    });
    tbodyGrupos.addEventListener('dragend', async e => { const row = e.target.closest('tr'); if(row) { row.classList.remove('dragging'); await salvarOrdemGrupos(); } });
    tbodyGrupos.addEventListener('dragover', e => { e.preventDefault(); const afterElement = getDragAfterElement(tbodyGrupos, e.clientY); const draggable = document.querySelector('.draggable-row.dragging'); if (afterElement == null) { tbodyGrupos.appendChild(draggable); } else { tbodyGrupos.insertBefore(draggable, afterElement); } });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.draggable-row:not(.dragging)')];
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) { return { offset: offset, element: child }; } else { return closest; }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

async function salvarOrdemGrupos() {
    const rows = document.querySelectorAll('#tbody-grupos tr.draggable-row');
    const novaOrdem = [];
    rows.forEach((row, index) => { novaOrdem.push({ id: row.dataset.id, ordem: index + 1 }); });
    try { await fetch('/api/grupos_adicionais/reordenar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ordem: novaOrdem }) }); } catch (e) { console.error(e); }
}

window.onload = function() {
    const savedTab = localStorage.getItem('activeTab') || 'tab-produtos';
    openTab(savedTab);
    
    const savedCat = localStorage.getItem('activeCat') || 'all';
    filtrarCategoria(savedCat, document.querySelector(`#prodFilters .cat-chip[data-cat-id="${savedCat}"]`));
    
    const savedConfigCat = localStorage.getItem('activeConfigCat') || 'all';
    filtrarConfig(savedConfigCat, document.querySelector(`#configFilters .cat-chip[data-cat-id="${savedConfigCat}"]`));
};

// ==========================================
// NOVA LÓGICA DE BUSCA SEPARADA
// ==========================================

// Busca 1: Apenas as categorias
function filtrarCategoriasGlobais() {
    const searchEl = document.getElementById('searchCategory');
    if (!searchEl) return;
    const termoCat = searchEl.value.toLowerCase();
    
    // Esconde/Mostra os botões de chips nas duas abas
    document.querySelectorAll('.cat-chip').forEach(chip => {
        if(chip.dataset.catId === 'all' || chip.innerText.toLowerCase().includes(termoCat)) {
            chip.style.display = '';
        } else {
            chip.style.display = 'none';
        }
    });

    // Re-aplica as buscas internas para refletir se alguma categoria sumiu
    aplicarFiltrosProdutos();
    aplicarFiltrosConfig();
}

// Clique no Chip da Aba Produtos
function filtrarCategoria(cat, btn) { 
    document.querySelectorAll('#prodFilters .cat-chip').forEach(c=>c.classList.remove('active')); 
    if(btn) btn.classList.add('active'); 
    else if(cat === 'all') {
        const first = document.querySelector('#prodFilters .cat-chip:first-child');
        if(first) first.classList.add('active');
    }
    categoriaAtiva = cat; 
    localStorage.setItem('activeCat', cat);
    aplicarFiltrosProdutos(); 
}

// Clique no Chip da Aba Configurações
function filtrarConfig(cat, btn) { 
    document.querySelectorAll('#configFilters .cat-chip').forEach(c=>c.classList.remove('active')); 
    if(btn) btn.classList.add('active'); 
    else if(cat === 'all') {
        const first = document.querySelector('#configFilters .cat-chip:first-child');
        if(first) first.classList.add('active');
    }
    
    configAtiva = cat;
    localStorage.setItem('activeConfigCat', cat);
    
    // Trava o drag & drop visualmente se estiver em "Todas"
    const allowDrag = (cat !== 'all');
    document.querySelectorAll('#tbody-grupos tr.draggable-row').forEach(r => {
        r.setAttribute('draggable', allowDrag);
        const handle = r.querySelector('.drag-handle');
        if (handle) {
            handle.style.opacity = allowDrag ? '1' : '0.2';
            handle.style.cursor = allowDrag ? 'grab' : 'not-allowed';
            handle.title = allowDrag ? 'Arraste para reordenar' : 'Selecione uma categoria específica para ordenar';
        }
    });

    aplicarFiltrosConfig(); 
}

// Busca 2: Interna dos Produtos
// Substitua a sua aplicarFiltrosProdutos por esta:
function aplicarFiltrosProdutos() {
    const elGlobal = document.getElementById('searchCategory');
    const elInterno = document.getElementById('searchProd');
    if (!elGlobal || !elInterno) return;

    const termoCatGlobal = elGlobal.value.toLowerCase();
    const termoItemInterno = elInterno.value.toLowerCase();

    document.querySelectorAll('#lista-produtos .category-section').forEach(sec => {
        const h2 = sec.querySelector('h2');
        if (!h2) return;
        const nomeCategoriaSection = h2.innerText.toLowerCase();
        
        const passaGlobal = nomeCategoriaSection.includes(termoCatGlobal);
        const passaChip = (categoriaAtiva === 'all' || sec.dataset.cat === categoriaAtiva);

        // Se não passar no filtro de categoria, esconde a seção inteira
        if (!passaGlobal || !passaChip) {
            sec.classList.add('force-hide');
            return;
        } else {
            sec.classList.remove('force-hide');
        }

        let vis = 0;
        sec.querySelectorAll('.prod-row').forEach(row => {
            if(row.innerText.toLowerCase().includes(termoItemInterno)) {
                row.classList.remove('force-hide');
                vis++;
            } else {
                row.classList.add('force-hide');
            }
        });

        if (vis === 0) sec.classList.add('force-hide');
    });
}

// Substitua a sua aplicarFiltrosConfig por esta:
function aplicarFiltrosConfig() {
    const elGlobal = document.getElementById('searchCategory');
    const elInterno = document.getElementById('searchConfig');
    if (!elGlobal || !elInterno) return;

    const termoCatGlobal = elGlobal.value.toLowerCase();
    const termoConfigInterno = elInterno.value.toLowerCase();

    document.querySelectorAll('#tbody-variacoes tr.config-row, #tbody-grupos tr.config-row').forEach(row => {
        const catBadge = row.querySelector('.scope-cat');
        const catBadgeText = catBadge ? catBadge.innerText.toLowerCase() : row.dataset.cat.toLowerCase();
        
        const passaGlobal = catBadgeText.includes(termoCatGlobal);
        const passaChip = (configAtiva === 'all' || row.dataset.cat === configAtiva);
        const passaBuscaInterna = row.innerText.toLowerCase().includes(termoConfigInterno);

        if (passaGlobal && passaChip && passaBuscaInterna) {
            row.classList.remove('force-hide');
            row.style.display = ''; // Limpa o style inline antigo se houver
        } else {
            row.classList.add('force-hide');
        }
    });
}

// Busca 3: Interna das Regras (Aba Config)
function aplicarFiltrosConfig() {
    const elGlobal = document.getElementById('searchCategory');
    const elInterno = document.getElementById('searchConfig');
    if (!elGlobal || !elInterno) return;

    const termoCatGlobal = elGlobal.value.toLowerCase();
    const termoConfigInterno = elInterno.value.toLowerCase();

    document.querySelectorAll('#tbody-variacoes tr.config-row, #tbody-grupos tr.config-row').forEach(row => {
        const catBadge = row.querySelector('.scope-cat');
        const catBadgeText = catBadge ? catBadge.innerText.toLowerCase() : row.dataset.cat.toLowerCase();
        
        const passaGlobal = catBadgeText.includes(termoCatGlobal);
        const passaChip = (configAtiva === 'all' || row.dataset.cat === configAtiva);
        const passaBuscaInterna = row.innerText.toLowerCase().includes(termoConfigInterno);

        if (passaGlobal && passaChip && passaBuscaInterna) {
            row.classList.remove('force-hide');
            row.style.display = ''; // Limpa o style inline antigo se houver
        } else {
            row.classList.add('force-hide');
        }
    });
}

// ==========================================

function openTab(id){ 
    document.querySelectorAll('.tab-content').forEach(d=>d.classList.remove('active')); 
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active')); 
    const tab = document.getElementById(id);
    if(tab) tab.classList.add('active'); 
    const btnId = id === 'tab-produtos' ? 'btn-tab-produtos' : 'btn-tab-config';
    const btn = document.getElementById(btnId);
    if(btn) btn.classList.add('active');
    localStorage.setItem('activeTab', id);
}

function closeModal(id){ document.getElementById(id).style.display='none'; }
function abrirModalAdicionar(){ document.getElementById('prodId').value=''; document.getElementById('formProd').reset(); if (categoriaAtiva !== 'all') document.getElementById('prodCat').value = categoriaAtiva; document.getElementById('modalProd').style.display='flex'; }
function editProd(btn){ document.getElementById('formProd').reset(); const i=JSON.parse(btn.dataset.item); document.getElementById('prodId').value=i.id; document.getElementById('prodCat').value=btn.dataset.cat; document.getElementById('prodNome').value=i.nome; document.getElementById('prodPreco').value=i.preco; document.getElementById('prodDesc').value=i.descricao||i.ingredientes||''; document.getElementById('modalProd').style.display='flex'; }
async function salvarProduto(e){ e.preventDefault(); const id=document.getElementById('prodId').value; const cat=document.getElementById('prodCat').value; const d={nome:document.getElementById('prodNome').value, categoria:cat, preco:document.getElementById('prodPreco').value, descricao:document.getElementById('prodDesc').value}; if(cat=='pizza') d.ingredientes=d.descricao; const url=id?`/api/cardapio/${cat}/${id}`:'/api/cardapio'; await fetch(url,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}); location.reload(); }
async function delProd(cat,id){ if(confirm('Excluir Produto?')) { await fetch(`/api/cardapio/${cat}/${id}`,{method:'DELETE'}); location.reload(); } }

function modalVariacao(){ document.getElementById('formVar').reset(); document.getElementById('varId').value = ''; document.getElementById('varFatias').value = 8; document.getElementById('varSabores').value = 2; if (configAtiva !== 'all') document.getElementById('varCat').value = configAtiva; togglePizzaFields(); document.getElementById('modalVar').style.display='flex'; }
function editVariacao(btn) { document.getElementById('formVar').reset(); const v = JSON.parse(btn.dataset.var); document.getElementById('varId').value = v.id; document.getElementById('varCat').value = v.categoria; document.getElementById('varNome').value = v.nome; document.getElementById('varSigla').value = v.sigla || ''; document.getElementById('varPreco').value = v.preco; document.getElementById('varFatias').value = v.fatias || 8; document.getElementById('varSabores').value = v.max_sabores || 2; document.getElementById('varTamanho').value = v.tamanho_cm || ''; togglePizzaFields(); document.getElementById('modalVar').style.display='flex'; }
function togglePizzaFields() { const cat = document.getElementById('varCat').value; const area = document.getElementById('areaPizzaConfig'); if(cat === 'pizza') { area.style.display = 'block'; } else { area.style.display = 'none'; } }
async function salvarVariacao(e){ e.preventDefault(); const cat = document.getElementById('varCat').value; const d = { id: document.getElementById('varId').value, categoria: cat, nome: document.getElementById('varNome').value, sigla: document.getElementById('varSigla').value, preco: document.getElementById('varPreco').value, fatias: (cat === 'pizza') ? document.getElementById('varFatias').value : 0, max_sabores: (cat === 'pizza') ? document.getElementById('varSabores').value : 1, tamanho_cm: (cat === 'pizza') ? document.getElementById('varTamanho').value : '' }; await fetch('/api/variacoes',{ method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(d) }); location.reload(); }
async function delVariacao(id){ if(confirm('Excluir Variação?')) { await fetch(`/api/variacoes/${id}`,{method:'DELETE'}); location.reload(); } }

function modalGrupo(){ document.getElementById('formGrp').reset(); document.getElementById('grpId').value=''; document.getElementById('listaOpcoes').innerHTML=''; addOpcaoLinha(); document.getElementById('grpMin').value = 0; document.getElementById('grpMax').value = 1; document.getElementById('grpGratis').value = 0; document.getElementById('grpOrdem').value = 1; if (configAtiva !== 'all') document.getElementById('grpCat').value = configAtiva; document.getElementById('grpEscopoTipo').value = 'todos'; atualizarEscopo(); toggleOpcoes('unica'); document.getElementById('modalGrp').style.display='flex'; }
function atualizarEscopo(){ const cat = document.getElementById('grpCat').value; const tipoEscopo = document.getElementById('grpEscopoTipo').value; const divValor = document.getElementById('divEscopoValor'); const selectValor = document.getElementById('grpEscopoValor'); selectValor.innerHTML = ''; if (tipoEscopo === 'todos') { divValor.style.display = 'none'; return; } if (tipoEscopo === 'produto') { divValor.style.display = 'block'; document.getElementById('lblEscopoValor').innerText = "Selecione o Produto:"; const prods = todosProdutos.filter(p => p.categoria_origem === cat); prods.forEach(p => { const opt = document.createElement('option'); opt.value = p.id; opt.innerText = p.nome; selectValor.appendChild(opt); }); } else if (tipoEscopo === 'variacao') { divValor.style.display = 'block'; document.getElementById('lblEscopoValor').innerText = "Selecione a Variação:"; const vars = todasVariacoes.filter(v => v.categoria === cat); vars.forEach(v => { const opt = document.createElement('option'); opt.value = v.id; opt.innerText = v.nome + (v.sigla ? ' ('+v.sigla+')' : ''); selectValor.appendChild(opt); }); } }
function toggleOpcoes(tipo){ const area = document.getElementById('areaOpcoes'); const divGratis = document.getElementById('divLimiteGratis'); const divMinMax = document.getElementById('divMinMax'); if(tipo === 'texto' || tipo === 'quantidade'){ area.style.display = 'none'; divGratis.style.display = 'none'; divMinMax.style.display = 'none'; } else { area.style.display = 'block'; divGratis.style.display = (tipo === 'multipla') ? 'block' : 'none'; divMinMax.style.display = 'block'; } }

// MODAL DRAG & DROP
function addOpcaoLinha(nome='', preco=0){ 
    const div = document.createElement('div'); 
    div.className = 'draggable-item'; 
    div.innerHTML = `
        <span class="drag-handle-modal">☰</span>
        <input type="text" class="input-std op-nome m-0" placeholder="Nome da Opção" value="${nome}">
        <input type="number" class="input-std op-preco m-0" placeholder="R$ Add" value="${preco}" step="0.01">
        <button type="button" onclick="this.parentElement.remove()" class="btn-remove-opcao">&times;</button>
    `; 
    const container = document.getElementById('listaOpcoes'); 
    container.appendChild(div); 
}

function editarGrupo(btn){ document.getElementById('formGrp').reset(); const g = JSON.parse(btn.dataset.group); document.getElementById('grpId').value = g.id; document.getElementById('grpCat').value = g.categoria_alvo; document.getElementById('grpOrdem').value = g.ordem || 1; document.getElementById('grpTitulo').value = g.titulo; document.getElementById('grpDesc').value = g.descricao; document.getElementById('grpTipo').value = g.tipo; document.getElementById('grpGratis').value = g.limite_gratis || 0; document.getElementById('grpMin').value = (g.minimo_escolha !== undefined) ? g.minimo_escolha : 0; document.getElementById('grpMax').value = (g.maximo_escolha !== undefined) ? g.maximo_escolha : 1; if (g.produto_alvo_id) document.getElementById('grpEscopoTipo').value = 'produto'; else if (g.variacao_alvo_id) document.getElementById('grpEscopoTipo').value = 'variacao'; else document.getElementById('grpEscopoTipo').value = 'todos'; atualizarEscopo(); if (g.produto_alvo_id) document.getElementById('grpEscopoValor').value = g.produto_alvo_id; if (g.variacao_alvo_id) document.getElementById('grpEscopoValor').value = g.variacao_alvo_id; document.getElementById('listaOpcoes').innerHTML=''; if(g.opcoes && g.opcoes.length > 0) g.opcoes.forEach(op => addOpcaoLinha(op.nome, op.preco_adicional)); else addOpcaoLinha(); toggleOpcoes(g.tipo); document.getElementById('modalGrp').style.display='flex'; }
async function salvarGrupo(e){ e.preventDefault(); const ops = []; document.querySelectorAll('#listaOpcoes .draggable-item').forEach(r => { const nome = r.querySelector('.op-nome').value; if(nome) ops.push({ nome: nome, preco: r.querySelector('.op-preco').value || 0 }); }); const escopoTipo = document.getElementById('grpEscopoTipo').value; const escopoValor = document.getElementById('grpEscopoValor').value; const data = { id: document.getElementById('grpId').value, categoria_alvo: document.getElementById('grpCat').value, titulo: document.getElementById('grpTitulo').value, descricao: document.getElementById('grpDesc').value, tipo: document.getElementById('grpTipo').value, ordem: document.getElementById('grpOrdem').value, limite_gratis: document.getElementById('grpGratis').value, minimo_escolha: document.getElementById('grpMin').value, maximo_escolha: document.getElementById('grpMax').value, produto_alvo_id: (escopoTipo === 'produto') ? escopoValor : null, variacao_alvo_id: (escopoTipo === 'variacao') ? escopoValor : null, opcoes: ops }; await fetch('/api/grupos_adicionais', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}); location.reload(); }
async function delGrupo(id){ if(confirm('Apagar Grupo?')) { await fetch('/api/grupos_adicionais/'+id, {method:'DELETE'}); location.reload(); } }

document.addEventListener('click', function(e) {
    // 1. Tenta pegar o clique na barra inteira do cabeçalho
    const header = e.target.closest('.card-section-header');
    if (header) {
        const card = header.closest('.card-section-wrapper');
        if (card) { card.classList.toggle('collapsed'); }
        return;
    }
    
    // 2. Proteção (Fallback) caso o clique vá direto no texto em outras áreas
    const h2 = e.target.closest('.config-card h2, .category-section h2');
    if (h2) {
        const card = h2.closest('.config-card, .category-section, .card-section-wrapper');
        if (card) { card.classList.toggle('collapsed'); }
    }
});

// ATIVA O DRAG AND DROP PODEROSO (FUNCIONA NO CELULAR E PC)
document.addEventListener('DOMContentLoaded', () => {
    // Ativar o arrasto nas Variações / Grupos principais
    const tbodyGrupos = document.getElementById('tbody-grupos');
    if (tbodyGrupos) {
        Sortable.create(tbodyGrupos, {
            handle: '.drag-handle',
            animation: 150,
            forceFallback: true, // Força compatibilidade com mobile antigo
            fallbackOnBody: true
        });
    }

    // Ativar o arrasto nas Opções dentro do Modal
    const listaOpcoes = document.getElementById('listaOpcoes');
    if (listaOpcoes) {
        Sortable.create(listaOpcoes, {
            handle: '.drag-handle-modal',
            animation: 150,
            forceFallback: true, 
            fallbackOnBody: true
        });
    }
});