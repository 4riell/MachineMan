async function vincularMotoboyIndividual(pedidoId, motoboyId) {
    const val = motoboyId ? parseInt(motoboyId) : null;
    await fetch(`/api/gestao/vincular_motoboy/${pedidoId}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({entregador_id: val}) });
    const selectEl = document.querySelector(`.motoboy-select[data-id="${pedidoId}"]`);
    if(selectEl) { selectEl.style.borderColor = 'var(--success)'; setTimeout(() => selectEl.style.borderColor = '#555', 2000); }
}

async function vincularMotoboyEmMassa() {
    const checked = document.querySelectorAll('.card-select-box:checked'); const motoboyId = document.getElementById('bulk_motoboy').value;
    if (!checked.length || !motoboyId) return alert("Selecione os pedidos e o motoboy!");
    const val = parseInt(motoboyId); let ids = []; checked.forEach(c => ids.push(c.value));
    const btn = document.querySelector('.btn-bulk-info[onclick="vincularMotoboyEmMassa()"]'); btn.innerText = "Atribuindo..."; btn.disabled = true;
    await Promise.all(ids.map(id => fetch(`/api/gestao/vincular_motoboy/${id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({entregador_id: val}) })));
    window.location.reload();
}

function updateBulkBar() {
    const checked = document.querySelectorAll('.card-select-box:checked');
    const bar = document.getElementById('bulk-actions-bar'); const countSpan = document.getElementById('bulk-count');
    if (checked.length > 0) { bar.style.display = 'flex'; countSpan.innerText = `${checked.length} selecionado${checked.length > 1 ? 's' : ''}`; } else { bar.style.display = 'none'; }
}

function toggleSelecionarTodos() {
    const visibleCards = document.querySelectorAll('.pedido-card:not([style*="display: none"])');
    let checkboxes = []; visibleCards.forEach(c => { const cb = c.querySelector('.card-select-box'); if(cb) checkboxes.push(cb); });
    if(checkboxes.length === 0) return; const allChecked = checkboxes.every(c => c.checked);
    checkboxes.forEach(c => c.checked = !allChecked); updateBulkBar();
}

async function excluirSelecionados() {
    const checked = document.querySelectorAll('.card-select-box:checked'); if (!checked.length) return;
    if (!confirm(`Excluir ${checked.length} pedidos?`)) return;
    let ids = []; checked.forEach(c => ids.push(c.value));
    await Promise.all(ids.map(id => fetch(`/api/pedidos/${id}`, { method: 'DELETE' }))); window.location.reload();
}

async function limparTudo(filtro) {
    if (!confirm("ATENÇÃO: Excluir TODOS visíveis?")) return;
    const allCards = document.querySelectorAll('.pedido-card:not([style*="display: none"])'); let ids = []; allCards.forEach(card => ids.push(card.dataset.id));
    if (ids.length === 0) return; await Promise.all(ids.map(id => fetch(`/api/pedidos/${id}`, { method: 'DELETE' }))); window.location.reload();
}

async function excluirTodosCliente(telefone) {
    if (!confirm(`Excluir histórico de ${telefone}?`)) return;
    const allCards = document.querySelectorAll(`.status-select[data-phone="${telefone}"]`); let ids = []; allCards.forEach(select => { const card = select.closest('.pedido-card'); if(card) ids.push(card.dataset.id); });
    if (ids.length === 0) return; await Promise.all(ids.map(id => fetch(`/api/pedidos/${id}`, { method: 'DELETE' }))); window.location.reload();
}

function aplicarFiltrosUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    let filtroAtual = urlParams.get('filtro') || 'hoje';
    const tipo = document.getElementById('filtroTipo').value;
    const status = document.getElementById('filtroStatus').value;
    const dataFiltro = document.getElementById('filtroData').value;

    // Se tem data selecionada, muda contexto para 'todos' (histórico) se estava em 'hoje'
    if (dataFiltro && filtroAtual === 'hoje') {
        filtroAtual = 'todos';
    }

    let url = `/pedidos?filtro=${filtroAtual}&tipo=${tipo}&status=${status}`;
    if (dataFiltro) {
        url += `&data_filtro=${dataFiltro}`;
    }
    
    window.location.href = url;
}

let timerBusca = null; let listaItens = []; let bairrosCache = null; let listaPagamentos = []; let cacheSaboresPizza = []; let promocoesGlobais = []; let categoriasComVariacaoCache = {};
let isCaixaRapido = false;
let clienteEncontrado = false;

async function carregarPromocoesDoBanco() { try { const res = await fetch('/api/pedidos/promocoes'); promocoesGlobais = await res.json(); } catch(e) {} }

function calcularPrecoComDesconto(precoBase, categoriaId, produtoId) {
    let pBase = parseFloat(precoBase) || 0; if (!promocoesGlobais || promocoesGlobais.length === 0) return pBase;
    let promo = promocoesGlobais.find(p => String(p.categoria).trim().toLowerCase() === String(categoriaId).trim().toLowerCase() && String(p.produto_id).trim() === String(produtoId).trim());
    if (!promo) promo = promocoesGlobais.find(p => String(p.categoria).trim().toLowerCase() === String(categoriaId).trim().toLowerCase() && String(p.produto_id).trim() === "0");
    if(!promo) return pBase;
    let desc = String(promo.desconto).replace(',', '.').trim(); let val = Math.abs(parseFloat(desc.replace(/[^0-9.-]/g, '')));
    if(desc.includes('%')) return Math.max(0, pBase * (1 - (val / 100))); else return Math.max(0, pBase - val);
}

async function verificarSeCategoriaTemVariacao(catId, prodId) {
    if(categoriasComVariacaoCache[catId] !== undefined) return categoriasComVariacaoCache[catId];
    try { const res = await fetch(`/api/detalhes_produto/${catId}/${prodId}`); const data = await res.json(); const temVariacao = (data.variacoes && data.variacoes.length > 0); categoriasComVariacaoCache[catId] = temVariacao; return temVariacao; } catch(e) { return false; }
}

// NOVA FUNCAO: MODO CAIXA VS NORMAL
function toggleModoCaixa() {
    isCaixaRapido = !isCaixaRapido;
    const btn = document.getElementById('btn_modo_caixa');
    const boxCli = document.getElementById('box_cliente_normal');
    const boxOri = document.getElementById('box_origem');
    const tituloModal = document.getElementById('titulo_modal_manual');

    limparCamposCliente();
    const manTel = document.getElementById('man_telefone');
    if(manTel) {
        manTel.value = '';
        manTel.readOnly = false;
    }
    const statusBusca = document.getElementById('status_busca');
    if(statusBusca) statusBusca.innerText = '';
    
    clienteEncontrado = false;

    if (isCaixaRapido) {
        if(btn) {
            btn.innerHTML = "👤 Modo Normal (Clientes Cadastrados)";
            btn.style.background = "#2196f3";
        }
        if(tituloModal) tituloModal.innerText = "⚡ Novo Caixa Rápido";
        
        if(boxOri) boxOri.style.display = 'block';
        if(boxCli) boxCli.style.display = 'none'; 
        
        const manNome = document.getElementById('man_nome');
        if(manNome) manNome.value = "Caixa Rápido";
        
        const manEntrega = document.getElementById('man_entrega');
        if(manEntrega) manEntrega.value = 'Retirada';
        
        atualizarInterfacePagamento();

        // Destrava os campos de endereço
        ['man_rua', 'man_numero', 'man_ref'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.readOnly = false;
        });
        const manBairro = document.getElementById('man_bairro');
        if(manBairro) manBairro.disabled = false;

    } else {
        if(btn) {
            btn.innerHTML = "⚡ Ativar Caixa Rápido";
            btn.style.background = "#ff9800";
        }
        if(tituloModal) tituloModal.innerText = "📝 Novo Pedido";
        
        if(boxOri) boxOri.style.display = 'none';
        if(boxCli) boxCli.style.display = 'block'; 
        
        const manNome = document.getElementById('man_nome');
        if(manNome) manNome.readOnly = true;
        
        if(manTel) manTel.placeholder = "📱 Telefone (Obrigatório)*";
        
        const manEntrega = document.getElementById('man_entrega');
        if(manEntrega) manEntrega.value = 'Entrega';
        
        atualizarInterfacePagamento();

        // Trava os campos de endereço no Modo Normal
        ['man_rua', 'man_numero', 'man_ref'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.readOnly = true;
        });
        const manBairro = document.getElementById('man_bairro');
        if(manBairro) manBairro.disabled = true;
    }
    toggleEndereco();
    validarBotaoSalvar();
}

async function abrirModalManual() {
    document.getElementById('modalManual').style.display = 'flex';
    await carregarBairros(); 
    isCaixaRapido = true; 
    toggleModoCaixa(); 
    listaPagamentos = []; 
    renderizarPagamentos(); 
    document.getElementById('sel_pgt_metodo').selectedIndex = 0;
    atualizarInterfacePagamento();
    await carregarPromocoesDoBanco();
}

function atualizarInterfacePagamento() {
    const sel = document.getElementById('sel_pgt_metodo');
    const opt = sel.options[sel.selectedIndex];
    const inputDetalhe = document.getElementById('input_pgt_detalhe');

    if(!opt || !opt.value) {
        inputDetalhe.style.display = 'none';
        inputDetalhe.value = '';
        return;
    }

    const pedeDetalhe = opt.dataset.pede === "1";
    const pergunta = opt.dataset.pergunta || "Detalhe...";
    
    if (pedeDetalhe) {
        inputDetalhe.style.display = 'block';
        inputDetalhe.placeholder = pergunta;
    } else {
        inputDetalhe.style.display = 'none';
        inputDetalhe.value = '';
    }
    
    let totalFinal = parseFloat(document.getElementById('man_valor_final').value) || 0;
    let jaPago = listaPagamentos.reduce((acc, p) => acc + p.valor, 0);
    let restante = Math.max(0, totalFinal - jaPago);
    document.getElementById('input_pgt_valor').value = restante.toFixed(2);
}

function adicionarPagamento() {
    const sel = document.getElementById('sel_pgt_metodo');
    const opt = sel.options[sel.selectedIndex];
    if(!opt || !opt.value) return alert("Selecione um método.");
    const metodo = sel.value;
    const valor = parseFloat(document.getElementById('input_pgt_valor').value);
    if (!valor || valor <= 0) { alert("Valor inválido."); return; }
    
    let detalhe = "";
    if (opt.dataset.pede === "1") {
        const valDet = document.getElementById('input_pgt_detalhe').value.trim();
        if (metodo.toLowerCase().includes('dinheiro')) {
            const valNum = parseFloat(valDet.replace(',', '.'));
            if(!isNaN(valNum)) {
                if(valNum < valor) { alert('Valor do troco menor que o pagamento!'); return; }
                detalhe = `Troco para ${valNum.toFixed(2)}`;
            } else if(valDet) { detalhe = valDet; }
        } else { detalhe = valDet; }
    }
    
    let totalFinal = parseFloat(document.getElementById('man_valor_final').value) || 0;
    let jaPago = listaPagamentos.reduce((acc, p) => acc + p.valor, 0);
    if (jaPago + valor > totalFinal + 0.05) { alert("Valor excede o total!"); return; }
    
    listaPagamentos.push({ metodo: metodo, valor: valor, detalhe: detalhe });
    renderizarPagamentos(); document.getElementById('input_pgt_detalhe').value = ''; atualizarInterfacePagamento();
    validarBotaoSalvar();
}

function removerPagamento(index) { listaPagamentos.splice(index, 1); renderizarPagamentos(); atualizarInterfacePagamento(); validarBotaoSalvar();}

function renderizarPagamentos() {
    const tbody = document.getElementById('lista_pagamentos_tabela'); tbody.innerHTML = ''; let totalPago = 0;
    listaPagamentos.forEach((pg, index) => {
        totalPago += pg.valor; let displayDet = pg.detalhe || '';
        if(pg.metodo.toLowerCase().includes('dinheiro') && displayDet.includes('Troco para')) {
            let valEntregue = parseFloat(displayDet.replace(/[^0-9.]/g, ''));
            if(!isNaN(valEntregue) && valEntregue > pg.valor) {
                let troco = valEntregue - pg.valor;
                displayDet += `<div style="color:var(--success); font-weight:bold; font-size:0.85rem;">↳ Troco: R$ ${troco.toFixed(2)}</div>`;
            }
        }
        tbody.innerHTML += `<tr><td>${pg.metodo}</td><td style="color:#ccc;">${displayDet || '-'}</td><td>R$ ${pg.valor.toFixed(2)}</td><td style="text-align:right;"><button type="button" class="btn-rem-item" onclick="removerPagamento(${index})">X</button></td></tr>`;
    });
    document.getElementById('span_total_pago').innerText = totalPago.toFixed(2);
    const totalFinal = parseFloat(document.getElementById('man_valor_final').value) || 0;
    const restante = Math.max(0, totalFinal - totalPago); document.getElementById('span_total_restante').innerText = restante.toFixed(2);
    
    if (Math.abs(restante) < 0.05 && totalFinal > 0) {
        document.getElementById('span_total_restante').style.color = 'var(--success)'; document.getElementById('span_total_restante').innerText = "OK"; 
    } else {
        document.getElementById('span_total_restante').style.color = 'var(--danger)'; 
    }
}

async function carregarBairros() {
    if(bairrosCache) return;
    try { const resp = await fetch('/api/bairros_lookup'); bairrosCache = await resp.json(); const sel = document.getElementById('man_bairro'); sel.innerHTML = '<option value="">Selecione o Bairro...</option>'; bairrosCache.bairros.forEach(b => { const taxa = b.taxa !== null ? b.taxa : -1; sel.innerHTML += `<option value="${b.nome}" data-taxa="${taxa}">${b.nome} (${taxa >=0 ? 'R$ '+taxa : 'Padrão'})</option>`; }); } catch(e){}
}

function toggleEndereco() {
    const tipo = document.getElementById('man_entrega').value;
    const isEnt = (tipo === 'Entrega');
    
    document.getElementById('box_endereco').style.display = isEnt ? 'block' : 'none';
    
    document.getElementById('row_taxa_entrega').style.display = isEnt ? 'flex' : 'none';
    if(!isEnt) document.getElementById('val_entrega').value = "0.00"; else autoCalcularEntrega();
    calcularTotalManual();
}

function autoCalcularEntrega() {
    const manEntrega = document.getElementById('man_entrega');
    if (!manEntrega || manEntrega.value !== 'Entrega' || !bairrosCache) return;
    
    const selBairro = document.getElementById('man_bairro');
    if(!selBairro) return;

    const optSelected = selBairro.options[selBairro.selectedIndex];
    let taxaFinal = parseFloat(bairrosCache.taxa_padrao || 0);

    if (optSelected && optSelected.value) {
        let taxaBairro = parseFloat(optSelected.dataset.taxa);
        if (taxaBairro >= 0) taxaFinal = taxaBairro; 
    }
    
    const valInput = document.getElementById('val_entrega');
    if(valInput) valInput.value = taxaFinal.toFixed(2);
    
    const display = document.getElementById('display_entrega');
    if (display) display.innerText = `R$ ${taxaFinal.toFixed(2)}`;
    
    calcularTotalManual();
}

function limparCamposCliente() {
    document.getElementById('man_nome').value = '';
    const manCpf = document.getElementById('man_cpf');
    if(manCpf) manCpf.value = '';
    if(!isCaixaRapido) document.getElementById('man_nome').readOnly = true;
    document.getElementById('man_rua').value = '';
    document.getElementById('man_numero').value = '';
    document.getElementById('man_ref').value = '';
    document.getElementById('man_bairro').value = '';
    document.getElementById('val_entrega').value = "0.00";
    calcularTotalManual();
}

function validarBotaoSalvar() {
    const btnSalvar = document.getElementById('btn_salvar_pedido');
    let totalFinal = parseFloat(document.getElementById('man_valor_final').value) || 0;
    let jaPago = listaPagamentos.reduce((acc, p) => acc + p.valor, 0);
    let restante = Math.max(0, totalFinal - jaPago);
    
    let pagamentoOk = Math.abs(restante) < 0.05 && totalFinal > 0;
    let clienteOk = isCaixaRapido || clienteEncontrado;

    if (pagamentoOk && clienteOk && listaItens.length > 0) {
        btnSalvar.disabled = false; btnSalvar.style.opacity = 1;
    } else {
        btnSalvar.disabled = true; btnSalvar.style.opacity = 0.5;
    }
}

function buscarClienteDelay(val) {
    clearTimeout(timerBusca);
    const numeros = val.replace(/\D/g, '');
    if(numeros.length < 8) { 
        document.getElementById('status_busca').innerText = ''; 
        limparCamposCliente();
        clienteEncontrado = false;
        validarBotaoSalvar();
        return; 
    }
    document.getElementById('status_busca').innerText = 'Buscando...';
    timerBusca = setTimeout(async () => {
        const resp = await fetch(`/api/cliente_lookup/${encodeURIComponent(val)}`); const data = await resp.json();
        if(data.encontrado) {
            clienteEncontrado = true;
            document.getElementById('status_busca').innerText = '✅ Cliente encontrado!'; document.getElementById('status_busca').style.color = 'var(--success)';
            document.getElementById('man_nome').value = data.dados.nome||''; 
            document.getElementById('man_nome').readOnly = true;
            const manCpf = document.getElementById('man_cpf');
            if(manCpf) manCpf.value = data.dados.cpf||'';
            document.getElementById('man_rua').value = data.dados.rua||''; document.getElementById('man_numero').value = data.dados.numero_casa||''; document.getElementById('man_ref').value = data.dados.ponto_referencia||'';
            if(data.dados.bairro) {
                const sel = document.getElementById('man_bairro'); if(!bairrosCache) await carregarBairros();
                for(let i=0; i<sel.options.length; i++){ if(sel.options[i].value.toLowerCase() === data.dados.bairro.toLowerCase()){ sel.selectedIndex = i; break; } }
            }
            autoCalcularEntrega();
        } else { 
            clienteEncontrado = false;
            document.getElementById('status_busca').innerText = '❌ Não cadastrado. Use o Caixa Rápido.'; 
            document.getElementById('status_busca').style.color = 'var(--danger)'; 
            limparCamposCliente();
        }
        validarBotaoSalvar();
    }, 800);
}

// BUSCA GLOBAL DE PRODUTOS
let timerBuscaProd;
async function buscarProdutoGlobal() {
    clearTimeout(timerBuscaProd);
    const q = document.getElementById('busca_global').value.trim();
    const resBox = document.getElementById('resultado_busca');
    if(q.length < 2) { resBox.style.display = 'none'; return; }
    
    timerBuscaProd = setTimeout(async () => {
        try {
            const res = await fetch(`/api/pedidos/buscar_produtos?q=${encodeURIComponent(q)}`);
            const data = await res.json();
            
            resBox.innerHTML = '';
            if(data.length === 0) {
                resBox.innerHTML = '<div class="p-10 text-muted text-center text-sm">Nenhum produto encontrado.</div>';
            } else {
                for (let p of data) {
                    let pid = p.produto_id || p.id;
                    let temVariacao = await verificarSeCategoriaTemVariacao(p.categoria_id, pid);
                    let precoBase = parseFloat(p.preco) || 0;
                    let precoFinal = calcularPrecoComDesconto(precoBase, p.categoria_id, pid);
                    
                    let displayPreco = "";
                    if (!temVariacao && (precoBase > 0 || precoFinal > 0)) {
                        displayPreco = precoFinal !== precoBase ? `- <span class="text-warning font-bold">R$ ${precoFinal.toFixed(2)}</span> <span class="text-xs text-success">(Promo)</span>` : `- R$ ${precoBase.toFixed(2)}`;
                    }

                    const div = document.createElement('div');
                    div.className = 'search-item-result';
                    div.innerHTML = `<strong class="text-white">${p.nome}</strong> <br><span class="text-muted text-xs">${p.emoji || ''} ${p.categoria_nome} ${displayPreco}</span>`;
                    div.onclick = () => selecionarProdutoDaBusca(p.categoria_id, pid);
                    resBox.appendChild(div);
                }
            }
            resBox.style.display = 'block';
        } catch(e) { console.error("Erro na busca", e); }
    }, 400);
}

async function selecionarProdutoDaBusca(catId, prodId) {
    document.getElementById('resultado_busca').style.display = 'none';
    document.getElementById('busca_global').value = '';
    document.getElementById('sel_categoria').value = catId;
    await carregarProdutosDaCategoria();
    document.getElementById('sel_produto').value = prodId;
    carregarDetalhesProduto();
}

async function carregarProdutosDaCategoria() {
    const catId = document.getElementById('sel_categoria').value; const selProd = document.getElementById('sel_produto'); const boxDyn = document.getElementById('box_detalhes_dinamicos');
    selProd.innerHTML = '<option value="">Selecione...</option>'; boxDyn.innerHTML = ''; boxDyn.style.display = 'none';
    const qtdInput = document.getElementById('manual_qtd_item'); if(qtdInput) qtdInput.value = 1;
    if(!catId) return; 
    selProd.innerHTML = '<option>Carregando...</option>'; await carregarPromocoesDoBanco(); const resp = await fetch(`/api/produtos_categoria/${catId}`); const produtos = await resp.json();
    if(catId === 'pizza') cacheSaboresPizza = produtos;
    let temVariacaoDeTamanho = false; if(produtos.length > 0) temVariacaoDeTamanho = await verificarSeCategoriaTemVariacao(catId, produtos[0].id);
    selProd.innerHTML = '<option value="">Selecione...</option>';
    produtos.forEach(p => {
        let precoBase = parseFloat(p.preco) || 0; let precoFinal = calcularPrecoComDesconto(precoBase, catId, p.id); let txtExtra = "";
        if (!temVariacaoDeTamanho) { if (precoBase > 0 || precoFinal > 0) { txtExtra = precoFinal !== precoBase ? `(Promo: R$ ${precoFinal.toFixed(2)})` : `(R$ ${precoBase.toFixed(2)})`; } }
        const opt = document.createElement('option'); opt.value = p.id; opt.dataset.preco_base = precoFinal; opt.dataset.nome = p.nome; opt.dataset.txtextra = txtExtra; opt.innerText = txtExtra ? `${p.nome} ${txtExtra}` : p.nome; selProd.appendChild(opt);
    });
}

async function carregarDetalhesProduto() {
    const catId = document.getElementById('sel_categoria').value; const prodId = document.getElementById('sel_produto').value; const box = document.getElementById('box_detalhes_dinamicos'); const selProd = document.getElementById('sel_produto');
    Array.from(selProd.options).forEach(o => { if (o.dataset.txtextra !== undefined) { o.innerText = o.dataset.txtextra ? `${o.dataset.nome} ${o.dataset.txtextra}` : o.dataset.nome; } });
    if (!prodId) { box.style.display = 'none'; box.innerHTML = ''; return; }
    box.style.display = 'block'; const optAtiva = selProd.options[selProd.selectedIndex]; let precoBaseProd = parseFloat(optAtiva.dataset.preco_base) || 0;
    box.innerHTML = '<div style="color:#aaa; text-align:center;">Carregando opções...</div>'; 
    const resp = await fetch(`/api/detalhes_produto/${catId}/${prodId}`); const dados = await resp.json(); let html = '';
    if (dados.variacoes && dados.variacoes.length > 0) {
        optAtiva.innerText = optAtiva.dataset.nome; 
        html += `<strong style="color:#ff9800; display:block; margin-bottom:5px;">Tamanho:</strong><select id="sel_variacao" class="input-std" style="width:100%;" onchange="atualizarInterfaceSabores()">`;
        dados.variacoes.forEach((v, index) => { const sel = index===0?'selected':''; let precoVarBase = parseFloat(v.preco) || 0; let precoVarPromo = calcularPrecoComDesconto(precoVarBase, catId, prodId); let precoExibicao = precoBaseProd + precoVarPromo; html += `<option value="${v.nome}" data-preco="${precoVarPromo}" data-max-sabores="${v.max_sabores||1}" ${sel}>${v.nome} (R$ ${precoExibicao.toFixed(2)})</option>`; }); html += `</select>`;
    }
    if (catId === 'pizza') html += `<div id="container_sabores_extras"></div>`;
    if (dados.adicionais) {
        dados.adicionais.forEach(grupo => {
            html += `<div class="mt-10 border-t border-dark pt-5"><strong class="text-success">${grupo.titulo||grupo.nome}</strong><br>`;
            if (grupo.tipo === 'texto' || grupo.tipo === 'numero' || grupo.tipo === 'quantidade') { html += `<input type="text" class="input-std input-dyn-text w-100" data-label="${grupo.titulo||grupo.nome}" placeholder="Digite...">`; } 
            else if(grupo.itens) {
                let type = (grupo.tipo === 'unica') ? 'radio' : 'checkbox'; let name = `adicional_${grupo.id}`; let minimo = parseInt(grupo.minimo_escolha) || 0; let nomesParaMarcar = [];
                if (minimo > 0 && grupo.itens.length > 0) { let itensOrdenados = [...grupo.itens].sort((a, b) => { return (parseFloat(a.preco_adicional) || 0) - (parseFloat(b.preco_adicional) || 0); }); for (let k = 0; k < minimo && k < itensOrdenados.length; k++) { nomesParaMarcar.push(itensOrdenados[k].nome); } }
                grupo.itens.forEach(i => { let p = parseFloat(i.preco_adicional) || 0; let txt = p > 0 ? ` (+R$ ${p.toFixed(2)})` : ''; let isChecked = nomesParaMarcar.includes(i.nome) ? 'checked' : ''; html += `<label class="d-inline-block mr-10 text-muted cursor-pointer mb-5"><input type="${type}" name="${name}" class="chk-adicional" value="${i.nome}" data-preco="${p}" ${isChecked}> ${i.nome}${txt}</label><br>`; });
            } html += `</div>`;
        });
    }
    box.innerHTML = html; if(catId === 'pizza') atualizarInterfaceSabores();
}

function atualizarInterfaceSabores() {
    const container = document.getElementById('container_sabores_extras'); if(!container) return;
    const selVar = document.getElementById('sel_variacao'); const max = parseInt(selVar.options[selVar.selectedIndex].dataset.maxSabores)||1;
    let html = '';
    if(max > 1) { html += `<div class="sabores-extras-box"><div style="color:#ff9800; font-size:0.9rem; margin-top:10px;">+ Sabores:</div>`; for(let i=2; i<=max; i++) { html += `<select class="input-std select-sabor-extra" style="margin-top:5px; width:100%;"><option value="">-- ${i}º Sabor --</option>${cacheSaboresPizza.map(p=>`<option value="${p.nome}">${p.nome}</option>`).join('')}</select>`; } html += `</div>`; }
    container.innerHTML = html;
}

function adicionarItemLista() {
    const selProd = document.getElementById('sel_produto'); if(!selProd.value) return alert("Selecione um produto!");
    let nomeFinal = selProd.options[selProd.selectedIndex].dataset.nome; let preco = parseFloat(selProd.options[selProd.selectedIndex].dataset.preco_base) || 0; let varNome = "";
    const selVar = document.getElementById('sel_variacao'); if(selVar) { preco += parseFloat(selVar.options[selVar.selectedIndex].dataset.preco) || 0; varNome = selVar.value; }
    const extras = document.querySelectorAll('.select-sabor-extra'); let sabores = []; extras.forEach(e => { if(e.value) sabores.push(e.value); });
    if(sabores.length>0) { nomeFinal += " / " + sabores.join(" / "); if(!nomeFinal.toLowerCase().includes("pizza")) nomeFinal = "Pizza " + nomeFinal; }
    let adds = []; let totalAdds = 0; document.querySelectorAll('.chk-adicional:checked').forEach(c => { totalAdds += parseFloat(c.dataset.preco); adds.push({nome: c.value}); });
    let obs = ""; document.querySelectorAll('.input-dyn-text').forEach(i => { if(i.value.trim()) obs += `${i.dataset.label}: ${i.value.trim()}. `; });
    const qtdInput = document.getElementById('manual_qtd_item'); const qtd = qtdInput ? (parseInt(qtdInput.value) || 1) : 1; const unitario = preco + totalAdds;

    listaItens.push({ categoria: document.getElementById('sel_categoria').value, produto_id: selProd.value, nome: nomeFinal, variacao_nome: varNome, quantidade: qtd, observacao: obs, total_unitario: unitario, total: unitario * qtd, lista_adicionais: adds });
    renderizarListaItens(); if(qtdInput) qtdInput.value = 1; document.querySelectorAll('.input-dyn-text').forEach(t => t.value = ''); if(selVar) selVar.selectedIndex = 0; document.querySelectorAll('.chk-adicional').forEach(c => c.checked = false); document.querySelectorAll('.select-sabor-extra').forEach(s => s.value = '');
}

function removerItem(i) { listaItens.splice(i,1); renderizarListaItens(); }
function renderizarListaItens() {
    const tb = document.getElementById('tabela_itens_manual'); tb.innerHTML = '';
    listaItens.forEach((it, i) => tb.innerHTML += `<tr><td>${it.quantidade}</td><td>${it.nome}</td><td>R$ ${it.total.toFixed(2)}</td><td><button type="button" class="btn-rem-item" onclick="removerItem(${i})">X</button></td></tr>`);
    calcularTotalManual();
    validarBotaoSalvar();
}

function calcularTotalManual() {
    const itens = listaItens.reduce((a,b)=>a+b.total,0); const ent = parseFloat(document.getElementById('val_entrega').value)||0; const ext = parseFloat(document.getElementById('val_extra').value)||0; const desc = parseFloat(document.getElementById('val_desconto').value)||0;
    const fin = itens + ent + ext - desc;
    document.getElementById('subtotal_manual').innerText = `R$ ${itens.toFixed(2)}`; document.getElementById('total_manual_display').innerText = fin.toFixed(2); document.getElementById('man_valor_final').value = fin;
    renderizarPagamentos(); atualizarInterfacePagamento();
}

async function salvarPedidoManual(e) {
    e.preventDefault();
    
    if (!isCaixaRapido && !clienteEncontrado) {
        alert("Para salvar um pedido normal, o cliente DEVE estar cadastrado.");
        return;
    }
    if(!listaItens.length) return alert("Adicione itens!");
    
    const payload = {
        is_caixa_rapido: isCaixaRapido,
        telefone: document.getElementById('man_telefone').value,
        nome: document.getElementById('man_nome').value,
        tipo_entrega: document.getElementById('man_entrega').value,
        origem: isCaixaRapido ? document.getElementById('man_origem').value : 'BalcaoWpp',
        endereco: { rua: document.getElementById('man_rua').value, numero: document.getElementById('man_numero').value, bairro: document.getElementById('man_bairro').value, ref: document.getElementById('man_ref').value },
        itens: listaItens, valor_total: document.getElementById('man_valor_final').value, pagamentos: listaPagamentos
    };
    const r = await fetch('/api/pedidos/manual', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    if(r.ok) window.location.reload(); 
    else {
        const err = await r.json();
        alert('Erro: ' + err.erro);
    }
}

function imprimirCupomPopup(id) { 
    const w = 400; const h = 600; 
    const left = (screen.width/2)-(w/2); 
    const top = (screen.height/2)-(h/2); 
    window.open(`/pedidos/cupom/${id}`, 'ImprimirCupom', `toolbar=no, location=no, directories=no, status=no, menubar=no, scrollbars=yes, resizable=no, copyhistory=no, width=${w}, height=${h}, top=${top}, left=${left}`); 
}

// Inicializador
window.onload = function() {
    let lastC = -1;
    setInterval(async()=>{
        const p = new URLSearchParams(window.location.search);
        // Só atualiza se não houver nenhum checkbox de seleção marcado (para não atrapalhar ações em massa)
        if(!document.querySelector('.card-select-box:checked')) {
            try { 
                const filtro = p.get('filtro')||'hoje';
                const tipo = p.get('tipo')||'todos';
                const status = p.get('status')||'todos';
                const dataFiltro = p.get('data_filtro')||'';
                
                const url = `/api/pedidos/check?filtro=${filtro}&tipo=${tipo}&status=${status}&data_filtro=${dataFiltro}`;
                const r = await fetch(url); 
                const d = await r.json(); 
                if(lastC !== -1 && d.count !== lastC) window.location.reload(); 
                lastC = d.count; 
            } catch(e){}
        }
    }, 10000); 
    
    const grid = document.getElementById('pedidos-grid');
    if(grid) {
        grid.addEventListener('change', e => { 
            if(e.target.classList.contains('status-select')) {
                fetch(`/api/status/${e.target.dataset.id}/${e.target.value}`, {method:'POST'}).then(()=>window.location.reload()); 
            }
        });
        grid.addEventListener('click', e => { 
            if(e.target.closest('.btn-del') && confirm('Excluir?')) {
                fetch(`/api/pedidos/${e.target.closest('.btn-del').dataset.del}`, {method:'DELETE'}).then(()=>window.location.reload()); 
            }
        });
    }

    const searchInput = document.getElementById('searchPedidos');
    if(searchInput) {
        searchInput.addEventListener('keyup', function(){ 
            const t = this.value.toLowerCase(); 
            for(let c of document.getElementsByClassName('pedido-card')) {
                c.style.display = c.innerText.toLowerCase().includes(t) ? 'flex' : 'none'; 
            }
        });
    }

    // Fechar modal de Novo Pedido ao clicar fora dele
    const modalManualOverlay = document.getElementById('modalManual');
    if(modalManualOverlay) {
        modalManualOverlay.addEventListener('click', function(event) {
            // Verifica se o clique foi exatamente no fundo escuro, e não na janela do modal
            if (event.target === modalManualOverlay) {
                modalManualOverlay.style.display = 'none';
            }
        });
    }
};