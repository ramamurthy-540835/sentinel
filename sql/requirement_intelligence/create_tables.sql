-- Requirement Intelligence Layer for Prompt Scope Cleaning
-- Dataset: ctoteam.prism_requirement_intelligence

-- (Tables already created via bq in this session)
-- This file is for version control / reproducible setup

CREATE SCHEMA IF NOT EXISTS `ctoteam.prism_requirement_intelligence`
OPTIONS (description = "Requirement Intelligence Layer - cleans noisy prompts before AI estimation");

-- See agents/bqml_requirement_scope.py for the current robust Python implementation
-- of classification (used because of BigQuery streaming buffer limitations in dev).