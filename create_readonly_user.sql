-- =========================================================
-- Intelligent Site Services Copilot
-- Cria um usuário read-only dedicado para o SQL Agent.
-- Rode este script UMA VEZ, conectado como superusuário (ex: postgres):
--   psql -U postgres -d site_services -f create_readonly_user.sql
-- =========================================================

-- Ajuste a senha antes de rodar em produção
CREATE ROLE agent_readonly WITH LOGIN PASSWORD 'troque_esta_senha';

-- Permite conectar ao banco
GRANT CONNECT ON DATABASE site_services TO agent_readonly;

-- Permite enxergar o schema
GRANT USAGE ON SCHEMA public TO agent_readonly;

-- Permite apenas SELECT nas tabelas existentes
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_readonly;

-- Garante que tabelas criadas no futuro também sejam somente-leitura
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO agent_readonly;

-- Revoga explicitamente qualquer permissão de escrita (defesa extra)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM agent_readonly;
