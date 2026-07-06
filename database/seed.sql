INSERT INTO companies (id, name, slug, active) VALUES (1, 'Vigware Demo', 'default', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, company_id, name, email, role, active) VALUES (1, 1, 'Operador Demo', 'operador@vigware.local', 'operator', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO clients (id, company_id, name, trade_name, phone, email, address, active) VALUES
(1, 1, 'KW Engenharia LTDA', 'KW Engenharia', '(12) 99999-0000', 'contato@kw.local', 'Av. Exemplo, 1000 - Centro', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO accounts (id, company_id, client_id, code, name, partition_number, armed, notes, protocol_note, active) VALUES
(1, 1, 1, '0594', 'KW Engenharia - Matriz', '001', true, 'Cliente demo para testes.', 'Confirmar senha/contrassenha. Se não atender, acionar responsável 2 e deslocamento.', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO receivers (id, company_id, name, protocol, active) VALUES
(1, 1, 'Receiver HTTP Simulado', 'HTTP_SIMULATED', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO account_zones (account_id, zone_number, name, area, active) VALUES
(1, '001', 'Recepção', 'Frente', true),
(1, '002', 'Escritório', 'Administrativo', true),
(1, '005', 'Porta dos fundos', 'Fundos', true)
ON CONFLICT ON CONSTRAINT uq_account_zones_account_zone DO NOTHING;

INSERT INTO account_contacts (account_id, name, phone, priority, password_hint, active) VALUES
(1, 'João Responsável', '(12) 98888-0001', 1, 'Senha verbal cadastrada', true),
(1, 'Maria Responsável', '(12) 98888-0002', 2, 'Contrassenha cadastrada', true);

INSERT INTO event_codes (code, name, event_type, priority, open_occurrence, sound) VALUES
('E130', 'Disparo de alarme', 'alarm', 'high', true, 'alarm'),
('R130', 'Restauração de alarme', 'restore', 'low', false, null),
('E301', 'Falha de energia AC', 'technical', 'medium', true, 'beep'),
('R301', 'Restauração de energia AC', 'technical_restore', 'low', false, null),
('E302', 'Bateria baixa', 'technical', 'medium', true, 'beep'),
('E401', 'Arme/desarme', 'open_close', 'low', false, null),
('E602', 'Teste periódico', 'test', 'low', false, null)
ON CONFLICT (code) DO NOTHING;

INSERT INTO patrol_cars (company_id, description, plates, online, available, latitude, longitude, last_keep_alive) VALUES
(1, 'VTR 01', 'ABC1D23', true, true, '-23.026', '-45.555', NOW()),
(1, 'VTR 02', 'XYZ9A88', true, false, '-23.021', '-45.548', NOW());
