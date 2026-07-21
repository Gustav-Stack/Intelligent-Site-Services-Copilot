-- ============================================================
-- Intelligent Site Services Copilot
-- Schema: Operations & Materials Database 
-- ============================================================

-- 1. Categorias de Serviços
CREATE TABLE IF NOT EXISTS service_categories (
    id SERIAL PRIMARY KEY,
    group_name TEXT NOT NULL,
    name TEXT NOT NULL
);

-- 2. Equipamentos (Frota e Maquinário)
CREATE TABLE IF NOT EXISTS equipment (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    hourly_rate NUMERIC(10,2) NOT NULL,
    last_service_date DATE
);

-- 3. Clientes
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    municipality TEXT
);

-- 4. Projetos/Obras
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    site_address TEXT NOT NULL,
    project_type TEXT NOT NULL,
    status TEXT NOT NULL,
    start_date DATE,
    est_completion DATE
);

-- 5. Licenças e Permissões
CREATE TABLE IF NOT EXISTS permits (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    permit_type TEXT NOT NULL,
    status TEXT NOT NULL,
    submitted_date DATE,
    approved_date DATE,
    notes TEXT
);

-- 6. Solicitações de Serviço e Cronograma
CREATE TABLE IF NOT EXISTS service_requests (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    service_category_id INTEGER REFERENCES service_categories(id),
    equipment_id INTEGER REFERENCES equipment(id),
    crew_name TEXT,
    scheduled_date DATE,
    completed_date DATE,
    status TEXT NOT NULL,
    estimated_cost NUMERIC(12,2),
    final_cost NUMERIC(12,2),
    notes TEXT
);

-- 7. Agregados e Materiais (Estoque interno/Vendas)
CREATE TABLE IF NOT EXISTS aggregates (
    id SERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL,
    stock_qty NUMERIC(12,2) NOT NULL DEFAULT 0,
    reorder_point NUMERIC(12,2) DEFAULT 0,
    source TEXT,
    last_updated DATE
);

-- 8. Histórico de Preços dos Agregados
CREATE TABLE IF NOT EXISTS aggregate_price_history (
    id SERIAL PRIMARY KEY,
    aggregate_id INTEGER REFERENCES aggregates(id) ON DELETE CASCADE,
    price NUMERIC(10,2) NOT NULL,
    recorded_at DATE NOT NULL
);

-- 9. Pedidos/Vendas de Agregados
CREATE TABLE IF NOT EXISTS aggregate_orders (
    id SERIAL PRIMARY KEY,
    aggregate_id INTEGER REFERENCES aggregates(id),
    client_id INTEGER REFERENCES clients(id),
    project_id INTEGER REFERENCES projects(id), -- Pode ser nulo se for venda avulsa
    quantity NUMERIC(12,2) NOT NULL,
    total_price NUMERIC(12,2) NOT NULL,
    delivery_date DATE
);

-- Índices para otimizar as buscas do Agente de IA
CREATE INDEX idx_projects_client ON projects(client_id);
CREATE INDEX idx_equipment_status ON equipment(status);
CREATE INDEX idx_aggregates_stock ON aggregates(stock_qty);