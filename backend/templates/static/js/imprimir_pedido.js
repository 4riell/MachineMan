// --- JAVASCRIPT: EDITAR / IMPRIMIR PEDIDO ---

let PEDIDO_ID, PEDIDO_TOTAL_DB, BAIRRO_DB;
let listaItens = [];
let regrasVariacoes = {};

let listaPagamentos = [];
let bairrosCache = null;
let produtosCache = [];
let promocoesGlobais = [];
let categoriasComVariacaoCache = {};
let isCaixaRapido = false;
let clienteEncontrado = true;
let cacheSaboresPizza = [];
let timerBusca;
let timerBuscaProd;

document.addEventListener("DOMContentLoaded", async () => {
    // Carrega os dados injetados pelo Jinja no HTML
    PEDIDO_ID = Number(JSON.parse(document.getElementById('data-pedido-id').textContent));
    PEDIDO_TOTAL_DB = parseFloat(JSON.parse(document.getElementById('data-pedido-total').textContent));
    BAIRRO_DB = JSON.parse(document.getElementById('data-pedido-bairro').textContent);
    
    listaItens = JSON.parse(document.getElementById('itens-iniciais').textContent || "[]");
    regrasVariacoes = JSON.parse(document.getElementById('regras-variacoes').textContent || "{}");
    
    await inicializarPagina();
});

async function inicializarPagina() {
    extrairPagamentosDoTexto();
    
    // 1. Carrega promocoes e bairros PRIMEIRO
    try { 
        const r = await fetch('/api/pedidos/promocoes'); 
        promocoesGlobais = await r.json(); 
    } catch(e) {}
    
    await carregarBairros();

    // 2. Seta o bairro do banco (se houver)
    const selBairro = document.getElementById('man_bairro');
    if(BAIRRO_DB && selBairro) {
        for(let i=0; i<selBairro.options.length; i++){
            if(selBairro.options[i].value.toLowerCase() === BAIRRO_DB.toLowerCase()){
                selBairro.selectedIndex = i;
                break;
            }
        }
    }

    // 3. Aplica o modo da tela
    toggleModoCaixa(true);
    renderizarListaItens();
    
    // 4. Força calcular a entrega para exibir a taxa correta assim que abre a edição
    autoCalcularEntrega();

    // 5. Ajusta possíveis diferenças (descontos/acréscimos)
    let somaItens = listaItens.reduce((acc, it) => acc + it.total, 0);
    let taxaEntrega = parseFloat(document.getElementById('val_entrega').value) || 0;
    let somaCalculada = somaItens + taxaEntrega;
    let diferenca = PEDIDO_TOTAL_DB - somaCalculada;

    if (Math.abs(diferenca) > 0.05) {
        if (diferenca > 0) document.getElementById('val_extra').value = diferenca.toFixed(2);
        else document.getElementById('val_desconto').value = Math.abs(diferenca).toFixed(2);
    }
    
    calcularTotalManual(false); 
    renderizarPagamentos();
    atualizarInterfacePagamento();
    validarBotaoSalvar();
}

function extrairPagamentosDoTexto() {
    const pgtStr = JSON.parse(document.getElementById('data-pedido-pgtstr').textContent);
    const detStr = JSON.parse(document.getElementById('data-pedido-detstr').textContent);
    
    listaPagamentos = [];

    // Definindo Origem no Select se houver tag
    const selOrigem = document.getElementById('man_origem');
    let originApp = "BalcaoWpp";
    let cleanDetStr = detStr;

    if(detStr.includes("[App:")) {
        const mApp = detStr.match(/\[App:\s*(.*?)\]/);
        if(mApp && selOrigem) {
            originApp = mApp[1].trim();
            cleanDetStr = detStr.replace(/\[App:\s*.*?\]/, '').trim();
            for(let i=0; i<selOrigem.options.length; i++) {
                if(selOrigem.options[i].value === originApp) {
                    selOrigem.selectedIndex = i;
                    break;
                }
            }
        }
    }
    
    const telInicial = document.getElementById('man_telefone').value.replace(/\D/g, '');
    if (telInicial === '00000000000' || telInicial.startsWith('999') || originApp !== "BalcaoWpp") {
        isCaixaRapido = true;
    }

    if (cleanDetStr) {
        const parts = cleanDetStr.includes('|') ? cleanDetStr.split('|') : [cleanDetStr];
        parts.forEach(p => {
            let str = p.trim();
            if(!str) return;

            let metodo = pgtStr;
            let valor = PEDIDO_TOTAL_DB;
            let detalhe = str;

            // Remove tag [App: ] antes do regex para nao sujar o detalhe no visual
            str = str.replace(/\[App:\s*.*?\]/, '').trim();

            const regexComplexo = /^(.*?):\s*R\$\s*([\d\.]+)\s*(?:\((.*)\))?$/;
            const match = str.match(regexComplexo);

            if (match) {
                metodo = match[1].trim(); 
                valor = parseFloat(match[2]); 
                detalhe = match[3] ? match[3].trim() : "";
            } else if (pgtStr.includes('+')) {
                metodo = pgtStr;
            } else {
                metodo = pgtStr;
                detalhe = str;
            }
            
            listaPagamentos.push({ metodo: metodo, valor: valor, detalhe: detalhe });
        });
    } else {
        if(pgtStr) {
            listaPagamentos.push({ metodo: pgtStr, valor: PEDIDO_TOTAL_DB, detalhe: "" });
        }
    }
}

function toggleModoCaixa(isInit = false) {
    if(!isInit) {
        isCaixaRapido = !isCaixaRapido;
        limparCamposCliente();
        
        const manTel = document.getElementById('man_telefone');
        if(manTel) {
            manTel.value = '';
            manTel.readOnly = false; 
            manTel.placeholder = "📱 Digite o telefone para buscar...";
        }
        
        const statusBusca = document.getElementById('status_busca');
        if(statusBusca) statusBusca.innerText = '';
        
        clienteEncontrado = false; 
    }

    const btn = document.getElementById('btn_modo_caixa');
    const boxOri = document.getElementById('box_origem');
    const boxCli = document.getElementById('box_cliente_normal');
    const tituloModal = document.getElementById('titulo_modal_manual');

    // Garante que o título NUNCA mude, pois estamos apenas editando
    if(tituloModal) tituloModal.innerText = `📝 Editando Pedido #${PEDIDO_ID}`;

    if (isCaixaRapido) {
        if(btn) btn.innerHTML = "👤 Voltar para Modo Normal";
        if(btn) btn.style.background = "#2196f3";
        
        if(boxOri) boxOri.style.display = 'block';
        if(boxCli) boxCli.style.display = 'none'; 
        
        const manNome = document.getElementById('man_nome');
        if(manNome) {
            if(!isInit) manNome.value = "Caixa Rápido"; 
        }
        
        if(!isInit && document.getElementById('man_entrega') && document.getElementById('man_entrega').value !== 'Mesa') {
            document.getElementById('man_entrega').value = 'Retirada';
        }
        filtrarMetodosPagamento(true);

        // Destrava os campos de endereço
        ['man_rua', 'man_numero', 'man_ref'].forEach(id => {
            const el = document.getElementById(id);
            if(el) el.readOnly = false;
        });
        const manBairro = document.getElementById('man_bairro');
        if(manBairro) manBairro.disabled = false;

    } else {
        if(btn) btn.innerHTML = "⚡ Transformar em Caixa Rápido";
        if(btn) btn.style.background = "#ff9800";
        
        if(boxOri) boxOri.style.display = 'none';
        if(boxCli) boxCli.style.display = 'block'; 
        
        const manNome = document.getElementById('man_nome');
        if(manNome) {
            manNome.readOnly = true;
            if(!isInit) manNome.value = "";
        }
        
        if(!isInit && document.getElementById('man_entrega') && document.getElementById('man_entrega').value !== 'Mesa') {
            document.getElementById('man_entrega').value = 'Entrega';
        }
        filtrarMetodosPagamento(false);

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

function calcularPrecoComDesconto(precoBase, categoriaId, produtoId) {
    let pBase = parseFloat(precoBase) || 0;
    if (!promocoesGlobais || promocoesGlobais.length === 0) return pBase;
    let promo = promocoesGlobais.find(p => String(p.categoria).trim().toLowerCase() === String(categoriaId).trim().toLowerCase() && String(p.produto_id).trim() === String(produtoId).trim());
    if (!promo) promo = promocoesGlobais.find(p => String(p.categoria).trim().toLowerCase() === String(categoriaId).trim().toLowerCase() && String(p.produto_id).trim() === "0");
    if(!promo) return pBase;
    let desc = String(promo.desconto).replace(',', '.').trim();
    let val = Math.abs(parseFloat(desc.replace(/[^0-9.-]/g, '')));
    if(desc.includes('%')) return Math.max(0, pBase * (1 - (val / 100)));
    else return Math.max(0, pBase - val);
}

async function verificarSeCategoriaTemVariacao(catId, prodId) {
    if(categoriasComVariacaoCache[catId] !== undefined) return categoriasComVariacaoCache[catId];
    try { 
        const res = await fetch(`/api/detalhes_produto/${catId}/${prodId}`); 
        const data = await res.json(); 
        const temVariacao = (data.variacoes && data.variacoes.length > 0); 
        categoriasComVariacaoCache[catId] = temVariacao; 
        return temVariacao; 
    } catch(e) { return false; }
}

async function carregarBairros() {
    const selBairro = document.getElementById('man_bairro');
    try {
        const resp = await fetch('/api/bairros_lookup');
        bairrosCache = await resp.json();
        selBairro.innerHTML = '<option value="">Selecione o Bairro...</option>';
        if(bairrosCache.bairros) {
            bairrosCache.bairros.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b.nome;
                opt.dataset.taxa = b.taxa !== null ? b.taxa : -1;
                // Mantém o bairro do pedido selecionado
                if (BAIRRO_DB && b.nome.toLowerCase() === BAIRRO_DB.toLowerCase()) opt.selected = true;
                let txtTaxa = (b.taxa !== null) ? `R$ ${parseFloat(b.taxa).toFixed(2)}` : "Taxa Padrão";
                opt.innerText = `${b.nome} (${txtTaxa})`;
                selBairro.appendChild(opt);
            });
        }
        autoCalcularEntrega(); // Garante que o valor total inicial reconheça a entrega
    } catch(e) { console.error("Erro nos bairros:", e); }
}

function autoCalcularEntrega() {
    const tipo = document.getElementById('man_entrega').value;
    if (tipo !== 'Entrega' || !bairrosCache) return;
    
    const selBairro = document.getElementById('man_bairro');
    const optSelected = selBairro.options[selBairro.selectedIndex];
    
    let taxaFinal = parseFloat(bairrosCache.taxa_padrao || 0);

    if (optSelected && optSelected.value) {
        let taxaBairro = parseFloat(optSelected.dataset.taxa);
        if (taxaBairro >= 0) taxaFinal = taxaBairro;
    }
    
    document.getElementById('val_entrega').value = taxaFinal.toFixed(2);
    const display = document.getElementById('display_entrega');
    if (display) display.innerText = `R$ ${taxaFinal.toFixed(2)}`;
    calcularTotalManual(true);
}

function toggleEndereco() {
    const tipo = document.getElementById('man_entrega').value;
    const isEntrega = (tipo === 'Entrega');
    
    const boxEnd = document.getElementById('box_endereco');
    const boxRua = document.getElementById('box_endereco_rua');

    if (isEntrega) {
        boxEnd.classList.remove('hide-addr'); boxEnd.classList.add('show-addr');
        if(boxRua) { boxRua.classList.remove('hide-addr'); boxRua.classList.add('flex-box'); }
    } else {
        boxEnd.classList.remove('show-addr'); boxEnd.classList.add('hide-addr');
    }
    
    const rowTaxa = document.getElementById('row_taxa_entrega');
    if(rowTaxa) rowTaxa.style.display = isEntrega ? 'flex' : 'none';
    
    if(!isEntrega) {
        document.getElementById('val_entrega').value = "0.00";
        const display = document.getElementById('display_entrega');
        if (display) display.innerText = "R$ 0.00";
        calcularTotalManual(true);
    } else {
        autoCalcularEntrega();
    }
}

function limparCamposCliente() {
    const manNome = document.getElementById('man_nome');
    if(manNome) manNome.value = '';
    const manCpf = document.getElementById('man_cpf');
    if(manCpf) manCpf.value = '';
    if(!isCaixaRapido && manNome) manNome.readOnly = true;
    
    document.getElementById('man_rua').value = '';
    document.getElementById('man_numero').value = '';
    document.getElementById('man_ref').value = '';
    document.getElementById('man_bairro').value = '';
    document.getElementById('val_entrega').value = "0.00";
    const display = document.getElementById('display_entrega');
    if (display) display.innerText = "R$ 0.00";
    calcularTotalManual(true);
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
        const resp = await fetch(`/api/cliente_lookup/${encodeURIComponent(val)}`); 
        const data = await resp.json();
        filtrarMetodosPagamento(false);
        if(data.encontrado) {
            clienteEncontrado = true;
            document.getElementById('status_busca').innerText = '✅ Cliente encontrado!'; 
            document.getElementById('status_busca').style.color = 'var(--success)';
            document.getElementById('man_nome').value = data.dados.nome||''; 
            document.getElementById('man_nome').readOnly = true;
            const manCpf = document.getElementById('man_cpf');
            if(manCpf) manCpf.value = data.dados.cpf||'';
            document.getElementById('man_rua').value = data.dados.rua||''; 
            document.getElementById('man_numero').value = data.dados.numero_casa||''; 
            document.getElementById('man_ref').value = data.dados.ponto_referencia||'';
            if(data.dados.bairro) {
                const sel = document.getElementById('man_bairro');
                for(let i=0; i<sel.options.length; i++){ 
                    if(sel.options[i].value.toLowerCase() === data.dados.bairro.toLowerCase()){ 
                        sel.selectedIndex = i; 
                        break; 
                    } 
                }
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

function filtrarMetodosPagamento(isAvulso) {
    const sel = document.getElementById('sel_pgt_metodo');
    if (!sel) return;
    
    Array.from(sel.options).forEach(opt => {
        if(opt.value === "") return;
        
        // Verifica se é True (string ou bool) ou 1
        const isWpp = String(opt.dataset.wpp).toLowerCase() === "true" || opt.dataset.wpp === "1";
        
        // No modo edição ou Caixa Rápido (isAvulso), mostra tudo.
        if (isAvulso || isWpp) {
            opt.hidden = false;
            opt.disabled = false;
            opt.style.display = "block";
        } else {
            opt.hidden = true;
            opt.disabled = true;
            opt.style.display = "none";
        }
    });
    
    // Se o método selecionado sumiu pelo filtro, limpa a seleção
    if (sel.selectedOptions[0] && sel.selectedOptions[0].style.display === "none") {
        sel.value = "";
    }
    atualizarInterfacePagamento();
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
    
    // BLOQUEIO: Se o pagamento for maior que o necessário para fechar a conta
    if ((jaPago + valor).toFixed(2) > (totalFinal + 0.05).toFixed(2)) { 
        alert("O valor pago excede o total restante do pedido! Verifique os valores."); 
        return; 
    }
    
    listaPagamentos.push({ metodo: metodo, valor: valor, detalhe: detalhe });
    renderizarPagamentos(); document.getElementById('input_pgt_detalhe').value = ''; atualizarInterfacePagamento();
    validarBotaoSalvar();
}

function removerPagamento(index) { 
    listaPagamentos.splice(index, 1); 
    renderizarPagamentos(); 
    atualizarInterfacePagamento(); 
    validarBotaoSalvar(); 
}

function renderizarPagamentos() {
    const tbody = document.getElementById('lista_pagamentos_tabela'); 
    tbody.innerHTML = ''; 
    let totalPago = 0;
    
    listaPagamentos.forEach((pg, index) => {
        totalPago += pg.valor; 
        let displayDet = pg.detalhe || '';
        if(pg.metodo.toLowerCase().includes('dinheiro') && displayDet.toLowerCase().includes('troco para')) {
            let valEntregue = parseFloat(displayDet.replace(/[^0-9.]/g, ''));
            if(!isNaN(valEntregue) && valEntregue > pg.valor) {
                let troco = valEntregue - pg.valor;
                displayDet += `<br><span style="color:var(--success); font-weight:bold; font-size:0.85rem;">↳ Troco: R$ ${troco.toFixed(2)}</span>`;
            }
        }
        tbody.innerHTML += `<tr><td>${pg.metodo}</td><td style="color:#ccc;">${displayDet || '-'}</td><td>R$ ${pg.valor.toFixed(2)}</td><td style="text-align:right;"><button type="button" class="btn-rem" onclick="removerPagamento(${index})">X</button></td></tr>`;
    });
    
    document.getElementById('span_total_pago').innerText = totalPago.toFixed(2);
    const totalFinal = parseFloat(document.getElementById('man_valor_final').value) || 0;
    
    // Calcula a diferença real (pode ser negativa se pagou a mais antes de mudar os itens)
    const restante = totalFinal - totalPago; 
    
    const spanRestante = document.getElementById('span_total_restante');
    const lblStatusPgt = document.getElementById('lbl_status_pgt'); // Seleciona o Label "Restante:"
    
    if (Math.abs(restante) < 0.05 && totalFinal > 0) {
        // Conta fechou perfeitamente
        spanRestante.style.color = 'var(--success)'; 
        spanRestante.innerText = "OK"; 
        if (lblStatusPgt) lblStatusPgt.style.color = 'var(--success)';
    } else if (restante < -0.05) {
        // Pagou MAIS do que o pedido vale (ex: removeu itens depois de pagar)
        spanRestante.style.color = 'var(--warning)'; 
        spanRestante.innerText = `Pago a maior (R$ ${Math.abs(restante).toFixed(2)})`; 
        if (lblStatusPgt) lblStatusPgt.style.color = 'var(--warning)';
    } else {
        // Faltando pagar
        spanRestante.style.color = 'var(--danger)'; 
        spanRestante.innerText = `R$ ${restante.toFixed(2)}`;
        if (lblStatusPgt) lblStatusPgt.style.color = 'var(--danger)';
    }
}

function validarBotaoSalvar() {
    const btnSalvar = document.getElementById('btn_salvar');
    if(!btnSalvar) return;
    
    let totalFinal = parseFloat(document.getElementById('man_valor_final').value) || 0;
    let jaPago = listaPagamentos.reduce((acc, p) => acc + p.valor, 0);
    
    // Valida se o pagamento bate exatamente com o total (margem de erro de 5 centavos para arredondamentos)
    let pagamentoOk = Math.abs(totalFinal - jaPago) < 0.05 && totalFinal > 0;
    let clienteOk = isCaixaRapido || clienteEncontrado;

    // Só libera se Cliente e Pagamento estiverem corretos, e tiver itens
    if (pagamentoOk && clienteOk && listaItens.length > 0) {
        btnSalvar.disabled = false; btnSalvar.style.opacity = 1;
    } else {
        btnSalvar.disabled = true; btnSalvar.style.opacity = 0.5;
    }
}

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
                resBox.innerHTML = '<div style="padding:10px; color:#aaa; font-size:0.9rem; text-align:center;">Nada encontrado.</div>';
            } else {
                for (let p of data) {
                    let pid = p.produto_id || p.id;
                    let temVariacao = await verificarSeCategoriaTemVariacao(p.categoria_id, pid);
                    let precoBase = parseFloat(p.preco) || 0;
                    let precoFinal = calcularPrecoComDesconto(precoBase, p.categoria_id, pid);
                    
                    let displayPreco = "";
                    if (!temVariacao && (precoBase > 0 || precoFinal > 0)) {
                        displayPreco = precoFinal !== precoBase ? `- <span style="color:#ff9800; font-weight:bold;">R$ ${precoFinal.toFixed(2)}</span> <span style="font-size:0.7rem;color:#4CAF50;">(Promo)</span>` : `- R$ ${precoBase.toFixed(2)}`;
                    }

                    const div = document.createElement('div');
                    div.style.padding = '10px'; div.style.borderBottom = '1px solid #444'; div.style.cursor = 'pointer';
                    div.onmouseover = () => div.style.background = '#333'; div.onmouseout = () => div.style.background = 'transparent';
                    div.innerHTML = `<strong style="color:#fff;">${p.nome}</strong> <br><span style="font-size:0.8rem; color:#aaa;">${p.emoji || ''} ${p.categoria_nome} ${displayPreco}</span>`;
                    div.onclick = () => selecionarProdutoDaBusca(p.categoria_id, pid);
                    resBox.appendChild(div);
                }
            }
            resBox.style.display = 'block';
        } catch(e) { console.error("Erro na busca", e); }
    }, 400);
}

async function selecionarProdutoDaBusca(catId, prodId) {
    document.getElementById('resultado_busca').style.display = 'none'; document.getElementById('busca_global').value = '';
    document.getElementById('sel_categoria').value = catId; await carregarProdutosDaCategoria();
    document.getElementById('sel_produto').value = prodId; carregarDetalhesProduto();
}

async function carregarProdutosDaCategoria() {
    const catId = document.getElementById('sel_categoria').value; 
    const selProd = document.getElementById('sel_produto');
    const boxDyn = document.getElementById('box_detalhes_dinamicos');
    
    selProd.innerHTML = '<option value="">Carregando...</option>';
    boxDyn.innerHTML = ''; boxDyn.style.display = 'none';
    const qtdInput = document.getElementById('manual_qtd_item'); if(qtdInput) qtdInput.value = 1;
    if(!catId) return; 
    
    produtosCache = [];
    try {
        const resp = await fetch(`/api/produtos_categoria/${catId}`);
        produtosCache = await resp.json();
        
        if(catId === 'pizza') cacheSaboresPizza = produtosCache;
        
        selProd.innerHTML = '<option value="">Selecione o Produto/Sabor...</option>';
        
        let temVariacaoDeTamanho = false; 
        if(produtosCache.length > 0) temVariacaoDeTamanho = await verificarSeCategoriaTemVariacao(catId, produtosCache[0].id);

        produtosCache.forEach(p => {
            let precoBase = parseFloat(p.preco) || 0; 
            let precoFinal = calcularPrecoComDesconto(precoBase, catId, p.id); 
            let txtExtra = "";
            if (!temVariacaoDeTamanho) { 
                if (precoBase > 0 || precoFinal > 0) { 
                    txtExtra = precoFinal !== precoBase ? `(Promo: R$ ${precoFinal.toFixed(2)})` : `(R$ ${precoBase.toFixed(2)})`; 
                } 
            }
            const opt = document.createElement('option'); 
            opt.value = p.id; 
            opt.dataset.preco_base = precoFinal; 
            opt.dataset.nome = p.nome; 
            opt.dataset.txtextra = txtExtra; 
            opt.innerText = txtExtra ? `${p.nome} ${txtExtra}` : p.nome; 
            selProd.appendChild(opt);
        });
    } catch(e) {}
}

async function carregarDetalhesProduto() {
    const catId = document.getElementById('sel_categoria').value; 
    const prodId = document.getElementById('sel_produto').value; 
    const box = document.getElementById('box_detalhes_dinamicos'); 
    const selProd = document.getElementById('sel_produto');
    
    Array.from(selProd.options).forEach(o => { 
        if (o.dataset.txtextra !== undefined) { 
            o.innerText = o.dataset.txtextra ? `${o.dataset.nome} ${o.dataset.txtextra}` : o.dataset.nome; 
        } 
    });
    
    if (!prodId) { box.style.display = 'none'; box.innerHTML = ''; return; }
    
    box.style.display = 'block'; 
    const optAtiva = selProd.options[selProd.selectedIndex]; 
    let precoBaseProd = parseFloat(optAtiva.dataset.preco_base) || 0;
    box.innerHTML = '<div style="color:#aaa; text-align:center;">Carregando opções...</div>'; 
    
    const resp = await fetch(`/api/detalhes_produto/${catId}/${prodId}`); 
    const dados = await resp.json(); 
    let html = '';
    
    if (dados.variacoes && dados.variacoes.length > 0) {
        optAtiva.innerText = optAtiva.dataset.nome; 
        html += `<strong style="color:#ff9800; display:block; margin-bottom:5px;">Tamanho:</strong><select id="sel_variacao" class="input-std" style="width:100%;" onchange="atualizarInterfaceSabores()">`;
        dados.variacoes.forEach((v, index) => { 
            const sel = index===0?'selected':''; 
            let precoVarBase = parseFloat(v.preco) || 0; 
            let precoVarPromo = calcularPrecoComDesconto(precoVarBase, catId, prodId); 
            let precoExibicao = precoBaseProd + precoVarPromo; 
            html += `<option value="${v.nome}" data-preco="${precoVarPromo}" data-max-sabores="${v.max_sabores||1}" ${sel}>${v.nome} (R$ ${precoExibicao.toFixed(2)})</option>`; 
        }); 
        html += `</select>`;
    }
    
    if (catId === 'pizza') html += `<div id="container_sabores_extras"></div>`;
    
    if (dados.adicionais) {
        dados.adicionais.forEach(grupo => {
            html += `<div style="border-top:1px dotted #444; margin-top:10px; padding-top:5px;"><strong style="color:#4CAF50;">${grupo.titulo||grupo.nome}</strong><br>`;
            if (grupo.tipo === 'texto' || grupo.tipo === 'numero' || grupo.tipo === 'quantidade') { 
                html += `<input type="text" class="input-std input-dyn-text" data-label="${grupo.titulo||grupo.nome}" placeholder="Digite..." style="width:100%;">`; 
            } 
            else if(grupo.itens) {
                let type = (grupo.tipo === 'unica') ? 'radio' : 'checkbox'; 
                let name = `adicional_${grupo.id}`; 
                let minimo = parseInt(grupo.minimo_escolha) || 0; 
                let nomesParaMarcar = [];
                
                if (minimo > 0 && grupo.itens.length > 0) { 
                    let itensOrdenados = [...grupo.itens].sort((a, b) => { return (parseFloat(a.preco_adicional) || 0) - (parseFloat(b.preco_adicional) || 0); }); 
                    for (let k = 0; k < minimo && k < itensOrdenados.length; k++) { 
                        nomesParaMarcar.push(itensOrdenados[k].nome); 
                    } 
                }
                
                grupo.itens.forEach(i => { 
                    let p = parseFloat(i.preco_adicional) || 0; 
                    let txt = p > 0 ? ` (+R$ ${p.toFixed(2)})` : ''; 
                    let isChecked = nomesParaMarcar.includes(i.nome) ? 'checked' : ''; 
                    html += `<label style="display:inline-block; margin-right:10px; color:#ccc; cursor:pointer; margin-bottom:5px;"><input type="${type}" name="${name}" class="chk-adicional" value="${i.nome}" data-preco="${p}" ${isChecked}> ${i.nome}${txt}</label><br>`; 
                });
            } 
            html += `</div>`;
        });
    }
    
    if(!html.includes('input-dyn-text') && !html.includes('dyn_obs')) {
         html += `<div style="margin-top:10px;"><label class="label-dinamico">Obs:</label><input type="text" id="dyn_obs" class="input-std input-dyn-text" data-label="Obs" style="width:100%;" /></div>`;
    }
    
    box.innerHTML = html; 
    if(catId === 'pizza') atualizarInterfaceSabores();
}

function atualizarInterfaceSabores() {
    const container = document.getElementById('container_sabores_extras'); if(!container) return;
    const selVar = document.getElementById('sel_variacao'); 
    if(!selVar) return;
    const max = parseInt(selVar.options[selVar.selectedIndex].dataset.maxSabores)||1;
    let html = '';
    if(max > 1) { 
        html += `<div class="sabores-extras-box"><div style="color:#ff9800; font-size:0.9rem; margin-top:10px;">+ Sabores:</div>`; 
        for(let i=2; i<=max; i++) { 
            html += `<select class="input-std select-sabor-extra" style="margin-top:5px; width:100%;"><option value="">-- ${i}º Sabor --</option>${cacheSaboresPizza.map(p=>`<option value="${p.nome}">${p.nome}</option>`).join('')}</select>`; 
        } 
        html += `</div>`; 
    }
    container.innerHTML = html;
}

function adicionarItemLista() {
    const selProd = document.getElementById('sel_produto'); if(!selProd.value) return alert("Selecione um produto!");
    let nomeFinal = selProd.options[selProd.selectedIndex].dataset.nome; 
    let preco = parseFloat(selProd.options[selProd.selectedIndex].dataset.preco_base) || 0; 
    let varNome = "";
    
    const selVar = document.getElementById('sel_variacao'); 
    if(selVar) { preco += parseFloat(selVar.options[selVar.selectedIndex].dataset.preco) || 0; varNome = selVar.value; }
    
    const extras = document.querySelectorAll('.select-sabor-extra'); let sabores = []; extras.forEach(e => { if(e.value) sabores.push(e.value); });
    if(sabores.length>0) { nomeFinal += " / " + sabores.join(" / "); if(!nomeFinal.toLowerCase().includes("pizza")) nomeFinal = "Pizza " + nomeFinal; }
    
    let adds = []; let totalAdds = 0; let nomesAdds = [];
    document.querySelectorAll('.chk-adicional:checked').forEach(c => { 
        totalAdds += parseFloat(c.dataset.preco); 
        adds.push({nome: c.value}); 
        nomesAdds.push(c.value);
    });

    let obs = ""; 
    document.querySelectorAll('.input-dyn-text').forEach(i => { if(i.value.trim()) obs += `${i.dataset.label}: ${i.value.trim()}. `; });

    const dynObsManual = document.getElementById('dyn_obs');
    if (dynObsManual && !dynObsManual.classList.contains('input-dyn-text') && dynObsManual.value.trim()) {
        obs += `Obs: ${dynObsManual.value.trim()}`;
    }

    const qtdInput = document.getElementById('manual_qtd_item'); const qtd = qtdInput ? (parseInt(qtdInput.value) || 1) : 1; const unitario = preco + totalAdds;

    let detalhesStr = nomesAdds.length ? "➕ " + nomesAdds.join(", ") : "";
    if(obs) detalhesStr += (detalhesStr ? " | " : "") + "📝 " + obs;

    listaItens.push({ categoria: document.getElementById('sel_categoria').value, produto_id: selProd.value, nome: nomeFinal, variacao_nome: varNome, quantidade: qtd, total_unitario: unitario, total: unitario * qtd, detalhes: detalhesStr, observacao: obs, lista_adicionais: adds });
    
    renderizarListaItens(); 
    
    if(qtdInput) qtdInput.value = 1; 
    document.querySelectorAll('.input-dyn-text').forEach(t => t.value = ''); 
    if(dynObsManual) dynObsManual.value = '';
    if(selVar) selVar.selectedIndex = 0; 
    document.querySelectorAll('.chk-adicional').forEach(c => c.checked = false); 
    document.querySelectorAll('.select-sabor-extra').forEach(s => s.value = '');
}

function removerItem(i) { 
    listaItens.splice(i,1); 
    renderizarListaItens(); 
}

function renderizarListaItens() {
    const tb = document.getElementById('tabela_itens');
    tb.innerHTML = '';
    listaItens.forEach((it, idx) => {
        let displayNome = it.nome; 
        let temTamanho = it.variacao_nome && displayNome.includes(it.variacao_nome);
        if (!temTamanho && it.variacao_nome) displayNome = `(${it.variacao_nome}) - ${displayNome}`;
        if ((it.categoria === 'pizza' || it.categoria === 'pizzas') && !displayNome.toLowerCase().includes('pizza')) displayNome = "Pizza " + displayNome;
        
        let addTxt = it.lista_adicionais && it.lista_adicionais.length ? `<br><small style="color:#888;">+ ${it.lista_adicionais.map(x=>x.nome).join(', ')}</small>` : '';
        let obsTxt = it.observacao ? `<br><small style="color:var(--warning);">${it.observacao}</small>` : '';
        
        tb.innerHTML += `<tr><td>${it.quantidade}x</td><td>${displayNome} ${addTxt} ${obsTxt}</td><td>R$ ${it.total.toFixed(2)}</td><td style="text-align:right;"><button type="button" class="btn-rem" onclick="removerItem(${idx})">X</button></td></tr>`;
    });
    calcularTotalManual(true);
}

function calcularTotalManual(forceUpdate = false) {
    let soma = listaItens.reduce((acc, it) => acc + it.total, 0);
    let ent = parseFloat(document.getElementById('val_entrega').value) || 0;
    let ext = parseFloat(document.getElementById('val_extra').value) || 0;
    let desc = parseFloat(document.getElementById('val_desconto').value) || 0;
    
    let final = soma + ent + ext - desc;
    
    document.getElementById('subtotal_manual').innerText = `R$ ${soma.toFixed(2)}`;
    document.getElementById('total_manual_display').innerText = `R$ ${final.toFixed(2)}`;
    document.getElementById('man_valor_final').value = final.toFixed(2);
    
    // ESSA CHAMADA É O QUE CORRIGE O VALOR RESTANTE:
    renderizarPagamentos(); 
    validarBotaoSalvar();
}

async function salvarAlteracoes(e) {
    e.preventDefault();
    
    if (!isCaixaRapido && !clienteEncontrado) {
        alert("Para salvar um pedido normal, o cliente DEVE estar cadastrado.");
        return;
    }
    if(listaItens.length === 0) return alert("O pedido precisa de itens.");
    
    const payload = {
        is_caixa_rapido: isCaixaRapido,
        telefone: document.getElementById('man_telefone').value,
        nome: document.getElementById('man_nome').value,
        tipo_entrega: document.getElementById('man_entrega').value,
        endereco: {
            rua: document.getElementById('man_rua').value,
            numero: document.getElementById('man_numero').value,
            bairro: document.getElementById('man_bairro').value,
            ref: document.getElementById('man_ref').value
        },
        itens: listaItens,
        pagamentos: listaPagamentos,
        valor_total: document.getElementById('man_valor_final').value
    };

    const selOrigem = document.getElementById('man_origem');
    if(isCaixaRapido && selOrigem && selOrigem.value !== 'BalcaoWpp') {
        payload.origem = selOrigem.value;
    } else {
        payload.origem = 'BalcaoWpp';
    }

    try {
        const resp = await fetch(`/api/pedidos/${PEDIDO_ID}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if(resp.ok) {
            alert("Pedido Atualizado!");
            window.location.reload();
        } else alert("Erro ao salvar.");
    } catch(e) { alert("Erro de conexão"); }
}

function imprimirCupom() {
    const w = 400; const h = 600; const left = (screen.width/2)-(w/2); const top = (screen.height/2)-(h/2);
    window.open(
        `/pedidos/cupom/${PEDIDO_ID}`, 
        'ImprimirCupom', 
        `toolbar=no, location=no, directories=no, status=no, menubar=no, scrollbars=yes, resizable=no, copyhistory=no, width=${w}, height=${h}, top=${top}, left=${left}`
    );
}