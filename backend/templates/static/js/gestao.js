// --- JAVASCRIPT: GESTÃO & FINANCEIRO ---

let globalDespesas = [];
let globalInsumos = [];
let globalFichas = [];
let cacheCardapio = []; 
let cacheInsumosFT = []; 
let cacheEntregadores = []; 
let funcAtivo = null;

document.addEventListener("DOMContentLoaded", () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    
    const currentMonth = `${year}-${month}`;
    const currentDate = `${year}-${month}-${day}`;
    
    if(document.getElementById('filtroMesResumo')) document.getElementById('filtroMesResumo').value = currentMonth;
    if(document.getElementById('filtroMesDespesas')) document.getElementById('filtroMesDespesas').value = currentMonth;
    if(document.getElementById('filtroMesFunc')) document.getElementById('filtroMesFunc').value = currentMonth;
    if(document.getElementById('filtroDataAcerto')) document.getElementById('filtroDataAcerto').value = currentDate;
    if(document.getElementById('lan_data')) document.getElementById('lan_data').value = currentDate;

    const activeTab = localStorage.getItem('gestao_active_tab') || 'resumo';
    const btn = document.querySelector(`.tab-btn[onclick*="'${activeTab}'"]`);
    if (btn) btn.click(); else switchTab('resumo', document.querySelector('.tab-btn'));
});

function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    if(btn) btn.classList.add('active');
    localStorage.setItem('gestao_active_tab', tabId);
    
    if(tabId === 'resumo') carregarResumo();
    else if(tabId === 'despesas') carregarDespesas();
    else if(tabId === 'estoque') carregarInsumos();
    else if(tabId === 'ficha') inicializarFichaTecnica();
    else if(tabId === 'equipe') carregarEquipe();
    else if(tabId === 'funcionarios') carregarFuncionarios();
}

let cacheResumoMes = null; 

async function carregarResumo() {
    const mes = document.getElementById('filtroMesResumo').value;
    const res = await fetch(`/api/gestao/resumo?mes_ano=${mes}&_t=${Date.now()}`);
    const data = await res.json();
    cacheResumoMes = data; 
    
    document.getElementById('dash_receita').innerText = `R$ ${data.receita.toFixed(2).replace('.',',')}`;
    document.getElementById('dash_compras').innerText = `R$ ${data.compras_estoque.toFixed(2).replace('.',',')}`;
    document.getElementById('dash_despesas').innerText = `R$ ${data.despesas.toFixed(2).replace('.',',')}`;
    document.getElementById('dash_taxas').innerText = `Oculta R$ ${data.taxas_cartao.toFixed(2).replace('.',',')} em Taxas de Cartão`;
    
    const elLucro = document.getElementById('dash_lucro');
    elLucro.innerText = `R$ ${data.lucro_liquido.toFixed(2).replace('.',',')}`;
    elLucro.className = data.lucro_liquido >= 0 ? 'value text-success' : 'value text-danger';

    const bk = data.breakdown_pagamentos || {}; let bkHtml = '';
    const cores_base = { "dinheiro": "#10b981", "pix": "#3b82f6", "crédito": "#f59e0b", "débito": "#a855f7", "ifood": "#ef4444", "outros": "#888" };
    
    for(let k in bk) {
        if(bk[k] > 0) {
            let pct = data.receita > 0 ? (bk[k] / data.receita) * 100 : 0;
            let cor = '#f59e0b';
            for(let cb in cores_base) { if(k.toLowerCase().includes(cb)) { cor = cores_base[cb]; break; } }
            bkHtml += `<div class="stat-row"><span>${k}</span><span>R$ ${bk[k].toFixed(2).replace('.',',')} (${pct.toFixed(1)}%)</span></div><div class="stat-bar-bg"><div class="stat-bar-fill" style="width: ${pct}%; background: ${cor};"></div></div>`;
        }
    }
    if(!bkHtml) bkHtml = '<p class="text-muted text-sm m-0">Nenhuma receita detetada no período.</p>';
    document.getElementById('breakdown_pagamentos').innerHTML = bkHtml;

    let margem = data.receita > 0 ? (data.lucro_liquido / data.receita) * 100 : 0;
    let cmv = data.receita > 0 ? (data.compras_estoque / data.receita) * 100 : 0;
    let desp = data.receita > 0 ? (data.despesas / data.receita) * 100 : 0;
    let taxas = data.receita > 0 ? (data.taxas_cartao / data.receita) * 100 : 0;

    document.getElementById('indicadores_saude').innerHTML = `
        <div class="stat-row"><span>Margem de Lucro Líquida</span><span class="${margem >= 0 ? 'text-success' : 'text-danger'} font-bold">${margem.toFixed(1)}%</span></div><div class="stat-bar-bg"><div class="stat-bar-fill" style="width: ${Math.max(0, Math.min(100, margem))}%; background: ${margem >= 0 ? 'var(--success)' : 'var(--danger)'};"></div></div>
        <div class="stat-row"><span>Custo de Estoque (CMV)</span><span>${cmv.toFixed(1)}% da receita</span></div><div class="stat-bar-bg"><div class="stat-bar-fill" style="width: ${Math.min(100, cmv)}%; background: var(--warning);"></div></div>
        <div class="stat-row"><span>Despesas Operacionais</span><span>${desp.toFixed(1)}% da receita</span></div><div class="stat-bar-bg"><div class="stat-bar-fill" style="width: ${Math.min(100, desp)}%; background: var(--danger);"></div></div>
        <div class="stat-row"><span>Taxas de Pagamento (Maquininha)</span><span>${taxas.toFixed(1)}% da receita</span></div><div class="stat-bar-bg"><div class="stat-bar-fill" style="width: ${Math.min(100, taxas)}%; background: #a855f7;"></div></div>`;
}

// === DESPESAS ===
async function carregarDespesas() { 
    const m = document.getElementById('filtroMesDespesas').value; 
    const r = await fetch(`/api/despesas?mes_ano=${m}&_t=${Date.now()}`); 
    globalDespesas = await r.json(); 
    filtrarDespesas(); 
}

window.filtrarDespesas = function() {
    const termo = document.getElementById('busca_despesa').value.toLowerCase();
    const status = document.getElementById('filtro_status_despesa').value;
    
    let despFiltradas = globalDespesas.filter(d => {
        let matchTermo = d.descricao.toLowerCase().includes(termo) || d.categoria.toLowerCase().includes(termo);
        let matchStatus = true;
        if(status !== 'todos') matchStatus = d.status === status;
        return matchTermo && matchStatus;
    });

    renderDespesasTable(despFiltradas);
    atualizarCardsDespesa(globalDespesas); 
};

function atualizarCardsDespesa(dados) {
    let totalGeral = 0, totalPago = 0, totalPendente = 0;
    dados.forEach(d => {
        totalGeral += d.valor;
        if(d.status === 'pago') totalPago += d.valor;
        else totalPendente += d.valor;
    });
    document.getElementById('sum_desp_total').innerText = `R$ ${totalGeral.toFixed(2).replace('.',',')}`;
    document.getElementById('sum_desp_pago').innerText = `R$ ${totalPago.toFixed(2).replace('.',',')}`;
    document.getElementById('sum_desp_pendente').innerText = `R$ ${totalPendente.toFixed(2).replace('.',',')}`;
}

function renderDespesasTable(dados) {
    const t = document.getElementById('lista_despesas'); t.innerHTML=''; 
    if(dados.length===0){ t.innerHTML='<tr><td colspan="6" class="text-center p-20 text-muted">Nenhuma despesa encontrada.</td></tr>'; return; } 
    
    dados.forEach(x => {
        const isP = x.status === 'pago';
        const b = `<span class="status-badge ${isP?'badge-pago':'badge-pendente'}">${isP?'Pago':'Pendente'}</span>`;
        let v = x.data_vencimento.split('-'); let ds = `${v[2]}/${v[1]}/${v[0]}`;
        
        // CORREÇÃO DOS BOTÕES: Usando gap-10 sem margens extras para não "grudar"
        let bt = `<button class="btn-neon btn-neon-warning" onclick="abrirModalDespesa(${x.id}, '${x.descricao}', ${x.valor}, '${x.data_vencimento}', '${x.categoria}')">✏️ Editar</button><button class="btn-neon btn-neon-danger" onclick="excluirDespesa(${x.id})">🗑️</button>`;
        if(!isP) { bt = `<button class="btn-neon btn-neon-success" onclick="pagarDespesa(${x.id})">✅ Pagar</button>` + bt; }
        
        t.innerHTML+=`<tr>
            <td class="font-bold">${x.descricao}</td><td>${ds}</td><td class="text-muted" style="text-transform:capitalize;">${x.categoria}</td>
            <td class="text-danger font-bold text-lg">R$ ${x.valor.toFixed(2).replace('.',',')}</td><td>${b}</td>
            <td><div class="d-flex gap-10">${bt}</div></td>
        </tr>`;
    });
}

function abrirModalDespesa(id='', desc='', val='', venc='', cat='operacional'){ 
    document.getElementById('desp_id').value=id; 
    document.getElementById('desp_desc').value=desc; 
    document.getElementById('desp_valor').value=val; 
    document.getElementById('desp_juros').value=''; // Limpa os juros ao abrir
    if(document.getElementById('desp_juros_tipo')) document.getElementById('desp_juros_tipo').value = 'dinheiro'; // Volta para R$ por padrão
    document.getElementById('desp_venc').value=venc; 
    document.getElementById('desp_cat').value=cat; 
    
    if(id) { 
        document.getElementById('box_recorrente').style.display='none'; 
        document.getElementById('txt_help_recorrente').style.display='none'; 
    } else { 
        document.getElementById('box_recorrente').style.display='flex'; 
        document.getElementById('txt_help_recorrente').style.display='block'; 
        document.getElementById('desp_recorrente').checked=false; 
    } 
    document.getElementById('modalDespesa_titulo').innerText = id ? 'Editar Despesa' : 'Lançar Despesa'; 
    document.getElementById('modalDespesa').style.display='flex'; 
}

async function salvarDespesa(e){ 
    e.preventDefault(); 
    const id = document.getElementById('desp_id').value; 
    
    let desc = document.getElementById('desp_desc').value;
    let vBase = parseFloat(document.getElementById('desp_valor').value) || 0;
    
    // Novas variáveis para ler os Juros
    let jurosInput = parseFloat(document.getElementById('desp_juros').value) || 0;
    let tipoJuros = document.getElementById('desp_juros_tipo').value;
    
    let vJuros = 0;
    
    // O sistema decide se soma o valor bruto ou calcula a percentagem
    if (tipoJuros === 'porcentagem') {
        vJuros = vBase * (jurosInput / 100);
    } else {
        vJuros = jurosInput;
    }

    let valorFinal = vBase + vJuros;
    
    // Ajusta o aviso na descrição para mostrar % ou R$ corretamente
    if(vJuros > 0) {
        let txtAviso = tipoJuros === 'porcentagem' ? `${jurosInput}%` : `R$ ${vJuros.toFixed(2).replace('.',',')}`;
        desc += ` (Inclui ${txtAviso} de Juros)`;
    }

    const data = {
        descricao: desc,
        valor: valorFinal,
        data_vencimento: document.getElementById('desp_venc').value,
        categoria: document.getElementById('desp_cat').value,
        recorrente: document.getElementById('desp_recorrente') ? document.getElementById('desp_recorrente').checked : false
    }; 
    
    await fetch(id ? `/api/despesas/${id}` : '/api/despesas', {
        method: id ? 'PUT' : 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(data)
    }); 
    
    document.getElementById('modalDespesa').style.display='none'; 
    carregarDespesas(); 
    carregarResumo(); 
}
async function pagarDespesa(id){ if(confirm("Confirmar Pagamento?")){ await fetch(`/api/despesas/${id}/pagar`,{method:'PUT'}); carregarDespesas(); carregarResumo(); } }
async function excluirDespesa(id){ if(confirm("Excluir despesa?")){ await fetch(`/api/despesas/${id}`,{method:'DELETE'}); carregarDespesas(); carregarResumo(); } }

// === ALMOXARIFADO ===
async function carregarInsumos(){ 
    const r = await fetch(`/api/estoque/insumos?_t=${Date.now()}`); 
    globalInsumos = await r.json(); 
    filtrarInsumos();
}

window.filtrarInsumos = function() {
    const termo = document.getElementById('busca_insumo').value.toLowerCase();
    const status = document.getElementById('filtro_status_insumo').value;
    
    let filtrados = globalInsumos.filter(i => {
        let matchTermo = i.nome.toLowerCase().includes(termo);
        let isBaixo = (i.estoque_minimo > 0 && i.quantidade_atual <= i.estoque_minimo);
        let matchStatus = true;
        if (status === 'baixo') matchStatus = isBaixo;
        if (status === 'normal') matchStatus = !isBaixo;
        return matchTermo && matchStatus;
    });
    
    renderInsumosTable(filtrados);
};

function renderInsumosTable(dados) {
    const t = document.getElementById('lista_insumos'); t.innerHTML=''; 
    if(dados.length===0){ t.innerHTML='<tr><td colspan="5" class="text-center p-20 text-muted">Nenhum insumo encontrado.</td></tr>'; return; } 
    
    dados.forEach(i => { 
        const isBaixo = i.estoque_minimo > 0 && i.quantidade_atual <= i.estoque_minimo; 
        const st = isBaixo ? '<span class="status-badge badge-pendente">⚠️ Baixo</span>' : '<span class="status-badge badge-pago">✅ Normal</span>'; 
        
        t.innerHTML+=`<tr>
            <td><strong class="text-lg">${i.nome}</strong>${i.estoque_minimo > 0 ? `<br><span class="text-xs text-muted">Min: ${i.estoque_minimo}</span>` : ''}</td>
            <td><span class="text-xl font-bold text-info">${i.quantidade_atual.toFixed(2)}</span> <small class="text-muted">${i.unidade_medida}</small></td>
            <td class="text-muted">R$ ${i.custo_medio.toFixed(4).replace('.',',')}</td><td>${st}</td>
            <td><div class="d-flex gap-5">
                <button class="btn-neon btn-neon-success" onclick="abrirModalEntrada(${i.id}, '${i.nome}', '${i.unidade_medida}')">🛒 Compra</button>
                <button class="btn-neon btn-neon-info" onclick="abrirModalAjuste(${i.id}, '${i.nome}', ${i.quantidade_atual})">⚖️ Ajuste</button>
                <button class="btn-neon btn-neon-warning" onclick="abrirModalInsumo(${i.id}, '${i.nome}', '${i.unidade_medida}', ${i.estoque_minimo})">✏️</button>
                <button class="btn-neon btn-neon-danger" onclick="excluirInsumo(${i.id})">🗑️</button>
            </div></td>
        </tr>`;
    });
}

function abrirModalInsumo(id='',n='',m='UN',min=''){ document.getElementById('ins_id').value=id; document.getElementById('ins_nome').value=n; document.getElementById('ins_medida').value=m; document.getElementById('ins_min').value=min; document.getElementById('modalInsumo_titulo').innerText=id?'Editar Insumo':'Cadastrar Insumo'; document.getElementById('modalInsumo').style.display='flex'; }
async function salvarInsumo(e){ e.preventDefault(); const id=document.getElementById('ins_id').value; const d={nome:document.getElementById('ins_nome').value,unidade_medida:document.getElementById('ins_medida').value,estoque_minimo:document.getElementById('ins_min').value||0}; await fetch(id?`/api/estoque/insumos/${id}`:'/api/estoque/insumos', {method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}); document.getElementById('modalInsumo').style.display='none'; carregarInsumos(); }
async function excluirInsumo(id){ if(confirm("Apagar Insumo?")){ await fetch(`/api/estoque/insumos/${id}`,{method:'DELETE'}); carregarInsumos(); } }
function abrirModalAjuste(id, nome, qtd) { document.getElementById('ajuste_insumo_id').value=id; document.getElementById('ajuste_nome_display').innerText=nome; document.getElementById('ajuste_nova_qtd').value=qtd; document.getElementById('modalAjuste').style.display='flex'; }
async function salvarAjusteEstoque(e) { e.preventDefault(); const id = document.getElementById('ajuste_insumo_id').value; const nova_qtd = document.getElementById('ajuste_nova_qtd').value; await fetch(`/api/estoque/insumos/${id}/ajuste`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nova_quantidade: nova_qtd})}); document.getElementById('modalAjuste').style.display='none'; carregarInsumos(); }
function abrirModalEntrada(id,n,u){ document.getElementById('ent_insumo_id').value=id; document.getElementById('ent_nome_display').innerText=n; document.getElementById('ent_unidade_display').innerText=u; document.querySelectorAll('.lbl_unidade').forEach(e=>e.innerText=u); document.getElementById('ent_qtd_volume').value=''; document.getElementById('ent_fator').value='1'; document.getElementById('ent_custo').value=''; document.getElementById('ent_forma_pagamento').value='avista'; toggleParcelas(); calcularTotalEntrada(); document.getElementById('modalEntrada').style.display='flex'; }
function toggleParcelas(){ document.getElementById('box_compra_prazo').style.display = document.getElementById('ent_forma_pagamento').value==='prazo'?'flex':'none'; }
function calcularTotalEntrada(){ const v=parseFloat(document.getElementById('ent_qtd_volume').value)||0; const f=parseFloat(document.getElementById('ent_fator').value)||0; document.getElementById('display_calc_total').innerText=(v*f).toFixed(2); }
async function salvarEntrada(e){ e.preventDefault(); const d={insumo_id:document.getElementById('ent_insumo_id').value,quantidade:document.getElementById('ent_qtd_volume').value,fator_conversao:document.getElementById('ent_fator').value,custo_total:document.getElementById('ent_custo').value,forma_pagamento:document.getElementById('ent_forma_pagamento').value,parcelas:document.getElementById('ent_parcelas').value,primeiro_vencimento:document.getElementById('ent_primeiro_venc').value}; await fetch('/api/estoque/entradas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}); document.getElementById('modalEntrada').style.display='none'; carregarInsumos(); carregarResumo(); carregarDespesas(); }

// === FICHA TÉCNICA ===
async function inicializarFichaTecnica(){ 
    document.getElementById('view_editor_ficha').classList.add('hidden'); 
    document.getElementById('view_lista_fichas').classList.remove('hidden'); 
    
    if (cacheCardapio && cacheCardapio.length > 0) {
        carregarListaDeFichas(); 
        return; 
    }

    const cacheSalvo = sessionStorage.getItem('cacheCardapio_FT');
    if (cacheSalvo) {
        cacheCardapio = JSON.parse(cacheSalvo);
        montarSelectCategorias(); 
        carregarListaDeFichas(); 
        
        fetch(`/api/gestao/cardapio_lookup?_t=${Date.now()}`)
            .then(r => r.json())
            .then(data => {
                cacheCardapio = data;
                sessionStorage.setItem('cacheCardapio_FT', JSON.stringify(data));
            }).catch(e => console.log("Erro no update silencioso:", e));
            
        return;
    }
    
    document.getElementById('lista_fichas_cadastradas').innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:#888;">⏳ Carregando receitas do cardápio... Isso pode levar alguns segundos.</td></tr>';
    
    try {
        const [lookupRes, fichasRes] = await Promise.all([
            fetch(`/api/gestao/cardapio_lookup?_t=${Date.now()}`),
            fetch(`/api/gestao/fichas_cadastradas?_t=${Date.now()}`)
        ]);

        cacheCardapio = await lookupRes.json();
        globalFichas = await fichasRes.json();
        
        sessionStorage.setItem('cacheCardapio_FT', JSON.stringify(cacheCardapio));
        montarSelectCategorias();
        filtrarFichas();
    } catch(err) {
        console.error("Falha ao carregar as Fichas Técnicas:", err);
        document.getElementById('lista_fichas_cadastradas').innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--danger);">⚠️ Erro de conexão ao carregar as fichas. Tente recarregar a página.</td></tr>';
    }
}

function montarSelectCategorias() {
    const s = document.getElementById('ft_categoria'); 
    s.innerHTML = '<option value="">-- Escolha a Categoria --</option>'; 
    cacheCardapio.forEach(c => s.innerHTML += `<option value="${c.id}">${c.nome}</option>`);
}

async function carregarListaDeFichas(){ 
    const r = await fetch(`/api/gestao/fichas_cadastradas?_t=${Date.now()}`); 
    globalFichas = await r.json(); 
    filtrarFichas();
}

window.filtrarFichas = function() {
    const termo = document.getElementById('busca_ficha').value.toLowerCase();
    let filtradas = globalFichas.filter(f => {
        let haystack = (f.produto_nome + f.categoria_nome + f.tamanho + f.adicional_nome).toLowerCase();
        return haystack.includes(termo);
    });
    renderFichasTable(filtradas);
};

function renderFichasTable(dados) {
    const tb = document.getElementById('lista_fichas_cadastradas'); tb.innerHTML = ''; 
    if(dados.length === 0){ tb.innerHTML='<tr><td colspan="6" class="text-center p-20 text-muted">Nenhuma receita encontrada.</td></tr>'; return; } 
    
    dados.forEach(f => { 
        let lblCompleto = f.produto_id === 0 ? `<strong class="text-warning text-lg">${f.produto_nome}</strong>` : `<strong class="text-primary text-lg">${f.produto_nome}</strong>`;
        if(f.tamanho !== "UNICO") lblCompleto += `<br><span class="text-sm text-muted">Tamanho: ${f.tamanho}</span>`;
        if(f.adicional_nome) lblCompleto += `<br><span class="text-sm text-info">➕ Adicional: ${f.adicional_nome}</span>`;

        let txtVenda = '-'; let txtMargem = '-';
        if(f.preco_venda > 0) {
            txtVenda = `R$ ${f.preco_venda.toFixed(2).replace('.',',')}`;
            let lucro = f.preco_venda - f.custo_total; let margemPct = (lucro / f.preco_venda) * 100;
            let corClass = margemPct >= 40 ? 'text-success' : (margemPct > 15 ? 'text-warning' : 'text-danger');
            txtMargem = `<span class="${corClass} font-bold">${margemPct.toFixed(1)}%</span><br><small class="text-muted">Lucro: R$ ${lucro.toFixed(2).replace('.',',')}</small>`;
        }

        tb.innerHTML += `<tr>
            <td>${lblCompleto}</td><td class="text-muted">${f.categoria_nome}</td>
            <td class="text-danger font-bold text-lg">R$ ${f.custo_total.toFixed(2).replace('.',',')}</td>
            <td class="text-success font-bold">${txtVenda}</td><td>${txtMargem}</td>
            <td><button class="btn-neon btn-neon-primary" onclick="abrirEditorFicha('${f.categoria_id}', ${f.produto_id}, '${f.tamanho}', '${f.adicional_nome}')">✏️ Editar Receita</button></td>
        </tr>`;
    }); 
}

function fecharEditorFicha(){ 
    document.getElementById('view_editor_ficha').classList.add('hidden'); 
    document.getElementById('view_lista_fichas').classList.remove('hidden'); 
    carregarListaDeFichas(); 
}

function abrirEditorFicha(cid=null, pid=null, tam='UNICO', add_nome='') { 
    document.getElementById('view_lista_fichas').classList.add('hidden'); 
    document.getElementById('view_editor_ficha').classList.remove('hidden'); 
    const bx = document.getElementById('btn_excluir_ficha'); 
    
    if(cid){ 
        document.getElementById('ft_categoria').value = cid; 
        atualizarComboProduto(pid, tam, add_nome);
        bx.style.display = 'inline-flex';
    } else {
        document.getElementById('ft_categoria').value = '';
        document.getElementById('ft_produto').innerHTML = '<option value="0">⭐ Selecione a Categoria Primeiro</option>';
        document.getElementById('ft_produto').disabled = true;
        document.getElementById('box_variacoes').style.display = 'none';
        document.getElementById('box_adicionais').style.display = 'none';
        document.getElementById('box_receita').style.opacity = '0.5';
        document.getElementById('box_receita').style.pointerEvents = 'none';
        document.getElementById('lista_itens_ficha').innerHTML = '<tr><td colspan="4" style="text-align:center;">Aguardando Seleção</td></tr>'; 
        bx.style.display = 'none';
    } 
}

window.atualizarComboProduto = function(pid_selecionado = null, tam_selecionado = 'UNICO', add_selecionado = '') {
    if (pid_selecionado && typeof pid_selecionado === 'object') pid_selecionado = null;
    const cid = document.getElementById('ft_categoria').value;
    const selProd = document.getElementById('ft_produto');
    selProd.innerHTML = '<option value="0">⭐ Regra Geral (Ex: Massa p/ todas as Pizzas)</option>';

    if(!cid) {
        selProd.disabled = true;
        document.getElementById('box_variacoes').style.display = 'none';
        document.getElementById('box_adicionais').style.display = 'none';
        carregarReceitaDoProduto();
        return;
    }

    const cat = cacheCardapio.find(x => x.id == cid);
    if(cat && cat.produtos && cat.produtos.length > 0) {
        cat.produtos.forEach(p => {
            let sel = (pid_selecionado !== null && pid_selecionado == p.id) ? 'selected' : '';
            selProd.innerHTML += `<option value="${p.id}" ${sel}>${p.nome}</option>`;
        });
    }

    selProd.disabled = false; 
    atualizarComboTamanhoAdicional(tam_selecionado, add_selecionado);
};

window.atualizarComboTamanhoAdicional = function(tam_selecionado = 'UNICO', add_selecionado = '') {
    if (tam_selecionado && typeof tam_selecionado === 'object') tam_selecionado = 'UNICO';
    if (add_selecionado && typeof add_selecionado === 'object') add_selecionado = '';

    const cid = document.getElementById('ft_categoria').value;
    const pid = document.getElementById('ft_produto').value;
    const selTam = document.getElementById('ft_tamanho');
    const selAdd = document.getElementById('ft_adicional');
    const boxTam = document.getElementById('box_variacoes');
    const boxAdd = document.getElementById('box_adicionais');

    selTam.innerHTML = '<option value="UNICO">Padrão / Único</option>';
    selAdd.innerHTML = '<option value="">Nenhum (Configurando a Receita Principal)</option>';

    if(!cid) return;
    const cat = cacheCardapio.find(x => x.id == cid);
    if(!cat) return;

    let vars = new Set([...(cat.variacoes_gerais || [])]);
    let adds = new Set([...(cat.adicionais_gerais || [])]);

    if(pid && pid !== "0") {
        const prod = cat.produtos.find(x => x.id == pid);
        if(prod) {
            if(prod.variacoes) prod.variacoes.forEach(v => vars.add(v));
            if(prod.adicionais) prod.adicionais.forEach(a => adds.add(a));
        }
    }

    if(vars.size > 0) {
        boxTam.style.display = 'flex';
        vars.forEach(v => {
            let sel = (v === tam_selecionado) ? 'selected' : '';
            selTam.innerHTML += `<option value="${v}" ${sel}>${v}</option>`;
        });
    } else { boxTam.style.display = 'none'; selTam.innerHTML = '<option value="UNICO">UNICO</option>'; }

    if(adds.size > 0) {
        boxAdd.style.display = 'flex';
        adds.forEach(a => {
            let sel = (a === add_selecionado) ? 'selected' : '';
            selAdd.innerHTML += `<option value="${a}" ${sel}>➕ ${a}</option>`;
        });
    } else { boxAdd.style.display = 'none'; selAdd.innerHTML = '<option value="">Nenhum</option>'; }

    carregarReceitaDoProduto();
};

window.carregarReceitaDoProduto = async function() { 
    const cat_id = document.getElementById('ft_categoria').value; 
    const prod_id = document.getElementById('ft_produto').value; 
    const tamanho = document.getElementById('ft_tamanho').value; 
    const adicional = document.getElementById('ft_adicional').value; 
    
    const bx = document.getElementById('box_receita'); 
    const tb = document.getElementById('lista_itens_ficha'); 
    const be = document.getElementById('btn_excluir_ficha'); 
    
    if(!cat_id){ bx.style.opacity='0.5'; bx.style.pointerEvents='none'; be.style.display='none'; return; } 
    
    bx.style.opacity='1'; bx.style.pointerEvents='auto'; 
    tb.innerHTML='<tr><td colspan="4" style="text-align:center;">A carregar...</td></tr>'; 
    
    const r=await fetch(`/api/gestao/ficha?categoria_id=${cat_id}&produto_id=${prod_id}&tamanho=${encodeURIComponent(tamanho)}&adicional=${encodeURIComponent(adicional)}&_t=${Date.now()}`); 
    const rj=await r.json(); 
    tb.innerHTML=''; 
    let ct=0; 
    
    if(rj.length===0){
        be.style.display='none';
        tb.innerHTML='<tr><td colspan="4" class="text-center text-muted">Nenhum insumo configurado nesta hierarquia.</td></tr>';
    } else { 
        be.style.display='inline-flex'; 
        rj.forEach(x=>{ 
            let ci=x.quantidade_gasta*x.custo_medio; ct+=ci; 
            tb.innerHTML+=`<tr><td><strong>${x.nome}</strong></td><td>${x.quantidade_gasta} <small>${x.unidade_medida}</small></td><td class="text-warning">R$ ${ci.toFixed(2)}</td>
            <td><div class="d-flex gap-5">
                <button class="btn-neon btn-neon-warning" onclick="editarQtdItemFicha(${x.id},'${x.nome}',${x.quantidade_gasta})">✏️</button>
                <button class="btn-neon btn-neon-danger" onclick="removerItemFicha(${x.id})">🗑️</button>
            </div></td></tr>`;
        }); 
        tb.innerHTML+=`<tr style="background:rgba(0,0,0,0.5);"><td colspan="2" class="text-right font-bold">Custo desta Etapa:</td><td colspan="2" class="text-danger font-bold text-lg">R$ ${ct.toFixed(2)}</td></tr>`;
    }
};

async function abrirModalAddFicha(){ const r=await fetch(`/api/estoque/insumos?_t=${Date.now()}`); cacheInsumosFT=await r.json(); const s=document.getElementById('add_ft_insumo'); s.innerHTML='<option value="">-- Insumo --</option>'; cacheInsumosFT.forEach(i=>s.innerHTML+=`<option value="${i.id}" data-un="${i.unidade_medida}">${i.nome}</option>`); document.getElementById('add_ft_qtd').value=''; document.getElementById('add_ft_unidade').innerText='UN'; document.getElementById('modalAddFicha').style.display='flex'; }
function atualizarUnidadeFicha(){ const s=document.getElementById('add_ft_insumo'); const o=s.options[s.selectedIndex]; if(o&&o.dataset.un) document.getElementById('add_ft_unidade').innerText=o.dataset.un; }
async function salvarItemFicha(e){ e.preventDefault(); const d={categoria_id: document.getElementById('ft_categoria').value, produto_id: document.getElementById('ft_produto').value, tamanho: document.getElementById('ft_tamanho').value, adicional_nome: document.getElementById('ft_adicional').value, insumo_id: document.getElementById('add_ft_insumo').value, quantidade_gasta: document.getElementById('add_ft_qtd').value }; await fetch('/api/gestao/ficha',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}); document.getElementById('modalAddFicha').style.display='none'; carregarReceitaDoProduto(); }
window.editarQtdItemFicha = async function(id, n, q){ const nq=prompt(`Nova Qtd de [${n}]:`,q); if(nq!==null&&nq.trim()!==""&&!isNaN(nq)&&nq>0){ await fetch(`/api/gestao/ficha/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({quantidade_gasta:parseFloat(nq)})}); carregarReceitaDoProduto(); } };
window.removerItemFicha = async function(id){ if(confirm("Remover este insumo?")){ await fetch(`/api/gestao/ficha/${id}`,{method:'DELETE'}); carregarReceitaDoProduto(); } };
window.excluirFichaAberta = async function(){ const c = document.getElementById('ft_categoria').value; const p = document.getElementById('ft_produto').value; const t = document.getElementById('ft_tamanho').value; const a = document.getElementById('ft_adicional').value; if(confirm("Excluir esta configuração completamente?")){ await fetch(`/api/gestao/ficha/completa?categoria_id=${c}&produto_id=${p}&tamanho=${encodeURIComponent(t)}&adicional=${encodeURIComponent(a)}`,{method:'DELETE'}); fecharEditorFicha(); } };

// === EQUIPES E MOTOBOYS ===
window.toggleEntregas = function(id) { const row = document.getElementById(`row_entregas_${id}`); if(row.style.display === 'none') row.style.display = 'table-row'; else row.style.display = 'none'; };
async function carregarEquipe() { await carregarConfigEntregadores(); await carregarConfigTaxas(); await carregarAcertoDoDia(); }

async function carregarAcertoDoDia() {
    const dataStr = document.getElementById('filtroDataAcerto').value;
    const tbAcerto = document.getElementById('lista_acerto');
    tbAcerto.innerHTML = '<tr><td colspan="5" class="text-center text-muted">A calcular acerto e comissões...</td></tr>';
    
    try {
        const resAcerto = await fetch(`/api/gestao/acerto_motoboys?data_acerto=${dataStr}&_t=${Date.now()}`);
        const acertos = await resAcerto.json();
        tbAcerto.innerHTML = '';
        
        if(acertos.length === 0) {
            tbAcerto.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nenhum motoboy teve entregas ou vales nesta data.</td></tr>';
        } else {
            acertos.forEach(a => {
                // Cálculos detalhados da lógica:
                
                // 1. Total bruto de todas as entregas (Cartão, PIX, Dinheiro, Ifood, etc)
                let total_pedidos = a.entregas.reduce((acc, e) => acc + e.valor, 0); 
                
                // 2. O que o gestor VAI RECEBER na mão do motoboy no fim da noite.
                // É o valor de todos os pedidos, menos o que o motoboy ganhou (taxas e bônus), mais os vales (se ele pegou dinheiro extra do caixa)
                let gestor_recebe = total_pedidos - a.valor_taxas - a.total_bonus + a.total_vales;
                // Evitar número negativo bizarro se o motoboy ganhou mais em taxa do que carregou de pedido
                if (gestor_recebe < 0) gestor_recebe = 0; 

                // 3. Acerto Final
                let corClass = a.saldo > 0 ? 'text-warning' : (a.saldo < 0 ? 'text-success' : 'text-white');
                let txtSaldo = a.saldo >= 0 ? `R$ ${a.saldo.toFixed(2)}` : `Ele Deve R$ ${Math.abs(a.saldo).toFixed(2)}`;
                
                let htmlLancamentos = '';
                if(a.lancamentos && a.lancamentos.length > 0) {
                    htmlLancamentos = '<div class="mt-5">' + a.lancamentos.map(l => `
                        <span class="tag-mini">
                            ${l.tipo === 'vale' ? '<span class="text-danger">💸 Vale</span>' : '<span class="text-info">⭐ Bônus</span>'}
                            R$ ${l.valor.toFixed(2)} 
                        </span>`).join('') + '</div>';
                }

                let badgesPgto = '';
                for(let k in a.totais_pgto) {
                    if(a.totais_pgto[k] > 0) {
                        let cor = k.toLowerCase().includes('dinheiro')?'#10b981':k.toLowerCase().includes('pix')?'#3b82f6':k.toLowerCase().includes('ifood')?'#ef4444':'#f59e0b';
                        badgesPgto += `<span class="tag-mini" style="border-color:${cor}; color:${cor}; background:rgba(255,255,255,0.05);">${k}: R$ ${a.totais_pgto[k].toFixed(2)}</span>`;
                    }
                }

                // --- Trecho atualizado dentro da função carregarAcertoDoDia em gestao.js ---

                tbAcerto.innerHTML += `
                    <tr>
                        <td data-label="Entregador & Detalhes">
                            <strong class="text-lg">${a.nome}</strong><br>
                            <span class="text-sm text-muted mr-10">Entregas: ${a.qtd_entregas}</span>
                            ${a.qtd_entregas > 0 ? `<button type="button" onclick="toggleEntregas(${a.id})" class="btn-action-sm text-info font-bold text-xs underline p-0">[Ver Entregas]</button>` : ''}
                            ${htmlLancamentos}
                        </td>
                        
                        <td data-label="Gestor a Receber">
                            <span class="text-success font-bold text-lg">R$ ${gestor_recebe.toFixed(2)}</span>
                            <br><span class="text-xs text-muted">Dinheiro com ele: R$ ${a.recolhido_dinheiro.toFixed(2)}</span>
                        </td>
                        
                        <td data-label="Total Entregue">
                            <span class="text-info font-bold text-lg">R$ ${total_pedidos.toFixed(2)}</span>
                            <br><span class="text-xs text-muted">Apenas Taxas dele: R$ ${a.valor_taxas.toFixed(2)}</span>
                        </td>
                        
                        <td data-label="ACERTO FINAL" class="${corClass} font-bold text-lg">
                            ${txtSaldo}
                        </td>
                        
                        <td data-label="Ações" style="vertical-align: middle;">
                            <div class="d-flex flex-column gap-5 w-100">
                                <button class="btn-neon btn-neon-warning p-5 text-sm w-100" onclick="abrirModalLancMotoboy(${a.id}, '${a.nome}')">💸 Vale/Bônus</button>
                                ${a.saldo > 0 ? `<button class="btn-neon btn-neon-success p-5 text-sm w-100" onclick="fecharAcertoMotoboy('${a.nome}', ${a.saldo})">✅ Lançar Despesa</button>` : ''}
                            </div>
                        </td>
                    </tr>
                    <tr id="row_entregas_${a.id}" style="display:none; background: rgba(0,0,0,0.3);">
                        <td colspan="5" class="p-10" style="max-width: 0;">
                            <div class="mb-5">${badgesPgto}</div>
                            
                            <div style="width: 100%; overflow-x: auto; border-radius: 6px; border: 1px solid #444;">
                                <table class="sub-table" style="min-width: 500px; margin: 0; border: none;">
                                    <thead><tr><th>#</th><th>Cliente</th><th>Método</th><th>Troco para</th><th>Total Pedido</th><th>Ganhos (Taxa)</th><th>Ação</th></tr></thead>
                                    <tbody>
                                        ${a.entregas.map(e => `
                                            <tr>
                                                <td data-label="Pedido">#${e.id}</td>
                                                <td data-label="Cliente">${e.cliente}</td>
                                                <td data-label="Método" class="text-info"><strong>${e.cat_metodo}</strong>${e.metodo_str !== e.cat_metodo ? `<br><span class="text-xs text-muted">${e.metodo_str}</span>` : ''}</td>
                                                <td data-label="Troco para">${e.troco > 0 ? `<span class="text-warning font-bold">R$ ${e.troco.toFixed(2)}</span>` : '-'}</td>
                                                <td data-label="Total Pedido" class="font-bold">R$ ${e.valor.toFixed(2)}</td>
                                                <td data-label="Ganhos (Taxa)" class="text-success">R$ ${e.taxa_motoboy.toFixed(2)}</td>
                                                <td><button type="button" class="btn-neon btn-neon-danger p-5 text-xs" onclick="desvincularPedido(${e.id})" title="Remover entrega">🗑️ Remover</button></td>
                                            </tr>`).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </td>
                    </tr>`;
            });
        }

        const resPendentes = await fetch(`/api/gestao/pedidos_sem_motoboy?data_acerto=${dataStr}&_t=${Date.now()}`);
        const pendentes = await resPendentes.json();
        const divPendentes = document.getElementById('lista_pedidos_soltos'); divPendentes.innerHTML = '';
        
        if(pendentes.length === 0) {
            divPendentes.innerHTML = '<p class="text-success text-center mt-20">✅ Nenhuma entrega solta.</p>';
        } else {
            let selectOptions = '<option value="">Atribuir a...</option>';
            cacheEntregadores.forEach(e => selectOptions += `<option value="${e.id}">${e.nome}</option>`);
            pendentes.forEach(p => {
                divPendentes.innerHTML += `
                    <div class="acerto-box">
                        <div class="d-flex justify-between mb-5"><strong>#${p.id} - ${p.cliente_nome.split(' ')[0]}</strong><span class="text-success font-bold">R$ ${p.valor_total.toFixed(2)}</span></div>
                        <div class="text-xs text-muted mb-8">Pagamento: ${p.forma_pagamento || 'Não Informado'}</div>
                        <select class="input-std w-100 p-5" style="border-color:var(--primary);" onchange="vincularPedido(this, ${p.id})">${selectOptions}</select>
                    </div>`;
            });
        }
    } catch(e) { tbAcerto.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Erro interno ao calcular acerto.</td></tr>'; }
}

window.desvincularPedido = async function(pedidoId) {
    if(!confirm("Remover este pedido do motoboy e devolvê-lo para a lista de pendentes?")) return;
    try {
        await fetch(`/api/gestao/vincular_motoboy/${pedidoId}`, { 
            method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({entregador_id: null}) 
        });
        carregarAcertoDoDia(); 
    } catch(e) { alert("Erro ao desvincular o pedido."); }
};

window.fecharAcertoMotoboy = async function(nomeMotoboy, valor) {
    const dataAcerto = document.getElementById('filtroDataAcerto').value;
    const dataBR = dataAcerto.split('-').reverse().join('/');
    const descExata = `Acerto Motoboy: ${nomeMotoboy} (${dataBR})`;
    
    if(!confirm(`Lançar R$ ${valor.toFixed(2)} nas Despesas referente ao acerto de ${nomeMotoboy}?\n\n(Se já houver um lançamento hoje para ele, o valor antigo será atualizado).`)) return;
    
    const dadosDespesa = { 
        descricao: descExata, 
        valor: valor, 
        data_vencimento: dataAcerto, 
        categoria: 'variavel', 
        recorrente: false 
    };

    try {
        // 1. Busca as despesas deste mês para verificar se a de hoje já foi lançada
        const resDesp = await fetch(`/api/despesas?mes_ano=${dataAcerto.substring(0,7)}&_t=${Date.now()}`);
        const despesasMes = await resDesp.json();
        const despExistente = despesasMes.find(d => d.descricao === descExata);

        // 2. Se achou, faz PUT (Substitui). Se não achou, faz POST (Cria).
        if(despExistente) {
            await fetch(`/api/despesas/${despExistente.id}`, { 
                method: 'PUT', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(dadosDespesa) 
            });
            alert(`Acerto atualizado com sucesso! O valor antigo foi substituído por R$ ${valor.toFixed(2)}.`);
        } else {
            await fetch('/api/despesas', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(dadosDespesa) 
            });
            alert(`Acerto de R$ ${valor.toFixed(2)} enviado para a aba de Despesas!`);
        }
        
        // Atualiza os dados financeiros em background
        carregarDespesas(); 
        carregarResumo();
    } catch(e) { 
        alert('Erro ao lançar acerto nas despesas.'); 
    }
};

async function vincularPedido(selectElement, pedidoId) { const motoboyId = selectElement.value; if(!motoboyId) return; selectElement.disabled = true; await fetch(`/api/gestao/vincular_motoboy/${pedidoId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({entregador_id: motoboyId}) }); carregarAcertoDoDia(); }
async function carregarConfigEntregadores() { 
    const r = await fetch(`/api/gestao/entregadores?_t=${Date.now()}`); 
    cacheEntregadores = await r.json(); 
    const tb = document.getElementById('lista_entregadores'); tb.innerHTML = ''; 
    const selPadrao = document.getElementById('sel_motoboy_padrao'); selPadrao.innerHTML = '<option value="">Nenhum (Vincular Manualmente)</option>'; 
    
    cacheEntregadores.forEach(e => { 
        let lblRepasse = "Padrão (Fixa)"; 
        if(e.tipo_repasse === 'bairro') lblRepasse = "Integral do Bairro"; 
        if(e.tipo_repasse === 'maior') lblRepasse = "Sempre a Maior"; 
        
        let freq = e.frequencia_pagamento || 'diario';
        let freqLabels = { 'diario': 'Diário', 'semanal': 'Semanal', 'quinzenal': 'Quinzenal', 'mensal': 'Mensal' };
        
        tb.innerHTML += `<tr>
            <td style="font-weight:bold;">${e.nome}<br><span class="tag-mini text-info">${freqLabels[freq]}</span></td>
            <td>R$ ${e.taxa_padrao.toFixed(2)}<br><span style="font-size:0.7rem; color:#aaa;">${lblRepasse}</span></td>
            <td>
                <div style="display:flex; gap:5px;">
                    <button class="btn-neon btn-neon-warning" onclick="abrirModalEntregador(${e.id}, '${e.nome}', '${e.telefone}', ${e.taxa_padrao}, '${e.tipo_repasse}', '${freq}')">✏️</button>
                    <button class="btn-neon btn-neon-danger" onclick="excluirEntregador(${e.id})">🗑️</button>
                </div>
            </td>
        </tr>`; 
        selPadrao.innerHTML += `<option value="${e.id}">${e.nome}</option>`; 
    }); 
    
    const rConf = await fetch(`/api/gestao/config_motoboy?_t=${Date.now()}`); 
    const dConf = await rConf.json(); 
    if(dConf.motoboy_padrao_id) selPadrao.value = dConf.motoboy_padrao_id; 
}
async function salvarMotoboyPadrao() { const val = document.getElementById('sel_motoboy_padrao').value; await fetch('/api/gestao/config_motoboy', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ motoboy_padrao_id: val }) }); alert("Automação atualizada!"); }
function abrirModalEntregador(id='', nome='', tel='', taxa='', repasse='padrao', freq='diario') { 
    document.getElementById('entregador_id').value = id; 
    document.getElementById('entregador_nome').value = nome; 
    document.getElementById('entregador_telefone').value = tel; 
    document.getElementById('entregador_taxa').value = taxa; 
    document.getElementById('entregador_tipo_repasse').value = repasse; 
    document.getElementById('entregador_frequencia').value = freq;
    document.getElementById('modalEntregador_titulo').innerText = id ? 'Editar Entregador' : 'Novo Entregador'; 
    document.getElementById('modalEntregador').style.display = 'flex'; 
}
async function salvarEntregador(e) { 
    e.preventDefault(); 
    const id = document.getElementById('entregador_id').value; 
    const data = { 
        nome: document.getElementById('entregador_nome').value, 
        telefone: document.getElementById('entregador_telefone').value, 
        taxa_padrao: document.getElementById('entregador_taxa').value, 
        tipo_repasse: document.getElementById('entregador_tipo_repasse').value,
        frequencia_pagamento: document.getElementById('entregador_frequencia').value
    }; 
    await fetch(id ? `/api/gestao/entregadores/${id}` : '/api/gestao/entregadores', { 
        method: id ? 'PUT' : 'POST', 
        headers: {'Content-Type':'application/json'}, 
        body: JSON.stringify(data) 
    }); 
    document.getElementById('modalEntregador').style.display = 'none'; 
    carregarEquipe(); 
}
async function excluirEntregador(id) { if(confirm("Desativar motoboy?")) { await fetch(`/api/gestao/entregadores/${id}`, {method: 'DELETE'}); carregarEquipe(); } }

function abrirModalLancMotoboy(id, nome) { document.getElementById('lan_moto_id').value = id; document.getElementById('txt_nome_motoboy_lanc').innerText = "A lançar para: " + nome; document.getElementById('lan_moto_valor').value = ''; document.getElementById('lan_moto_desc').value = ''; document.getElementById('modalLancMotoboy').style.display = 'flex'; }
async function salvarLancMotoboy(e) { e.preventDefault(); const data = { entregador_id: document.getElementById('lan_moto_id').value, tipo_lancamento: document.getElementById('lan_moto_tipo').value, valor: document.getElementById('lan_moto_valor').value, descricao: document.getElementById('lan_moto_desc').value, data_lancamento: document.getElementById('filtroDataAcerto').value }; await fetch('/api/gestao/motoboy_extrato', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) }); document.getElementById('modalLancMotoboy').style.display = 'none'; carregarAcertoDoDia(); carregarResumo(); carregarDespesas(); }
async function excluirLancMotoboy(id) { if(confirm("Remover este lançamento?")) { await fetch(`/api/gestao/motoboy_extrato/${id}`, { method: 'DELETE' }); carregarAcertoDoDia(); carregarResumo(); carregarDespesas(); } }

// === TAXAS E TARIFAS (NOVO FORMATO HÍBRIDO) ===
window.carregarConfigTaxas = async function() { 
    const r = await fetch(`/api/gestao/taxas?_t=${Date.now()}`); 
    const taxas = await r.json(); 
    const tb = document.getElementById('lista_taxas'); 
    tb.innerHTML = ''; 
    taxas.forEach(t => { 
        // Suporta os dados novos (valor/tipo) ou dados antigos já gravados (percentual/taxa_percentual)
        let val = (t.valor !== undefined && t.valor !== null) ? t.valor : (t.taxa_percentual || t.percentual || 0);
        let tipo = t.tipo || 'porcentagem';
        
        let txtTaxa = tipo === 'dinheiro' ? `R$ ${parseFloat(val).toFixed(2).replace('.', ',')}` : `${parseFloat(val).toFixed(2)} %`;
        
        tb.innerHTML += `<tr>
            <td style="font-weight:bold;">${t.nome}</td>
            <td style="color:var(--danger); font-weight:bold;">${txtTaxa}</td>
            <td><button class="btn-neon btn-neon-danger" onclick="excluirTaxa(${t.id})">🗑️</button></td>
        </tr>`; 
    }); 
}

window.abrirModalTaxa = function() { 
    document.getElementById('taxa_nome').value = ''; 
    if(document.getElementById('taxa_valor')) document.getElementById('taxa_valor').value = ''; 
    if(document.getElementById('taxa_tipo')) document.getElementById('taxa_tipo').value = 'porcentagem'; 
    document.getElementById('modalTaxa').style.display = 'flex'; 
}

window.salvarTaxa = async function(e) { 
    e.preventDefault(); 
    const nome = document.getElementById('taxa_nome').value;
    const valor = parseFloat(document.getElementById('taxa_valor').value) || 0;
    const tipo = document.getElementById('taxa_tipo').value;
    
    if(!nome || valor < 0) return alert("Preencha corretamente.");
    
    const payload = { 
        nome: nome, 
        taxa_percentual: tipo === 'porcentagem' ? valor : 0, 
        percentual: tipo === 'porcentagem' ? valor : 0, 
        valor: valor, 
        tipo: tipo 
    };
    
    await fetch('/api/gestao/taxas', { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'}, 
        body: JSON.stringify(payload) 
    }); 
    
    document.getElementById('modalTaxa').style.display = 'none'; 
    carregarConfigTaxas(); 
    carregarResumo(); 
}

window.excluirTaxa = async function(id) { 
    if(confirm("Remover taxa?")) { 
        await fetch(`/api/gestao/taxas/${id}`, {method: 'DELETE'}); 
        carregarConfigTaxas(); 
        carregarResumo(); 
    } 
}

// === FUNCIONÁRIOS E EXTRATOS ===
async function carregarFuncionarios() {
    const res = await fetch(`/api/gestao/funcionarios?_t=${Date.now()}`); const lista = await res.json(); const div = document.getElementById('lista_funcionarios'); div.innerHTML = '';
    if (lista.length === 0) { div.innerHTML = '<p style="color:#aaa; text-align:center;">Nenhum funcionário cadastrado.</p>'; return; }
    lista.forEach(f => {
        let funcClass = funcAtivo && funcAtivo.id === f.id ? 'func-card active' : 'func-card';
        div.innerHTML += `<div class="${funcClass}" onclick="selecionarFuncionario(${f.id}, '${f.nome}', '${f.cargo}', ${f.salario_base})"><div><strong style="color:white; display:block;">${f.nome}</strong><span style="font-size:0.8rem; color:#aaa;">${f.cargo || 'Funcionário'}</span></div><div style="text-align:right;"><span style="color:var(--success); font-weight:bold; display:block;">R$ ${f.salario_base.toFixed(2)}</span><div style="display:flex; gap:5px; justify-content:flex-end; margin-top:5px;"><button class="btn-neon btn-neon-warning" onclick="event.stopPropagation(); abrirModalFuncionario(${f.id}, '${f.nome}', '${f.cargo}', ${f.salario_base}, ${f.dia_pagamento})">✏️</button><button class="btn-neon btn-neon-danger" onclick="event.stopPropagation(); excluirFuncionario(${f.id})">🗑️</button></div></div></div>`;
    });
}
function selecionarFuncionario(id, nome, cargo, salario) { funcAtivo = { id, nome, cargo, salario }; carregarFuncionarios(); document.getElementById('painel_extrato_vazio').classList.add('hidden'); document.getElementById('painel_extrato_ativo').classList.remove('hidden'); document.getElementById('extrato_nome').innerText = nome; document.getElementById('extrato_cargo').innerText = cargo || 'Funcionário Padrão'; carregarExtratoAtivo(); }

async function carregarExtratoAtivo() {
    if(!funcAtivo) return; 
    const mes = document.getElementById('filtroMesFunc').value;
    
    // 1. Obter os dados do mês atual selecionado
    const res = await fetch(`/api/gestao/funcionarios/${funcAtivo.id}/extrato?mes_ano=${mes}&_t=${Date.now()}`); 
    const data = await res.json();
    
    // 2. BUSCA INTELIGENTE: Verificar o saldo acumulado dos últimos 4 meses
    let [ano, mesNum] = mes.split('-');
    let dataRef = new Date(ano, parseInt(mesNum) - 1, 1);
    let promessas = [];
    
    for(let i=1; i<=4; i++) { 
        let d = new Date(dataRef.getFullYear(), dataRef.getMonth() - i, 1);
        let mStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
        promessas.push(fetch(`/api/gestao/funcionarios/${funcAtivo.id}/extrato?mes_ano=${mStr}&_t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(()=>null));
    }
    
    let resultados = await Promise.all(promessas);
    let saldo_anterior = 0;
    
    resultados.forEach(r => { 
        // CORREÇÃO: Só puxa o saldo de meses anteriores se for NEGATIVO
        // Isso impede que salários esquecidos/antigos virem uma bola de neve de R$ 200,00
        if(r && r.saldo_a_pagar !== undefined && r.saldo_a_pagar < 0) {
            saldo_anterior += r.saldo_a_pagar; 
        }
    });
    
    // 3. Aplicar a lógica de desconto ao Total Devido
    let total_devido_atual = data.salario_base + data.total_bonus;
    // Como o saldo_anterior aqui será sempre negativo (ex: -20), ele vai abater no salário atual
    let novo_total_devido = total_devido_atual + saldo_anterior; 
    let novo_saldo_restante = novo_total_devido - data.total_pago;

    // 4. Montar a Interface Visual
    let htmlDevido = `<h3 class="m-0 mt-5 text-info" id="extrato_devido">R$ ${novo_total_devido.toFixed(2).replace('.',',')}</h3>`;
    
    if (saldo_anterior < 0) {
        htmlDevido += `<span class="text-xs text-danger font-bold d-block mt-5">(- R$ ${Math.abs(saldo_anterior).toFixed(2)} Vales Antigos)</span>`;
    }

    const containerDevido = document.getElementById('extrato_devido').parentElement;
    containerDevido.innerHTML = `<span class="text-muted text-sm">Total Devido Atual</span>${htmlDevido}`;

    document.getElementById('extrato_pago').innerText = `R$ ${data.total_pago.toFixed(2).replace('.',',')}`;
    
    let corSaldo = novo_saldo_restante >= 0 ? "text-success" : "text-danger";
    const txtSaldo = document.getElementById('extrato_saldo');
    txtSaldo.innerText = `R$ ${novo_saldo_restante.toFixed(2).replace('.',',')}`;
    txtSaldo.className = `m-0 mt-5 ${corSaldo}`;
    
    window.saldoAtivoPendente = novo_saldo_restante;
    
    const tb = document.getElementById('lista_lancamentos_func'); tb.innerHTML = '';
    if(data.extrato.length === 0) { tb.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#888;">Nenhum lançamento neste mês.</td></tr>'; return; }
    
    data.extrato.forEach(l => {
        let icone = "💰", cor = "text-danger";
        if(l.tipo_lancamento === 'vale') { icone = "💸 Vale"; cor = "text-warning"; }
        if(l.tipo_lancamento === 'salario') { icone = "💵 Salário"; cor = "text-success"; }
        if(l.tipo_lancamento === 'bonus') { icone = "⭐ Bônus"; cor = "text-info"; }
        let dBR = l.data_lancamento.split('-').reverse().slice(0,2).join('/');
        tb.innerHTML += `<tr><td>${dBR}</td><td><span style="background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px; font-size:0.8rem;">${icone}</span></td><td class="text-muted">${l.descricao}</td><td class="${cor} font-bold">R$ ${l.valor.toFixed(2).replace('.',',')}</td><td><button class="btn-neon btn-neon-danger" onclick="excluirLancamentoFunc(${l.id})">🗑️</button></td></tr>`;
    });
}

function abrirModalFuncionario(id='', nome='', cargo='', salario='', dia=5) { document.getElementById('func_id').value = id; document.getElementById('func_nome').value = nome; document.getElementById('func_cargo').value = cargo; document.getElementById('func_salario').value = salario; document.getElementById('func_dia').value = dia; document.getElementById('modalFuncionario_titulo').innerText = id ? 'Editar Funcionário' : 'Cadastrar Funcionário'; document.getElementById('modalFuncionario').style.display = 'flex'; }
async function salvarFuncionario(e) { e.preventDefault(); const id = document.getElementById('func_id').value; const data = { nome: document.getElementById('func_nome').value, cargo: document.getElementById('func_cargo').value, salario_base: document.getElementById('func_salario').value, dia_pagamento: document.getElementById('func_dia').value }; await fetch(id ? `/api/gestao/funcionarios/${id}` : '/api/gestao/funcionarios', { method: id ? 'PUT' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) }); document.getElementById('modalFuncionario').style.display = 'none'; if(funcAtivo && funcAtivo.id == id) { funcAtivo.nome = data.nome; funcAtivo.cargo = data.cargo; } carregarFuncionarios(); if(funcAtivo) carregarExtratoAtivo(); }
async function excluirFuncionario(id) { if(confirm("Demitir / Inativar este funcionário? O histórico dele será mantido.")) { await fetch(`/api/gestao/funcionarios/${id}`, {method: 'DELETE'}); if(funcAtivo && funcAtivo.id == id) { funcAtivo = null; document.getElementById('painel_extrato_vazio').classList.remove('hidden'); document.getElementById('painel_extrato_ativo').classList.add('hidden'); } carregarFuncionarios(); } }
function abrirModalLancamentoFunc() { if(!funcAtivo) return alert("Selecione um funcionário primeiro."); document.getElementById('lan_valor').value = ''; document.getElementById('lan_desc').value = ''; document.getElementById('modalLancamentoFunc').style.display = 'flex'; }
async function salvarLancamentoFunc(e) { e.preventDefault(); const data = { tipo_lancamento: document.getElementById('lan_tipo').value, valor: document.getElementById('lan_valor').value, data_lancamento: document.getElementById('lan_data').value, descricao: document.getElementById('lan_desc').value }; await fetch(`/api/gestao/funcionarios/${funcAtivo.id}/extrato`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) }); document.getElementById('modalLancamentoFunc').style.display = 'none'; carregarExtratoAtivo(); carregarResumo(); carregarDespesas(); }
async function excluirLancamentoFunc(id_extrato) { if(confirm("Excluir este lançamento? Isto removerá a despesa do mês também.")) { await fetch(`/api/gestao/funcionarios/extrato/${id_extrato}`, {method: 'DELETE'}); carregarExtratoAtivo(); carregarResumo(); carregarDespesas(); } }
function preencherSaldoQuitar() { if (window.saldoAtivoPendente && window.saldoAtivoPendente > 0) { document.getElementById('lan_valor').value = window.saldoAtivoPendente.toFixed(2); document.getElementById('lan_tipo').value = 'salario'; document.getElementById('lan_desc').value = 'Fechamento de Salário'; } else { alert("Não há saldo pendente para quitar ou o funcionário está com saldo negativo (já pediu mais vales do que devia)."); } }

// ==========================================
// DETALHES DO DASHBOARD (Mini DRE)
// ==========================================
async function abrirDetalheDash(tipo) {
    if (!cacheResumoMes) return alert("Aguarde os dados carregarem.");
    
    const titulo = document.getElementById('detalhe_titulo');
    const box = document.getElementById('detalhe_conteudo');
    box.innerHTML = '<p class="text-center text-muted">Carregando detalhes...</p>';
    document.getElementById('modalDashDetalhes').style.display = 'flex';

    if (tipo === 'receita') {
        titulo.innerText = "💰 Origem do Faturamento";
        let html = '';
        for(let k in cacheResumoMes.breakdown_pagamentos) {
            if(cacheResumoMes.breakdown_pagamentos[k] > 0) {
                html += `<div class="dre-row"><span>Pagamentos via ${k}</span><strong class="text-success">R$ ${cacheResumoMes.breakdown_pagamentos[k].toFixed(2).replace('.',',')}</strong></div>`;
            }
        }
        html += `<div class="dre-row total"><span>Total Bruto Faturado</span><strong class="text-success">R$ ${cacheResumoMes.receita.toFixed(2).replace('.',',')}</strong></div>`;
        box.innerHTML = html;
    } 
    else if (tipo === 'despesas') {
        titulo.innerText = "🧾 Para onde foi o dinheiro?";
        const mes = document.getElementById('filtroMesResumo').value;
        const res = await fetch(`/api/despesas?mes_ano=${mes}&_t=${Date.now()}`);
        const desp = await res.json();
        
        let subTotais = { operacional: 0, variavel: 0, impostos: 0, folha: 0 };
        desp.forEach(d => {
            if(d.categoria in subTotais) subTotais[d.categoria] += d.valor;
            else if(d.categoria.includes('func') || d.categoria === 'fixa') subTotais.folha += d.valor;
            else subTotais.variavel += d.valor;
        });

        let html = `
            <p class="text-muted text-sm line-height-base">Aqui estão somadas apenas as despesas lançadas manualmente ou de salários (não inclui compras de estoque físico).</p>
            <div class="dre-row"><span>🏢 Custos Operacionais (Aluguel, Luz)</span><strong class="text-danger">R$ ${subTotais.operacional.toFixed(2).replace('.',',')}</strong></div>
            <div class="dre-row"><span>📦 Custos Variáveis (Embalagens, Gás)</span><strong class="text-warning">R$ ${subTotais.variavel.toFixed(2).replace('.',',')}</strong></div>
            <div class="dre-row"><span>👨‍🍳 Folha de Pagamento e Vales</span><strong class="text-info">R$ ${subTotais.folha.toFixed(2).replace('.',',')}</strong></div>
            <div class="dre-row"><span>⚖️ Impostos (Contador, DAS)</span><strong class="text-danger">R$ ${subTotais.impostos.toFixed(2).replace('.',',')}</strong></div>
            <div class="dre-row" style="background:rgba(255,255,255,0.05); padding:10px; margin-top:10px; border-radius:6px;"><span>💳 Taxas de Maquininha/Ifood <br><small class="text-muted">(Deduzido automaticamente do caixa)</small></span><strong style="color:#a855f7;">R$ ${cacheResumoMes.taxas_cartao.toFixed(2).replace('.',',')}</strong></div>
            <div class="dre-row total"><span>Total em Despesas</span><strong class="text-danger">R$ ${(cacheResumoMes.despesas + cacheResumoMes.taxas_cartao).toFixed(2).replace('.',',')}</strong></div>
        `;
        box.innerHTML = html;
    }
    else if (tipo === 'compras') {
        titulo.innerText = "📉 Custo com Mercadorias";
        box.innerHTML = `
            <p class="text-muted text-sm line-height-base">Total gasto este mês na aba <b>Almoxarifado</b> reabastecendo insumos físicos (Comidas, Bebidas, Ingredientes).</p>
            <div class="dre-row text-lg"><span>Total de Compras</span><strong class="text-warning">R$ ${cacheResumoMes.compras_estoque.toFixed(2).replace('.',',')}</strong></div>
            <p class="text-info text-sm mt-20">💡 Dica: Se o seu custo de estoque ultrapassar 35% do faturamento, é hora de rever os preços do seu cardápio!</p>
        `;
    }
    else if (tipo === 'lucro') {
        titulo.innerText = "🏆 DRE (Demonstrativo de Resultado)";
        let lucroReal = cacheResumoMes.lucro_liquido;
        let corLucro = lucroReal >= 0 ? "text-success" : "text-danger";
        
        box.innerHTML = `
            <p class="text-muted text-sm mb-15">O cálculo exato de quanto dinheiro sobrou livre no final do mês.</p>
            <div class="dre-row text-success font-bold"><span>(+) Faturamento Bruto (Caixa)</span><span>R$ ${cacheResumoMes.receita.toFixed(2).replace('.',',')}</span></div>
            <div class="dre-row sub"><span>(-) Taxas de Maquininhas e App</span><span>R$ ${cacheResumoMes.taxas_cartao.toFixed(2).replace('.',',')}</span></div>
            <div class="dre-row sub"><span>(-) Compras de Mercadoria (Estoque)</span><span>R$ ${cacheResumoMes.compras_estoque.toFixed(2).replace('.',',')}</span></div>
            <div class="dre-row sub"><span>(-) Despesas Extras, Contas e Salários</span><span>R$ ${cacheResumoMes.despesas.toFixed(2).replace('.',',')}</span></div>
            <div class="dre-row total ${corLucro}"><span>(=) Lucro Líquido Final</span><span>R$ ${lucroReal.toFixed(2).replace('.',',')}</span></div>
        `;
    }
}
window.baixarRelatorioContador = function() {
    const mes = document.getElementById('filtroMesResumo').value;
    if(!mes) return alert("Selecione um mês primeiro.");
    window.location.href = `/api/gestao/exportar_contabilidade?mes_ano=${mes}`;
};

// ==========================================
// FECHAR MODAIS CLICANDO FORA (OVERLAY)
// ==========================================
window.addEventListener('click', function(event) {
    // Verifica se o elemento clicado tem a classe 'modal-overlay' (o fundo escuro)
    if (event.target.classList.contains('modal-overlay')) {
        // Esconde o modal que foi clicado
        event.target.style.display = 'none';
    }
});