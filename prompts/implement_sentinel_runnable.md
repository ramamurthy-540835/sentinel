Proceed with prompts/build_sentinel_quality_agent.md.

Implement the actual runnable Sentinel code.

Do not only write documentation.
Do not create placeholder agents.
Create working Python scripts and shell runners.

Required:
1. agents/requirement_mapper.py
2. agents/gap_analyzer.py
3. agents/code_quality_reviewer.py
4. agents/env_validator.py
5. agents/gcs_auditor.py
6. agents/audit_packager.py

Each agent must:
- accept --target-project argument
- write output to reports/
- never print secrets
- exit non-zero only for critical runtime failure
- produce both markdown and JSON where useful

Create runnable shell scripts:
- scripts/run_requirement_mapping.sh
- scripts/run_gap_analysis.sh
- scripts/run_code_quality.sh
- scripts/run_env_validation.sh
- scripts/run_gcs_audit.sh
- scripts/run_audit_package.sh
- scripts/run_sentinel_all.sh

After implementation, run:

chmod +x scripts/*.sh

python3 -m compileall agents

bash -n scripts/*.sh

./scripts/run_sentinel_all.sh /home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run

Acceptance:
All reports must be created under reports/.
Show final file list:
find reports -maxdepth 2 -type f | sort

After Aider finishes, run manually:

cd /home/appadmin/projects/Ram_Projects/DiracDelta/sentinel

python3 -m compileall agents
bash -n scripts/*.sh
./scripts/run_sentinel_all.sh /home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run
find reports -maxdepth 2 -type f | sort
