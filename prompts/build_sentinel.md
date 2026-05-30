Build PRISM Sentinel from the existing copied coder project.

Goal:
Refactor this project into an enterprise delivery assurance agent.

Tasks:
1. Rename README and messaging from coder to PRISM Sentinel.
2. Remove coding-agent assumptions where inappropriate.
3. Create agents:
   - requirement_mapper.py
   - gap_analyzer.py
   - code_quality_reviewer.py
   - env_validator.py
   - audit_packager.py
4. Create scripts:
   - run_requirement_mapping.sh
   - run_gap_analysis.sh
   - run_code_quality.sh
   - run_env_validation.sh
   - run_audit_package.sh
   - run_sentinel_all.sh
5. Create reports/ output folder.
6. Keep start_aider.sh and models.json.
7. Enforce model policy:
   allowed only gemini-3.5-flash, xai/grok-4.2-reasoning, xai/grok-4.2-non-reasoning.
8. Add README usage examples.

Do not implement Cloud Run deployment.
Do not implement Prompt Lakehouse.
Sentinel validates and audits projects; it does not replace gcloud_run.
