"""Compile all results into a single publication-ready markdown report."""
from __future__ import annotations

import json

from common import OUTPUT_DIR, get_logger

log = get_logger("tables")

RESULTS = OUTPUT_DIR / "results.json"
DIAG = OUTPUT_DIR / "diagnostics.json"
FSUM = OUTPUT_DIR / "factor_summary_stats.json"
ERREP = OUTPUT_DIR / "entity_resolution_report.json"

TABLE_REG = OUTPUT_DIR / "tables" / "regression_table.md"
TABLE_ROB = OUTPUT_DIR / "tables" / "robustness_table.md"
OUT = OUTPUT_DIR / "tables" / "full_results_summary.md"


def _load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    results = _load(RESULTS)
    diag = _load(DIAG)
    fsum = _load(FSUM)
    er = _load(ERREP)
    reg_table = TABLE_REG.read_text() if TABLE_REG.exists() else "_missing_"
    rob_table = TABLE_ROB.read_text() if TABLE_ROB.exists() else "_missing_"

    lines: list[str] = []
    lines.append("# Pipeline Risk Factor -- Phase 1 Results\n")

    lines.append("## Table 1. Pipeline Risk Factor Summary Statistics\n")
    if fsum:
        lines.append("| Statistic | Value |")
        lines.append("|---|---|")
        for k, v in fsum.items():
            lines.append(f"| {k} | {v} |" if v is None else f"| {k} | {v:.4f} |" if isinstance(v, float) else f"| {k} | {v} |")
    lines.append("")

    lines.append("## Table 2. Regression Results\n")
    lines.append(reg_table)
    lines.append("")

    lines.append("## Table 3. Model Comparison\n")
    if results:
        lines.append("| ETF | dAdjR2 | PartF | PartF p | dAIC | dBIC | PR p (raw) | PR p (Bonf) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for t, r in results.items():
            c = r["comparison"]
            pf = c["partial_f_test"]
            lines.append(
                f"| {t} | {c['delta_adj_r_squared']:+.4f} | {pf['f_stat']:.3f} | {pf['p_value']:.4f} | "
                f"{c['delta_aic']:+.3f} | {c['delta_bic']:+.3f} | {c['pr_p_raw']:.4f} | {c['pr_p_bonferroni']:.4f} |"
            )
    lines.append("")

    lines.append("## Table 4. Diagnostic Tests\n")
    if diag.get("models"):
        lines.append("| ETF | Model | JB p | LB(3) p | BP p | max VIF |")
        lines.append("|---|---|---|---|---|---|")
        for t, m in diag["models"].items():
            vif_max = max(v for k, v in m["vif_ff5_pr"].items() if k != "const")
            for label, key in (("FF5", "model1_residual_tests"), ("FF5+PR", "model2_residual_tests")):
                rt = m[key]
                lb3 = rt["ljung_box"].get("3", list(rt["ljung_box"].values())[0])
                lines.append(
                    f"| {t} | {label} | {rt['jarque_bera']['p']:.3f} | "
                    f"{lb3['p']:.3f} | {rt['breusch_pagan']['p']:.3f} | {vif_max:.2f} |"
                )
    lines.append("")

    lines.append("## Table 5. Robustness Checks\n")
    lines.append(rob_table)
    lines.append("")

    lines.append("## Data Quality Summary\n")
    if er:
        lines.append(f"- Total trials: {er.get('total_trials')}")
        lines.append(f"- Match rate: {er.get('match_rate'):.3f}" if er.get("match_rate") is not None else "- Match rate: --")
        lines.append(f"- Unique tickers matched: {er.get('unique_tickers_matched')}")
        lines.append(f"- Alias coverage: {er.get('alias_coverage'):.3f}" if er.get("alias_coverage") is not None else "- Alias coverage: --")
        lines.append(f"- Matched by type: {er.get('matched_by_type')}")
    lines.append("")

    OUT.write_text("\n".join(lines))
    log.info("wrote %s", OUT)


if __name__ == "__main__":
    main()
