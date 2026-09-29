let mesaAtualId = null;
let mesaAtualNome = "";
let itensMesaCache = [];
let totalMesaAtual = 0;
let cacheSaboresPizza = [];
let pagamentosLancados = [];

let promocoesGlobais = [];
let categoriasComVariacaoCache = {};

window.addEventListener('DOMContentLoaded', () => {
    setInterval(carregarMesas, 15000);
    carregarMesas();
});

async function carregarPromocoesDoBanco() {
    try {
        const res = await fetch('/api/mesas/promocoes');
        promocoesGlobais = await res.json();
    } catch(e) {}
}

function calcularPrecoComDesconto(precoBase, categoriaId, produtoId) {
    let pBase = parseFloat(precoBase) || 0;
    if (!promocoesGlobais || promocoesGlobais.length === 0) return pBase;
    
    let promo = promocoesGlobais.find(p => String(p.categoria).trim().toLowerCase() === String(categoriaId).trim().toLowerCase() && String(p.produto_id).trim() === String(produtoId).trim());
    if (!promo) promo = promocoesGlobais.find(p => String(p.categoria).trim().toLowerCase() === String(categoriaId).trim().toLowerCase() && String(p.produto_id).trim() === "0");
    if(!promo) return pBase;
    
    let desc = String(promo.desconto).replace(',', '.').trim();
    let val = Math.abs(parseFloat(desc.replace(/[^0-9.-]/g, '')));
    
    if(desc.includes('%')) { return Math.max(0, pBase * (1 - (val / 100))); } 
    else { return Math.max(0, pBase - val); }
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

let timerBusca;
async function buscarProdutoGlobal() {
    clearTimeout(timerBusca);
    const q = document.getElementById('busca_global').value.trim();
    const resBox = document.getElementById('resultado_busca');
    if(q.length < 2) { resBox.style.display = 'none'; return; }
    
    timerBusca = setTimeout(async () => {
        await carregarPromocoesDoBanco(); 
        const res = await fetch(`/api/mesas/buscar_produtos?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        
        resBox.innerHTML = '';
        if(data.length === 0) {
            resBox.innerHTML = '<div class="p-10 text-muted text-center text-sm">Nenhum produto encontrado.</div>';
        } else {
            for (let p of data) {
                let temVariacao = await verificarSeCategoriaTemVariacao(p.categoria_id, p.produto_id);
                let precoBase = parseFloat(p.preco) || 0;
                let precoFinal = calcularPrecoComDesconto(precoBase, p.categoria_id, p.produto_id);
                
                let displayPreco = "";
                if (!temVariacao && (precoBase > 0 || precoFinal > 0)) {
                    displayPreco = precoFinal !== precoBase ? `- <span class="text-warning font-bold">R$ ${precoFinal.toFixed(2)}</span> <span class="text-xs text-success">(Promo)</span>` : `- R$ ${precoBase.toFixed(2)}`;
                }

                const div = document.createElement('div');
                div.className = 'search-item-result';
                div.innerHTML = `<strong class="text-white">${p.nome}</strong> <br><span class="text-muted text-xs">${p.emoji || ''} ${p.categoria_nome} ${displayPreco}</span>`;
                div.onclick = () => selecionarProdutoDaBusca(p.categoria_id, p.produto_id);
                resBox.appendChild(div);
            }
        }
        resBox.style.display = 'block';
    }, 400);
}

async function selecionarProdutoDaBusca(catId, prodId) {
    document.getElementById('resultado_busca').style.display = 'none';
    document.getElementById('busca_global').value = '';
    document.getElementById('sel_categoria').value = catId;
    await carregarProdutosDaCategoria();
    document.getElementById('sel_produto').value = prodId;
    produtoPrincipalSelecionado();
}

function mudarDivisorSimples(delta) {
    let input = document.getElementById('pg_divisor');
    let val = parseInt(input.value) || 1;
    val += delta;
    if(val < 1) val = 1;
    input.value = val;
    aplicarDivisao();
}

function aplicarDivisao() {
    let pessoas = parseInt(document.getElementById('pg_divisor').value) || 1;
    let restante = getRestanteMesa();
    let valorDividido = (restante / pessoas).toFixed(2);
    
    document.getElementById('pg_valor').value = valorDividido;
    calcularTrocoVisual('simples');
}

function togglePgtoDetalhes(modo) {
    let sel, inputDet;
    if (modo === 'simples') {
        sel = document.getElementById('pg_metodo');
        inputDet = document.getElementById('pg_detalhe');
    } else {
        sel = document.getElementById('pg_metodo_pessoa');
        inputDet = document.getElementById('pg_detalhe_pessoa');
    }
    
    const opt = sel.options[sel.selectedIndex];
    if(!opt || !opt.value) { inputDet.style.display = 'none'; return; }

    const pede = opt.dataset.pede === "1";
    const perg = opt.dataset.pergunta || "Detalhe...";

    if (pede) {
        inputDet.style.display = 'block';
        inputDet.placeholder = perg;
    } else {
        inputDet.style.display = 'none';
        inputDet.value = '';
    }
    calcularTrocoVisual(modo);
}

let sepItensMesa = [];
let sepItensPessoa = [];

function voltarPagamentoSimples() {
    sepItensMesa = [];
    sepItensPessoa = [];
    
    const areaSeparado = document.getElementById('area_pgto_separado');
    const areaSimples = document.getElementById('area_pgto_simples');
    
    if (areaSeparado) {
        areaSeparado.style.display = 'none';
        areaSeparado.style.pointerEvents = 'auto'; 
    }
    if (areaSimples) {
        areaSimples.style.display = 'block';
        areaSimples.style.pointerEvents = 'auto'; 
    }
    
    const btnSeparador = document.getElementById('btn_abrir_separador');
    if (btnSeparador) btnSeparador.style.display = 'block';
    
    if(window.innerWidth > 768) {
        document.getElementById('modalPgContent').className = 'modal-pagamento-content w-500';
    }
}

function iniciarSeparacaoComandas(event) {
    if(event && event.target) event.target.blur();

    // Se o Reset for chamado, limpamos os pagamentos lançados
    pagamentosLancados = []; 
    
    document.getElementById('area_pgto_simples').style.display = 'none';
    document.getElementById('area_pgto_separado').style.display = 'block';
    document.getElementById('btn_abrir_separador').style.display = 'none';
    
    if(window.innerWidth > 768) {
        document.getElementById('modalPgContent').className = 'modal-pagamento-content w-850';
    }
    
    // Recarrega itens originais
    sepItensMesa = JSON.parse(JSON.stringify(itensMesaCache)).map(item => {
        const dados = processarTextoItem(item);
        let precoBase = parseFloat(item.preco_vendido || item.total_unitario || 0) * parseInt(item.quantidade || 1);
        return { ...item, nome: dados.nome, preco_restante: precoBase };
    });
    
    sepItensPessoa = [];
    renderInterfaceSeparacao();
    actualizarModalPagamento(); // Atualiza a lista visual de pagamentos para ficar vazia
}

function renderInterfaceSeparacao() {
    const listMesa = document.getElementById('lista_sep_mesa');
    const listPessoa = document.getElementById('lista_sep_pessoa');
    const termoBusca = (document.getElementById('filtro_itens_mesa').value || "").toLowerCase();
    
    listMesa.innerHTML = '';
    let itensDisponiveis = sepItensMesa.filter(i => i.preco_restante > 0.01);
    if(termoBusca) itensDisponiveis = itensDisponiveis.filter(i => i.nome.toLowerCase().includes(termoBusca));
    
    if(itensDisponiveis.length === 0) {
        listMesa.innerHTML = '<div class="text-center p-20 text-muted">Nenhum item livre encontrado.</div>';
    } else {
        itensDisponiveis.forEach(item => {
            listMesa.innerHTML += `
                <div class="sep-mesa-item">
                    <div class="sep-mesa-header">
                        <span class="sep-mesa-title">${item.nome}</span>
                        <span class="sep-mesa-price">R$ ${item.preco_restante.toFixed(2)}</span>
                    </div>
                    <div class="sep-btn-group">
                        <button class="sep-btn sep-btn-move" onclick="addPessoaTudo(${item.id})">👉 Mover p/ Comanda</button>
                        <button class="sep-btn sep-btn-split" onclick="dividirItemPessoa(${item.id})">➗ Fatiar Item</button>
                    </div>
                </div>
            `;
        });
    }

    let totalPessoa = 0; listPessoa.innerHTML = '';
    if(sepItensPessoa.length === 0) {
        listPessoa.innerHTML = '<div class="text-muted text-xs text-center mt-20">Clique nos itens ao lado para adicionar aqui...</div>';
    } else {
        sepItensPessoa.forEach((item, idx) => {
            totalPessoa += item.valor;
            let classColor = item.valor < 0 ? 'negativo' : '';
            let btnClose = item.idMesa === -1 ? '' : `<span class="text-danger cursor-pointer ml-10" onclick="removerDaPessoa(${idx})">✖</span>`;
            listPessoa.innerHTML += `
                <div class="sep-pessoa-item ${classColor}">
                    <span class="text-muted text-sm">${item.desc}</span>
                    <div class="font-bold">R$ ${item.valor.toFixed(2)}${btnClose}</div>
                </div>
            `;
        });
    }
    
    totalPessoa = Math.max(0, totalPessoa);
    
    // CORREÇÃO: Limita o valor visual da cobrança ao que a mesa DE FATO ainda deve
    let restanteMesaGlobal = getRestanteMesa();
    let valorCobranca = totalPessoa;
    let htmlTotal = valorCobranca.toFixed(2);

    // Se o cliente moveu mais itens do que a mesa deve (porque já houve pgto fora), o sistema limita e avisa!
    if (totalPessoa > restanteMesaGlobal && restanteMesaGlobal >= 0) {
        valorCobranca = restanteMesaGlobal;
        htmlTotal = `${valorCobranca.toFixed(2)} <span style="font-size: 0.75rem; color: #ff9800; display: block; line-height: 1;">(Limitado ao saldo da mesa)</span>`;
    }

    document.getElementById('total_sep_pessoa').innerHTML = htmlTotal;
    
    const inputValorPg = document.getElementById('pg_valor_pessoa');
    if(valorCobranca > 0) inputValorPg.value = valorCobranca.toFixed(2);
    else inputValorPg.value = "";
    
    calcularTrocoVisual('separado'); 
}

function addPessoaTudo(idMesa) {
    const item = sepItensMesa.find(i => i.id === idMesa);
    sepItensPessoa.push({ idMesa: item.id, desc: item.nome, valor: item.preco_restante });
    item.preco_restante = 0; 
    document.getElementById('filtro_itens_mesa').value = '';
    renderInterfaceSeparacao();
}

function dividirItemPessoa(idMesa) {
    const itemIndex = sepItensMesa.findIndex(i => i.id === idMesa);
    if(itemIndex === -1) return;
    const item = sepItensMesa[itemIndex];
    const partes = prompt(`Fatiar "${item.nome}" (R$ ${item.preco_restante.toFixed(2)}) em quantas partes na mesa?`, "4");
    const numPartes = parseInt(partes);
    
    if(!isNaN(numPartes) && numPartes > 1) {
        const valorTotal = item.preco_restante;
        const valorBase = Math.floor((valorTotal / numPartes) * 100) / 100;
        let soma = 0;
        sepItensMesa.splice(itemIndex, 1);
        for(let i = 0; i < numPartes; i++) {
            let valorParte = valorBase;
            if (i === numPartes - 1) valorParte = parseFloat((valorTotal - soma).toFixed(2));
            soma += valorParte;
            sepItensMesa.unshift({ id: Date.now() + i + Math.random(), nome: `(1/${numPartes}) ${item.nome}`, preco_total: valorParte, preco_restante: valorParte });
        }
        document.getElementById('filtro_itens_mesa').value = '';
        renderInterfaceSeparacao();
    }
}

function removerDaPessoa(idx) {
    const removido = sepItensPessoa.splice(idx, 1)[0];
    const itemMesa = sepItensMesa.find(i => i.id === removido.idMesa);
    if(itemMesa) itemMesa.preco_restante += removido.valor;
    renderInterfaceSeparacao();
}

function pagarComandaAtual() {
    if(sepItensPessoa.length === 0) return alert("Adicione itens à comanda antes de pagar.");
    
    let totalPessoaReal = sepItensPessoa.reduce((acc, i) => acc + i.valor, 0);
    let restanteMesaGlobal = getRestanteMesa();
    
    // Garante que não cobre a mais do que a mesa deve
    let valorCobranca = Math.min(Math.max(0, totalPessoaReal), restanteMesaGlobal);

    const valorPago = parseFloat(document.getElementById('pg_valor_pessoa').value);
    if(isNaN(valorPago) || valorPago <= 0) return alert("Digite um valor válido a ser pago.");
    
    if(valorPago > (valorCobranca + 0.05)) return alert(`Aviso: O valor máximo a ser cobrado agora é R$ ${valorCobranca.toFixed(2)}.`);

    const sel = document.getElementById('pg_metodo_pessoa');
    const opt = sel.options[sel.selectedIndex];
    if(!opt || !opt.value) return alert("Selecione um método.");
    const metodo = sel.value;
    
    let detalhe = "";
    if (opt.dataset.pede === "1") {
        const detInput = document.getElementById('pg_detalhe_pessoa').value.trim();
        if (metodo.toLowerCase().includes('dinheiro')) {
            const valNum = parseFloat(detInput.replace(',', '.'));
            if(!isNaN(valNum)) {
                if(valNum < valorPago) { alert('Valor entregue menor que o pagamento!'); return; }
                detalhe = `Troco para ${valNum.toFixed(2)}`;
            } else if (detInput) { detalhe = detInput; }
        } else { detalhe = detInput; }
    }

    pagamentosLancados.push({ metodo: metodo, valor: valorPago, detalhe: detalhe });

    if (Math.abs(valorCobranca - valorPago) < 0.05) {
        sepItensPessoa = []; 
        document.getElementById('pg_detalhe_pessoa').value = "";
    } else {
        sepItensPessoa.push({ idMesa: -1, desc: `Pago Parcialmente (${metodo})`, valor: -valorPago });
        document.getElementById('pg_detalhe_pessoa').value = "";
    }
    
    calcularTrocoVisual('separado');
    renderInterfaceSeparacao(); 
    atualizarModalPagamento(); 
}

function getRestanteMesa() {
    const totalLancado = pagamentosLancados.reduce((acc, p) => acc + p.valor, 0);
    return Math.max(0, totalMesaAtual - totalLancado);
}

function abrirPagamento() {
    if(totalMesaAtual <= 0.01) return alert("Mesa zerada.");
    pagamentosLancados = [];
    document.getElementById('modalPgContent').className = 'modal-pagamento-content w-500';
    document.getElementById('area_pgto_simples').style.display = 'block';
    document.getElementById('btn_abrir_separador').style.display = 'block';
    document.getElementById('area_pgto_separado').style.display = 'none';

    document.getElementById('pg_total_mesa').innerText = totalMesaAtual.toFixed(2);
    document.getElementById('pg_detalhe').value = '';
    document.getElementById('pg_divisor').value = "1";
    
    togglePgtoDetalhes('simples');
    atualizarModalPagamento(); 
    document.getElementById('modalPagamento').style.display = 'flex';
}

function calcularTrocoVisual(modo) {
    let sel, inputDet, valorPagar, display;
    if(modo === 'simples') {
        sel = document.getElementById('pg_metodo'); inputDet = document.getElementById('pg_detalhe');
        valorPagar = parseFloat(document.getElementById('pg_valor').value) || 0; display = document.getElementById('display_troco');
    } else {
        sel = document.getElementById('pg_metodo_pessoa'); inputDet = document.getElementById('pg_detalhe_pessoa');
        valorPagar = parseFloat(document.getElementById('pg_valor_pessoa').value) || 0; display = document.getElementById('display_troco_pessoa');
    }
    
    const metodo = sel.value;
    display.innerText = "";
    if (metodo.toLowerCase().includes('dinheiro')) {
        const valorEntregue = parseFloat(inputDet.value.replace(',', '.')) || 0;
        const troco = valorEntregue - valorPagar;
        if (troco > 0) { display.innerText = `Troco: R$ ${troco.toFixed(2)}`; display.style.color = "#4CAF50"; } 
        else { display.innerText = "Sem troco"; display.style.color = "#aaa"; }
    }
}

function lancarPagamentoSimples() {
    const sel = document.getElementById('pg_metodo');
    const opt = sel.options[sel.selectedIndex];
    if(!opt || !opt.value) return alert("Selecione um método.");
    const metodo = sel.value;
    const valor = parseFloat(document.getElementById('pg_valor').value);
    if (isNaN(valor) || valor <= 0) return alert("Valor inválido.");
    
    let detalhe = "";
    if (opt.dataset.pede === "1") {
        const detInput = document.getElementById('pg_detalhe').value.trim();
        if (metodo.toLowerCase().includes('dinheiro')) {
            const valNum = parseFloat(detInput.replace(',', '.'));
            if(!isNaN(valNum)) {
                if(valNum < valor) { alert('Valor entregue menor que o pagamento!'); return; }
                detalhe = `Troco para ${valNum.toFixed(2)}`;
            } else if (detInput) { detalhe = detInput; }
        } else { detalhe = detInput; }
    }

    const restante = getRestanteMesa();
    if (valor > (restante + 0.05)) return alert(`Valor maior que o restante! Falta apenas R$ ${restante.toFixed(2)}`);
    
    pagamentosLancados.push({ metodo: metodo, valor: valor, detalhe: detalhe });
    
    let divisorInput = document.getElementById('pg_divisor'); let divVal = parseInt(divisorInput.value) || 1;
    if (divVal > 1) divisorInput.value = divVal - 1;
    
    document.getElementById('pg_detalhe').value = ""; 
    calcularTrocoVisual('simples');
    atualizarModalPagamento();
}

function removerPagamento(index) {
    pagamentosLancados.splice(index, 1); actualizarModalPagamento();
}

function actualizarModalPagamento() {
    const lista = document.getElementById('lista_pagamentos_adicionados');
    const displayRestante = document.getElementById('pg_restante');
    const btnFinalizar = document.getElementById('btn_finalizar_pg');
    const inputValor = document.getElementById('pg_valor');
    const inputValorPessoa = document.getElementById('pg_valor_pessoa');
    const restante = getRestanteMesa();
    
    lista.innerHTML = "";
    if (pagamentosLancados.length === 0) {
        lista.innerHTML = '<div style="text-align:center; color:#666; font-size:0.8rem;">Nenhum pagamento lançado.</div>';
    } else {
        pagamentosLancados.forEach((pg, idx) => {
            let displayDet = pg.detalhe || '';
            
            if(pg.metodo.toLowerCase().includes('dinheiro') && displayDet.includes('Troco para')) {
                let valEntregue = parseFloat(displayDet.replace(/[^0-9.]/g, ''));
                if(!isNaN(valEntregue) && valEntregue > pg.valor) {
                    let troco = valEntregue - pg.valor;
                    displayDet += `<div style="color:var(--success); font-weight:bold; font-size:0.85rem; margin-top:2px;">↳ Troco: R$ ${troco.toFixed(2)}</div>`;
                }
            }
            
            lista.innerHTML += `
            <div class="pgto-row">
                <div style="display:flex; flex-direction:column;">
                    <span style="font-weight:bold; color: #fff;">${pg.metodo}</span>
                    <span style="color:#aaa; font-size:0.8rem;">${displayDet || '-'}</span>
                </div>
                <span style="font-weight:bold; color: #fff;">R$ ${pg.valor.toFixed(2)} <span onclick="removerPagamento(${idx})" style="cursor:pointer; color:#ff4444; margin-left:15px; font-size: 1.2rem;">&times;</span></span>
            </div>`;
        });
    }
    
    // Garante que as divs principais NUNCA fiquem bloqueadas por pointer-events
    const areaSeparado = document.getElementById('area_pgto_separado');
    const areaSimples = document.getElementById('area_pgto_simples');
    if (areaSeparado) { areaSeparado.style.opacity = "1"; areaSeparado.style.pointerEvents = "auto"; }
    if (areaSimples) { areaSimples.style.opacity = "1"; areaSimples.style.pointerEvents = "auto"; }

    // Seleciona os inputs e botões exatos para bloquear quando a conta for paga
    const inputsParaBloquear = ['pg_divisor', 'pg_metodo', 'pg_valor', 'pg_detalhe', 'pg_metodo_pessoa', 'pg_valor_pessoa', 'pg_detalhe_pessoa'];
    const botoesParaBloquear = ['btn_lancar_simples', 'btn_lancar_separado'];

    if (Math.abs(restante) < 0.05) {
        // CONTA TOTALMENTE PAGA
        displayRestante.innerText = "Pago ✅"; displayRestante.style.color = "#4CAF50";
        btnFinalizar.disabled = false; btnFinalizar.innerText = `✅ Finalizar Conta da Mesa`;
        if(inputValor) inputValor.value = "";
        if(inputValorPessoa) inputValorPessoa.value = "";
        
        // Bloqueia individualmente só os campos de lançamento
        inputsParaBloquear.forEach(id => {
            const el = document.getElementById(id);
            if(el) { el.disabled = true; el.style.opacity = "0.5"; }
        });
        botoesParaBloquear.forEach(id => {
            const el = document.getElementById(id);
            if(el) { el.disabled = true; el.style.opacity = "0.5"; el.style.pointerEvents = "none"; }
        });

    } else {
        // CONTA COM SALDO PENDENTE
        displayRestante.innerText = `R$ ${restante.toFixed(2)}`; displayRestante.style.color = "#ff4444";
        btnFinalizar.disabled = true; btnFinalizar.innerText = `Falta R$ ${restante.toFixed(2)} para Fechar`;
        
        // Desbloqueia todos os campos
        inputsParaBloquear.forEach(id => {
            const el = document.getElementById(id);
            if(el) { el.disabled = false; el.style.opacity = "1"; }
        });
        botoesParaBloquear.forEach(id => {
            const el = document.getElementById(id);
            if(el) { el.disabled = false; el.style.opacity = "1"; el.style.pointerEvents = "auto"; }
        });
        
        aplicarDivisao();
    }
}
const atualizarModalPagamento = actualizarModalPagamento;

async function finalizarFechamento() {
    let formas = [...new Set(pagamentosLancados.map(p => p.metodo))].sort();
    let forma_pgt = formas.join(" + ");
    
    let detalhes_arr = pagamentosLancados.map(p => {
        let det = p.detalhe ? ` (${p.detalhe})` : "";
        return `${p.metodo}: R$ ${p.valor.toFixed(2)}${det}`;
    });
    let detalhe_pagamento = detalhes_arr.join(" | ");

    const res = await fetch(`/api/mesas/${mesaAtualId}/fechar`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ forma_pagamento: forma_pgt, detalhe_pagamento: detalhe_pagamento, total: totalMesaAtual })
    });
    
    if(res.ok) { document.getElementById('modalPagamento').style.display = 'none'; fecharModal(); carregarMesas(); } 
    else alert("Erro ao fechar.");
}

function imprimirConteudoEmPopup(htmlContent) {
    const win = window.open('', '', 'width=400,height=600');
    win.document.write(`<html><head><style>@page { margin: 0; size: 80mm auto; } body { font-family: 'Courier New', monospace; font-size: 15px; font-weight: bold; width: 100%; margin: 0; padding: 5px 10px; color: #000; box-sizing: border-box; } .cupom-header { text-align: center; border-bottom: 2px dashed #000; padding-bottom: 8px; margin-bottom: 10px; } .cupom-title { font-size: 1.2em; font-weight: 900; display: block; margin-bottom: 3px; text-transform: uppercase;} .cupom-mesa { font-size: 1.4em; font-weight: 900; margin: 5px 0; display: block; border: 2px solid #000; padding: 2px; } .cupom-item { margin-bottom: 10px; border-bottom: 1px dotted #000; padding-bottom: 4px; display: flex; flex-direction: column; } .cupom-line-main { display: flex; justify-content: space-between; align-items: flex-start; font-size: 1.05em; } .cupom-nome { flex: 1; margin-right: 10px; } .cupom-preco { white-space: nowrap; flex-shrink: 0; text-align: right; } .cupom-line-adds { font-size: 0.9em; padding-left: 0; margin-top: 2px; font-weight: normal; color: #222; font-style: italic; } .cupom-line-obs { font-size: 0.9em; font-weight: normal; margin-top: 2px; display: block; background: #eee; padding: 2px; } .cupom-total { text-align: right; font-size: 1.4em; font-weight: 900; margin-top: 15px; border-top: 2px dashed #000; padding-top: 10px; }</style></head><body>${htmlContent}<br><br><center style="font-size:0.8em">--- Fim ---</center><script>setTimeout(() => { window.print(); }, 500);<\/script></body></html>`);
    win.document.close(); win.focus();
}

function imprimirCozinha() {
    if(itensMesaCache.length === 0) return alert("Mesa vazia!");
    const now = new Date(); const dataHora = now.toLocaleDateString() + ' ' + now.toLocaleTimeString().substring(0,5);
    let html = `<div class="cupom-header"><span class="cupom-title">PEDIDO COZINHA</span><span class="cupom-mesa">${mesaAtualNome.toUpperCase()}</span><span>${dataHora}</span></div>`;
    itensMesaCache.forEach(item => {
        if(item.preco_vendido < 0 || item.tipo === 'desconto') return; 
        const dados = processarTextoItem(item);
        html += `<div class="cupom-item"><div class="cupom-line-main"><span class="cupom-nome">${item.quantidade}x ${dados.nome}</span></div>`;
        if(item.adicionais) html += `<span class="cupom-line-adds">+ ${item.adicionais}</span>`;
        if(dados.obs && dados.obs !== "") html += `<span class="cupom-line-obs">OBS: ${dados.obs}</span>`;
        html += `</div>`;
    });
    html += `<div style="margin-top:20px; text-align:center; border-top:1px solid #000; padding-top:10px;"><br>_____________Garçom_____________</div>`;
    imprimirConteudoEmPopup(html);
}

function imprimirCliente() {
    if(itensMesaCache.length === 0) return alert("Mesa vazia!");
    const now = new Date(); const dataHora = now.toLocaleDateString() + ' ' + now.toLocaleTimeString().substring(0,5);
    let html = `<div class="cupom-header"><span class="cupom-title">CONFERÊNCIA DE CONTA</span><span class="cupom-mesa">${mesaAtualNome.toUpperCase()}</span><span>${dataHora}</span></div>`;
    const nomeCli = document.getElementById('nomeClienteMesa').value;
    if(nomeCli) html += `<div style="text-align:center; border-bottom:1px dashed #000; margin-bottom:10px; padding-bottom:5px;">Cliente: ${nomeCli}</div>`;
    itensMesaCache.forEach(item => {
        const dados = processarTextoItem(item);
        let totalItem = item.preco_vendido * item.quantidade;
        let displayPreco = item.preco_vendido < 0 ? `- R$ ${Math.abs(totalItem).toFixed(2)}` : `R$ ${totalItem.toFixed(2)}`;
        html += `<div class="cupom-item"><div class="cupom-line-main"><span class="cupom-nome">${item.quantidade}x ${dados.nome}</span><span class="cupom-preco">${displayPreco}</span></div>`;
        if(item.adicionais) html += `<span class="cupom-line-adds">+ ${item.adicionais}</span>`;
        if(dados.obs && dados.obs !== "") html += `<span class="cupom-line-obs">Obs: ${dados.obs}</span>`;
        html += `</div>`;
    });
    html += `<div class="cupom-total">TOTAL: R$ ${totalMesaAtual.toFixed(2)}</div><div style="text-align:center; margin-top:20px; font-size:10px;">Obrigado pela preferência!</div>`;
    imprimirConteudoEmPopup(html);
}

async function carregarMesas() {
    try {
        const res = await fetch('/api/mesas'); 
        const mesas = await res.json();
        const grid = document.getElementById('gridMesas'); 
        grid.innerHTML = '';
        
        mesas.forEach(m => {
            const ocupada = m.status === 'OCUPADA'; 
            const style = ocupada ? 'mesa-ocupada' : 'mesa-livre';
            const totalDisplay = ocupada ? `R$ ${m.total.toFixed(2)}` : '<span style="opacity:0.5">Livre</span>';
            
            // CORREÇÃO: Trocado m.display_nome por m.nome
            grid.innerHTML += `<div class="mesa-card ${style}" onclick="abrirMesa(${m.id}, '${m.nome}')"><div class="mesa-icon">${ocupada ? '🍝' : '🍽️'}</div><div class="mesa-nome">${m.nome}</div><div class="mesa-total">${totalDisplay}</div></div>`;
        });
    } catch (e) {}
}

async function abrirMesa(id, nomeOriginal) {
    mesaAtualId = id; mesaAtualNome = nomeOriginal;
    document.getElementById('tituloMesa').innerText = nomeOriginal;
    document.getElementById('modalMesa').style.display = 'flex';
    document.getElementById('sel_categoria').value = "";
    document.getElementById('sel_produto').innerHTML = '<option value="">Selecione...</option>';
    document.getElementById('box_detalhes_dinamicos').innerHTML = '<div style="color: #666; text-align: center; margin-top: 30px;">Selecione um produto</div>';
    document.getElementById('sys_qtd').value = 1; document.getElementById('nomeClienteMesa').value = ""; document.getElementById('extra_valor').value = "";
    await carregarPromocoesDoBanco(); await carregarItensMesa();
}

function processarTextoItem(item) {
    let rawNome = item.nome_cache || item.nome || 'Item'; let rawObs = item.observacao || '';
    let tamanho = ""; const matchTam = rawObs.match(/Tamanho:\s*(.*?)\./);
    if(matchTam) { tamanho = matchTam[1].trim(); rawObs = rawObs.replace(matchTam[0], ''); }
    let nomeFinal = rawNome.replace(/\[NM:.*?\]/g, '').trim(); rawObs = rawObs.replace(/\[NM:.*?\]/g, '').trim();
    if(tamanho) { nomeFinal = nomeFinal.replace(/^Pizza\s*/i, ''); nomeFinal = `Pizza (${tamanho}) - ${nomeFinal}`; }
    let obsFinal = rawObs.replace(/^[\s\.\,\-]+/g, '').trim();
    return { nome: nomeFinal, obs: obsFinal };
}

async function carregarItensMesa() {
    const res = await fetch(`/api/mesas/${mesaAtualId}/itens`); const data = await res.json();
    totalMesaAtual = data.total || 0; itensMesaCache = data.itens || [];
    if (data.cliente_nome) { document.getElementById('nomeClienteMesa').value = data.cliente_nome; mesaAtualNome = data.cliente_nome; } 
    else { mesaAtualNome = document.getElementById('tituloMesa').innerText; }

    const lista = document.getElementById('listaItens'); lista.innerHTML = '';
    if((data.itens && data.itens.length > 0) || (data.cliente_nome && data.cliente_nome !== "")) {
        document.getElementById('statusMesaBadge').innerText = "Ocupada"; document.getElementById('statusMesaBadge').className = "badge-ocupada";
        document.getElementById('btnFecharMesa').style.display = 'block'; document.getElementById('btnCancelarMesa').style.display = 'block';
    } else {
        document.getElementById('statusMesaBadge').innerText = "Livre"; document.getElementById('statusMesaBadge').className = "badge-livre";
        document.getElementById('btnFecharMesa').style.display = 'none'; document.getElementById('btnCancelarMesa').style.display = 'none';
    }

    if(data.itens) {
        data.itens.forEach(item => {
            const dados = processarTextoItem(item); const colorPrice = item.preco_vendido < 0 ? '#ff4444' : '#fff';
            lista.innerHTML += `<div class="item-row"><div style="flex:1;"><div class="item-nome">${item.quantidade}x ${dados.nome}</div>${item.adicionais ? `<div class="item-adds">+ ${item.adicionais}</div>` : ''}${dados.obs ? `<div class="item-obs">Obs: ${dados.obs}</div>` : ''}</div><div style="text-align:right;"><div style="font-family: monospace; font-weight:bold; color:${colorPrice}">R$ ${(item.preco_vendido * item.quantidade).toFixed(2)}</div><button class="btn-remove" onclick="removerItemMesa(${item.id})">×</button></div></div>`;
        });
    }
    document.getElementById('totalMesa').innerText = totalMesaAtual.toFixed(2);
}

async function lancarExtraOuDesconto() {
    const tipo = document.getElementById('extra_tipo').value;
    let valor = parseFloat(document.getElementById('extra_valor').value);
    if(isNaN(valor) || valor <= 0) return alert("Digite um valor válido.");
    let nomeItem = "Extra"; if (tipo === 'desconto') { nomeItem = "Desconto"; valor = valor * -1; }
    try {
        await fetch(`/api/mesas/${mesaAtualId}/adicionar`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({categoria: tipo, produto_id: 0, nome: nomeItem, quantidade: 1, total_unitario: valor, observacao: ""}) });
        document.getElementById('extra_valor').value = ""; carregarItensMesa();
    } catch(e) { alert("Erro ao adicionar."); }
}

function fecharModal() { document.getElementById('modalMesa').style.display = 'none'; mesaAtualId = null; carregarMesas(); }
async function salvarNomeCliente() {
    if(!mesaAtualId) return; const nome = document.getElementById('nomeClienteMesa').value; if(nome.trim() === "") return;
    await fetch(`/api/mesas/${mesaAtualId}/nome_cliente`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({nome: nome}) });
    carregarItensMesa();
}
async function cancelarMesa() {
    if(!confirm("Liberar a mesa e CANCELAR o pedido atual?")) return;
    await fetch(`/api/mesas/${mesaAtualId}/cancelar`, { method: 'POST' }); fecharModal();
}
function definirQtdMesas() {
    const qtd = prompt("Quantas mesas ao todo?", "15");
    if(qtd) { fetch('/api/mesas/configurar_qtd', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({qtd: parseInt(qtd)}) }).then(() => carregarMesas()); }
}

async function carregarProdutosDaCategoria() {
    const catId = document.getElementById('sel_categoria').value; 
    const selProd = document.getElementById('sel_produto');
    const boxDyn = document.getElementById('box_detalhes_dinamicos');
    selProd.innerHTML = '<option value="">Selecione...</option>';
    boxDyn.innerHTML = '<div style="color: #666; text-align: center; margin-top: 30px;">Selecione um produto</div>';
    document.getElementById('sys_qtd').value = 1;
    if(!catId) return; 
    
    selProd.innerHTML = '<option>Carregando...</option>';
    await carregarPromocoesDoBanco(); const resp = await fetch(`/api/produtos_categoria/${catId}`); const produtos = await resp.json();
    if(catId === 'pizza') cacheSaboresPizza = produtos;
    let temVariacaoDeTamanho = false;
    if(produtos.length > 0) temVariacaoDeTamanho = await verificarSeCategoriaTemVariacao(catId, produtos[0].id);
    
    selProd.innerHTML = '<option value="">Selecione...</option>';
    produtos.forEach(p => {
        let precoBase = parseFloat(p.preco) || 0; let precoFinal = calcularPrecoComDesconto(precoBase, catId, p.id);
        let txtExtra = "";
        if (!temVariacaoDeTamanho) { if (precoBase > 0 || precoFinal > 0) { txtExtra = precoFinal !== precoBase ? `(Promo: R$ ${precoFinal.toFixed(2)})` : `(R$ ${precoBase.toFixed(2)})`; } }
        const opt = document.createElement('option'); opt.value = p.id; opt.dataset.preco_base = precoFinal; opt.dataset.nome = p.nome; opt.innerText = txtExtra ? `${p.nome} ${txtExtra}` : p.nome; selProd.appendChild(opt);
    });
}

function produtoPrincipalSelecionado() { carregarDetalhesProduto(); }

async function carregarDetalhesProduto() {
    const catId = document.getElementById('sel_categoria').value; 
    const prodId = document.getElementById('sel_produto').value; 
    const box = document.getElementById('box_detalhes_dinamicos');
    const selProd = document.getElementById('sel_produto');

    if (!prodId) { box.innerHTML = ''; return; }
    const optAtiva = selProd.options[selProd.selectedIndex]; let precoBaseProd = parseFloat(optAtiva.dataset.preco_base) || 0;
    
    box.innerHTML = 'Carregando...'; 
    const resp = await fetch(`/api/detalhes_produto/${catId}/${prodId}`); const dados = await resp.json(); let html = '';
    
    if (dados.variacoes && dados.variacoes.length > 0) {
        html += `<strong style="color:#ff9800; display:block; margin-bottom:5px;">Tamanho:</strong><select id="sel_variacao" class="input-std" style="width: 100%; box-sizing: border-box;" onchange="atualizarInterfaceSabores()">`;
        dados.variacoes.forEach((v, index) => {
            const sel = index===0?'selected':''; let precoVarBase = parseFloat(v.preco) || 0; let precoVarPromo = calcularPrecoComDesconto(precoVarBase, catId, prodId);
            let precoExibicao = precoBaseProd + precoVarPromo;
            html += `<option value="${v.nome}" data-preco="${precoVarPromo}" data-max-sabores="${v.max_sabores||1}" ${sel}>${v.nome} (R$ ${precoExibicao.toFixed(2)})</option>`;
        });
        html += `</select>`;
    }
    
    if (catId === 'pizza') html += `<div id="container_sabores_extras"></div>`;
    
    if (dados.adicionais) {
        dados.adicionais.forEach(grupo => {
            html += `<div style="margin-top:10px; border-top:1px dashed #444; padding-top:5px;"><strong style="color:#4CAF50;">${grupo.titulo||grupo.nome}</strong><br>`;
            if (grupo.tipo === 'texto' || grupo.tipo === 'numero' || grupo.tipo === 'quantidade') { html += `<input type="text" class="input-std input-dyn-text" data-label="${grupo.titulo||grupo.nome}" placeholder="Digite..." style="width: 100%; box-sizing: border-box;">`; } 
            else if(grupo.itens) {
                let type = (grupo.tipo === 'unica') ? 'radio' : 'checkbox'; let name = `adicional_${grupo.id}`; let minimo = parseInt(grupo.minimo_escolha) || 0; let nomesParaMarcar = [];
                if (minimo > 0 && grupo.itens.length > 0) { let itensOrdenados = [...grupo.itens].sort((a, b) => { return (parseFloat(a.preco_adicional) || 0) - (parseFloat(b.preco_adicional) || 0); }); for (let k = 0; k < minimo && k < itensOrdenados.length; k++) { nomesParaMarcar.push(itensOrdenados[k].nome); } }
                grupo.itens.forEach(i => { let p = parseFloat(i.preco_adicional) || 0; let txt = p > 0 ? ` (+R$ ${p.toFixed(2)})` : ''; let isChecked = nomesParaMarcar.includes(i.nome) ? 'checked' : ''; html += `<label style="display:inline-block; margin-right:10px; color:#ccc; cursor:pointer;"><input type="${type}" name="${name}" class="chk-adicional" value="${i.nome}" data-preco="${p}" ${isChecked}> ${i.nome}${txt}</label>`; });
            }
            html += `</div>`;
        });
    }
    box.innerHTML = html; if(catId === 'pizza') atualizarInterfaceSabores();
}

function atualizarInterfaceSabores() {
    const container = document.getElementById('container_sabores_extras'); if(!container) return;
    const selVar = document.getElementById('sel_variacao'); const max = parseInt(selVar.options[selVar.selectedIndex].dataset.maxSabores)||1;
    let html = '';
    if(max > 1) {
        html += `<div class="sabores-extras-box"><div style="color:#ff9800; font-size:0.9rem;">+ Sabores:</div>`;
        for(let i=2; i<=max; i++) { html += `<select class="input-std select-sabor-extra" style="margin-top:5px; width: 100%; box-sizing: border-box;"><option value="">-- ${i}º Sabor --</option>${cacheSaboresPizza.map(p=>`<option value="${p.nome}">${p.nome}</option>`).join('')}</select>`; }
        html += `</div>`;
    }
    container.innerHTML = html;
}

async function adicionarItemMesa() {
    const selProd = document.getElementById('sel_produto'); if(!selProd.value) return alert("Selecione um produto!");
    let nomeFinal = selProd.options[selProd.selectedIndex].dataset.nome; let preco = parseFloat(selProd.options[selProd.selectedIndex].dataset.preco_base) || 0; let varNome = "";
    const selVar = document.getElementById('sel_variacao'); 
    if(selVar) { preco += parseFloat(selVar.options[selVar.selectedIndex].dataset.preco) || 0; varNome = selVar.value; }
    const extras = document.querySelectorAll('.select-sabor-extra'); let sabores = []; extras.forEach(e => { if(e.value) sabores.push(e.value); });
    if(sabores.length>0) { nomeFinal += " / " + sabores.join(" / "); if(!nomeFinal.toLowerCase().includes("pizza")) nomeFinal = "Pizza " + nomeFinal; }
    let adds = []; let totalAdds = 0; document.querySelectorAll('.chk-adicional:checked').forEach(c => { totalAdds += parseFloat(c.dataset.preco); adds.push({nome: c.value}); });
    let obs = ""; document.querySelectorAll('.input-dyn-text').forEach(i => { if(i.value.trim()) obs += `${i.dataset.label}: ${i.value}. `; });
    const payload = { categoria: document.getElementById('sel_categoria').value, produto_id: selProd.value, nome: nomeFinal, variacao_nome: varNome, quantidade: parseInt(document.getElementById('sys_qtd').value)||1, total_unitario: preco + totalAdds, observacao: obs, lista_adicionais: adds };
    enviarItem(payload);
}

async function enviarItem(payload) {
    try { await fetch(`/api/mesas/${mesaAtualId}/adicionar`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) }); document.querySelectorAll('.input-dyn-text').forEach(i=>i.value=''); document.querySelectorAll('.select-sabor-extra').forEach(s=>s.value=''); document.getElementById('sys_qtd').value = 1; carregarItensMesa(); } catch(e) { alert("Erro ao adicionar"); }
}

async function removerItemMesa(id) { if(confirm("Remover?")) { await fetch(`/api/mesas/${mesaAtualId}/item/${id}`, {method:'DELETE'}); await carregarItensMesa(); carregarMesas(); } }

const observer = new MutationObserver(() => {
    let modalAberto = false;
    document.querySelectorAll('.modal-overlay').forEach(m => {
        if (window.getComputedStyle(m).display !== 'none') modalAberto = true;
    });

    if (modalAberto) {
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
        document.body.style.height = '100%';
    } else {
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.width = '';
        document.body.style.height = '';
    }
});
document.querySelectorAll('.modal-overlay').forEach(m => observer.observe(m, { attributes: true, attributeFilter: ['style'] }));

function imprimirComandaSeparada() {
    if(sepItensPessoa.length === 0) return alert("Adicione itens à comanda antes de imprimir.");
    
    const now = new Date(); 
    const dataHora = now.toLocaleDateString() + ' ' + now.toLocaleTimeString().substring(0,5);
    const totalComanda = sepItensPessoa.reduce((acc, i) => acc + i.valor, 0);
    
    let html = `<div class="cupom-header">
                    <span class="cupom-title">COMANDA INDIVIDUAL</span>
                    <span class="cupom-mesa">${mesaAtualNome.toUpperCase()}</span>
                    <span>${dataHora}</span>
                </div>`;

    sepItensPessoa.forEach(item => {
        if(item.valor < 0) return; // Não imprime descontos/pagamentos parciais no cupom de consumo
        html += `<div class="cupom-item">
                    <div class="cupom-line-main">
                        <span class="cupom-nome">${item.desc}</span>
                        <span class="cupom-preco">R$ ${item.valor.toFixed(2)}</span>
                    </div>
                 </div>`;
    });

    html += `<div class="cupom-total">TOTAL COMANDA: R$ ${totalComanda.toFixed(2)}</div>
             <div style="text-align:center; margin-top:20px; font-size:10px;">Conferência de itens individuais</div>`;
    
    imprimirConteudoEmPopup(html);
}