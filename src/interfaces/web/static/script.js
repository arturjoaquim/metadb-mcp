document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('connectionForm');
    const btnConnect = document.getElementById('btnConnect');
    const btnSync = document.getElementById('btnSync');
    const tablesContainer = document.getElementById('tablesContainer');
    const totalTablesCount = document.getElementById('totalTablesCount');
    const selectedTablesCount = document.getElementById('selectedTablesCount');
    const alertBox = document.getElementById('alertBox');
    const alertMessage = document.getElementById('alertMessage');
    const alertIcon = document.getElementById('alertIcon');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingTitle = document.getElementById('loadingTitle');
    const loadingDesc = document.getElementById('loadingDesc');
    const savedConnections = document.getElementById('savedConnections');
    const tableSearch = document.getElementById('tableSearch');
    const chkSelectAll = document.getElementById('chkSelectAll');

    let availableTables = [];
    let syncedTables = [];
    let selectedTables = new Set();
    let sensitiveTables = new Set();
    let connectionsData = [];

    // Elementos de Autenticação
    const viewLogin = document.getElementById('view-login');
    const viewRegister = document.getElementById('view-register');
    const viewDashboard = document.getElementById('view-dashboard');
    const statusBadge = document.getElementById('statusBadge');
    const btnLogout = document.getElementById('btnLogout');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    // Verifica status inicial
    async function checkAuthStatus() {
        try {
            const response = await fetch('/api/auth/status');
            const data = await response.json();

            updateViewStatus(data);
        } catch (e) {
            console.error("Erro ao verificar status", e);
        }
    }

    function updateViewStatus(data) {
        // Esconde todas as views
        viewLogin.classList.add('hidden');
        viewRegister.classList.add('hidden');
        viewDashboard.classList.add('hidden');

        if (data.is_unlocked) {
            viewDashboard.classList.remove('hidden');
            statusBadge.className = "flex items-center space-x-2 bg-green-500/10 text-green-400 px-3 py-1.5 rounded-full border border-green-500/20 text-sm font-medium";
            statusBadge.innerHTML = '<i class="fa-solid fa-unlock text-xs"></i><span>Unlocked</span>';
            btnLogout.classList.remove('hidden');
            loadConnections();
        } else if (!data.db_exists) {
            viewRegister.classList.remove('hidden');
            statusBadge.className = "flex items-center space-x-2 bg-yellow-500/10 text-yellow-400 px-3 py-1.5 rounded-full border border-yellow-500/20 text-sm font-medium";
            statusBadge.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-xs"></i><span>Setup Required</span>';
            btnLogout.classList.add('hidden');
        } else {
            viewLogin.classList.remove('hidden');
            statusBadge.className = "flex items-center space-x-2 bg-red-500/10 text-red-400 px-3 py-1.5 rounded-full border border-red-500/20 text-sm font-medium";
            statusBadge.innerHTML = '<i class="fa-solid fa-lock text-xs"></i><span>Locked</span>';
            btnLogout.classList.add('hidden');
        }
    }

    // Formulário de Cadastro
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('regUsername').value;
            const password = document.getElementById('regPassword').value;
            const confirmPassword = document.getElementById('regConfirmPassword').value;
            const alertBox = document.getElementById('registerAlert');

            if (password !== confirmPassword) {
                alertBox.textContent = "As senhas não coincidem.";
                alertBox.classList.remove('hidden');
                return;
            }

            alertBox.classList.add('hidden');
            showLoading("Criando Banco Seguro...", "Gerando chaves e configurando criptografia SQLCipher.");

            try {
                const response = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await response.json();

                if (response.ok) {
                    checkAuthStatus();
                } else {
                    alertBox.textContent = data.detail || "Erro ao cadastrar.";
                    alertBox.classList.remove('hidden');
                }
            } catch (error) {
                alertBox.textContent = "Erro de conexão.";
                alertBox.classList.remove('hidden');
            } finally {
                hideLoading();
            }
        });
    }

    // Formulário de Login
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            const alertBox = document.getElementById('loginAlert');

            alertBox.classList.add('hidden');
            showLoading("Desbloqueando...", "Validando credenciais e acessando banco seguro.");

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await response.json();

                if (response.ok) {
                    document.getElementById('loginPassword').value = '';
                    checkAuthStatus();
                } else {
                    alertBox.textContent = data.detail || "Credenciais inválidas.";
                    alertBox.classList.remove('hidden');
                }
            } catch (error) {
                alertBox.textContent = "Erro de conexão.";
                alertBox.classList.remove('hidden');
            } finally {
                hideLoading();
            }
        });
    }

    // Logout
    if (btnLogout) {
        btnLogout.addEventListener('click', async () => {
            showLoading("Bloqueando...", "Fechando conexões seguras e limpando sessão.");
            try {
                await fetch('/api/auth/logout', { method: 'POST' });

                // Limpa formulários para não deixar dados residuais visíveis
                if (loginForm) loginForm.reset();
                if (form) form.reset();

                // Reseta estado das tabelas
                availableTables = [];
                syncedTables = [];
                selectedTables.clear();
                sensitiveTables.clear();

                if (chkSelectAll) chkSelectAll.checked = false;
                if (tableSearch) tableSearch.value = '';

                if (tablesContainer) {
                    tablesContainer.innerHTML = `
                    <div class="flex flex-col items-center justify-center h-48 text-gray-500">
                        <i class="fa-regular fa-folder-open text-4xl mb-3 text-gray-600"></i>
                        <p>Conecte-se ao banco para visualizar as tabelas.</p>
                    </div>
                `;
                }

                updateCounts();
                checkAuthStatus();
            } finally {
                hideLoading();
            }
        });
    }

    // Carregar conexões salvas
    async function loadConnections() {
        try {
            const response = await fetch('/api/connections');
            if (!response.ok) return;
            const data = await response.json();
            connectionsData = data.connections;

            connectionsData.forEach(conn => {
                const option = document.createElement('option');
                option.value = conn.name;
                option.textContent = conn.name;
                savedConnections.appendChild(option);
            });
        } catch (e) {
            console.error("Erro ao carregar conexões", e);
        }
    }

    if (savedConnections) {
        savedConnections.addEventListener('change', (e) => {
            const val = e.target.value;
            if (!val) {
                document.getElementById('connName').value = '';
                document.getElementById('dbHost').value = '';
                document.getElementById('dbPort').value = '';
                document.getElementById('dbName').value = '';
                document.getElementById('dbUser').value = '';
                document.getElementById('dbPass').value = '';
                return;
            }
            const conn = connectionsData.find(c => c.name === val);
            if (conn) {
                document.getElementById('connName').value = conn.name;
                document.getElementById('dbType').value = conn.db_type;
                document.getElementById('dbHost').value = conn.host;
                document.getElementById('dbPort').value = conn.port;
                document.getElementById('dbName').value = conn.dbname;
                document.getElementById('dbUser').value = conn.user;
                document.getElementById('dbPass').value = '';
                document.getElementById('dbPass').focus();
            }
        });
    }

    // checkAuthStatus vai chamar loadConnections se unlocked
    checkAuthStatus();

    function showAlert(message, type = 'error') {
        alertBox.className = `mt-4 rounded-lg p-4 text-sm flex items-start shadow-lg ${type === 'error' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                'bg-green-500/10 text-green-400 border border-green-500/20'
            }`;
        alertIcon.className = `fa-solid mt-0.5 mr-3 ${type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'
            }`;
        alertMessage.textContent = message;
        alertBox.classList.remove('hidden');

        setTimeout(() => {
            alertBox.classList.add('hidden');
        }, 5000);
    }

    function showLoading(title, desc) {
        loadingTitle.textContent = title;
        loadingDesc.textContent = desc;
        loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }

    function getFormData() {
        return {
            conn_name: document.getElementById('connName').value,
            db_type: document.getElementById('dbType').value,
            host: document.getElementById('dbHost').value,
            port: parseInt(document.getElementById('dbPort').value, 10),
            dbname: document.getElementById('dbName').value,
            user: document.getElementById('dbUser').value,
            password: document.getElementById('dbPass').value
        };
    }

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = getFormData();

            showLoading("Conectando...", `Tentando acessar banco ${data.db_type} em ${data.host}...`);

            try {
                const response = await fetch('/api/tables', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || 'Erro ao conectar no banco de dados.');
                }

                availableTables = result.tables;
                const syncedData = result.synced_tables || [];

                // Extrair nomes e restaurar estado de sensibilidade do cache
                syncedTables = syncedData.map(t => t.name);
                selectedTables.clear();
                sensitiveTables.clear();

                syncedData.forEach(t => {
                    if (t.is_sensitive) {
                        sensitiveTables.add(t.name);
                    }
                });

                // Restaurar sample_size do cache (usa o primeiro valor encontrado)
                if (syncedData.length > 0 && syncedData[0].sample_size) {
                    document.getElementById('sampleSize').value = syncedData[0].sample_size;
                }

                if (chkSelectAll) {
                    chkSelectAll.checked = false;
                }
                if (tableSearch) {
                    tableSearch.value = '';
                }

                renderTables();

            } catch (error) {
                showAlert(error.message, 'error');
            } finally {
                hideLoading();
            }
        });
    }

    function renderTables() {
        if (availableTables.length === 0) {
            tablesContainer.innerHTML = `
                <div class="flex flex-col items-center justify-center h-48 text-gray-500">
                    <i class="fa-solid fa-triangle-exclamation text-4xl mb-3 text-yellow-600/50"></i>
                    <p>Nenhuma tabela encontrada no schema do usuário.</p>
                </div>
            `;
            updateCounts();
            return;
        }

        tablesContainer.innerHTML = availableTables.map((table, index) => {
            const isSynced = syncedTables.includes(table);
            const isSensitive = sensitiveTables.has(table);
            const badge = isSynced ? `<span class="ml-auto text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full border border-green-500/30">Sincronizada</span>` : '';
            const sensitiveClass = isSensitive ? 'text-red-400' : 'text-gray-500 hover:text-red-400';
            const sensitiveTitle = isSensitive ? 'Remover marcação de sensível' : 'Marcar como sensível (não coleta amostras)';

            return `
            <div class="table-item-anim flex items-center p-3 rounded-lg hover:bg-gray-700/50 transition-colors border border-transparent hover:border-gray-600/50 cursor-pointer" 
                 style="animation-delay: ${Math.min(index * 10, 500)}ms"
                 onclick="document.getElementById('chk-${table}').click()">
                <input type="checkbox" id="chk-${table}" value="${table}" class="table-checkbox mr-4" onclick="event.stopPropagation()">
                <i class="fa-solid fa-table text-gray-500 mr-3"></i>
                <span class="table-name-text text-gray-200 text-sm font-medium tracking-wide flex-1">${table}</span>
                <button class="btn-sensitive mx-2 transition-colors ${sensitiveClass}" title="${sensitiveTitle}" onclick="event.stopPropagation(); toggleSensitive('${table}')">
                    <i class="fa-solid ${isSensitive ? 'fa-shield-halved' : 'fa-shield'}"></i>
                </button>
                ${badge}
            </div>
            `;
        }).join('');

        // Define a função toggleSensitive no escopo global para o onclick funcionar
        window.toggleSensitive = (table) => {
            if (sensitiveTables.has(table)) {
                sensitiveTables.delete(table);
            } else {
                sensitiveTables.add(table);
            }
            renderTables();
        };

        document.querySelectorAll('.table-checkbox').forEach(chk => {
            chk.addEventListener('change', (e) => {
                if (e.target.checked) {
                    selectedTables.add(e.target.value);
                } else {
                    selectedTables.delete(e.target.value);
                }
                updateCounts();
                updateSelectAllState();
            });
        });

        updateCounts();
    }

    if (tableSearch) {
        tableSearch.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('.table-item-anim').forEach(item => {
                const tableName = item.querySelector('.table-name-text').textContent.toLowerCase();
                if (tableName.includes(term)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
            updateSelectAllState();
        });
    }

    if (chkSelectAll) {
        chkSelectAll.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            document.querySelectorAll('.table-item-anim').forEach(item => {
                if (item.style.display !== 'none') {
                    const chk = item.querySelector('.table-checkbox');
                    if (chk.checked !== isChecked) {
                        chk.checked = isChecked;
                        if (isChecked) {
                            selectedTables.add(chk.value);
                        } else {
                            selectedTables.delete(chk.value);
                        }
                    }
                }
            });
            updateCounts();
        });
    }

    function updateSelectAllState() {
        if (!chkSelectAll) return;

        const visibleItems = Array.from(document.querySelectorAll('.table-item-anim')).filter(item => item.style.display !== 'none');
        if (visibleItems.length === 0) {
            chkSelectAll.checked = false;
            return;
        }

        let allChecked = true;
        visibleItems.forEach(item => {
            if (!item.querySelector('.table-checkbox').checked) {
                allChecked = false;
            }
        });
        chkSelectAll.checked = allChecked;
    }

    function updateCounts() {
        totalTablesCount.textContent = availableTables.length;
        selectedTablesCount.textContent = selectedTables.size;

        if (selectedTables.size > 0) {
            btnSync.disabled = false;
            btnSync.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            btnSync.disabled = true;
            btnSync.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    if (btnSync) {
        btnSync.addEventListener('click', async () => {
            if (selectedTables.size === 0) return;

            const data = getFormData();
            data.tables = Array.from(selectedTables);
            data.sensitive_tables = Array.from(sensitiveTables);
            data.sample_size = parseInt(document.getElementById('sampleSize').value, 10) || 10;

            showLoading("Sincronizando...", `Extraindo metadados e amostras de ${selectedTables.size} tabelas...`);

            try {
                const response = await fetch('/api/sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || 'Erro ao sincronizar as tabelas.');
                }

                showAlert(result.message, 'success');

            } catch (error) {
                showAlert(error.message, 'error');
            } finally {
                hideLoading();
            }
        });
    }
});
