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


def _spec_header(spec_name: str) -> str:
    return "Uniform (primary)" if spec_name == "uniform" else "Disease-adjusted (secondary)"


def main() -> None:
    results = _load(RESULTS)
    diag = _load(DIAG)
    fsum = _load(FSUM)
    er = _load(ERREP)

    lines: list[str] = ["# Pipeline Risk Factor — Phase 3 dual-spec results summary\n"]

    # Section 1: summary stats for both specs
    lines.append("## Table 1. Factor Summary Statistics\n")
    lines.append("| Statistic | Uniform | Adjusted |")
    lines.append("|---|---|---|")
    for k in ["n", "mean", "std", "skew", "kurtosis", "sharpe_annualized", "ac_1", "avg_n_long", "avg_n_short"]:
        u = fsum.get("uniform", {}).get(k)
        a = fsum.get("adjusted", {}).get(k)
        def _fmt(v):
            if v is None:
                return "--"
            return f"{v:.4f}" if isinstance(v, float) else str(v)
        lines.append(f"| {k} | {_fmt(u)} | {_fmt(a)} |")
    lines.append("")

    # Section 2: regression tables for each spec
    for spec_name in ["uniform", "adjusted"]:
        path = OUTPUT_DIR / "tables" / f"regression_table_{spec_name}.md"
        if path.exists():
            lines.append(f"## Table 2{'a' if spec_name == 'uniform' else 'b'}. Regression Results ({_spec_header(spec_name)})\n")
            lines.append(path.read_text())
            lines.append("")

    # Section 3: model comparison for both specs
    lines.append("## Table 3. Model Comparison\n")
    lines.append("| Spec | ETF | dAdjR2 | PartF | PartF p | dAIC | dBIC | PR p (raw) | PR p (Bonf) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for spec_name in ["uniform", "adjusted"]:
        for t, r in results.get(spec_name, {}).items():
            c = r["comparison"]
            pf = c["partial_f_test"]
            lines.append(
                f"| {spec_name} | {t} | {c['delta_adj_r_squared']:+.4f} | {pf['f_stat']:.3f} | {pf['p_value']:.4f} | "
                f"{c['delta_aic']:+.3f} | {c['delta_bic']:+.3f} | {c['pr_p_raw']:.4f} | {c['pr_p_bonferroni']:.4f} |"
            )
    lines.append("")

    # Section 4: diagnostic tests for both specs
    lines.append("## Table 4. Diagnostic Tests\n")
    lines.append("| Spec | ETF | Model | JB p | LB(3) p | BP p | max VIF |")
    lines.append("|---|---|---|---|---|---|---|")
    for spec_name in ["uniform", "adjusted"]:
        for t, m in diag.get(spec_name, {}).get("models", {}).items():
            vif_max = max(v for k, v in m["vif_ff5_pr"].items() if k != "const")
            for label, key in (("FF5", "model1_residual_tests"), ("FF5+PR", "model2_residual_tests")):
                rt = m[key]
                lb3 = rt["ljung_box"].get("3", list(rt["ljung_box"].values())[0])
                lines.append(
                    f"| {spec_name} | {t} | {label} | {rt['jarque_bera']['p']:.3f} | "
                    f"{lb3['p']:.3f} | {rt['breusch_pagan']['p']:.3f} | {vif_max:.2f} |"
                )
    lines.append("")

    # Section 5: concentration robustness
    rob_summary = OUTPUT_DIR / "robustness" / "robustness_summary.md"
    if rob_summary.exists():
        lines.append("## Table 5. Concentration Robustness\n")
        lines.append(rob_summary.read_text())
        lines.append("")

    # Section 6: data quality summary
    lines.append("## Data Quality Summary\n")
    if er:
        lines.append(f"- Total trials: {er.get('total_trials')}")
        if er.get("match_rate") is not None:
            lines.append(f"- Match rate: {er['match_rate']:.3f}")
        lines.append(f"- Unique tickers matched: {er.get('unique_tickers_matched')}")
        if er.get("alias_coverage") is not None:
            lines.append(f"- Alias coverage: {er['alias_coverage']:.3f}")
        lines.append(f"- Matched by type: {er.get('matched_by_type')}")
    lines.append("")
    lines.append("See `RESULTS_SUMMARY.md` and `survivorship_analysis.md` for the full writeup.")

    OUT.write_text("\n".join(lines))
    log.info("wrote %s", OUT)


if __name__ == "__main__":
    main()
