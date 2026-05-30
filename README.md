# PRISM Sentinel Quality Agent

PRISM Sentinel is an enterprise quality assurance, requirements traceability, and audit evidence agent. It is designed to verify and assure target projects without modifying their code.

## Features

- **Requirements Traceability**: Maps requirements from `requirements/` to implementation evidence in target projects.
- **Gap Analysis**: Compares requirements vs files delivered, flagging missing implementations, tests, docs, or configs.
- **Code Quality Review**: Runs static checks (Python compilation, Bash syntax, SQL best practices, forbidden model policy, and secret scanning).
- **Environment Validation**: Validates `.env.local` and `models.json` without printing secrets.
- **GCS Layout Audit**: Audits GCS bucket references and Medallion architecture layouts.
- **Audit Evidence Packaging**: Combines all reports into a single comprehensive audit package.

## Usage

To run all audits against a target project:

```bash
./scripts/run_sentinel_all.sh /home/appadmin/projects/Ram_Projects/DiracDelta/gcloud_run
```

## Output Reports

All reports are generated under the `reports/` directory:
- `reports/requirements_traceability.md`
- `reports/requirements_traceability.json`
- `reports/gap_analysis.md`
- `reports/code_quality_report.md`
- `reports/environment_validation.md`
- `reports/gcs_audit.md`
- `reports/audit_evidence_package.md`
