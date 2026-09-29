// Carrega bairros do JSON embutido
const bairrosDoBanco = JSON.parse(document.getElementById('dados-bairros').textContent);

window.onload = function() {
    const select = document.getElementById('editBairro');
    if(select && bairrosDoBanco) {
        bairrosDoBanco.forEach(bairro => {
            const opt = document.createElement('option');
            opt.value = bairro;
            opt.innerText = bairro;
            select.appendChild(opt);
        });
    }
};

// --- ORDENAÇÃO DE TABELA ---
let ordemDirecao = {};
function ordenarTabela(colIndex) {
    const table = document.getElementById('tabelaClientes');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr.cliente-row')); 
    
    if(rows.length === 0) return;

    ordemDirecao[colIndex] = !ordemDirecao[colIndex];
    const asc = ordemDirecao[colIndex];

    rows.sort((a, b) => {
        const valA = a.children[colIndex].innerText.toLowerCase();
        const valB = b.children[colIndex].innerText.toLowerCase();
        
        if (valA < valB) return asc ? -1 : 1;
        if (valA > valB) return asc ? 1 : -1;
        return 0;
    });

    rows.forEach(row => tbody.appendChild(row));
}

// FILTROS
function aplicarFiltros() {
    const termo = document.getElementById('searchClientes').value.toLowerCase();
    const statusFiltro = document.getElementById('filterStatus').value; // all, active, blocked
    
    const linhas = document.querySelectorAll('#tabelaClientes tbody tr.cliente-row');
    
    linhas.forEach(linha => {
        const texto = linha.innerText.toLowerCase();
        const statusLinha = linha.dataset.status; 
        let mostrar = true;

        if (termo && !texto.includes(termo)) mostrar = false;
        if (statusFiltro !== 'all' && statusFiltro !== statusLinha) mostrar = false;

        linha.style.display = mostrar ? '' : 'none';
    });
}

// --- AÇÕES EM MASSA ---
async function alterarStatusTodos(ativar) {
    const acao = ativar ? "DESBLOQUEAR" : "BLOQUEAR";
    if(!confirm(`ATENÇÃO: Deseja realmente ${acao} o robô para TODOS os clientes cadastrados?`)) return;

    try {
        const dados = { novo_status: ativar ? 1 : 0 };
        const resp = await fetch('/api/clientes/bulk_update_status', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(dados)
        });

        if (resp.ok) {
            alert("Atualização em massa concluída!");
            window.location.reload();
        } else {
            const err = await resp.json();
            alert("Erro: " + (err.erro || "Falha na API."));
        }
    } catch (e) {
        console.error(e);
        alert("Erro de conexão.");
    }
}

// --- TOGGLE INDIVIDUAL DIRETO NA TABELA ---
async function toggleClienteIndividual(telefone, checkbox) {
    const novoStatus = checkbox.checked ? 1 : 0;
    try {
        const resp = await fetch(`/api/clientes/${telefone}/chat_status`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ chat_ativo: novoStatus })
        });
        
        if (!resp.ok) {
            checkbox.checked = !checkbox.checked; // Reverte se der erro
            alert("Erro ao atualizar status.");
        } else {
            // Atualiza o atributo data-status da linha para os filtros funcionarem sem reload
            const linha = checkbox.closest('tr');
            if(linha) linha.dataset.status = novoStatus ? 'active' : 'blocked';
        }
    } catch (e) {
        checkbox.checked = !checkbox.checked;
        alert("Erro de conexão.");
    }
}

const modal = document.getElementById('modalOverlay');
let isEditing = false;

function prepararEdicao(btn) {
    isEditing = true;
    document.getElementById('modalTitle').innerText = "Editar Cliente";
    const dados = btn.dataset;
    
    const campoTel = document.getElementById('editTelefone');
    campoTel.value = dados.telefone;
    campoTel.disabled = true; 

    document.getElementById('editNome').value = dados.nome;
    document.getElementById('editCpf').value = dados.cpf;
    document.getElementById('editRua').value = dados.rua;
    document.getElementById('editNumero').value = dados.numero;
    document.getElementById('editBairro').value = dados.bairro; 
    document.getElementById('editRef').value = dados.ref;
    
    document.getElementById('editChatAtivo').checked = (dados.chat !== '0');
    
    // --- POPULA OS CAMPOS DINÂMICOS NO MODAL ---
    const dynamicInputs = document.querySelectorAll('.dynamic-input');
    dynamicInputs.forEach(input => {
        const col = input.getAttribute('data-coluna');
        input.value = btn.getAttribute(`data-dyn-${col}`) || '';
    });

    modal.style.display = 'flex';
}

function abrirModalNovo() {
    isEditing = false;
    document.getElementById('modalTitle').innerText = "Cadastrar Novo Cliente";
    document.getElementById('editForm').reset();
    
    const campoTel = document.getElementById('editTelefone');
    campoTel.disabled = false;
    campoTel.value = ""; 

    document.getElementById('editChatAtivo').checked = true;
    
    // --- LIMPA OS CAMPOS DINÂMICOS NO MODAL ---
    const dynamicInputs = document.querySelectorAll('.dynamic-input');
    dynamicInputs.forEach(input => { input.value = ''; });

    modal.style.display = 'flex';
}

function fecharModal() { modal.style.display = 'none'; }

async function salvarCliente(e) {
    e.preventDefault();
    const telefone = document.getElementById('editTelefone').value.trim();
    if (!telefone) return alert("Telefone é obrigatório");

    const chatAtivoValor = document.getElementById('editChatAtivo').checked ? 1 : 0;
    const dados = { 
        telefone: telefone,
        nome: document.getElementById('editNome').value, 
        cpf: document.getElementById('editCpf').value, 
        rua: document.getElementById('editRua').value, 
        numero_casa: document.getElementById('editNumero').value, 
        bairro: document.getElementById('editBairro').value, 
        ponto_referencia: document.getElementById('editRef').value, 
        chat_ativo: chatAtivoValor 
    };

    // --- COLETA OS VALORES DOS CAMPOS DINÂMICOS PARA SALVAR ---
    const dynamicInputs = document.querySelectorAll('.dynamic-input');
    dynamicInputs.forEach(input => {
        const col = input.getAttribute('data-coluna');
        dados[col] = input.value;
    });

    let url = isEditing ? `/api/clientes/${telefone}` : `/api/clientes`;
    let method = isEditing ? 'PUT' : 'POST';

    try {
        const resp = await fetch(url, { 
            method: method, 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(dados) 
        });
        
        if (resp.ok) window.location.reload();
        else {
            const err = await resp.json();
            alert("Erro: " + (err.detail || "Falha ao salvar."));
        }
    } catch (error) { alert("Erro de conexão."); }
}

async function excluirCliente(telefone, nome) {
    if (!confirm(`Tem certeza que deseja excluir ${nome}?\nTodo o histórico será perdido.`)) return;
    try {
        const resp = await fetch(`/api/clientes/${telefone}`, { method: 'DELETE' });
        if (resp.ok) window.location.reload();
        else alert("Erro ao excluir.");
    } catch (error) { alert("Erro de conexão."); }
}

// Fecha o modal ao clicar fora dele
if (modal) {
    modal.addEventListener('click', (e) => { 
        if (e.target === modal) fecharModal(); 
    });
}