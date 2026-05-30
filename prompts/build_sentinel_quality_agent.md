# Build PRISM Sentinel Quality Agent

Workspace:
/home/appadmin/projects/Ram_Projects/DiracDelta/sentinel

Goal:
Refactor this copied coder project into PRISM Sentinel, an enterprise quality assurance, requirements traceability, and audit evidence agent.

Sentinel is NOT a coding agent.
Sentinel is a verification and assurance agent.

Primary Inputs:
- requirements/*.md
- requirements/*.json
- source project paths passed as arguments
- prompts used to generate code
- deployment scripts
- BigQuery SQL
- GCS layout
- README / architecture documents

Primary Outputs:
- reports/requirements_traceability.md
- reports/requirements_traceability.json
- reports/gap_analysis.md
- reports/code_quality_report.md
- reports/environment_validation.md
- reports/security_audit.md
- reports/gcs_audit.md
- reports/audit_evidence_package.md
- reports/remediation_plan.md

Create agents:
1. agents/requirement_mapper.py
   - Reads requirements from requirements/
   - Extracts requirement IDs
   - Maps each requirement to implementation evidence
   - Produces traceability matrix

2. agents/gap_analyzer.py
   - Compares requirements vs files delivered
   - Flags missing implementation, missing tests, missing docs, missing config

3. agents/code_quality_reviewer.py
   - Runs static checks:
     python compile
     bash syntax
     SQL scan
     forbidden model scan
     secret scan
   - Produces quality score

4. agents/env_validator.py
   - Validates .env.local presence without printing secrets
   - Checks models.json
   - Checks allowed model policy
   - Checks GCP project/region config

5. agents/gcs_auditor.py
   - Validates GCS paths and manifests
   - Checks bronze/silver/gold layout where applicable
   - Checks latest pointer and object presence

6. agents/audit_packager.py
   - Combines all reports into audit_evidence_package.md
   - Summarizes pass/fail/risk status

Create scripts:
- scripts/run_requirement_mapping.sh
- scripts/run_gap_analysis.sh
- scripts/run_code_quality.sh
- scripts/run_env_validation.sh
- scripts/run_gcs_audit.sh
- scripts/run_audit_package.sh
- scripts/run_sentinel_all.sh

Model policy:
Allowed:
- gemini-3.5-flash
- xai/grok-4.2-reasoning
- xai/grok-4.2-non-reasoning

Blocked:
- gemini-1.5
- gemini-2.0
- gemini-2.5

Rules:
- Default mode is read-only audit.
- Do not modify target project code.
- Do not print secrets.
- Do not use hidden chain-of-thought.
- Use execution_plan and reasoning_summary only.
- Every finding must include severity: critical, major, minor, info.
- Every gap must include recommendation and owner_hint.

Acceptance:
./scripts/run_sentinel_all.sh /home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run

must produce all reports under reports/.
