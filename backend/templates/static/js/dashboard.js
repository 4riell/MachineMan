// Configuração Global do Chart.js para Dark Theme
Chart.defaults.color = '#888';
Chart.defaults.borderColor = '#333';
Chart.defaults.font.family = 'inherit';

let graficosInstancias = {};

document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    carregarDadosDashboard();
});

// FUNÇÃO PARA ALTERNAR ENTRE AS ABAS
window.mudarAbaDashboard = function(viewId, btn) {
    document.querySelectorAll('.erp-view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(viewId).classList.add('active');
    btn.classList.add('active');
}

async function carregarDadosDashboard() {
    try {
        const response = await fetch('/api/dashboard/dados');
        const data = await response.json();

        // 1. Atualizar Visão Geral
        atualizarKPIs(data.kpis);
        renderizarGraficos(data.graficos);

        // 2. Atualizar Aba Financeiro
        atualizarFinanceiro(data.financeiro);
        atualizarFinanceiroDetalhado(data.financeiro_detalhado);

        // 3. Atualizar Aba Clientes
        atualizarClientes(data.clientes_detalhado);

    } catch (error) {
        console.error("Erro ao buscar dados do dashboard:", error);
    }
}

function atualizarKPIs(kpis) {
    document.getElementById('kpi-vendas-total').textContent = `R$ ${kpis.vendas_total_periodo}`;
    document.getElementById('kpi-vendas-mes-atual').textContent = `Mês Atual: R$ ${kpis.vendas_mes_atual}`;
    document.getElementById('kpi-vendas-mes-ant').textContent = `Mês Ant: R$ ${kpis.vendas_mes_anterior}`;

    document.getElementById('kpi-num-total').textContent = kpis.num_vendas_total;
    document.getElementById('kpi-num-mes-atual').textContent = `Mês Atual: ${kpis.num_vendas_mes_atual}`;
    document.getElementById('kpi-num-mes-ant').textContent = `Mês Ant: ${kpis.num_vendas_mes_anterior}`;

    document.getElementById('kpi-ticket-total').textContent = `R$ ${kpis.ticket_medio_total}`;
    document.getElementById('kpi-ticket-mes-atual').textContent = `Mês Atual: R$ ${kpis.ticket_medio_mes_atual}`;
    document.getElementById('kpi-ticket-mes-ant').textContent = `Mês Ant: R$ ${kpis.ticket_medio_mes_anterior}`;
}

function atualizarFinanceiro(financeiro) {
    document.getElementById('fin-rec-atraso').textContent = `R$ ${financeiro.receber.atraso}`;
    document.getElementById('fin-rec-semana').textContent = `R$ ${financeiro.receber.semana}`;
    document.getElementById('fin-rec-hoje').textContent = `R$ ${financeiro.receber.hoje}`;

    document.getElementById('fin-pag-atraso').textContent = `R$ ${financeiro.pagar.atraso}`;
    document.getElementById('fin-pag-semana').textContent = `R$ ${financeiro.pagar.semana}`;
    document.getElementById('fin-pag-hoje').textContent = `R$ ${financeiro.pagar.hoje}`;
}

function atualizarFinanceiroDetalhado(fin_detalhado) {
    document.getElementById('fin-det-receitas').textContent = `R$ ${fin_detalhado.receitas_mes}`;
    document.getElementById('fin-det-despesas').textContent = `R$ ${fin_detalhado.despesas_mes}`;
    document.getElementById('fin-det-saldo').textContent = `R$ ${fin_detalhado.saldo_mes}`;
}

function atualizarClientes(clientes_detalhado) {
    document.getElementById('cli-det-total').textContent = clientes_detalhado.total;
    document.getElementById('cli-det-novos').textContent = clientes_detalhado.novos_mes;

    const tb = document.getElementById('tb_top_clientes');
    tb.innerHTML = '';
    
    if (clientes_detalhado.top_clientes.length === 0) {
        tb.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Nenhum pedido atrelado a clientes foi encontrado.</td></tr>';
        return;
    }

    clientes_detalhado.top_clientes.forEach(c => {
        tb.innerHTML += `
            <tr>
                <td class="font-bold text-info">${c.nome}</td>
                <td class="text-center">${c.qtd_pedidos}</td>
                <td class="text-right text-success font-bold">R$ ${c.valor_gasto}</td>
            </tr>
        `;
    });
}

function renderizarGraficos(dadosGraficos) {
    Object.values(graficosInstancias).forEach(chart => chart.destroy());
    graficosInstancias = {};

    const ctxGrupos = document.getElementById('gruposChart').getContext('2d');
    graficosInstancias.grupos = new Chart(ctxGrupos, {
        type: 'pie',
        data: {
            labels: dadosGraficos.grupos_vendidos.labels,
            datasets: [{
                data: dadosGraficos.grupos_vendidos.data,
                backgroundColor: ['#86efac', '#1e3a8a', '#166534', '#fcd34d', '#9ca3af'],
                borderWidth: 1, borderColor: '#222'
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#ccc', boxWidth: 12 } } } }
    });

    const ctxMarcas = document.getElementById('marcasChart').getContext('2d');
    graficosInstancias.marcas = new Chart(ctxMarcas, {
        type: 'pie',
        data: {
            labels: dadosGraficos.marcas_vendidas.labels,
            datasets: [{
                data: dadosGraficos.marcas_vendidas.data,
                backgroundColor: ['#4b5563', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
                borderWidth: 1, borderColor: '#222'
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#ccc', boxWidth: 12 } } } }
    });

    const ctxHora = document.getElementById('horaChart').getContext('2d');
    graficosInstancias.hora = new Chart(ctxHora, {
        type: 'line',
        data: {
            labels: dadosGraficos.vendas_hora.labels,
            datasets: [{
                label: 'Qtd Vendas',
                data: dadosGraficos.vendas_hora.data,
                borderColor: '#60a5fa', backgroundColor: 'rgba(96, 165, 250, 0.2)',
                borderWidth: 2, fill: true, tension: 0.4, pointRadius: 2
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#333' } }, x: { grid: { display: false } } } }
    });

    const ctxDia = document.getElementById('diaChart').getContext('2d');
    graficosInstancias.dia = new Chart(ctxDia, {
        type: 'bar',
        data: {
            labels: dadosGraficos.vendas_dia.labels,
            datasets: [
                { label: 'Mês Anterior', data: dadosGraficos.vendas_dia.fev_data, backgroundColor: '#9ca3af', borderRadius: 4 },
                { label: 'Mês Atual', data: dadosGraficos.vendas_dia.mar_data, backgroundColor: '#facc15', borderRadius: 4 }
            ]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', labels: { color: '#ccc' } } }, scales: { y: { beginAtZero: true, grid: { color: '#333' } }, x: { grid: { display: false } } } }
    });
}