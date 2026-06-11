CREATE DATABASE IF NOT EXISTS `unplanned_work_inspection`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'health_user'@'localhost' IDENTIFIED BY 'health_2024!';
CREATE USER IF NOT EXISTS 'health_user'@'%' IDENTIFIED BY 'health_2024!';
GRANT ALL PRIVILEGES ON `unplanned_work_inspection`.* TO 'health_user'@'localhost';
GRANT ALL PRIVILEGES ON `unplanned_work_inspection`.* TO 'health_user'@'%';
FLUSH PRIVILEGES;

USE `unplanned_work_inspection`;

CREATE TABLE IF NOT EXISTS work_tickets (
  id VARCHAR(64) PRIMARY KEY,
  plan_id VARCHAR(80) NOT NULL,
  project_name VARCHAR(255) NOT NULL,
  district VARCHAR(80) NOT NULL,
  work_location VARCHAR(255) NOT NULL,
  work_content_raw TEXT NOT NULL,
  plan_status VARCHAR(40) NOT NULL,
  execution_status VARCHAR(40) NOT NULL,
  risk_level VARCHAR(20) NOT NULL,
  work_leader VARCHAR(80) NOT NULL,
  contractor VARCHAR(255) NOT NULL,
  video_control_enabled TINYINT(1) NOT NULL,
  plan_start DATETIME NOT NULL,
  plan_end DATETIME NOT NULL,
  raw_text TEXT NOT NULL,
  ticket_fact_json LONGTEXT NOT NULL,
  media_query_task_json LONGTEXT NOT NULL,
  validation_result_json LONGTEXT NOT NULL,
  agent_analysis_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uniq_plan_id (plan_id),
  INDEX idx_plan_status (plan_status),
  INDEX idx_risk_level (risk_level),
  INDEX idx_district (district),
  INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS parse_records (
  id VARCHAR(64) PRIMARY KEY,
  ticket_id VARCHAR(64),
  source_type VARCHAR(40) NOT NULL,
  summary VARCHAR(255) NOT NULL,
  record_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inspections (
  id VARCHAR(64) PRIMARY KEY,
  ticket_id VARCHAR(64),
  ticket VARCHAR(80),
  location VARCHAR(255),
  status VARCHAR(40),
  risk VARCHAR(20),
  operator_name VARCHAR(80),
  mode VARCHAR(40),
  record_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_updated_at (updated_at),
  INDEX idx_status (status),
  INDEX idx_risk (risk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conversations (
  id VARCHAR(64) PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  ticket_id VARCHAR(64),
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conversation_messages (
  id VARCHAR(64) PRIMARY KEY,
  conversation_id VARCHAR(64) NOT NULL,
  role VARCHAR(20) NOT NULL,
  content LONGTEXT NOT NULL,
  metadata_json LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_conversation_time (conversation_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
