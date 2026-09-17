-- company_profiles: one row per (company, crawler source).
--
-- company_data_crawler collects the same company from independent sources
-- (craft, owler, ...). Records from different sources must never overwrite
-- or merge each other, so every source persists its own row. Reconciling
-- them into a single profile is an explicit, on-demand step done by the
-- LLM merger in the pipeline layer (company_data.pipeline.llm_merger).
--
-- Apply with:
--   psql "postgresql://postgres:test123@localhost:5432/company_data" \
--       -f src/company_data/database/schema.sql
--
-- If an older single-record table exists, migrate it first:
--   DROP TABLE IF EXISTS company_profiles;

CREATE TABLE IF NOT EXISTS company_profiles (
    company_domain TEXT NOT NULL,
    source_name    TEXT NOT NULL,
    company_name   TEXT NOT NULL,
    profile_data   JSONB NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (company_domain, source_name)
);

CREATE INDEX IF NOT EXISTS idx_company_profiles_company_name
    ON company_profiles (company_name);
