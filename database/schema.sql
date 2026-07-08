CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  name VARCHAR(180) NOT NULL,
  slug VARCHAR(80) NOT NULL UNIQUE,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  name VARCHAR(160) NOT NULL,
  email VARCHAR(180) NOT NULL UNIQUE,
  role VARCHAR(60) DEFAULT 'operator',
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  name VARCHAR(180) NOT NULL,
  trade_name VARCHAR(180) NOT NULL,
  document VARCHAR(60),
  phone VARCHAR(80),
  email VARCHAR(180),
  address TEXT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  client_id INTEGER NOT NULL REFERENCES clients(id),
  code VARCHAR(30) NOT NULL,
  name VARCHAR(180) NOT NULL,
  partition_number VARCHAR(20) DEFAULT '001',
  armed BOOLEAN DEFAULT TRUE,
  active BOOLEAN DEFAULT TRUE,
  notes TEXT,
  protocol_note TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  CONSTRAINT uq_accounts_company_code UNIQUE (company_id, code)
);

CREATE TABLE IF NOT EXISTS account_zones (
  id SERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  zone_number VARCHAR(20) NOT NULL,
  name VARCHAR(160) NOT NULL,
  area VARCHAR(160),
  active BOOLEAN DEFAULT TRUE,
  CONSTRAINT uq_account_zones_account_zone UNIQUE (account_id, zone_number)
);

CREATE TABLE IF NOT EXISTS account_contacts (
  id SERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  name VARCHAR(160) NOT NULL,
  phone VARCHAR(80) NOT NULL,
  priority INTEGER DEFAULT 1,
  password_hint VARCHAR(180),
  active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS receivers (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  name VARCHAR(160) NOT NULL,
  protocol VARCHAR(60) DEFAULT 'HTTP_SIMULATED',
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_codes (
  id SERIAL PRIMARY KEY,
  code VARCHAR(30) NOT NULL UNIQUE,
  name VARCHAR(160) NOT NULL,
  event_type VARCHAR(60) DEFAULT 'alarm',
  priority VARCHAR(20) DEFAULT 'medium',
  open_occurrence BOOLEAN DEFAULT TRUE,
  sound VARCHAR(80)
);

CREATE TABLE IF NOT EXISTS occurrences (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  client_id INTEGER REFERENCES clients(id),
  account_id INTEGER REFERENCES accounts(id),
  account_code VARCHAR(30) NOT NULL,
  partition_number VARCHAR(20),
  zone_number VARCHAR(20),
  zone_name VARCHAR(160),
  event_code VARCHAR(30) NOT NULL,
  description VARCHAR(220) NOT NULL,
  priority VARCHAR(20) DEFAULT 'medium',
  status VARCHAR(30) DEFAULT 'NEW',
  event_count INTEGER DEFAULT 1,
  assigned_operator_id INTEGER REFERENCES users(id),
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_events (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  receiver_id INTEGER REFERENCES receivers(id),
  protocol VARCHAR(60) DEFAULT 'HTTP_SIMULATED',
  account_code VARCHAR(30) NOT NULL,
  event_code VARCHAR(30) NOT NULL,
  partition_number VARCHAR(20),
  zone_number VARCHAR(20),
  raw_payload TEXT,
  processed BOOLEAN DEFAULT FALSE,
  occurrence_id INTEGER REFERENCES occurrences(id),
  received_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS occurrence_timeline (
  id SERIAL PRIMARY KEY,
  occurrence_id INTEGER NOT NULL REFERENCES occurrences(id),
  type VARCHAR(60) DEFAULT 'EVENT',
  title VARCHAR(180) NOT NULL,
  description TEXT,
  event_code VARCHAR(30),
  created_by_user_id INTEGER REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS occurrence_watchers (
  id SERIAL PRIMARY KEY,
  occurrence_id INTEGER NOT NULL REFERENCES occurrences(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  CONSTRAINT uq_occurrence_watchers_occ_user UNIQUE (occurrence_id, user_id)
);

CREATE TABLE IF NOT EXISTS patrol_cars (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  description VARCHAR(160) NOT NULL,
  plates VARCHAR(40),
  online BOOLEAN DEFAULT TRUE,
  available BOOLEAN DEFAULT TRUE,
  latitude VARCHAR(40),
  longitude VARCHAR(40),
  last_keep_alive TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_occurrences_status ON occurrences(status);
CREATE INDEX IF NOT EXISTS ix_occurrences_account_code ON occurrences(account_code);
CREATE INDEX IF NOT EXISTS ix_raw_events_received_at ON raw_events(received_at);


CREATE TABLE IF NOT EXISTS receiver_nonces (
  id SERIAL PRIMARY KEY,
  bridge_id VARCHAR(120) NOT NULL,
  nonce VARCHAR(160) NOT NULL,
  received_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL,
  CONSTRAINT uq_receiver_nonces_bridge_nonce UNIQUE (bridge_id, nonce)
);

CREATE INDEX IF NOT EXISTS ix_receiver_nonces_bridge_id ON receiver_nonces(bridge_id);
CREATE INDEX IF NOT EXISTS ix_receiver_nonces_expires_at ON receiver_nonces(expires_at);
